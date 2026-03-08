"""Media player platform for the Yoto integration."""

from __future__ import annotations

from typing import Any

from yoto_api import YotoPlayer

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import YotoConfigEntry
from .const import DOMAIN
from .coordinator import YotoDataUpdateCoordinator

PARALLEL_UPDATES = 1
YOTO_VOLUME_MAX = 16

PLAYBACK_STATE_MAP: dict[str | None, MediaPlayerState] = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yoto media player entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        YotoMediaPlayerEntity(coordinator, player_id) for player_id in coordinator.data
    )


class YotoMediaPlayerEntity(
    CoordinatorEntity[YotoDataUpdateCoordinator], MediaPlayerEntity
):
    """Representation of a Yoto player as a media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player_id: str,
    ) -> None:
        """Initialise the media player entity."""
        super().__init__(coordinator)
        self._player_id = player_id
        self._attr_unique_id = player_id

        player = self._player
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
    def state(self) -> MediaPlayerState:
        """Return the current state of the player."""
        player = self._player

        if not player.online:
            return MediaPlayerState.OFF

        return PLAYBACK_STATE_MAP.get(player.playback_status, MediaPlayerState.IDLE)

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 to 1.0)."""
        volume = self._player.volume
        if volume is None:
            return None
        return volume / YOTO_VOLUME_MAX

    @property
    def media_title(self) -> str | None:
        """Return the title of the current track."""
        return self._player.track_title

    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current track in seconds."""
        return self._player.track_length

    @property
    def media_position(self) -> int | None:
        """Return the current playback position in seconds."""
        return self._player.track_position

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self.hass.async_add_executor_job(
            self.coordinator.manager.pause_player, self._player_id
        )

    async def async_media_play(self) -> None:
        """Resume playback."""
        await self.hass.async_add_executor_job(
            self.coordinator.manager.resume_player, self._player_id
        )

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self.hass.async_add_executor_job(
            self.coordinator.manager.stop_player, self._player_id
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        yoto_volume = int(volume * 100)
        await self.hass.async_add_executor_job(
            self.coordinator.manager.set_volume, self._player_id, yoto_volume
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a card on the player."""
        await self.hass.async_add_executor_job(
            self.coordinator.manager.play_card, self._player_id, media_id
        )
