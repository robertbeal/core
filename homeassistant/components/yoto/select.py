"""Platform for select."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from yoto_api import YotoPlayer

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YotoConfigEntry
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoSelectEntityDescription(YotoEntityDescription, SelectEntityDescription):
    """Describes a Yoto select entity."""

    current_fn: Callable[[YotoPlayer], str | None]
    select_fn: Callable[[YotoDataUpdateCoordinator, str, str], Awaitable[None]]


async def _set_raw_config_option(
    coordinator: YotoDataUpdateCoordinator,
    player_id: str,
    api_key: str,
    local_attr: str,
    value: str,
) -> None:
    """Set a raw config field not supported by the yoto_api library."""
    await coordinator.async_set_raw_player_config(
        player_id,
        api_payload={api_key: value},
        local_updates={local_attr: value},
    )


SELECTS: tuple[YotoSelectEntityDescription, ...] = (
    YotoSelectEntityDescription(
        key="display_dim_timeout",
        translation_key="display_dim_timeout",
        entity_category=EntityCategory.CONFIG,
        options=["0", "15", "30", "60", "180", "300"],
        current_fn=lambda player: (
            getattr(player.config, "display_dim_timeout", None)
            if player.config
            else None
        ),
        select_fn=lambda coordinator, player_id, value: _set_raw_config_option(
            coordinator, player_id, "displayDimTimeout", "display_dim_timeout", value
        ),
    ),
    YotoSelectEntityDescription(
        key="shutdown_timeout",
        translation_key="shutdown_timeout",
        entity_category=EntityCategory.CONFIG,
        options=["0", "900", "1800", "3600", "7200", "10800"],
        current_fn=lambda player: (
            getattr(player.config, "shutdown_timeout", None) if player.config else None
        ),
        select_fn=lambda coordinator, player_id, value: _set_raw_config_option(
            coordinator, player_id, "shutdownTimeout", "shutdown_timeout", value
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
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
                YotoSelectEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in SELECTS
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoSelectEntity(YotoEntity, SelectEntity):
    """Yoto select entity."""

    entity_description: YotoSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.current_fn(self._player)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(
            self.coordinator,
            self._player_id,
            option,
        )
