"""DataUpdateCoordinator for the Yoto integration."""

from __future__ import annotations

import logging

from yoto_api import AuthenticationError, YotoManager, YotoPlayer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class YotoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, YotoPlayer]]):
    """Coordinator to fetch player data from the Yoto API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        manager: YotoManager,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.manager = manager

    async def _async_update_data(self) -> dict[str, YotoPlayer]:
        """Fetch player data from the Yoto API."""
        try:
            await self.hass.async_add_executor_job(self.manager.check_and_refresh_token)
            await self.hass.async_add_executor_job(self.manager.update_players_status)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_key="auth_failed", translation_domain=DOMAIN
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from err

        self._persist_token_if_changed()

        return self.manager.players

    def _persist_token_if_changed(self) -> None:
        """Persist the refresh token to the config entry if it has changed."""
        token = self.manager.token.refresh_token
        if token != self.config_entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )
