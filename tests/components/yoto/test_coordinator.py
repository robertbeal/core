"""Tests for the Yoto coordinator."""

from threading import Thread
from unittest.mock import MagicMock

from yoto_api import AuthenticationError, YotoPlayer
from yoto_api.Card import Card, Chapter

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
    """Test coordinator returns players dict."""
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
    """Test coordinator refreshes token during updates."""
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
    """Test setup retry when API is unreachable."""
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
    """Test auth error during refresh."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator

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
    """Test API error during refresh."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator

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
    """Test coordinator persists a new refresh token."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_yoto_manager.token.refresh_token = "new-refresh-token"

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert mock_config_entry.data[CONF_TOKEN] == "new-refresh-token"


async def test_coordinator_skips_persist_when_token_unchanged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator skips persist when token is unchanged."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    version_before = mock_config_entry.version

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()

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


async def test_coordinator_defers_mqtt_when_no_players(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator does not connect to MQTT when players dict is empty."""
    mock_yoto_manager.players = {}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_yoto_manager.connect_to_events.assert_not_called()


async def test_coordinator_connects_to_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator connects to MQTT events once players are available."""
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
    """Test MQTT callback updates entities."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.IDLE

    mock_yoto_manager.players[PLAYER_ID] = _make_player(playback_status="playing")

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]

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
    """Test coordinator disconnects MQTT on unload."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_yoto_manager.disconnect.assert_called_once()


async def test_coordinator_fetches_library_on_first_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator fetches library when empty."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_yoto_manager.update_library.assert_called_once()


async def test_coordinator_skips_library_when_already_populated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator skips library when already populated."""
    mock_yoto_manager.library = {"card-1": Card(id="card-1", title="Test Card")}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_yoto_manager.update_library.assert_not_called()

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()

    mock_yoto_manager.update_library.assert_not_called()


async def test_mqtt_callback_fetches_card_detail_for_unknown_card(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test MQTT callback fetches card detail for unknown card."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    mock_yoto_manager.update_card_detail.assert_called_once_with("card-1")


async def test_mqtt_callback_fetches_card_detail_when_chapters_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test MQTT callback fetches card detail when chapters missing."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_yoto_manager.library = {"card-1": Card(id="card-1", title="Test Card")}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    mock_yoto_manager.update_card_detail.assert_called_once_with("card-1")


async def test_coordinator_tolerates_library_type_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator loads successfully when library raises TypeError.

    The yoto_api library has a bug where int(None) is called when a player's
    API response is missing temperature data. The coordinator should log a
    warning and return partial player data rather than failing the update.
    """
    player = YotoPlayer(id="player-1", name="My Yoto")
    mock_yoto_manager.players = {"player-1": player}
    mock_yoto_manager.update_players_status.side_effect = TypeError(
        "int() argument must be a string, a bytes-like object or a real number, "
        "not 'NoneType'"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True
    assert coordinator.data == {"player-1": player}


async def test_coordinator_returns_all_players_when_type_error_aborts_loop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test all players are returned even when update_players_status crashes mid-loop.

    The library's update_players() iterates over devices and crashes on the
    first player whose status response has None temperature. Players after the
    crash never get added to manager.players. The coordinator should pre-populate
    all players from the device list so every device is visible in HA even when
    the detailed status parsing fails partway through.
    """
    mock_yoto_manager.api._get_devices.return_value = {
        "devices": [
            {
                "deviceId": "player-1",
                "name": "Lounge Yoto",
                "deviceType": "v3",
                "online": True,
            },
            {
                "deviceId": "player-2",
                "name": "Bedroom Yoto",
                "deviceType": "v3",
                "online": True,
            },
        ]
    }

    def crash_after_first_player() -> None:
        """Simulate the library populating only the first player before crashing."""
        mock_yoto_manager.players["player-1"] = YotoPlayer(
            id="player-1", name="Lounge Yoto", device_type="v3", online=True
        )
        raise TypeError(
            "int() argument must be a string, a bytes-like object or a real number, "
            "not 'NoneType'"
        )

    mock_yoto_manager.update_players_status.side_effect = crash_after_first_player

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True
    assert "player-1" in coordinator.data
    assert "player-2" in coordinator.data
    assert coordinator.data["player-2"].name == "Bedroom Yoto"
    assert coordinator.data["player-2"].online is True


async def test_coordinator_persists_token_when_player_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator persists refreshed token even when player update raises."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator

    mock_yoto_manager.token.refresh_token = "new-refresh-token"
    mock_yoto_manager.update_players_status.side_effect = ConnectionError(
        "API unreachable"
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert mock_config_entry.data[CONF_TOKEN] == "new-refresh-token"


async def test_mqtt_callback_skips_card_detail_when_chapter_known(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test MQTT callback skips card detail when chapter known."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_yoto_manager.library = {
        "card-1": Card(
            id="card-1",
            title="Test Card",
            chapters={"ch-01": Chapter(key="ch-01", title="Chapter 1")},
        )
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    mock_yoto_manager.update_card_detail.assert_not_called()
