"""Switch platform for the Yoto integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription


@dataclass(frozen=True, kw_only=True)
class YotoSwitchEntityDescription(YotoEntityDescription, SwitchEntityDescription):
    """Description of a Yoto switch entity."""

    is_on_fn: Callable[[YotoPlayer], bool | None]
    config_field: str


SWITCHES: tuple[YotoSwitchEntityDescription, ...] = (
    YotoSwitchEntityDescription(
        key="day_auto_brightness",
        translation_key="day_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda player: player.config.day_display_brightness == "auto"
        if player.config and player.config.day_display_brightness is not None
        else None,
        config_field="day_display_brightness",
    ),
    YotoSwitchEntityDescription(
        key="night_auto_brightness",
        translation_key="night_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda player: player.config.night_display_brightness == "auto"
        if player.config and player.config.night_display_brightness is not None
        else None,
        config_field="night_display_brightness",
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
        """Turn the switch on (set brightness to auto)."""
        config = YotoPlayerConfig()
        setattr(config, self.entity_description.config_field, "auto")
        await self.hass.async_add_executor_job(
            self.coordinator.manager.set_player_config,
            self._player_id,
            config,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (disable auto brightness)."""
        config = YotoPlayerConfig()
        setattr(config, self.entity_description.config_field, "0")
        await self.hass.async_add_executor_job(
            self.coordinator.manager.set_player_config,
            self._player_id,
            config,
        )
