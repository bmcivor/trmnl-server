"""Command line entry point for the TRMNL BYOS server."""

import logging

import uvicorn

from trmnl_server.api import create_app
from trmnl_server.config import load_config

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the HTTP server using environment-derived settings."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = load_config()
    logger.info("Binding to %s:%s", config.host, config.port)
    logger.info("Device API server URL: %s", config.base_url)
    logger.info("Reading usage state from %s", config.state_file)
    uvicorn.run(create_app(config), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
