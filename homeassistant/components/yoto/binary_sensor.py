"""Binary sensor platform for the Yoto integration."""

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription


@dataclass(frozen=True, kw_only=True)
class YotoBinarySensorEntityDescription(
    YotoEntityDescription, BinarySensorEntityDescription
):
    """Description of a Yoto binary sensor entity."""

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
        value_fn=lambda player: player.bluetooth_audio_connected,
    ),
    YotoBinarySensorEntityDescription(
        key="sleep_timer",
        translation_key="sleep_timer",
        value_fn=lambda player: player.sleep_timer_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yoto binary sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        YotoBinarySensorEntity(coordinator, player_id, description)
        for player_id in coordinator.data
        for description in BINARY_SENSORS
    )


class YotoBinarySensorEntity(YotoEntity, BinarySensorEntity):
    """Representation of a Yoto binary sensor."""

    entity_description: YotoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        description: YotoBinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor entity."""
        super().__init__(coordinator, player_id, description)

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value."""
        return self.entity_description.value_fn(self._player)
