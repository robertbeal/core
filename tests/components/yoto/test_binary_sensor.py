"""Tests for the Yoto binary_sensor platform."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

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
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(**player_overrides)
    }
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
        state.attributes[ATTR_DEVICE_CLASS]
        == BinarySensorDeviceClass.BATTERY_CHARGING
    )


async def test_bluetooth_connected_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Bluetooth binary sensor should reflect connection state."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        bluetooth_audio_connected=True,
    )

    state = hass.states.get("binary_sensor.my_yoto_bluetooth_audio_connected")
    assert state is not None
    assert state.state == STATE_ON
    assert (
        state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    )


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
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, charging=None
    )

    state = hass.states.get("binary_sensor.my_yoto_charging")
    assert state is not None
    assert state.state == "unknown"
