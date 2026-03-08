"""Media player platform for the Yoto integration."""

from __future__ import annotations

from functools import partial
from typing import Any

from yoto_api import YotoPlayer
from yoto_api.Card import Card

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
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

    known_players: set[str] = set()

    @callback
    def _async_add_new_players() -> None:
        """Add media player entities for any newly discovered players."""
        current_players = set(coordinator.data)
        new_players = current_players - known_players
        if new_players:
            known_players.update(new_players)
            async_add_entities(
                YotoMediaPlayerEntity(coordinator, player_id)
                for player_id in new_players
            )

    _async_add_new_players()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_players))


class YotoMediaPlayerEntity(
    CoordinatorEntity[YotoDataUpdateCoordinator], MediaPlayerEntity
):
    """Representation of a Yoto player as a media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_volume_step = 1 / YOTO_VOLUME_MAX
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.BROWSE_MEDIA
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
        """Return the title of the current media.

        Combines chapter and track titles when they differ, or shows just
        the chapter title when they match or the track title is absent.
        """
        player = self._player
        chapter = player.chapter_title
        track = player.track_title

        if chapter and track and chapter != track:
            return f"{chapter} - {track}"
        return chapter or track

    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current track in seconds."""
        return self._player.track_length

    @property
    def media_position(self) -> int | None:
        """Return the current playback position in seconds."""
        return self._player.track_position

    @property
    def _active_card(self) -> Card | None:
        """Return the library card for the currently playing content."""
        card_id = self._player.card_id
        if card_id is None:
            return None
        return self.coordinator.manager.library.get(card_id)

    @property
    def media_image_url(self) -> str | None:
        """Return the cover image URL of the current card."""
        card = self._active_card
        if card is None:
            return None
        return card.cover_image_large

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Return True since Yoto image URLs are publicly accessible."""
        return True

    @property
    def media_artist(self) -> str | None:
        """Return the author of the current card."""
        card = self._active_card
        if card is None:
            return None
        return card.author

    @property
    def media_album_name(self) -> str | None:
        """Return the title of the current card as the album name."""
        card = self._active_card
        if card is None:
            return None
        return card.title

    @property
    def media_content_id(self) -> str | None:
        """Return the composite content ID of the current media."""
        player = self._player
        if player.card_id and player.chapter_key and player.track_key:
            return f"{player.card_id}+{player.chapter_key}+{player.track_key}"
        return None

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Return the content type of the current media."""
        if self.media_content_id:
            return MediaType.MUSIC
        return None

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
        """Play a card on the player.

        Accepts media IDs in the format: cardid[+chapterKey[+trackKey[+seconds]]].
        """
        parts = media_id.split("+")
        card_id = parts[0]
        play_kwargs: dict[str, Any] = {}
        if len(parts) >= 2:
            play_kwargs["chapterKey"] = parts[1]
        if len(parts) >= 3:
            play_kwargs["trackKey"] = parts[2]
        if len(parts) >= 4:
            play_kwargs["secondsIn"] = int(parts[3])

        await self.hass.async_add_executor_job(
            partial(
                self.coordinator.manager.play_card,
                self._player_id,
                card_id,
                **play_kwargs,
            )
        )

    async def async_media_seek(self, position: float) -> None:
        """Seek to a position in the current track."""
        player = self._player
        await self.hass.async_add_executor_job(
            partial(
                self.coordinator.manager.play_card,
                self._player_id,
                player.card_id,
                chapterKey=player.chapter_key,
                trackKey=player.track_key,
                secondsIn=int(position),
            )
        )

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        player = self._player
        chapter_key = str(int(player.chapter_key) + 1) if player.chapter_key else None
        track_key = str(int(player.track_key) + 1) if player.track_key else None
        await self.hass.async_add_executor_job(
            partial(
                self.coordinator.manager.play_card,
                self._player_id,
                player.card_id,
                chapterKey=chapter_key,
                trackKey=track_key,
            )
        )

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        player = self._player
        chapter_key = str(int(player.chapter_key) - 1) if player.chapter_key else None
        track_key = str(int(player.track_key) - 1) if player.track_key else None
        await self.hass.async_add_executor_job(
            partial(
                self.coordinator.manager.play_card,
                self._player_id,
                player.card_id,
                chapterKey=chapter_key,
                trackKey=track_key,
            )
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse the Yoto card library."""
        library = self.coordinator.manager.library

        if media_content_id is not None and media_content_id != "library":
            await self.hass.async_add_executor_job(
                self.coordinator.manager.update_card_detail, media_content_id
            )
            return self._browse_card_chapters(media_content_id, library)

        return BrowseMedia(
            title="Yoto Library",
            media_class=MediaClass.DIRECTORY,
            media_content_id="library",
            media_content_type=MediaType.MUSIC,
            can_play=False,
            can_expand=True,
            children=[
                BrowseMedia(
                    title=card.title,
                    media_class=MediaClass.MUSIC,
                    media_content_id=card.id,
                    media_content_type=MediaType.MUSIC,
                    can_play=True,
                    can_expand=True,
                    thumbnail=card.cover_image_large,
                )
                for card in library.values()
            ],
            children_media_class=MediaClass.MUSIC,
        )

    def _browse_card_chapters(
        self, card_id: str, library: dict[str, Card]
    ) -> BrowseMedia:
        """Build a browse response for a card's chapters."""
        card = library[card_id]
        children: list[BrowseMedia] = []

        if card.chapters:
            children = [
                BrowseMedia(
                    title=chapter.title,
                    media_class=MediaClass.MUSIC,
                    media_content_id=f"{card_id}+{chapter.key}",
                    media_content_type=MediaType.MUSIC,
                    can_play=True,
                    can_expand=False,
                    thumbnail=chapter.icon,
                )
                for chapter in card.chapters.values()
            ]

        return BrowseMedia(
            title=card.title,
            media_class=MediaClass.MUSIC,
            media_content_id=card_id,
            media_content_type=MediaType.MUSIC,
            can_play=True,
            can_expand=False,
            children=children,
            children_media_class=MediaClass.MUSIC,
        )
