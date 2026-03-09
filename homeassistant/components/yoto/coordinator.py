"""Yoto coordinator."""

from __future__ import annotations

import datetime
from datetime import timedelta
import logging

import pytz
from yoto_api import AuthenticationError, YotoManager, YotoPlayer
from yoto_api.const import POWER_SOURCE
from yoto_api.utils import get_child_value
from yoto_api.YotoPlayer import Alarm, YotoPlayerConfig

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

    def _update_all_players(self) -> None:
        """Fetch devices and update each player's status and config safely.

        The upstream yoto_api library's update_players() has a bug where
        int(None) is called when a field like temperature is missing from
        the API response. This crashes the entire update loop, leaving all
        players with no status data.

        This method replaces the library's monolithic update by calling the
        per-device APIs directly and parsing each field with None guards.
        Each player is updated independently so one failure doesn't block
        the others.
        """
        api = self.manager.api
        token = self.manager.token
        players = self.manager.players

        response = api._get_devices(token)  # noqa: SLF001
        for device in response.get("devices", []):
            device_id = get_child_value(device, "deviceId")
            if not device_id:
                continue

            if device_id not in players:
                players[device_id] = YotoPlayer(id=device_id)

            players[device_id].name = get_child_value(device, "name")
            players[device_id].device_type = get_child_value(device, "deviceType")
            players[device_id].online = get_child_value(device, "online")

            try:
                self._update_player_status(device_id)
            except Exception as err:
                _LOGGER.warning(
                    "Failed to update status for player %s: %s: %s",
                    device_id,
                    type(err).__name__,
                    err,
                )

            try:
                self._update_player_config(device_id)
            except Exception as err:
                _LOGGER.warning(
                    "Failed to update config for player %s: %s: %s",
                    device_id,
                    type(err).__name__,
                    err,
                )

            players[device_id].last_updated_at = datetime.datetime.now(pytz.utc)

    def _update_player_status(self, device_id: str) -> None:
        """Update a single player's status fields from the API."""
        api = self.manager.api
        token = self.manager.token
        player = self.manager.players[device_id]

        status = api._get_device_status(token, device_id)  # noqa: SLF001

        player.last_updated_api = datetime.datetime.now(pytz.utc)

        active_card = get_child_value(status, "activeCard")
        player.is_playing = active_card != "none"
        player.active_card = active_card

        player.ambient_light_sensor_reading = get_child_value(
            status, "ambientLightSensorReading"
        )
        player.day_mode_on = get_child_value(status, "dayMode")
        player.user_volume = get_child_value(status, "userVolumePercentage")
        player.system_volume = get_child_value(status, "systemVolumePercentage")

        if player.battery_level_percentage is None:
            player.battery_level_percentage = get_child_value(
                status, "batteryLevelPercentage"
            )

        temp = get_child_value(status, "temperatureCelcius")
        if temp is not None and temp != "notSupported":
            try:
                if int(temp) != 0:
                    player.temperature_celcius = temp
            except ValueError, TypeError:
                pass

        player.bluetooth_audio_connected = get_child_value(
            status, "isBluetoothAudioConnected"
        )
        player.charging = get_child_value(status, "isCharging")
        player.audio_device_connected = get_child_value(
            status, "isAudioDeviceConnected"
        )
        player.firmware_version = get_child_value(status, "firmwareVersion")
        player.wifi_strength = get_child_value(status, "wifiStrength")
        player.playing_source = get_child_value(status, "playingSource")
        player.night_light_mode = get_child_value(status, "nightlightMode")

        power_source = get_child_value(status, "powerSource")
        player.power_source = POWER_SOURCE.get(power_source)

    def _update_player_config(self, device_id: str) -> None:
        """Update a single player's config fields from the API."""
        api = self.manager.api
        token = self.manager.token
        player = self.manager.players[device_id]

        config_response = api._get_device_config(token, device_id)  # noqa: SLF001

        if player.config is None:
            player.config = YotoPlayerConfig()

        day_time = get_child_value(config_response, "device.config.dayTime")
        if day_time is not None:
            player.config.day_mode_time = datetime.datetime.strptime(
                day_time, "%H:%M"
            ).time()

        player.config.day_display_brightness = get_child_value(
            config_response, "device.config.dayDisplayBrightness"
        )
        player.config.day_ambient_colour = get_child_value(
            config_response, "device.config.ambientColour"
        )
        player.config.day_max_volume_limit = get_child_value(
            config_response, "device.config.maxVolumeLimit"
        )

        night_time = get_child_value(config_response, "device.config.nightTime")
        if night_time is not None:
            player.config.night_mode_time = datetime.datetime.strptime(
                night_time, "%H:%M"
            ).time()

        player.config.night_ambient_colour = get_child_value(
            config_response, "device.config.nightAmbientColour"
        )
        player.config.night_max_volume_limit = get_child_value(
            config_response, "device.config.nightMaxVolumeLimit"
        )
        player.config.night_display_brightness = get_child_value(
            config_response, "device.config.nightDisplayBrightness"
        )

        alarms = get_child_value(config_response, "device.config.alarms")
        if alarms is not None:
            self._parse_alarms(player, alarms)

        player.last_update_config = datetime.datetime.now(pytz.utc)

    @staticmethod
    def _parse_alarms(player: YotoPlayer, alarms: list[str]) -> None:
        """Parse alarm config strings into Alarm objects."""
        if player.config.alarms is None:
            player.config.alarms = []

        for index in range(len(alarms)):
            values = alarms[index].split(",")
            if index > len(player.config.alarms) - 1:
                enabled = True
                if len(values) > 6:
                    enabled = values[6] != "0"
                player.config.alarms.append(
                    Alarm(
                        days_enabled=values[0],
                        time=values[1],
                        sound_id=values[2],
                        volume=values[5],
                        enabled=enabled,
                    )
                )
            else:
                player.config.alarms[index].days_enabled = values[0]
                player.config.alarms[index].time = values[1]
                player.config.alarms[index].sound_id = values[2]
                player.config.alarms[index].volume = values[5]
                if len(values) > 6:
                    player.config.alarms[index].enabled = values[6] != "0"

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
            await self.hass.async_add_executor_job(self._update_all_players)
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
