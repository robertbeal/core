"""Provide common fixtures for Yoto tests."""

from collections.abc import Generator
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.yoto.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.yoto.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Yoto",
        domain=DOMAIN,
        data={
            CONF_TOKEN: "mock-refresh-token",
        },
        unique_id="mock-refresh-token",
    )


@pytest.fixture
def device_auth_event() -> Generator[Event]:
    """Provide a threading Event to control device code auth completion."""
    event = Event()
    yield event
    event.set()


@pytest.fixture
def mock_yoto_manager() -> Generator[MagicMock]:
    """Mock the YotoManager for integration tests."""
    with patch(
        "homeassistant.components.yoto.YotoManager",
        autospec=True,
    ) as manager_class:
        manager = manager_class.return_value
        manager.token = MagicMock()
        manager.token.refresh_token = "mock-refresh-token"
        manager.players = {}
        manager.library = {}
        manager.api = MagicMock()
        manager.api._get_devices.return_value = {"devices": []}

        yield manager


@pytest.fixture
def mock_yoto_manager_config_flow(
    device_auth_event: Event,
) -> Generator[MagicMock]:
    """Mock the YotoManager for config flow tests."""
    with patch(
        "homeassistant.components.yoto.config_flow.YotoManager",
        autospec=True,
    ) as manager_class:
        manager = manager_class.return_value

        manager.device_code_flow_start.return_value = {
            "device_code": "test-device-code",
            "user_code": "ABCD-1234",
            "verification_uri_complete": "https://yoto.auth0.com/activate?user_code=ABCD-1234",
            "interval": 5,
            "expires_in": 900,
        }

        def mock_device_code_flow_complete() -> None:
            """Block until the test signals auth is complete."""
            device_auth_event.wait()

        manager.device_code_flow_complete = mock_device_code_flow_complete
        manager.token = MagicMock()
        manager.token.refresh_token = "mock-refresh-token"
        manager.players = {}

        yield manager
