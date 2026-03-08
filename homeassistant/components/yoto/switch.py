"""Switch platform for the Yoto integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yoto_api import YotoManager, YotoPlayer, YotoPlayerConfig
from yoto_api.YotoPlayer import Alarm

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import YotoConfigEntry
from .const import DOMAIN
from .coordinator import YotoDataUpdateCoordinator
from .entity import YotoEntity, YotoEntityDescription

PARALLEL_UPDATES = 1


def _set_brightness(
    manager: YotoManager, player_id: str, field: str, value: str
) -> None:
    """Set a display brightness field via the API."""
    config = YotoPlayerConfig()
    setattr(config, field, value)
    manager.set_player_config(player_id, config)


def _end_of_track_is_on(player: YotoPlayer) -> bool:
    """Return True when the sleep timer approximately matches the remaining track time."""
    if (
        player.track_length is None
        or player.track_position is None
        or player.sleep_timer_seconds_remaining is None
    ):
        return False
    seconds_to_end = player.track_length - player.track_position
    return abs(player.sleep_timer_seconds_remaining - seconds_to_end) <= 5


def _end_of_track_turn_on(manager: YotoManager, player: YotoPlayer) -> None:
    """Set the sleep timer to the remaining track time."""
    if player.track_length is not None and player.track_position is not None:
        seconds_to_end = player.track_length - player.track_position
        manager.set_sleep(player.id, seconds_to_end)


def _end_of_track_turn_off(manager: YotoManager, player: YotoPlayer) -> None:
    """Cancel the sleep timer."""
    manager.set_sleep(player.id, 0)


@dataclass(frozen=True, kw_only=True)
class YotoSwitchEntityDescription(YotoEntityDescription, SwitchEntityDescription):
    """Description of a Yoto switch entity."""

    is_on_fn: Callable[[YotoPlayer], bool | None]
    turn_on_fn: Callable[[YotoManager, YotoPlayer], None]
    turn_off_fn: Callable[[YotoManager, YotoPlayer], None]


SWITCHES: tuple[YotoSwitchEntityDescription, ...] = (
    YotoSwitchEntityDescription(
        key="day_auto_brightness",
        translation_key="day_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda player: (
            player.config.day_display_brightness == "auto"
            if player.config and player.config.day_display_brightness is not None
            else None
        ),
        turn_on_fn=lambda manager, player: _set_brightness(
            manager, player.id, "day_display_brightness", "auto"
        ),
        turn_off_fn=lambda manager, player: _set_brightness(
            manager, player.id, "day_display_brightness", "0"
        ),
    ),
    YotoSwitchEntityDescription(
        key="night_auto_brightness",
        translation_key="night_auto_brightness",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda player: (
            player.config.night_display_brightness == "auto"
            if player.config and player.config.night_display_brightness is not None
            else None
        ),
        turn_on_fn=lambda manager, player: _set_brightness(
            manager, player.id, "night_display_brightness", "auto"
        ),
        turn_off_fn=lambda manager, player: _set_brightness(
            manager, player.id, "night_display_brightness", "0"
        ),
    ),
    YotoSwitchEntityDescription(
        key="end_of_track_sleep",
        translation_key="end_of_track_sleep",
        is_on_fn=_end_of_track_is_on,
        turn_on_fn=_end_of_track_turn_on,
        turn_off_fn=_end_of_track_turn_off,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yoto switch entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    known_players: set[str] = set()

    @callback
    def _async_add_new_players() -> None:
        """Add switch entities for any newly discovered players."""
        current_players = set(coordinator.data)
        new_players = current_players - known_players
        if new_players:
            known_players.update(new_players)

            entities: list[SwitchEntity] = [
                YotoSwitchEntity(coordinator, player_id, description)
                for player_id in new_players
                for description in SWITCHES
            ]

            for player_id in new_players:
                player = coordinator.data[player_id]
                if player.config and player.config.alarms:
                    entities.extend(
                        YotoAlarmSwitchEntity(coordinator, player_id, index)
                        for index in range(len(player.config.alarms))
                    )

            async_add_entities(entities)

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoSwitchEntity(YotoEntity, SwitchEntity):
    """Representation of a Yoto switch entity."""

    entity_description: YotoSwitchEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        description: YotoSwitchEntityDescription,
    ) -> None:
        """Initialise the switch entity."""
        super().__init__(coordinator, player_id, description)

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.entity_description.is_on_fn(self._player)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_on_fn,
            self.coordinator.manager,
            self._player,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(
            self.entity_description.turn_off_fn,
            self.coordinator.manager,
            self._player,
        )


class YotoAlarmSwitchEntity(CoordinatorEntity[YotoDataUpdateCoordinator], SwitchEntity):
    """Representation of a Yoto alarm enable/disable switch."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "alarm"

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
        alarm_index: int,
    ) -> None:
        """Initialise the alarm switch entity."""
        super().__init__(coordinator)
        self._player_id = player_id
        self._alarm_index = alarm_index
        self._attr_unique_id = f"{player_id}-alarm-{alarm_index}"
        self._attr_translation_placeholders = {"number": str(alarm_index + 1)}

        player = coordinator.data[player_id]
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

    @property
    def _alarm(self) -> Alarm | None:
        """Return the alarm for this entity."""
        player = self._player
        if player.config and player.config.alarms:
            if self._alarm_index < len(player.config.alarms):
                return player.config.alarms[self._alarm_index]
        return None

    @property
    def is_on(self) -> bool | None:
        """Return True if the alarm is enabled."""
        alarm = self._alarm
        if alarm is None:
            return None
        return alarm.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the alarm."""
        await self._set_alarm_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the alarm."""
        await self._set_alarm_enabled(False)

    async def _set_alarm_enabled(self, enabled: bool) -> None:
        """Enable or disable the alarm via the API."""
        player = self._player
        if player.config and player.config.alarms:
            config = YotoPlayerConfig()
            config.alarms = [
                Alarm(
                    days_enabled=a.days_enabled,
                    enabled=a.enabled,
                    time=a.time,
                    volume=a.volume,
                    sound_id=a.sound_id,
                )
                for a in player.config.alarms
            ]
            config.alarms[self._alarm_index].enabled = enabled
            await self.hass.async_add_executor_job(
                self.coordinator.manager.set_player_config,
                self._player_id,
                config,
            )
