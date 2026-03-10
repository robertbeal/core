"""Platform for time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoTimeEntityDescription(YotoEntityDescription, TimeEntityDescription):
    """Describes a Yoto time entity."""

    value_fn: Callable[[YotoPlayer], time | None]
    config_field: str


TIMES: tuple[YotoTimeEntityDescription, ...] = (
    YotoTimeEntityDescription(
        key="day_mode_time",
        translation_key="day_mode_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda player: player.config.day_mode_time if player.config else None,
        config_field="day_mode_time",
    ),
    YotoTimeEntityDescription(
        key="night_mode_time",
        translation_key="night_mode_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda player: (
            player.config.night_mode_time if player.config else None
        ),
        config_field="night_mode_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up times."""
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
                YotoTimeEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in TIMES
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoTimeEntity(YotoEntity, TimeEntity):
    """Yoto time entity."""

    entity_description: YotoTimeEntityDescription

    @property
    def native_value(self) -> time | None:
        """Return the current time value."""
        return self.entity_description.value_fn(self._player)

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        config = YotoPlayerConfig()
        setattr(config, self.entity_description.config_field, value)
        await self.coordinator.async_set_player_config(
            self._player_id,
            config,
        )
