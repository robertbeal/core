"""Tests for the Yoto sensor platform."""

import datetime
from unittest.mock import MagicMock

import pytest
from yoto_api import YotoPlayer

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
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
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(**player_overrides)
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_battery_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Battery sensor should expose battery_level_percentage."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, battery_level_percentage=75
    )

    state = hass.states.get("sensor.my_yoto_battery")
    assert state is not None
    assert state.state == "75"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE


async def test_temperature_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Temperature sensor should expose temperature_celcius."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, temperature_celcius=22
    )

    state = hass.states.get("sensor.my_yoto_temperature")
    assert state is not None
    assert state.state == "22"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    )


async def test_wifi_strength_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """WiFi strength sensor should expose wifi_strength as dBm."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, wifi_strength=-61
    )

    state = hass.states.get("sensor.my_yoto_wifi_signal_strength")
    assert state is not None
    assert state.state == "-61"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )


async def test_firmware_version_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Firmware version sensor should be a diagnostic entity."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, firmware_version="2.17.5"
    )

    state = hass.states.get("sensor.my_yoto_firmware_version")
    assert state is not None
    assert state.state == "2.17.5"

    entry = entity_registry.async_get("sensor.my_yoto_firmware_version")
    assert entry is not None
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_sensor_unavailable_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Sensor should report unknown when the underlying value is None."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, battery_level_percentage=None
    )

    state = hass.states.get("sensor.my_yoto_battery")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_last_updated_at_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Last updated at sensor should expose a timestamp when enabled."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        last_updated_at=datetime.datetime(2025, 6, 15, 10, 30, 0, tzinfo=datetime.UTC),
    )

    state = hass.states.get("sensor.my_yoto_last_updated_at")
    assert state is not None
    assert state.state == "2025-06-15T10:30:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_ambient_light_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Ambient light sensor should expose illuminance in lux when enabled."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, ambient_light_sensor_reading=350
    )

    state = hass.states.get("sensor.my_yoto_ambient_light")
    assert state is not None
    assert state.state == "350"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ILLUMINANCE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == LIGHT_LUX


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_battery_temperature_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Battery temperature sensor should be a diagnostic entity when enabled."""
    await _setup_player(
        hass, mock_config_entry, mock_yoto_manager, battery_temperature=32
    )

    state = hass.states.get("sensor.my_yoto_battery_temperature")
    assert state is not None
    assert state.state == "32"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS

    entry = entity_registry.async_get("sensor.my_yoto_battery_temperature")
    assert entry is not None
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_niche_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Niche sensors should be disabled by default in the entity registry."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        battery_temperature=32,
        ambient_light_sensor_reading=350,
        last_updated_at=None,
    )

    for entity_id in (
        "sensor.my_yoto_battery_temperature",
        "sensor.my_yoto_ambient_light",
        "sensor.my_yoto_last_updated_at",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, f"{entity_id} not found in registry"
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, (
            f"{entity_id} should be disabled by default"
        )
