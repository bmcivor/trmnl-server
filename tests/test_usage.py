"""Tests for reading and interpreting Claude Code rate limit state."""

import time
from pathlib import Path
from typing import Any, Dict

import orjson

from trmnl_server.usage import Window, read_snapshot


def _write_state(path: Path, payload: Dict[str, Any]) -> None:
    """Write a state file for the reader under test.

    Args:
      path: Destination file.
      payload: Object to serialise.
    """
    path.write_bytes(orjson.dumps(payload))


def test_missing_state_file_yields_placeholder(tmp_path: Path) -> None:
    """
    Setup: Point the reader at a path that does not exist.
    Expectations: A placeholder snapshot with available False and zeroed usage.
    """
    snapshot = read_snapshot(tmp_path / "absent.json")

    assert snapshot.available is False
    assert snapshot.five_hour.used_percentage == 0.0
    assert snapshot.seven_day.used_percentage == 0.0


def test_malformed_state_file_yields_placeholder(tmp_path: Path) -> None:
    """
    Setup: Write bytes that are not valid JSON to the state file.
    Expectations: The reader returns a placeholder rather than raising.
    """
    state = tmp_path / "state.json"
    state.write_bytes(b"{not json")

    snapshot = read_snapshot(state)

    assert snapshot.available is False


def test_reads_both_windows(tmp_path: Path) -> None:
    """
    Setup: Write a payload containing both rate limit windows.
    Expectations: Percentages and reset timestamps are parsed for each.
    """
    state = tmp_path / "state.json"
    resets = int(time.time()) + 3600
    _write_state(
        state,
        {
            "rate_limits": {
                "five_hour": {"used_percentage": 30.0, "resets_at": resets},
                "seven_day": {"used_percentage": 27.5, "resets_at": resets + 60},
            },
            "updated_at": time.time(),
        },
    )

    snapshot = read_snapshot(state)

    assert snapshot.available is True
    assert snapshot.five_hour.used_percentage == 30.0
    assert snapshot.seven_day.used_percentage == 27.5
    assert snapshot.five_hour.resets_at == resets


def test_expired_window_reports_zero_usage() -> None:
    """
    Setup: Build a window whose reset time has already passed.
    Expectations: effective_percentage is zero despite a stored value.
    """
    window = Window("5-HOUR", 88.0, int(time.time()) - 10)

    assert window.expired is True
    assert window.effective_percentage == 0.0


def test_countdown_formats_hours_and_minutes() -> None:
    """
    Setup: Build a window resetting a little over ninety-five minutes out,
    clear of the boundary where flooring would report a minute less.
    Expectations: The countdown renders as "1h 35m".
    """
    window = Window("5-HOUR", 10.0, int(time.time()) + (95 * 60) + 30)

    assert window.countdown() == "1h 35m"


def test_countdown_without_reset_time() -> None:
    """
    Setup: Build a window with no reset timestamp.
    Expectations: The countdown renders as a placeholder.
    """
    window = Window("WEEKLY", 10.0, None)

    assert window.countdown() == "--"
    assert window.expired is False


def test_snapshot_is_stale_without_timestamp(tmp_path: Path) -> None:
    """
    Setup: Write a payload with rate limits but no updated_at field.
    Expectations: The snapshot reports itself stale and ages as "never".
    """
    state = tmp_path / "state.json"
    _write_state(state, {"rate_limits": {"five_hour": {"used_percentage": 5}}})

    snapshot = read_snapshot(state)

    assert snapshot.stale is True
    assert snapshot.age() == "never"
