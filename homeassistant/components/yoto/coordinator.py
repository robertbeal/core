"""DataUpdateCoordinator for the Yoto integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from yoto_api import AuthenticationError, YotoManager, YotoPlayer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
        scan_minutes = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_minutes),
        )
        self.manager = manager
        self.previous_players: set[str] = set()

    async def _async_setup(self) -> None:
        """Connect to MQTT events for real-time push updates."""
        await self.hass.async_add_executor_job(
            self.manager.connect_to_events, self._handle_mqtt_event
        )

    def _handle_mqtt_event(self) -> None:
        """Handle an MQTT event from the yoto-api background thread.

        This callback is invoked by paho-mqtt from a background thread,
        so we must use call_soon_threadsafe to marshal the update onto
        the event loop.
        """
        self.hass.loop.call_soon_threadsafe(self._process_mqtt_update)

    def _process_mqtt_update(self) -> None:
        """Process an MQTT update on the event loop."""
        self._fetch_missing_card_details()
        self.async_set_updated_data(self.manager.players)

    def _fetch_missing_card_details(self) -> None:
        """Schedule card detail fetches for cards with missing chapter data."""
        for player in self.manager.players.values():
            card_id = player.card_id
            chapter_key = player.chapter_key
            if not card_id or not chapter_key:
                continue

            card = self.manager.library.get(card_id)
            if card is None or not card.chapters or chapter_key not in card.chapters:
                self.hass.async_add_executor_job(
                    self.manager.update_card_detail, card_id
                )

    async def _async_update_data(self) -> dict[str, YotoPlayer]:
        """Fetch player data from the Yoto API."""
        try:
            await self.hass.async_add_executor_job(self.manager.check_and_refresh_token)
            await self.hass.async_add_executor_job(self.manager.update_players_status)
            if not self.manager.library:
                await self.hass.async_add_executor_job(self.manager.update_library)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_key="auth_failed", translation_domain=DOMAIN
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from err

        self.persist_token_if_changed()

        current_players = set(self.manager.players)
        if stale_players := self.previous_players - current_players:
            device_registry = dr.async_get(self.hass)
            for player_id in stale_players:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, player_id)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        self.previous_players = current_players

        return self.manager.players

    def persist_token_if_changed(self) -> None:
        """Persist the refresh token to the config entry if it has changed."""
        token = self.manager.token.refresh_token
        if token != self.config_entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )
