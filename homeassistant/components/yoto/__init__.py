"""Set up Yoto integration."""

from __future__ import annotations

from dataclasses import dataclass

from yoto_api import YotoManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import CLIENT_ID, DOMAIN
from .coordinator import YotoDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


@dataclass
class YotoRuntimeData:
    """Runtime data for the Yoto integration."""

    coordinator: YotoDataUpdateCoordinator


type YotoConfigEntry = ConfigEntry[YotoRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: YotoConfigEntry) -> bool:
    """Set up Yoto from a config entry."""
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
        coordinator._persist_token_if_changed()
        await hass.async_add_executor_job(coordinator.manager.disconnect)

    return unload
