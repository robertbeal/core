"""Tests for the Yoto integration setup and teardown."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer

from homeassistant.components.yoto import async_remove_config_entry_device
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

PLAYER_ID = "player-1"


def _make_player(**overrides: object) -> YotoPlayer:
    """Create a YotoPlayer with sensible defaults."""
    defaults = {
        "id": PLAYER_ID,
        "name": "My Yoto",
        "device_type": "v3",
        "online": True,
        "firmware_version": "1.2.3",
    }
    return YotoPlayer(**{**defaults, **overrides})


async def test_unload_persists_refreshed_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Unloading should persist a changed refresh token before disconnecting."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Simulate the library having refreshed the token since last poll
    mock_yoto_manager.token.refresh_token = "new-refresh-token"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.data[CONF_TOKEN] == "new-refresh-token"


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Removing a device via the UI should succeed."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={("yoto", PLAYER_ID)})
    assert device_entry is not None

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, device_entry
    )
    assert result is True
