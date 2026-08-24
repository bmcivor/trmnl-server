"""Rendering a usage snapshot to a 1-bit image for the e-ink panel."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from trmnl_server.config import DISPLAY_HEIGHT, DISPLAY_WIDTH
from trmnl_server.usage import UsageSnapshot, Window

logger = logging.getLogger(__name__)

BLACK = 0
WHITE = 255
MARGIN = 40
BAR_HEIGHT = 34
CONTENT_RIGHT = DISPLAY_WIDTH - MARGIN

FONT_CANDIDATES = (
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/mnt/c/Windows/Fonts/arialbd.ttf",
)

FontType = Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]


@lru_cache(maxsize=None)
def load_font(size: int) -> FontType:
    """Load a bold sans font at the given size.

    Tries several distribution-specific paths before falling back to
    Pillow's bundled bitmap font, which ignores the requested size.
    Results are cached, since every render requests the same handful of
    sizes and loading a TrueType face is not free.

    Args:
      size: Desired point size.

    Returns:
      A Pillow font object suitable for drawing.
    """
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    logger.error("No TrueType font found; falling back to bitmap default")
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: FontType) -> int:
    """Measure the rendered width of a string.

    Args:
      draw: Drawing context the text will be rendered with.
      text: String to measure.
      font: Font the string will be drawn in.

    Returns:
      Width in pixels.
    """
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(right - left)


def _draw_bar(
    draw: ImageDraw.ImageDraw, top_left: Tuple[int, int], percentage: float
) -> None:
    """Draw a progress bar showing a percentage of a window consumed.

    Args:
      draw: Drawing context.
      top_left: Upper-left corner of the bar.
      percentage: Value between 0 and 100.
    """
    x, y = top_left
    right = CONTENT_RIGHT
    draw.rectangle([x, y, right, y + BAR_HEIGHT], outline=BLACK, width=3)
    clamped = max(0.0, min(100.0, percentage))
    if clamped <= 0:
        return
    span = right - x - 6
    filled = int(span * clamped / 100.0)
    if filled > 0:
        draw.rectangle(
            [x + 3, y + 3, x + 3 + filled, y + BAR_HEIGHT - 3], fill=BLACK
        )


def _draw_window(
    draw: ImageDraw.ImageDraw,
    window: Window,
    top: int,
    label_font: FontType,
    value_font: FontType,
    detail_font: FontType,
) -> None:
    """Draw one rate limit window as a label, percentage, bar and countdown.

    Args:
      draw: Drawing context.
      window: The window being rendered.
      top: Y coordinate the block starts at.
      label_font: Font for the window name.
      value_font: Font for the large percentage.
      detail_font: Font for the reset countdown.
    """
    percentage = window.effective_percentage
    draw.text((MARGIN, top + 18), window.label, font=label_font, fill=BLACK)

    value = f"{percentage:.0f}%"
    width = _text_width(draw, value, value_font)
    draw.text((CONTENT_RIGHT - width, top), value, font=value_font, fill=BLACK)

    _draw_bar(draw, (MARGIN, top + 86), percentage)

    detail = f"resets in {window.countdown()}"
    draw.text((MARGIN, top + 130), detail, font=detail_font, fill=BLACK)


def write_monochrome(image: Image.Image, destination: Path) -> Path:
    """Convert a greyscale image to 1-bit and write it as a BMP.

    Dithering is disabled deliberately. Pillow defaults to Floyd-Steinberg,
    which diffuses the error from antialiased glyph edges into surrounding
    pixels and reads as speckle on a monochrome panel. Hard thresholding
    keeps edges solid.

    Args:
      image: Greyscale source image.
      destination: File path the BMP is written to.

    Returns:
      The path written to.

    Raises:
      OSError: If the destination cannot be written.

    Example:
      A uniform mid-grey input produces a single flat colour, where
      dithering would produce a checkerboard.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.convert("1", dither=Image.Dither.NONE).save(destination, format="BMP")
    return destination


def render_snapshot(snapshot: UsageSnapshot, destination: Path) -> Path:
    """Render a usage snapshot to a 1-bit BMP the firmware can display.

    Drawing happens in greyscale so text is antialiased, then hands off to
    write_monochrome for the 1-bit conversion.

    Args:
      snapshot: Usage data to draw.
      destination: File path the BMP is written to.

    Returns:
      The path written to.

    Raises:
      OSError: If the destination cannot be written.
    """
    image = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)

    title_font = load_font(30)
    label_font = load_font(30)
    value_font = load_font(88)
    detail_font = load_font(24)
    footer_font = load_font(20)

    draw.text((MARGIN, 26), "CLAUDE CODE USAGE", font=title_font, fill=BLACK)
    draw.line([MARGIN, 70, CONTENT_RIGHT, 70], fill=BLACK, width=3)

    if not snapshot.available:
        empty_font = load_font(52)
        message = "No usage data yet"
        hint = "Waiting for the Claude Code statusline hook"
        draw.text((MARGIN, 200), message, font=empty_font, fill=BLACK)
        draw.text((MARGIN, 276), hint, font=detail_font, fill=BLACK)
    else:
        _draw_window(
            draw, snapshot.five_hour, 92, label_font, value_font, detail_font
        )
        _draw_window(
            draw, snapshot.seven_day, 262, label_font, value_font, detail_font
        )

    footer = f"updated {snapshot.age()}"
    if snapshot.stale and snapshot.available:
        footer = f"{footer}  (stale)"
    draw.text((MARGIN, DISPLAY_HEIGHT - 40), footer, font=footer_font, fill=BLACK)

    return write_monochrome(image, destination)
