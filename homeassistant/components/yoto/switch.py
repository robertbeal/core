"""Switch platform for the Yoto integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yoto_api import YotoManager, YotoPlayer, YotoPlayerConfig

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 1


def _set_brightness(manager: YotoManager, player_id: str, field: str, value: str) -> None:
    """Set a display brightness field via the API."""
    config = YotoPlayerConfig()
    setattr(config, field, value)
    manager.set_player_config(player_id, config)


def _end_of_track_is_on(player: YotoPlayer) -> bool:
    """Return True when the sleep timer approximately matches the remaining track time."""
    if player.track_length is None or player.track_position is None:
        return False
    seconds_to_end = player.track_length - player.track_position
    return abs(player.sleep_timer_seconds_remaining - seconds_to_end) <= 5


def _end_of_track_turn_on(manager: YotoManager, player: YotoPlayer) -> None:
    """Set the sleep timer to the remaining track time."""
    if player.track_length is not None and player.track_position is not None:
        seconds_to_end = player.track_length - player.track_position
        manager.set_sleep(player.id, seconds_to_end)


def _end_of_track_turn_off(manager: YotoManager, player: YotoPlayer) -> None:
    """Cancel the sleep timer."""
    manager.set_sleep(player.id, 0)


@dataclass(frozen=True, kw_only=True)
class YotoSwitchEntityDescription(YotoEntityDescription, SwitchEntityDescription):
    """Description of a Yoto switch entity."""

    is_on_fn: Callable[[YotoPlayer], bool | None]
    turn_on_fn: Callable[[YotoManager, YotoPlayer], None]
    turn_off_fn: Callable[[YotoManager, YotoPlayer], None]


SWITCHES: tuple[YotoSwitchEntityDescription, ...] = (
    YotoSwitchEntityDescription(
        key="day_auto_brightness",
        translation_key="day_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda player: player.config.day_display_brightness == "auto"
        if player.config and player.config.day_display_brightness is not None
        else None,
        turn_on_fn=lambda manager, player: _set_brightness(
            manager, player.id, "day_display_brightness", "auto"
        ),
        turn_off_fn=lambda manager, player: _set_brightness(
            manager, player.id, "day_display_brightness", "0"
        ),
    ),
    YotoSwitchEntityDescription(
        key="night_auto_brightness",
        translation_key="night_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda player: player.config.night_display_brightness == "auto"
        if player.config and player.config.night_display_brightness is not None
        else None,
        turn_on_fn=lambda manager, player: _set_brightness(
            manager, player.id, "night_display_brightness", "auto"
        ),
        turn_off_fn=lambda manager, player: _set_brightness(
            manager, player.id, "night_display_brightness", "0"
        ),
    ),
    YotoSwitchEntityDescription(
        key="end_of_track_sleep",
        translation_key="end_of_track_sleep",
        is_on_fn=_end_of_track_is_on,
        turn_on_fn=_end_of_track_turn_on,
        turn_off_fn=_end_of_track_turn_off,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yoto switch entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        YotoSwitchEntity(coordinator, player_id, description)
        for player_id in coordinator.data
        for description in SWITCHES
    )


class YotoSwitchEntity(YotoEntity, SwitchEntity):
    """Representation of a Yoto switch entity."""

    entity_description: YotoSwitchEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        description: YotoSwitchEntityDescription,
    ) -> None:
        """Initialise the switch entity."""
        super().__init__(coordinator, player_id, description)

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.entity_description.is_on_fn(self._player)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_on_fn,
            self.coordinator.manager,
            self._player,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_off_fn,
            self.coordinator.manager,
            self._player,
        )
