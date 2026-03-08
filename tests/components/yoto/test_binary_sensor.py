"""Tests for the Yoto binary_sensor platform."""

from unittest.mock import MagicMock

import pytest
from yoto_api import YotoPlayer

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def _setup_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    **player_overrides: object,
) -> None:
    """Set up hass with a single player entity."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player(**player_overrides)}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_online_binary_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Online binary sensor should be on when player is online."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, online=True)

    state = hass.states.get("binary_sensor.my_yoto_online")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY


async def test_online_binary_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Online binary sensor should be off when player is offline."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, online=False)

    state = hass.states.get("binary_sensor.my_yoto_online")
    assert state is not None
    assert state.state == STATE_OFF


async def test_charging_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Charging binary sensor should reflect charging state."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, charging=True)

    state = hass.states.get("binary_sensor.my_yoto_charging")
    assert state is not None
    assert state.state == STATE_ON
    assert (
        state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.BATTERY_CHARGING
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_bluetooth_connected_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Bluetooth binary sensor should reflect connection state when enabled."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        bluetooth_audio_connected=True,
    )

    state = hass.states.get("binary_sensor.my_yoto_bluetooth_audio_connected")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY


async def test_sleep_timer_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Sleep timer binary sensor should reflect active state."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, sleep_timer_active=True
    )

    state = hass.states.get("binary_sensor.my_yoto_sleep_timer")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_none_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Binary sensor should report unknown when the underlying value is None."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, charging=None)

    state = hass.states.get("binary_sensor.my_yoto_charging")
    assert state is not None
    assert state.state == "unknown"


async def test_day_mode_on_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Day mode binary sensor should reflect whether day mode is active."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, day_mode_on=True)

    state = hass.states.get("binary_sensor.my_yoto_day_mode")
    assert state is not None
    assert state.state == STATE_ON


async def test_day_mode_off_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Day mode binary sensor should be off during night mode."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, day_mode_on=False)

    state = hass.states.get("binary_sensor.my_yoto_day_mode")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_audio_device_connected_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Audio device connected binary sensor should reflect state when enabled."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, audio_device_connected=True
    )

    state = hass.states.get("binary_sensor.my_yoto_audio_device_connected")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_night_light_mode_binary_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Night light mode should be on when not 'off' (when enabled)."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, night_light_mode="0xff0000"
    )

    state = hass.states.get("binary_sensor.my_yoto_night_light_mode")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_night_light_mode_binary_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Night light mode should be off when value is 'off' (when enabled)."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, night_light_mode="off"
    )

    state = hass.states.get("binary_sensor.my_yoto_night_light_mode")
    assert state is not None
    assert state.state == STATE_OFF


async def test_niche_binary_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Niche binary sensors should be disabled by default in the entity registry."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        bluetooth_audio_connected=True,
        audio_device_connected=True,
        night_light_mode="0xff0000",
    )

    for entity_id in (
        "binary_sensor.my_yoto_bluetooth_audio_connected",
        "binary_sensor.my_yoto_audio_device_connected",
        "binary_sensor.my_yoto_night_light_mode",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, f"{entity_id} not found in registry"
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, (
            f"{entity_id} should be disabled by default"
        )
