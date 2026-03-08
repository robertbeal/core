"""Time platform for the Yoto integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription


@dataclass(frozen=True, kw_only=True)
class YotoTimeEntityDescription(YotoEntityDescription, TimeEntityDescription):
    """Description of a Yoto time entity."""

    value_fn: Callable[[YotoPlayer], time | None]
    config_field: str


TIMES: tuple[YotoTimeEntityDescription, ...] = (
    YotoTimeEntityDescription(
        key="day_mode_time",
        translation_key="day_mode_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda player: player.config.day_mode_time
        if player.config
        else None,
        config_field="day_mode_time",
    ),
    YotoTimeEntityDescription(
        key="night_mode_time",
        translation_key="night_mode_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda player: player.config.night_mode_time
        if player.config
        else None,
        config_field="night_mode_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yoto time entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        YotoTimeEntity(coordinator, player_id, description)
        for player_id in coordinator.data
        for description in TIMES
    )


class YotoTimeEntity(YotoEntity, TimeEntity):
    """Representation of a Yoto time entity."""

    entity_description: YotoTimeEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        description: YotoTimeEntityDescription,
    ) -> None:
        """Initialise the time entity."""
        super().__init__(coordinator, player_id, description)

    @property
    def native_value(self) -> time | None:
        """Return the current time value."""
        return self.entity_description.value_fn(self._player)

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        config = YotoPlayerConfig()
        setattr(config, self.entity_description.config_field, value)
        await self.hass.async_add_executor_job(
            self.coordinator.manager.set_player_config,
            self._player_id,
            config,
        )
