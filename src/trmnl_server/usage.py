"""Reading and interpreting Claude Code rate limit state."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import orjson

logger = logging.getLogger(__name__)

STALE_AFTER_SECONDS = 900


@dataclass(frozen=True)
class Window:
    """A single Claude Code rate limit window.

    Attributes:
      label: Human readable name shown on the display.
      used_percentage: Portion of the window consumed, 0 to 100.
      resets_at: Unix epoch second the window resets, or None if unknown.
    """

    label: str
    used_percentage: float
    resets_at: Optional[int]

    @property
    def expired(self) -> bool:
        """Whether the reset time has already passed."""
        return self.resets_at is not None and self.resets_at <= time.time()

    @property
    def effective_percentage(self) -> float:
        """Usage after zeroing windows whose reset time has passed.

        Claude Code only reports usage while a session is active, so a
        window that has since reset must be zeroed locally rather than
        left showing its last known value.
        """
        return 0.0 if self.expired else self.used_percentage

    def countdown(self) -> str:
        """Format the time remaining until this window resets.

        Returns:
          A string like "3h 13m", "45m", "now", or "--" when unknown.

        Example:
          A window resetting in 95 minutes renders as "1h 35m".
        """
        if self.resets_at is None:
            return "--"
        remaining = int(self.resets_at - time.time())
        if remaining <= 0:
            return "now"
        hours, leftover = divmod(remaining, 3600)
        minutes = leftover // 60
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


@dataclass(frozen=True)
class UsageSnapshot:
    """Both rate limit windows plus freshness metadata.

    Attributes:
      five_hour: The rolling five hour session window.
      seven_day: The longer all-models window.
      updated_at: Epoch seconds the state file was last written.
      available: Whether real data was found, as opposed to placeholders.
    """

    five_hour: Window
    seven_day: Window
    updated_at: Optional[float]
    available: bool

    @property
    def stale(self) -> bool:
        """Whether the state file has not been refreshed recently."""
        if self.updated_at is None:
            return True
        return (time.time() - self.updated_at) > STALE_AFTER_SECONDS

    def age(self) -> str:
        """Format how long ago the state file was written.

        Returns:
          A string like "4m ago", or "never" when no data exists.
        """
        if self.updated_at is None:
            return "never"
        elapsed = int(time.time() - self.updated_at)
        if elapsed < 60:
            return f"{elapsed}s ago"
        if elapsed < 3600:
            return f"{elapsed // 60}m ago"
        return f"{elapsed // 3600}h ago"


def _empty_snapshot() -> UsageSnapshot:
    """Build a placeholder snapshot used when no state file exists."""
    return UsageSnapshot(
        five_hour=Window("5-HOUR", 0.0, None),
        seven_day=Window("WEEKLY", 0.0, None),
        updated_at=None,
        available=False,
    )


def _parse_window(label: str, raw: Optional[Dict[str, Any]]) -> Window:
    """Convert one rate_limits entry into a Window.

    Args:
      label: Display label for this window.
      raw: The five_hour or seven_day object, if present.

    Returns:
      A Window, defaulting to zero usage when fields are missing.
    """
    if not isinstance(raw, dict):
        return Window(label, 0.0, None)
    used = raw.get("used_percentage", 0.0)
    resets = raw.get("resets_at")
    return Window(
        label=label,
        used_percentage=float(used) if isinstance(used, (int, float)) else 0.0,
        resets_at=int(resets) if isinstance(resets, (int, float)) else None,
    )


def read_snapshot(state_file: Path) -> UsageSnapshot:
    """Read the statusline hook's state file into a UsageSnapshot.

    A missing or unreadable file yields a placeholder snapshot rather than
    raising, so the display keeps rendering something useful.

    Args:
      state_file: Path the statusline hook writes to.

    Returns:
      UsageSnapshot describing both windows.
    """
    try:
        payload = orjson.loads(state_file.read_bytes())
    except FileNotFoundError:
        return _empty_snapshot()
    except (orjson.JSONDecodeError, OSError) as exc:
        logger.error("Could not read state file %s: %s", state_file, exc)
        return _empty_snapshot()

    if not isinstance(payload, dict):
        logger.error("State file %s did not contain an object", state_file)
        return _empty_snapshot()

    limits = payload.get("rate_limits")
    if not isinstance(limits, dict):
        return _empty_snapshot()

    updated = payload.get("updated_at")
    return UsageSnapshot(
        five_hour=_parse_window("5-HOUR", limits.get("five_hour")),
        seven_day=_parse_window("WEEKLY", limits.get("seven_day")),
        updated_at=float(updated) if isinstance(updated, (int, float)) else None,
        available=True,
    )
