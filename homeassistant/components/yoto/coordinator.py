"""Yoto coordinator."""

from __future__ import annotations

import dataclasses
import datetime
from datetime import timedelta
import json
import logging

import pytz
import requests
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

        Additionally, the dedicated status endpoint (/device-v2/{id}/status)
        now returns {"error": ...} for all devices. The config endpoint
        (/device-v2/{id}/config) returns both status and config data under
        device.status and device.config respectively.

        This method replaces the library's monolithic update by calling the
        config API once per device and extracting both status and config
        fields from that single response. Each player is updated
        independently so one failure doesn't block the others.
        """
        players = self.manager.players

        response = self.manager.api._get_devices(self.manager.token)  # noqa: SLF001
        for device in response.get("devices", []):
            device_id = get_child_value(device, "deviceId")
            if not device_id:
                continue

            if device_id not in players:
                players[device_id] = YotoPlayer(id=device_id)

            players[device_id].name = get_child_value(device, "name")
            players[device_id].device_type = get_child_value(device, "deviceType")
            players[device_id].online = get_child_value(device, "online")

            self._refresh_single_player(device_id)

    def _refresh_single_player(self, player_id: str) -> None:
        """Fetch and apply config/status data for a single player.

        Calls the config API for the given player and updates both status
        and config fields. Each step is wrapped in try/except so one
        failure does not prevent the other from being applied.
        """
        api = self.manager.api
        token = self.manager.token
        player = self.manager.players[player_id]

        try:
            config_response = api._get_device_config(token, player_id)  # noqa: SLF001
        except Exception as err:
            _LOGGER.warning(
                "Failed to fetch config for player %s: %s: %s",
                player_id,
                type(err).__name__,
                err,
            )
            return

        try:
            self._update_player_status(player=player, config_response=config_response)
        except Exception as err:
            _LOGGER.warning(
                "Failed to update status for player %s: %s: %s",
                player_id,
                type(err).__name__,
                err,
            )

        try:
            self._update_player_config(player=player, config_response=config_response)
        except Exception as err:
            _LOGGER.warning(
                "Failed to update config for player %s: %s: %s",
                player_id,
                type(err).__name__,
                err,
            )

        player.last_updated_at = datetime.datetime.now(pytz.utc)

    def _update_player_status(
        self, *, player: YotoPlayer, config_response: dict
    ) -> None:
        """Update a single player's status fields from the config API response.

        The dedicated status endpoint is broken (returns {"error": ...}).
        Status data is available in the config endpoint response under
        device.status, using abbreviated field names (e.g. 'als' instead
        of 'ambientLightSensorReading', 'day' instead of 'dayMode').
        """
        player.last_updated_api = datetime.datetime.now(pytz.utc)

        active_card = get_child_value(config_response, "device.status.activeCard")
        player.is_playing = active_card is not None and active_card != "none"
        player.active_card = active_card

        player.ambient_light_sensor_reading = get_child_value(
            config_response, "device.status.als"
        )
        player.day_mode_on = get_child_value(config_response, "device.status.day")
        player.user_volume = get_child_value(
            config_response, "device.status.userVolume"
        )
        player.system_volume = get_child_value(config_response, "device.status.volume")

        if player.battery_level_percentage is None:
            player.battery_level_percentage = get_child_value(
                config_response, "device.status.batteryLevel"
            )

        temp_raw = get_child_value(config_response, "device.status.temp")
        if temp_raw is not None:
            self._parse_temperature(player, temp_raw)

        player.bluetooth_audio_connected = get_child_value(
            config_response, "device.status.bluetoothHp"
        )
        player.charging = get_child_value(config_response, "device.status.charging")
        player.audio_device_connected = get_child_value(
            config_response, "device.status.headphones"
        )
        player.firmware_version = get_child_value(
            config_response, "device.status.fwVersion"
        )
        player.wifi_strength = get_child_value(
            config_response, "device.status.wifiStrength"
        )
        player.playing_source = get_child_value(
            config_response, "device.status.playingStatus"
        )
        player.night_light_mode = get_child_value(
            config_response, "device.status.nightlightMode"
        )

        power_source = get_child_value(config_response, "device.status.powerSrc")
        player.power_source = POWER_SOURCE.get(power_source)

    @staticmethod
    def _parse_temperature(player: YotoPlayer, temp_raw: str) -> None:
        """Parse temperature from the config API's abbreviated format.

        The config endpoint returns temp as "X:Y" where Y is the
        temperature in Celsius (e.g. "0:24" means 24°C).
        """
        try:
            temp_str = str(temp_raw)
            if ":" in temp_str:
                temp_str = temp_str.split(":")[1]
            temp_value = int(temp_str)
            if temp_value != 0:
                player.temperature_celcius = temp_value
        except ValueError, TypeError:
            pass

    def _update_player_config(
        self, *, player: YotoPlayer, config_response: dict
    ) -> None:
        """Update a single player's config fields from the API."""
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

        player.config.display_dim_timeout = get_child_value(
            config_response, "device.config.displayDimTimeout"
        )
        player.config.shutdown_timeout = get_child_value(
            config_response, "device.config.shutdownTimeout"
        )

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

    async def async_set_player_config(
        self, player_id: str, config: YotoPlayerConfig
    ) -> None:
        """Set player config, bypassing the library's buggy status refresh.

        YotoManager.set_player_config() calls update_players_status() after
        sending the config, which hits a bug in yoto_api where int(None) is
        called when the temperature field is missing from the API response.

        This method sends the config on the executor, then optimistically
        applies the sent fields to the local player and notifies HA.
        Reading back from the API immediately would return stale data since
        the device hasn't processed the change yet; the next scheduled poll
        will sync.
        """
        await self.hass.async_add_executor_job(
            self._send_player_config, player_id, config
        )
        player = self.manager.players[player_id]
        if player.config is None:
            player.config = YotoPlayerConfig()
        for field in dataclasses.fields(config):
            value = getattr(config, field.name)
            if value is not None:
                setattr(player.config, field.name, value)
        self.async_set_updated_data(self.manager.players)

    def _send_player_config(self, player_id: str, config: YotoPlayerConfig) -> None:
        """Send player config to the API (sync, runs on executor)."""
        self.manager.api.set_player_config(
            token=self.manager.token, player_id=player_id, config=config
        )

    async def async_set_raw_player_config(
        self,
        player_id: str,
        api_payload: dict[str, str],
        local_updates: dict[str, str],
    ) -> None:
        """Set raw config fields not supported by the yoto_api library.

        Some config fields (e.g. displayDimTimeout, shutdownTimeout) exist
        in the API but have no corresponding YotoPlayerConfig dataclass
        fields. This method sends arbitrary config key/value pairs directly
        to the API and optimistically applies local updates to the player
        config object using duck-typed attributes.

        api_payload: dict of API field names to string values
                     (e.g. {"displayDimTimeout": "120"})
        local_updates: dict of local attribute names to values
                       (e.g. {"display_dim_timeout": "120"})
        """
        await self.hass.async_add_executor_job(
            self._send_raw_player_config, player_id, api_payload
        )
        player = self.manager.players[player_id]
        if player.config is None:
            player.config = YotoPlayerConfig()
        for attr, value in local_updates.items():
            setattr(player.config, attr, value)
        self.async_set_updated_data(self.manager.players)

    def _send_raw_player_config(
        self, player_id: str, api_payload: dict[str, str]
    ) -> None:
        """Send raw config fields to the API (sync, runs on executor).

        Replicates the PUT logic from YotoAPI.set_player_config() for
        fields that the library doesn't know about.
        """
        api = self.manager.api
        token = self.manager.token
        url = f"{api.BASE_URL}/device-v2/{player_id}/config"
        headers = api._get_authenticated_headers(token)  # noqa: SLF001
        data = json.dumps({"deviceId": player_id, "config": api_payload})
        requests.put(url, headers=headers, data=data)

    def persist_token_if_changed(self) -> None:
        """Persist the refresh token if changed."""
        token = self.manager.token.refresh_token
        if token != self.config_entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )
