"""HTTP endpoints implementing the TRMNL BYOS device API."""

import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import FileResponse, ORJSONResponse

from trmnl_server.config import SCREEN_FILENAME, Config, load_config
from trmnl_server.render import render_snapshot
from trmnl_server.usage import read_snapshot

logger = logging.getLogger(__name__)


def create_app(config: Optional[Config] = None) -> FastAPI:
    """Build the FastAPI application serving the device API.

    Args:
      config: Settings to use; loaded from the environment when omitted.

    Returns:
      A configured FastAPI instance.
    """
    settings = config or load_config()
    screen_dir = Path(tempfile.gettempdir()) / "trmnl-server"
    screen_path = screen_dir / SCREEN_FILENAME

    app = FastAPI(
        title="TRMNL BYOS",
        default_response_class=ORJSONResponse,
    )
    app.state.config = settings
    app.state.screen_path = screen_path

    @app.get("/api/setup")
    async def setup(id: str = Header(default="")) -> Dict[str, Any]:
        """Register the device and hand back its credentials.

        Args:
          id: MAC address supplied by the firmware in the ID header.

        Returns:
          The api_key, friendly_id and a welcome image URL.
        """
        logger.info("Setup request from device %s", id or "<unknown>")
        return {
            "status": 200,
            "api_key": settings.api_key,
            "friendly_id": settings.friendly_id,
            "image_url": f"{settings.base_url}/{SCREEN_FILENAME}",
            "filename": SCREEN_FILENAME,
            "message": "Registered with local BYOS",
        }

    @app.get("/api/display")
    async def display(
        id: str = Header(default=""),
        access_token: str = Header(default="", alias="Access-Token"),
    ) -> Dict[str, Any]:
        """Render the current usage screen and tell the device where it is.

        Args:
          id: MAC address supplied by the firmware.
          access_token: API key previously issued at setup.

        Returns:
          A display payload naming the image URL and next refresh delay.
        """
        snapshot = read_snapshot(settings.state_file)
        try:
            render_snapshot(snapshot, screen_path)
        except OSError as exc:
            logger.error("Failed to render screen: %s", exc)

        stamp = int(time.time())
        return {
            "status": 0,
            "filename": f"{stamp}-{SCREEN_FILENAME}",
            "image_url": f"{settings.base_url}/{SCREEN_FILENAME}?v={stamp}",
            "image_url_timeout": 0,
            "refresh_rate": settings.refresh_rate,
            "reset_firmware": False,
            "update_firmware": False,
            "firmware_url": None,
            "firmware_version": None,
            "special_function": "none",
            "maximum_compatibility": False,
        }

    @app.post("/api/log", status_code=204)
    async def device_log(request: Request) -> Response:
        """Accept device log batches and record them locally.

        Args:
          request: Incoming request carrying a logs array.

        Returns:
          An empty 204 response, as the firmware expects.
        """
        try:
            payload = await request.json()
        except ValueError:
            logger.error("Device sent a log body that was not valid JSON")
            return Response(status_code=204)
        for entry in payload.get("logs", []) if isinstance(payload, dict) else []:
            logger.info(
                "device log [%s] %s",
                entry.get("level", "info"),
                entry.get("message", ""),
            )
        return Response(status_code=204)

    @app.get(f"/{SCREEN_FILENAME}")
    async def screen() -> Response:
        """Render the current usage screen and serve it.

        Rendering happens on every request rather than only when the file is
        absent, so a stale image is never served if the device fetches the
        image without first calling the display endpoint.

        Returns:
          The freshly rendered BMP.
        """
        render_snapshot(read_snapshot(settings.state_file), screen_path)
        return FileResponse(
            screen_path,
            media_type="image/bmp",
            headers={"Cache-Control": "no-store"},
        )

    return app
