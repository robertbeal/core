"""Base entity for the Yoto integration."""

from __future__ import annotations

from dataclasses import dataclass

from yoto_api import YotoPlayer

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YotoDataUpdateCoordinator


@dataclass(frozen=True)
class YotoEntityDescription(EntityDescription):
    """Base description for a Yoto entity."""


class YotoEntity(CoordinatorEntity[YotoDataUpdateCoordinator]):
    """Base class for Yoto entities."""

    _attr_has_entity_name = True
    entity_description: YotoEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        description: YotoEntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._player_id = player_id
        self._attr_unique_id = f"{player_id}-{description.key}"

        player = self._player
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player_id)},
            manufacturer="Yoto",
            model=player.device_type,
            name=player.name,
            sw_version=player.firmware_version,
        )

    @property
    def _player(self) -> YotoPlayer:
        """Return the current player data from the coordinator."""
        return self.coordinator.data[self._player_id]
