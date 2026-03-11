"""Platform for sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yoto_api import YotoPlayer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class YotoSensorEntityDescription(YotoEntityDescription, SensorEntityDescription):
    """Describes a Yoto sensor."""

    value_fn: Callable[[YotoPlayer], str | int | float | None]


SENSORS: tuple[YotoSensorEntityDescription, ...] = (
    YotoSensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda player: player.battery_level_percentage,
    ),
    YotoSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda player: player.temperature_celcius,
    ),
    YotoSensorEntityDescription(
        key="wifi_signal_strength",
        translation_key="wifi_signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda player: player.wifi_strength,
    ),
    YotoSensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda player: player.firmware_version,
    ),
    YotoSensorEntityDescription(
        key="last_updated_at",
        translation_key="last_updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda player: player.last_updated_at,
    ),
    YotoSensorEntityDescription(
        key="ambient_light",
        translation_key="ambient_light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda player: player.ambient_light_sensor_reading,
    ),
    YotoSensorEntityDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda player: player.battery_temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data.coordinator

    known_players: set[str] = set()

    @callback
    def _async_add_new_players() -> None:
        """Add entities for newly discovered players."""
        current_players = set(coordinator.data)
        new_players = current_players - known_players
        if new_players:
            known_players.update(new_players)
            async_add_entities(
                YotoSensorEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in SENSORS
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoSensorEntity(YotoEntity, SensorEntity):
    """Yoto sensor entity."""

    entity_description: YotoSensorEntityDescription

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._player)
