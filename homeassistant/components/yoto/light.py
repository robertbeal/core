"""Platform for light."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.light import (
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoLightEntityDescription(YotoEntityDescription, LightEntityDescription):
    """Describes a Yoto light entity."""

    value_fn: Callable[[YotoPlayer], str | None]
    config_field: str


LIGHTS: tuple[YotoLightEntityDescription, ...] = (
    YotoLightEntityDescription(
        key="day_ambient_colour",
        translation_key="day_ambient_colour",
        value_fn=lambda player: (
            player.config.day_ambient_colour if player.config else None
        ),
        config_field="day_ambient_colour",
    ),
    YotoLightEntityDescription(
        key="night_ambient_colour",
        translation_key="night_ambient_colour",
        value_fn=lambda player: (
            player.config.night_ambient_colour if player.config else None
        ),
        config_field="night_ambient_colour",
    ),
)


def _hex_to_rgb(hex_colour: str) -> tuple[int, int, int]:
    """Convert a hex colour string to an RGB tuple."""
    hex_colour = hex_colour.lstrip("#")
    return (
        int(hex_colour[0:2], 16),
        int(hex_colour[2:4], 16),
        int(hex_colour[4:6], 16),
    )


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert an RGB tuple to a hex colour string."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights."""
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
                YotoLightEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in LIGHTS
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoLightEntity(YotoEntity, LightEntity):
    """Yoto ambient colour light."""

    entity_description: YotoLightEntityDescription
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    @property
    def _colour_hex(self) -> str | None:
        """Return the raw hex colour value."""
        return self.entity_description.value_fn(self._player)

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        colour = self._colour_hex
        if colour is None:
            return None
        return colour != "#0"

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB colour."""
        colour = self._colour_hex
        if colour is None or colour == "#0":
            return None
        return _hex_to_rgb(colour)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_RGB_COLOR in kwargs:
            hex_colour = _rgb_to_hex(kwargs[ATTR_RGB_COLOR])
        else:
            hex_colour = "#ffffff"

        config = YotoPlayerConfig()
        setattr(config, self.entity_description.config_field, hex_colour)
        await self.coordinator.async_set_player_config(
            self._player_id,
            config,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        config = YotoPlayerConfig()
        setattr(config, self.entity_description.config_field, "#0")
        await self.coordinator.async_set_player_config(
            self._player_id,
            config,
        )
