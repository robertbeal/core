"""Tests for the Yoto diagnostics."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics returns redacted player data."""
    player = MagicMock()
    player.__dict__ = {
        "id": "player-123",
        "name": "Living Room",
        "device_type": "v3",
        "online": True,
        "last_updated_at": "2025-01-01T12:00:00",
        "firmware_version": "5.0.0",
        "is_playing": True,
        "battery_level_percentage": 85,
        "temperature_celcius": 22.5,
        "wifi_strength": -45,
    }

    mock_yoto_manager.players = {"player-123": player}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot
