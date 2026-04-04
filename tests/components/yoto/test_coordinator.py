"""Tests for the Yoto coordinator."""

from threading import Event, Thread
from unittest.mock import MagicMock

from yoto_api import AuthenticationError, YotoPlayer, YotoPlayerConfig
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


def _make_config_response(
    *,
    status_overrides: dict | None = None,
    config_overrides: dict | None = None,
    device_overrides: dict | None = None,
) -> dict:
    """Build a realistic config API response with embedded status and config.

    The Yoto config endpoint (/device-v2/{id}/config) returns both status
    and config data under device.status and device.config respectively.
    Status uses abbreviated field names (e.g. 'als' not
    'ambientLightSensorReading').
    """
    status = {
        "activeCard": "none",
        "als": 0,
        "batteryLevel": 100,
        "bluetoothHp": 0,
        "charging": 0,
        "day": 1,
        "fwVersion": "v2.17.5",
        "headphones": 0,
        "nightlightMode": "0x000000",
        "playingStatus": 0,
        "powerSrc": 2,
        "temp": "0:24",
        "userVolume": 50,
        "volume": 50,
        "wifiStrength": -54,
        "freeDisk": 30219824,
        "totalDisk": 31385600,
        "bytesPS": 0,
    }
    if status_overrides:
        status.update(status_overrides)

    config = {
        "dayTime": "07:00",
        "dayDisplayBrightness": "auto",
        "ambientColour": "#ffffff",
        "maxVolumeLimit": 10,
        "nightTime": "19:00",
        "nightAmbientColour": "#0",
        "nightMaxVolumeLimit": 8,
        "nightDisplayBrightness": "50",
        "alarms": [],
        "displayDimTimeout": "60",
        "shutdownTimeout": "3600",
        "hourFormat": "12",
        "btHeadphonesEnabled": False,
        "headphonesVolumeLimited": False,
    }
    if config_overrides:
        config.update(config_overrides)

    device = {
        "mac": "b4:8a:0a:92:7a:f4",
        "registrationCode": "IBSKCAAA",
        "status": status,
        "config": config,
    }
    if device_overrides:
        device.update(device_overrides)

    return {"device": device}


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


async def test_coordinator_tolerates_status_parse_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator loads when one player's status data is corrupt.

    Status and config are both extracted from the config API response.
    If status parsing raises (e.g. unexpected field format), the config
    should still be populated.
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
    # Return config response with corrupt status (missing 'status' key entirely)
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
    # Status fields are None because device.status was missing
    assert coordinator.data["player-1"].charging is None
    # Config should still be populated
    assert coordinator.data["player-1"].config is not None


async def test_coordinator_handles_config_failure_for_one_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test config API failure for one player doesn't block the other.

    Both status and config are extracted from the config endpoint. If
    the config API call fails for one player, that player gets neither
    status nor config. The other player should still have both.
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

    def config_side_effect(_token, device_id):
        if device_id == "player-1":
            raise ConnectionError("Config API error for player-1")
        return _make_config_response(
            status_overrides={"charging": 0, "wifiStrength": -50},
        )

    mock_yoto_manager.api._get_device_config.side_effect = config_side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True

    # Player 1 should exist with basic info only (config API failed)
    assert "player-1" in coordinator.data
    assert coordinator.data["player-1"].charging is None
    assert coordinator.data["player-1"].config is None

    # Player 2 should have both status and config
    player2 = coordinator.data["player-2"]
    assert player2.charging == 0
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response(
        status_overrides={
            "als": 42,
            "charging": 1,
            "day": 1,
            "fwVersion": "v2.17.5",
            "wifiStrength": -61,
            "batteryLevel": 85,
            "temp": None,
            "volume": 47,
            "userVolume": 50,
            "powerSrc": 2,
        },
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]

    assert player.charging == 1
    assert player.day_mode_on == 1
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
    """Test each player is fetched independently.

    When the config API call fails for one player, the other player should
    still have full status and config data populated.
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

    def config_side_effect(_token, device_id):
        if device_id == "player-1":
            raise ConnectionError("API error for player-1")
        return _make_config_response(
            status_overrides={
                "als": 10,
                "batteryLevel": 90,
                "charging": 0,
                "day": 0,
                "fwVersion": "v2.17.5",
                "temp": "0:22",
                "userVolume": 60,
                "volume": 50,
                "wifiStrength": -50,
            },
        )

    mock_yoto_manager.api._get_device_config.side_effect = config_side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    # Player 1 should exist with basic info only (config API failed)
    assert "player-1" in coordinator.data
    assert coordinator.data["player-1"].name == "Lounge Yoto"
    assert coordinator.data["player-1"].charging is None  # no status data

    # Player 2 should have full status and config data
    player2 = coordinator.data["player-2"]
    assert player2.name == "Bedroom Yoto"
    assert player2.charging == 0
    assert player2.temperature_celcius == 22
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


async def test_mqtt_callback_skips_card_detail_when_chapter_key_mismatches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test MQTT callback skips fetch when card has chapters but key format differs.

    The API returns chapter keys like "03-1" but MQTT reports chapter_key
    as "03". Once the card's chapters have been fetched, no further API
    calls should be made regardless of whether the MQTT chapter_key
    matches an exact key in card.chapters.
    """
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_yoto_manager.library = {
        "card-1": Card(
            id="card-1",
            title="Test Card",
            chapters={
                "03-1": Chapter(key="03-1", title="Chapter 3 Part 1"),
                "03-2": Chapter(key="03-2", title="Chapter 3 Part 2"),
            },
        )
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # MQTT reports chapter_key="03" which doesn't match "03-1" or "03-2"
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="03",
        playback_status="playing",
    )

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    mock_yoto_manager.update_card_detail.assert_not_called()


async def test_coordinator_parses_colon_separated_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test temperature is parsed from the config endpoint's 'X:Y' format.

    The config endpoint returns temp as 'X:Y' where Y is the temperature
    in Celsius (e.g. '0:24' means 24 degrees).
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response(
        status_overrides={"temp": "0:24"},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]
    assert player.temperature_celcius == 24


async def test_coordinator_ignores_zero_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test temperature of zero is treated as no reading."""
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response(
        status_overrides={"temp": "0:0"},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]
    assert player.temperature_celcius is None


async def test_coordinator_handles_unparseable_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test unparseable temperature does not crash the update."""
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response(
        status_overrides={"temp": "notSupported"},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]
    assert player.temperature_celcius is None
    # Other fields should still be populated
    assert player.wifi_strength == -54
    assert player.config is not None


async def test_set_player_config_applies_optimistically(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test set_player_config applies changes locally without re-fetching.

    The Yoto API may return stale data immediately after a config change
    (the device hasn't processed it yet). So set_player_config should
    optimistically apply the sent config fields to the local player,
    notify HA of the update, and not read back from the API.
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    # Reset call counts after initial setup
    mock_yoto_manager.api._get_devices.reset_mock()
    mock_yoto_manager.api._get_device_config.reset_mock()

    config = YotoPlayerConfig(day_ambient_colour="#ff0000")
    await coordinator.async_set_player_config("player-1", config)

    # Should NOT have re-fetched anything from the API
    mock_yoto_manager.api._get_devices.assert_not_called()
    mock_yoto_manager.api._get_device_config.assert_not_called()

    # Should have optimistically applied the config field locally
    player = coordinator.data["player-1"]
    assert player.config.day_ambient_colour == "#ff0000"
    # Unchanged fields should retain their original values
    assert player.config.night_ambient_colour == "#0"
    assert player.config.day_max_volume_limit == 10

    # HA entity state should reflect the change
    state = hass.states.get("light.lounge_yoto_day_ambient_colour")
    assert state is not None
    assert state.state == "on"


async def test_coordinator_parses_display_dim_and_shutdown_timeouts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator parses displayDimTimeout and shutdownTimeout from config API."""
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response(
        config_overrides={"displayDimTimeout": "120", "shutdownTimeout": "7200"},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]
    assert player.config.display_dim_timeout == "120"
    assert player.config.shutdown_timeout == "7200"


async def test_coordinator_parses_mac_and_registration_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator parses mac and registrationCode from config API response."""
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response()

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]
    assert player.mac == "b4:8a:0a:92:7a:f4"
    assert player.registration_code == "IBSKCAAA"


async def test_mqtt_callback_does_not_re_fetch_card_already_in_flight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test repeated MQTT events do not re-fetch card details already requested.

    When a player is actively playing, MQTT events arrive every few seconds
    with position updates. Each event triggers _fetch_missing_card_details().
    If the card is unknown (not in library), the first event should trigger
    an API fetch, but subsequent events for the same card should not trigger
    additional fetches until the first one completes or fails.
    """
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Player starts playing an unknown card
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )

    # Block the card detail fetch so it stays in-flight while events arrive
    fetch_started = Event()
    fetch_proceed = Event()

    original_update = mock_yoto_manager.update_card_detail

    def blocking_update(card_id: str) -> None:
        fetch_started.set()
        fetch_proceed.wait()
        original_update(card_id)

    mock_yoto_manager.update_card_detail = MagicMock(side_effect=blocking_update)

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]

    # Fire 5 rapid MQTT events; the first triggers a fetch that blocks
    for _ in range(5):
        thread = Thread(target=mqtt_callback)
        thread.start()
        thread.join()

    # Wait for the first fetch to start, then fire remaining events through
    fetch_started.wait(timeout=2)
    await hass.async_block_till_done()

    # Let the blocked fetch complete
    fetch_proceed.set()
    await hass.async_block_till_done()

    # Should only fetch the card detail ONCE, not 5 times
    assert mock_yoto_manager.update_card_detail.call_count == 1


async def test_mqtt_callback_fetches_each_unknown_card_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test MQTT events for different unknown cards each trigger one fetch.

    When different cards are inserted, each unknown card should be fetched
    exactly once, but the same card should not be re-fetched on subsequent
    events.
    """
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]

    # Block card detail fetches so they stay in-flight while events arrive
    fetch_started = Event()
    fetch_proceed = Event()

    def blocking_update(card_id: str) -> None:
        fetch_started.set()
        fetch_proceed.wait()

    mock_yoto_manager.update_card_detail = MagicMock(side_effect=blocking_update)

    # First card: multiple rapid events while fetch is in-flight
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )
    for _ in range(3):
        thread = Thread(target=mqtt_callback)
        thread.start()
        thread.join()

    # Wait for first fetch to start, then release it
    fetch_started.wait(timeout=2)
    await hass.async_block_till_done()
    fetch_proceed.set()
    await hass.async_block_till_done()

    assert mock_yoto_manager.update_card_detail.call_count == 1

    # Reset for second card
    fetch_started.clear()
    fetch_proceed.clear()

    # Second card: multiple rapid events while fetch is in-flight
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-2",
        chapter_key="ch-01",
        playback_status="playing",
    )
    for _ in range(3):
        thread = Thread(target=mqtt_callback)
        thread.start()
        thread.join()

    fetch_started.wait(timeout=2)
    await hass.async_block_till_done()
    fetch_proceed.set()
    await hass.async_block_till_done()

    # Should have fetched each card exactly once (2 total, not 6)
    assert mock_yoto_manager.update_card_detail.call_count == 2


async def test_mqtt_update_only_notifies_playback_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test MQTT events only notify listeners registered with PLAYBACK context.

    During playback, MQTT events arrive every few seconds with position
    updates. These should only notify media player entities (registered
    with CONTEXT_PLAYBACK), not sensors, lights, etc. (registered with
    no context). This avoids ~27 entities re-evaluating their properties
    when only the media player's position changed.
    """
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    # Register two mock listeners: one with PLAYBACK context, one without
    from homeassistant.components.yoto.const import CONTEXT_PLAYBACK

    playback_listener = MagicMock()
    other_listener = MagicMock()

    coordinator.async_add_listener(playback_listener, CONTEXT_PLAYBACK)
    coordinator.async_add_listener(other_listener)

    # Update playback state and fire MQTT event
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        playback_status="playing",
        track_position=42,
    )

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    # Playback listener should have been notified
    playback_listener.assert_called()
    # Non-playback listener should NOT have been notified
    other_listener.assert_not_called()


async def test_polling_update_notifies_all_listeners(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test polling refresh notifies all listeners regardless of context.

    Unlike MQTT events (which are frequent and only affect playback),
    polling updates fetch fresh data for all fields and should notify
    every listener.
    """
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    from homeassistant.components.yoto.const import CONTEXT_PLAYBACK

    playback_listener = MagicMock()
    other_listener = MagicMock()

    coordinator.async_add_listener(playback_listener, CONTEXT_PLAYBACK)
    coordinator.async_add_listener(other_listener)

    # Trigger a polling refresh (this uses async_set_updated_data internally)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Both listeners should have been notified
    playback_listener.assert_called()
    other_listener.assert_called()


async def test_mqtt_callback_does_not_refetch_card_after_first_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test card detail is only fetched once per playback session.

    When a card is not in the library, the first MQTT event should
    trigger a fetch. Subsequent MQTT events for the same card on the
    same player must not trigger another fetch. When a different card
    starts playing and then the original card is re-inserted, a new
    fetch should be triggered.
    """
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}
    mock_yoto_manager.library = {}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )

    mqtt_callback = mock_yoto_manager.connect_to_events.call_args[0][0]

    # First MQTT event triggers a fetch
    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    assert mock_yoto_manager.update_card_detail.call_count == 1

    # Subsequent MQTT events for the same card should NOT re-fetch
    for _ in range(5):
        thread = Thread(target=mqtt_callback)
        thread.start()
        thread.join()
    await hass.async_block_till_done()

    assert mock_yoto_manager.update_card_detail.call_count == 1

    # A different card starts playing
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-2",
        chapter_key="ch-01",
        playback_status="playing",
    )

    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    assert mock_yoto_manager.update_card_detail.call_count == 2

    # Original card is re-inserted -- should fetch again (content may
    # have changed, e.g. a playlist card was updated)
    mock_yoto_manager.players[PLAYER_ID] = _make_player(
        card_id="card-1",
        chapter_key="ch-01",
        playback_status="playing",
    )

    thread = Thread(target=mqtt_callback)
    thread.start()
    thread.join()
    await hass.async_block_till_done()

    assert mock_yoto_manager.update_card_detail.call_count == 3


async def test_coordinator_handles_missing_mac_and_registration_code(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test coordinator handles missing mac and registrationCode gracefully."""
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
    mock_yoto_manager.api._get_device_config.return_value = _make_config_response(
        device_overrides={"mac": None, "registrationCode": None},
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    player = coordinator.data["player-1"]
    assert player.mac is None
    assert player.registration_code is None
