"""Runtime configuration for the TRMNL BYOS server."""

import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = Path.home() / ".claude" / "trmnl-usage.json"
DEFAULT_PORT = 2300
DEFAULT_REFRESH_RATE = 900
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
SCREEN_FILENAME = "screen.bmp"


@dataclass(frozen=True)
class Config:
    """Settings resolved from the environment.

    Attributes:
      state_file: Path the statusline hook writes rate limit JSON to.
      host: Interface the HTTP server binds to.
      port: TCP port the HTTP server listens on.
      base_url: Externally reachable base URL the device fetches images from.
      refresh_rate: Seconds the device sleeps between polls.
      api_key: Token issued to the device during setup.
      friendly_id: Six character device identifier issued during setup.
    """

    state_file: Path
    host: str
    port: int
    base_url: str
    refresh_rate: int
    api_key: str
    friendly_id: str


def detect_lan_address() -> str:
    """Discover the LAN address a device on the same network can reach.

    Opens an unconnected UDP socket towards a public address so the OS
    selects the outbound interface without sending any traffic.

    Returns:
      Dotted-quad address string, falling back to 127.0.0.1.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        logger.error(
            "Could not determine a LAN address, falling back to 127.0.0.1. "
            "The device cannot reach that; set TRMNL_BASE_URL explicitly."
        )
        return "127.0.0.1"
    finally:
        sock.close()


def load_config() -> Config:
    """Build a Config from TRMNL_* environment variables.

    Returns:
      Config with defaults applied for anything unset.
    """
    port = int(os.environ.get("TRMNL_PORT", DEFAULT_PORT))
    base_url: Optional[str] = os.environ.get("TRMNL_BASE_URL")
    if base_url is None:
        base_url = f"http://{detect_lan_address()}:{port}"
    state_file = os.environ.get("TRMNL_STATE_FILE")
    return Config(
        state_file=Path(state_file) if state_file else DEFAULT_STATE_FILE,
        host=os.environ.get("TRMNL_HOST", "0.0.0.0"),
        port=port,
        base_url=base_url.rstrip("/"),
        refresh_rate=int(
            os.environ.get("TRMNL_REFRESH_RATE", DEFAULT_REFRESH_RATE)
        ),
        api_key=os.environ.get("TRMNL_API_KEY", "local-byos-key"),
        friendly_id=os.environ.get("TRMNL_FRIENDLY_ID", "CLAUDE"),
    )
