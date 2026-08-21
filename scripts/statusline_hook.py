"""Claude Code statusline hook recording rate limit state for the TRMNL server.

Claude Code pipes a JSON object to the configured statusline command on every
render. Since version 2.1.80 that payload carries a rate_limits object for
Pro and Max subscribers. This script persists it and prints a short status
line so the hook remains useful in the terminal too.

Only the standard library is used so the hook runs under whichever
interpreter Claude Code invokes, without needing a virtual environment.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_STATE_FILE = Path.home() / ".claude" / "trmnl-usage.json"


def resolve_state_file() -> Path:
    """Determine where the rate limit state should be written.

    Returns:
      Path from TRMNL_STATE_FILE, or the default under ~/.claude.
    """
    override = os.environ.get("TRMNL_STATE_FILE")
    return Path(override) if override else DEFAULT_STATE_FILE


def write_state(state_file: Path, rate_limits: Dict[str, Any]) -> None:
    """Persist rate limit data atomically.

    Args:
      state_file: Destination path.
      rate_limits: The rate_limits object from Claude Code.

    Raises:
      OSError: If the file cannot be written or replaced.
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"rate_limits": rate_limits, "updated_at": time.time()}
    temporary = state_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary, state_file)


def format_status(rate_limits: Optional[Dict[str, Any]]) -> str:
    """Build the single line shown in the Claude Code status bar.

    Args:
      rate_limits: The rate_limits object, or None when absent.

    Returns:
      A compact summary such as "5h 30% | wk 27%".
    """
    if not rate_limits:
        return "usage: no rate_limits in payload"
    parts = []
    for key, label in (("five_hour", "5h"), ("seven_day", "wk")):
        window = rate_limits.get(key)
        if isinstance(window, dict):
            used = window.get("used_percentage")
            if isinstance(used, (int, float)):
                parts.append(f"{label} {used:.0f}%")
    return " | ".join(parts) if parts else "usage: empty rate_limits"


def main() -> int:
    """Read the statusline payload, persist it, and print a summary.

    Returns:
      Process exit code; always 0 so Claude Code never reports a failure.
    """
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("usage: unreadable statusline payload")
        return 0

    rate_limits = payload.get("rate_limits") if isinstance(payload, dict) else None
    if isinstance(rate_limits, dict):
        try:
            write_state(resolve_state_file(), rate_limits)
        except OSError as exc:
            print(f"usage: write failed ({exc.strerror})")
            return 0

    print(format_status(rate_limits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
