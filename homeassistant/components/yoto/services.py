"""Yoto services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import selector, service

from .const import DOMAIN

if TYPE_CHECKING:
    from . import YotoConfigEntry

ATTR_CONFIG_ENTRY: Final = "config_entry"

SERVICE_UPDATE: Final = "update"
SERVICE_UPDATE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register service actions."""

    async def update(call: ServiceCall) -> None:
        """Force a data refresh."""
        entry: YotoConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY]
        )
        await entry.runtime_data.coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE,
        update,
        schema=SERVICE_UPDATE_SCHEMA,
    )
