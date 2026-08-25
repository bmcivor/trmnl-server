"""Tests for the BYOS device API endpoints."""

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from trmnl_server.api import create_app
from trmnl_server.config import Config


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Provide a test client wired to a temporary, absent state file.

    Args:
      tmp_path: Directory the state file would live in.

    Yields:
      A TestClient that propagates handler exceptions rather than
      converting them into 500 responses.
    """
    config = Config(
        state_file=tmp_path / "state.json",
        host="127.0.0.1",
        port=2300,
        base_url="http://testserver",
        refresh_rate=900,
        api_key="test-key",
        friendly_id="TEST01",
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_device_log_accepts_a_batch(client: TestClient) -> None:
    """
    Setup: Post a well formed batch of log entries.
    Expectations: The endpoint returns 204, as the firmware expects.
    """
    body = {"logs": [{"level": "info", "message": "wifi connected"}]}

    response = client.post("/api/log", json=body)

    assert response.status_code == 204


def test_device_log_accepts_an_empty_batch(client: TestClient) -> None:
    """
    Setup: Post an object with no logs key at all.
    Expectations: The endpoint returns 204 without raising.
    """
    response = client.post("/api/log", json={})

    assert response.status_code == 204


def test_device_log_ignores_a_non_object_body(client: TestClient) -> None:
    """
    Setup: Post a JSON array where an object is expected.
    Expectations: The endpoint returns 204 rather than raising while
    iterating something that has no get method.
    """
    response = client.post("/api/log", json=[1, 2, 3])

    assert response.status_code == 204


def test_device_log_ignores_invalid_json(client: TestClient) -> None:
    """
    Setup: Post a body that cannot be parsed as JSON.
    Expectations: The endpoint returns 204 rather than surfacing the
    decode error to the device.
    """
    response = client.post(
        "/api/log",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 204
