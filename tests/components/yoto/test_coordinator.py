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
    mock_yoto_manager.api._get_devices.assert_called()


async def test_coordinator_setup_retry_on_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setup retry when API is unreachable."""
    mock_yoto_manager.api._get_devices.side_effect = ConnectionError("API unreachable")

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

    mock_yoto_manager.api._get_devices.side_effect = ConnectionError("API unreachable")

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


async def test_coordinator_tolerates_single_player_status_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator loads when one player's status API call fails.

    The coordinator fetches each player's status independently. If one
    player's status call raises, the coordinator should log a warning and
    continue with the remaining players rather than failing the update.
    """
    mock_yoto_manager.api._get_devices.return_value = {
        "devices": [
            {
                "deviceId": "player-1",
                "name": "My Yoto",
                "deviceType": "v3",
                "online": True,
            },
        ]
    }
    mock_yoto_manager.api._get_device_status.side_effect = TypeError(
        "int() argument must be a string, a bytes-like object or a real number, "
        "not 'NoneType'"
    )
    mock_yoto_manager.api._get_device_config.return_value = {
        "device": {
            "config": {
                "dayTime": "07:00",
                "dayDisplayBrightness": "auto",
                "ambientColour": "#ffffff",
                "maxVolumeLimit": 10,
                "nightTime": "19:00",
                "nightAmbientColour": "#0",
                "nightMaxVolumeLimit": 8,
                "nightDisplayBrightness": "50",
                "alarms": [],
            }
        }
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True
    assert "player-1" in coordinator.data
    assert coordinator.data["player-1"].name == "My Yoto"
    assert coordinator.data["player-1"].config is not None


async def test_coordinator_handles_config_failure_for_one_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test config failure for one player doesn't block the other.

    Each player's config is fetched independently. If one player's config
    call fails, the other player should still have its config populated.
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
    mock_yoto_manager.api._get_device_status.return_value = {
        "activeCard": "none",
        "ambientLightSensorReading": 0,
        "batteryLevelPercentage": 100,
        "dayMode": False,
        "firmwareVersion": "v2.17.5",
        "isBluetoothAudioConnected": False,
        "isCharging": False,
        "isAudioDeviceConnected": False,
        "nightlightMode": "0x000000",
        "playingSource": 0,
        "powerSource": 2,
        "systemVolumePercentage": 50,
        "temperatureCelcius": "20",
        "userVolumePercentage": 50,
        "wifiStrength": -50,
    }

    def config_side_effect(_token, device_id):
        if device_id == "player-1":
            raise ConnectionError("Config API error for player-1")
        return {
            "device": {
                "config": {
                    "dayTime": "07:00",
                    "dayDisplayBrightness": "auto",
                    "ambientColour": "#ffffff",
                    "maxVolumeLimit": 10,
                    "nightTime": "19:00",
                    "nightAmbientColour": "#0",
                    "nightMaxVolumeLimit": 8,
                    "nightDisplayBrightness": "50",
                    "alarms": [],
                }
            }
        }

    mock_yoto_manager.api._get_device_config.side_effect = config_side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True

    # Player 1 should have status but no config
    assert "player-1" in coordinator.data
    assert coordinator.data["player-1"].charging is False
    assert coordinator.data["player-1"].config is None

    # Player 2 should have both status and config
    player2 = coordinator.data["player-2"]
    assert player2.charging is False
    assert player2.config is not None
    assert player2.config.day_max_volume_limit == 10


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
    mock_yoto_manager.api._get_devices.side_effect = ConnectionError("API unreachable")

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert mock_config_entry.data[CONF_TOKEN] == "new-refresh-token"


async def test_coordinator_populates_status_fields_despite_none_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test all status fields are populated even when temperature is None.

    The library's update_players() crashes on int(None) when temperature is
    missing. Our coordinator bypasses the library's monolithic update and
    parses each field safely, so temperature being None should not prevent
    charging, day_mode, battery, wifi etc. from being populated.
    """
    mock_yoto_manager.api._get_devices.return_value = {
        "devices": [
            {
                "deviceId": "player-1",
                "name": "Lounge Yoto",
                "deviceType": "v3",
                "online": True,
            },
        ]
    }
    mock_yoto_manager.api._get_device_status.return_value = {
        "activeCard": "none",
        "ambientLightSensorReading": 42,
        "batteryLevelPercentage": 85,
        "dayMode": True,
        "firmwareVersion": "v2.17.5",
        "isBluetoothAudioConnected": False,
        "isCharging": True,
        "isAudioDeviceConnected": False,
        "nightlightMode": "0x000000",
        "playingSource": 0,
        "powerSource": 2,
        "systemVolumePercentage": 47,
        "temperatureCelcius": None,
        "userVolumePercentage": 50,
        "wifiStrength": -61,
    }
    mock_yoto_manager.api._get_device_config.return_value = {
        "device": {
            "config": {
                "dayTime": "07:00",
                "dayDisplayBrightness": "auto",
                "ambientColour": "#ffffff",
                "maxVolumeLimit": 10,
                "nightTime": "19:00",
                "nightAmbientColour": "#0",
                "nightMaxVolumeLimit": 8,
                "nightDisplayBrightness": "50",
                "alarms": [],
            }
        }
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]

    assert player.charging is True
    assert player.day_mode_on is True
    assert player.wifi_strength == -61
    assert player.ambient_light_sensor_reading == 42
    assert player.firmware_version == "v2.17.5"
    assert player.temperature_celcius is None
    assert player.config is not None
    assert player.config.day_max_volume_limit == 10


async def test_coordinator_populates_all_players_independently(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test each player's status is fetched independently.

    When one player's status API call fails, the other player should still
    have full status data populated.
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

    def status_side_effect(_token, device_id):
        if device_id == "player-1":
            raise ConnectionError("API error for player-1")
        return {
            "activeCard": "none",
            "ambientLightSensorReading": 10,
            "batteryLevelPercentage": 90,
            "dayMode": False,
            "firmwareVersion": "v2.17.5",
            "isBluetoothAudioConnected": False,
            "isCharging": False,
            "isAudioDeviceConnected": False,
            "nightlightMode": "0x000000",
            "playingSource": 0,
            "powerSource": 2,
            "systemVolumePercentage": 50,
            "temperatureCelcius": "22",
            "userVolumePercentage": 60,
            "wifiStrength": -50,
        }

    mock_yoto_manager.api._get_device_status.side_effect = status_side_effect
    mock_yoto_manager.api._get_device_config.return_value = {
        "device": {
            "config": {
                "dayTime": "07:00",
                "dayDisplayBrightness": "auto",
                "ambientColour": "#ffffff",
                "maxVolumeLimit": 10,
                "nightTime": "19:00",
                "nightAmbientColour": "#0",
                "nightMaxVolumeLimit": 8,
                "nightDisplayBrightness": "50",
                "alarms": [],
            }
        }
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    # Player 1 should exist with basic info only (status failed)
    assert "player-1" in coordinator.data
    assert coordinator.data["player-1"].name == "Lounge Yoto"
    assert coordinator.data["player-1"].charging is None  # no status data

    # Player 2 should have full status data
    player2 = coordinator.data["player-2"]
    assert player2.name == "Bedroom Yoto"
    assert player2.charging is False
    assert player2.temperature_celcius == "22"
    assert player2.wifi_strength == -50
    assert player2.config is not None


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
