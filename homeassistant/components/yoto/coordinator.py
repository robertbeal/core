"""Yoto coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from yoto_api import AuthenticationError, YotoManager, YotoPlayer
from yoto_api.utils import get_child_value

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YotoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, YotoPlayer]]):
    """Yoto data update coordinator."""

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
        self._mqtt_connected = False

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

    def _connect_to_events_if_ready(self) -> None:
        """Connect to MQTT push events once players are available."""
        if self._mqtt_connected or not self.manager.players:
            return
        self.manager.connect_to_events(self._handle_mqtt_event)
        self._mqtt_connected = True

    def _handle_mqtt_event(self) -> None:
        """Handle an MQTT event."""
        self.hass.loop.call_soon_threadsafe(self._process_mqtt_update)

    def _process_mqtt_update(self) -> None:
        """Process an MQTT update."""
        self._fetch_missing_card_details()
        self.async_set_updated_data(self.manager.players)

    def _fetch_missing_card_details(self) -> None:
        """Fetch missing card details for playing cards."""
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

    def _discover_all_players(self) -> None:
        """Pre-populate manager.players with basic info for every device.

        The library's update_players() loop can crash mid-iteration due to
        a bug parsing status data (e.g. int(None) for missing temperature).
        When that happens, devices after the crash point never get added to
        manager.players. By fetching the device list first and creating basic
        YotoPlayer entries, we ensure every device is at least visible even
        when the detailed status parsing fails partway through.
        """
        response = self.manager.api._get_devices(self.manager.token)  # noqa: SLF001
        for device in response.get("devices", []):
            device_id = get_child_value(device, "deviceId")
            if device_id and device_id not in self.manager.players:
                self.manager.players[device_id] = YotoPlayer(
                    id=device_id,
                    name=get_child_value(device, "name"),
                    device_type=get_child_value(device, "deviceType"),
                    online=get_child_value(device, "online"),
                )

    async def _async_update_data(self) -> dict[str, YotoPlayer]:
        """Fetch data from API."""
        try:
            await self.hass.async_add_executor_job(self.manager.check_and_refresh_token)
        except AuthenticationError as err:
            _LOGGER.error("Authentication error during update: %s", err)
            raise ConfigEntryAuthFailed(
                translation_key="auth_failed", translation_domain=DOMAIN
            ) from err

        self.persist_token_if_changed()

        try:
            await self.hass.async_add_executor_job(self._discover_all_players)
        except Exception as err:
            _LOGGER.warning(
                "Failed to pre-discover players: %s: %s", type(err).__name__, err
            )

        try:
            await self.hass.async_add_executor_job(self.manager.update_players_status)
        except TypeError as err:
            _LOGGER.warning(
                "Library bug during player status parsing, "
                "continuing with partial data: %s",
                err,
            )
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during update: %s: %s", type(err).__name__, err
            )
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from err

        try:
            if not self.manager.library:
                await self.hass.async_add_executor_job(self.manager.update_library)
            await self.hass.async_add_executor_job(self._connect_to_events_if_ready)
        except Exception as err:
            _LOGGER.error(
                "Unexpected error during update: %s: %s", type(err).__name__, err
            )
            raise UpdateFailed(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from err

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
        """Persist the refresh token if changed."""
        token = self.manager.token.refresh_token
        if token != self.config_entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )
