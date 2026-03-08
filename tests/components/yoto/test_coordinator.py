"""Tests for the Yoto coordinator."""

from threading import Thread
from unittest.mock import MagicMock

from yoto_api import AuthenticationError, YotoPlayer

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
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


async def test_coordinator_persists_refreshed_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Coordinator should persist a new refresh token to the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Simulate the library obtaining a new refresh token
    mock_yoto_manager.token.refresh_token = "new-refresh-token"

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert mock_config_entry.data[CONF_TOKEN] == "new-refresh-token"


async def test_coordinator_skips_persist_when_token_unchanged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Coordinator should not update the config entry when the token is unchanged."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    version_before = mock_config_entry.version

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()

    # Config entry data should be the same object — no update call made
    assert mock_config_entry.data[CONF_TOKEN] == "mock-refresh-token"
    assert mock_config_entry.version == version_before


PLAYER_ID = "player-1"
ENTITY_ID = "media_player.my_yoto"


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


async def test_coordinator_connects_to_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Coordinator should connect to MQTT events during setup."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_yoto_manager.connect_to_events.assert_called_once()


async def test_mqtt_callback_updates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """MQTT callback should push updated player data to entities."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.IDLE

    # Simulate MQTT pushing a playing state — the library mutates the
    # player in-place, then invokes the callback from a background thread.
    mock_yoto_manager.players[PLAYER_ID] = _make_player(playback_status="playing")

    # Retrieve the callback that the coordinator registered
    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]

    # Fire the callback from a background thread, as paho-mqtt would
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING


async def test_coordinator_disconnects_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Coordinator should disconnect MQTT on unload."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_yoto_manager.disconnect.assert_called_once()
