"""Tests for the Yoto coordinator."""

from unittest.mock import MagicMock

from yoto_api import AuthenticationError, YotoPlayer

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_updates_players(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Coordinator should return the players dict from the manager."""
    player = YotoPlayer(id="player-1", name="My Yoto")
    mock_yoto_manager.players = {"player-1": player}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.data == {"player-1": player}


async def test_coordinator_refreshes_token_on_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Coordinator should call check_and_refresh_token during updates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_yoto_manager.check_and_refresh_token.assert_called()
    mock_yoto_manager.update_players_status.assert_called()


async def test_coordinator_setup_retry_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Setup should retry when the API is unreachable."""
    mock_yoto_manager.update_players_status.side_effect = ConnectionError(
        "API unreachable"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_error_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Auth error during coordinator refresh should raise UpdateFailed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator

    # Simulate auth failure on subsequent refresh
    mock_yoto_manager.check_and_refresh_token.side_effect = AuthenticationError(
        "Token expired"
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_api_error_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """API error during coordinator refresh should raise UpdateFailed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator

    # Simulate API failure on subsequent refresh
    mock_yoto_manager.update_players_status.side_effect = ConnectionError(
        "API unreachable"
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
