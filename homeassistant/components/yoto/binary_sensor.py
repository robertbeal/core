from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yoto_api import YotoPlayer

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class YotoBinarySensorEntityDescription(
    YotoEntityDescription, BinarySensorEntityDescription
):
    """Describes a Yoto binary sensor."""

    value_fn: Callable[[YotoPlayer], bool | None]


BINARY_SENSORS: tuple[YotoBinarySensorEntityDescription, ...] = (
    YotoBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda player: player.online,
    ),
    YotoBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda player: player.charging,
    ),
    YotoBinarySensorEntityDescription(
        key="bluetooth_audio_connected",
        translation_key="bluetooth_audio_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda player: player.bluetooth_audio_connected,
    ),
    YotoBinarySensorEntityDescription(
        key="sleep_timer",
        translation_key="sleep_timer",
        value_fn=lambda player: player.sleep_timer_active,
    ),
    YotoBinarySensorEntityDescription(
        key="day_mode",
        translation_key="day_mode",
        value_fn=lambda player: player.day_mode_on,
    ),
    YotoBinarySensorEntityDescription(
        key="audio_device_connected",
        translation_key="audio_device_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        value_fn=lambda player: player.audio_device_connected,
    ),
    YotoBinarySensorEntityDescription(
        key="night_light_mode",
        translation_key="night_light_mode",
        entity_registry_enabled_default=False,
        value_fn=lambda player: (
            player.night_light_mode != "off"
            if player.night_light_mode is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
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
                YotoBinarySensorEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in BINARY_SENSORS
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoBinarySensorEntity(YotoEntity, BinarySensorEntity):
    """Yoto binary sensor entity."""

    entity_description: YotoBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value."""
        return self.entity_description.value_fn(self._player)
