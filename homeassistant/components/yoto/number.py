"""Number platform for the Yoto integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription


@dataclass(frozen=True, kw_only=True)
class YotoNumberEntityDescription(YotoEntityDescription, NumberEntityDescription):
    """Description of a Yoto number entity."""

    value_fn: Callable[[YotoPlayer], float | None]
    config_field: str
    convert_fn: Callable[[float], int | str]


def _brightness_value(player: YotoPlayer, field: str) -> float | None:
    """Return the brightness as a float, or None when 'auto' or missing."""
    if player.config is None:
        return None
    value = getattr(player.config, field)
    if value is None or value == "auto":
        return None
    return float(value)


NUMBERS: tuple[YotoNumberEntityDescription, ...] = (
    YotoNumberEntityDescription(
        key="day_max_volume_limit",
        translation_key="day_max_volume_limit",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        value_fn=lambda player: float(player.config.day_max_volume_limit)
        if player.config and player.config.day_max_volume_limit is not None
        else None,
        config_field="day_max_volume_limit",
        convert_fn=int,
    ),
    YotoNumberEntityDescription(
        key="night_max_volume_limit",
        translation_key="night_max_volume_limit",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        value_fn=lambda player: float(player.config.night_max_volume_limit)
        if player.config and player.config.night_max_volume_limit is not None
        else None,
        config_field="night_max_volume_limit",
        convert_fn=int,
    ),
    YotoNumberEntityDescription(
        key="day_display_brightness",
        translation_key="day_display_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda player: _brightness_value(player, "day_display_brightness"),
        config_field="day_display_brightness",
        convert_fn=int,
    ),
    YotoNumberEntityDescription(
        key="night_display_brightness",
        translation_key="night_display_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda player: _brightness_value(player, "night_display_brightness"),
        config_field="night_display_brightness",
        convert_fn=int,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yoto number entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        YotoNumberEntity(coordinator, player_id, description)
        for player_id in coordinator.data
        for description in NUMBERS
    )


class YotoNumberEntity(YotoEntity, NumberEntity):
    """Representation of a Yoto number entity."""

    entity_description: YotoNumberEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        description: YotoNumberEntityDescription,
    ) -> None:
        """Initialise the number entity."""
        super().__init__(coordinator, player_id, description)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._player)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        config = YotoPlayerConfig()
        setattr(
            config,
            self.entity_description.config_field,
            self.entity_description.convert_fn(value),
        )
        await self.hass.async_add_executor_job(
            self.coordinator.manager.set_player_config,
            self._player_id,
            config,
        )
