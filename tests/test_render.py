"""Tests for rendering usage snapshots to e-ink images."""

import time
from pathlib import Path

from PIL import Image

from trmnl_server.config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from trmnl_server.render import render_snapshot, write_monochrome
from trmnl_server.usage import UsageSnapshot, Window


def _snapshot(available: bool = True) -> UsageSnapshot:
    """Build a snapshot for rendering tests.

    Args:
      available: Whether the snapshot should carry real data.

    Returns:
      A UsageSnapshot with both windows populated.
    """
    resets = int(time.time()) + 3600
    return UsageSnapshot(
        five_hour=Window("5-HOUR", 30.0, resets),
        seven_day=Window("WEEKLY", 27.0, resets + 7200),
        updated_at=time.time(),
        available=available,
    )


def test_render_produces_one_bit_panel_sized_bmp(tmp_path: Path) -> None:
    """
    Setup: Render a populated snapshot to a temporary path.
    Expectations: An 800x480 1-bit BMP is written to that path.
    """
    destination = tmp_path / "screen.bmp"

    render_snapshot(_snapshot(), destination)

    with Image.open(destination) as image:
        assert image.format == "BMP"
        assert image.mode == "1"
        assert image.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_render_creates_missing_directories(tmp_path: Path) -> None:
    """
    Setup: Render to a path whose parent directory does not exist.
    Expectations: The directory is created and the file written.
    """
    destination = tmp_path / "nested" / "deeper" / "screen.bmp"

    render_snapshot(_snapshot(), destination)

    assert destination.exists()


def test_render_handles_absent_usage_data(tmp_path: Path) -> None:
    """
    Setup: Render a snapshot marked unavailable.
    Expectations: A valid image is still produced rather than raising.
    """
    destination = tmp_path / "screen.bmp"

    render_snapshot(_snapshot(available=False), destination)

    with Image.open(destination) as image:
        assert image.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_write_monochrome_does_not_dither(tmp_path: Path) -> None:
    """
    Setup: Write a uniformly mid-grey image through the monochrome writer.
    Expectations: The output holds a single colour. Error-diffusion dithering
    would render mid-grey as a mix of black and white pixels instead.
    """
    destination = tmp_path / "grey.bmp"
    grey = Image.new("L", (64, 64), 128)

    write_monochrome(grey, destination)

    with Image.open(destination) as image:
        colours = image.convert("L").getcolors()

    assert colours is not None
    assert len(colours) == 1


def test_write_monochrome_creates_missing_directories(tmp_path: Path) -> None:
    """
    Setup: Write to a path whose parent directories do not exist.
    Expectations: The directories are created and the file written.
    """
    destination = tmp_path / "a" / "b" / "grey.bmp"

    write_monochrome(Image.new("L", (8, 8), 255), destination)

    assert destination.exists()


def test_render_is_not_blank(tmp_path: Path) -> None:
    """
    Setup: Render a populated snapshot.
    Expectations: The image contains black pixels, proving content was drawn.
    """
    destination = tmp_path / "screen.bmp"

    render_snapshot(_snapshot(), destination)

    with Image.open(destination) as image:
        colours = image.convert("L").getcolors()

    assert colours is not None
    assert any(value == 0 for _, value in colours)
