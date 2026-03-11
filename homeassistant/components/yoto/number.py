"""Platform for number."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 1


async def _set_player_config_field(
    coordinator: YotoDataUpdateCoordinator, player_id: str, field: str, value: float
) -> None:
    """Set a player config field."""
    config = YotoPlayerConfig()
    setattr(config, field, int(value))
    await coordinator.async_set_player_config(player_id, config)


async def _set_sleep_timer(
    coordinator: YotoDataUpdateCoordinator, player_id: str, value: float
) -> None:
    """Set the sleep timer."""
    await coordinator.hass.async_add_executor_job(
        coordinator.manager.set_sleep, player_id, int(value)
    )


@dataclass(frozen=True, kw_only=True)
class YotoNumberEntityDescription(YotoEntityDescription, NumberEntityDescription):
    """Describes a Yoto number entity."""

    value_fn: Callable[[YotoPlayer], float | None]
    set_fn: Callable[[YotoDataUpdateCoordinator, str, float], Awaitable[None]]
    available_fn: Callable[[YotoPlayer], bool] = lambda _: True


def _brightness_value(player: YotoPlayer, field: str) -> float | None:
    """Return the brightness value."""
    if player.config is None:
        return None
    value = getattr(player.config, field)
    if value is None:
        return None
    if value == "auto":
        return 100.0
    return float(value)


NUMBERS: tuple[YotoNumberEntityDescription, ...] = (
    YotoNumberEntityDescription(
        key="day_max_volume_limit",
        translation_key="day_max_volume_limit",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        value_fn=lambda player: (
            float(player.config.day_max_volume_limit)
            if player.config and player.config.day_max_volume_limit is not None
            else None
        ),
        set_fn=lambda coordinator, player_id, value: _set_player_config_field(
            coordinator, player_id, "day_max_volume_limit", value
        ),
    ),
    YotoNumberEntityDescription(
        key="night_max_volume_limit",
        translation_key="night_max_volume_limit",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        value_fn=lambda player: (
            float(player.config.night_max_volume_limit)
            if player.config and player.config.night_max_volume_limit is not None
            else None
        ),
        set_fn=lambda coordinator, player_id, value: _set_player_config_field(
            coordinator, player_id, "night_max_volume_limit", value
        ),
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
        set_fn=lambda coordinator, player_id, value: _set_player_config_field(
            coordinator, player_id, "day_display_brightness", value
        ),
        available_fn=lambda player: (
            player.config is not None and player.config.day_display_brightness != "auto"
        ),
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
        set_fn=lambda coordinator, player_id, value: _set_player_config_field(
            coordinator, player_id, "night_display_brightness", value
        ),
        available_fn=lambda player: (
            player.config is not None
            and player.config.night_display_brightness != "auto"
        ),
    ),
    YotoNumberEntityDescription(
        key="sleep_timer",
        translation_key="sleep_timer",
        native_min_value=0,
        native_max_value=46500,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda player: (
            float(player.sleep_timer_seconds_remaining)
            if player.sleep_timer_seconds_remaining is not None
            else None
        ),
        set_fn=_set_sleep_timer,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
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
                YotoNumberEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in NUMBERS
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoNumberEntity(YotoEntity, NumberEntity):
    """Yoto number entity."""

    entity_description: YotoNumberEntityDescription

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return super().available and self.entity_description.available_fn(self._player)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._player)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        await self.entity_description.set_fn(
            self.coordinator,
            self._player_id,
            value,
        )
