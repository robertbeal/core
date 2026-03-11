from __future__ import annotations

from dataclasses import dataclass

from yoto_api import YotoPlayer

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
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
        mac = getattr(player, "mac", None)
        connections: set[tuple[str, str]] = set()
        if mac:
            connections.add((CONNECTION_NETWORK_MAC, format_mac(mac)))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player_id)},
            connections=connections,
            manufacturer="Yoto",
            model=player.device_type,
            name=player.name,
            serial_number=getattr(player, "registration_code", None),
            sw_version=player.firmware_version,
        )

    @property
    def _player(self) -> YotoPlayer:
        """Return the current player data."""
        return self.coordinator.data[self._player_id]
