"""Tests for resolving runtime configuration from the environment."""

from pathlib import Path
from typing import Any

import pytest

from trmnl_server import config
from trmnl_server.config import (
    DEFAULT_API_KEY,
    DEFAULT_FRIENDLY_ID,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_REFRESH_RATE,
    DEFAULT_STATE_FILE,
    detect_lan_address,
    load_config,
)

TRMNL_VARS = (
    "TRMNL_HOST",
    "TRMNL_PORT",
    "TRMNL_BASE_URL",
    "TRMNL_STATE_FILE",
    "TRMNL_REFRESH_RATE",
    "TRMNL_API_KEY",
    "TRMNL_FRIENDLY_ID",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any TRMNL_ variables inherited from the developer's shell.

    Args:
      monkeypatch: pytest's environment patching fixture.
    """
    for name in TRMNL_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fixed_address(monkeypatch: pytest.MonkeyPatch) -> str:
    """Pin address detection so tests do not depend on the host's network.

    Args:
      monkeypatch: pytest's attribute patching fixture.

    Returns:
      The address detection will report.
    """
    address = "192.0.2.10"
    monkeypatch.setattr(config, "detect_lan_address", lambda: address)
    return address


def test_applies_defaults_when_nothing_is_set(fixed_address: str) -> None:
    """
    Setup: Resolve configuration with no TRMNL_ variables present.
    Expectations: Every field takes its documented default.
    """
    settings = load_config()

    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.refresh_rate == DEFAULT_REFRESH_RATE
    assert settings.api_key == DEFAULT_API_KEY
    assert settings.friendly_id == DEFAULT_FRIENDLY_ID
    assert settings.state_file == DEFAULT_STATE_FILE


def test_environment_overrides_every_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Setup: Set every TRMNL_ variable to a non-default value.
    Expectations: Each one reaches the corresponding Config field.
    """
    state = tmp_path / "elsewhere.json"
    monkeypatch.setenv("TRMNL_HOST", "127.0.0.1")
    monkeypatch.setenv("TRMNL_PORT", "9999")
    monkeypatch.setenv("TRMNL_BASE_URL", "http://example.test:9999")
    monkeypatch.setenv("TRMNL_STATE_FILE", str(state))
    monkeypatch.setenv("TRMNL_REFRESH_RATE", "60")
    monkeypatch.setenv("TRMNL_API_KEY", "a-different-key")
    monkeypatch.setenv("TRMNL_FRIENDLY_ID", "AB12CD")

    settings = load_config()

    assert settings.host == "127.0.0.1"
    assert settings.port == 9999
    assert settings.base_url == "http://example.test:9999"
    assert settings.state_file == state
    assert settings.refresh_rate == 60
    assert settings.api_key == "a-different-key"
    assert settings.friendly_id == "AB12CD"


def test_base_url_is_built_from_the_detected_address(
    fixed_address: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Setup: Leave TRMNL_BASE_URL unset while pinning address detection.
    Expectations: The base URL combines the detected address and the port.
    """
    monkeypatch.setenv("TRMNL_PORT", "8080")

    settings = load_config()

    assert settings.base_url == f"http://{fixed_address}:8080"


def test_base_url_trailing_slash_is_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Setup: Supply a base URL with a trailing slash.
    Expectations: The stored value has no trailing slash, so image URLs built
    by joining a path do not end up with a doubled separator.
    """
    monkeypatch.setenv("TRMNL_BASE_URL", "http://example.test:2300/")

    settings = load_config()

    assert settings.base_url == "http://example.test:2300"


def test_detect_lan_address_falls_back_and_closes_the_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Setup: Make the socket raise OSError when asked to connect.
    Expectations: Detection reports the loopback address and still closes the
    socket, since the caller has no other opportunity to release it.
    """
    closed: list[bool] = []

    class FailingSocket:
        def connect(self, address: Any) -> None:
            raise OSError("no route to host")

        def getsockname(self) -> Any:
            raise AssertionError("must not be reached after a failed connect")

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(
        "trmnl_server.config.socket.socket", lambda *a, **k: FailingSocket()
    )

    assert detect_lan_address() == "127.0.0.1"
    assert closed == [True]
