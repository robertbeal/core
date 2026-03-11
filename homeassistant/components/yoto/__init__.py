"""The Yoto integration."""

from __future__ import annotations

from dataclasses import dataclass

from yoto_api import YotoManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import CLIENT_ID, DOMAIN
from .coordinator import YotoDataUpdateCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class YotoRuntimeData:
    """Runtime data for Yoto."""

    coordinator: YotoDataUpdateCoordinator


type YotoConfigEntry = ConfigEntry[YotoRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: YotoConfigEntry) -> bool:
    """Set up a config entry."""
    manager = await hass.async_add_executor_job(YotoManager, CLIENT_ID)

    refresh_token = entry.data.get(CONF_TOKEN)
    if not refresh_token:
        raise ConfigEntryAuthFailed(
            translation_key="auth_failed", translation_domain=DOMAIN
        )

    await hass.async_add_executor_job(manager.set_refresh_token, refresh_token)

    coordinator = YotoDataUpdateCoordinator(hass, entry, manager)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = YotoRuntimeData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: YotoConfigEntry) -> bool:
    """Unload a config entry."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload:
        coordinator = entry.runtime_data.coordinator
        coordinator.persist_token_if_changed()
        await hass.async_add_executor_job(coordinator.manager.disconnect)

    return unload


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: YotoConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1] in entry.runtime_data.coordinator.data
    )
