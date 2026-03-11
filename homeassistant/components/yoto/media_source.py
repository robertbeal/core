from __future__ import annotations

import logging

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIME_TYPES: dict[str, str] = {
    "aac": "audio/aac",
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
}


async def async_get_media_source(hass: HomeAssistant) -> YotoMediaSource:
    """Set up the media source."""
    return YotoMediaSource(hass)


class YotoMediaSource(MediaSource):
    """Yoto media source."""

    name = "Yoto"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    @property
    def _coordinator(self):
        """Return the coordinator."""
        entry = self.hass.config_entries.async_loaded_entries(DOMAIN)[0]
        return entry.runtime_data.coordinator

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item."""
        card_id, chapter_key, track_key = _parse_identifier(item.identifier)
        coordinator = self._coordinator
        manager = coordinator.manager

        await self.hass.async_add_executor_job(manager.update_card_detail, card_id)

        card = manager.library.get(card_id)
        if card is None:
            raise Unresolvable(f"Card {card_id} not found in library")

        if chapter_key is None:
            chapter_key = next(iter(card.chapters), None)
        if chapter_key is None or chapter_key not in card.chapters:
            raise Unresolvable(f"No chapters found for card {card_id}")

        chapter = card.chapters[chapter_key]

        if track_key is None:
            track_key = next(iter(chapter.tracks), None)
        if track_key is None or track_key not in chapter.tracks:
            raise Unresolvable(f"No tracks found for chapter {chapter_key}")

        track = chapter.tracks[track_key]
        mime_type = MIME_TYPES.get(track.format, "audio/aac")

        return PlayMedia(track.trackUrl, mime_type)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse the card library."""
        coordinator = self._coordinator
        manager = coordinator.manager

        if item.identifier:
            parts = item.identifier.split("+")
            card_id = parts[0]
            card = manager.library.get(card_id)
            if card is None:
                raise Unresolvable(f"Card {card_id} not found in library")

            if not card.chapters:
                await self.hass.async_add_executor_job(
                    manager.update_card_detail, card_id
                )

            if len(parts) >= 2:
                return self._browse_chapter_tracks(card, parts[1])

            return self._browse_card_chapters(card)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title="Yoto Library",
            can_play=False,
            can_expand=True,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=card.id,
                    media_class=MediaClass.MUSIC,
                    media_content_type=MediaType.MUSIC,
                    title=card.title,
                    can_play=True,
                    can_expand=True,
                    thumbnail=card.cover_image_large,
                )
                for card in manager.library.values()
            ],
            children_media_class=MediaClass.MUSIC,
        )

    def _browse_card_chapters(self, card) -> BrowseMediaSource:
        """Browse a card's chapters."""
        children: list[BrowseMediaSource] = []
        if card.chapters:
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{card.id}+{chapter.key}",
                    media_class=MediaClass.MUSIC,
                    media_content_type=MediaType.MUSIC,
                    title=chapter.title,
                    can_play=True,
                    can_expand=bool(chapter.tracks),
                    thumbnail=chapter.icon,
                )
                for chapter in card.chapters.values()
            ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=card.id,
            media_class=MediaClass.MUSIC,
            media_content_type=MediaType.MUSIC,
            title=card.title,
            can_play=True,
            can_expand=False,
            children=children,
            children_media_class=MediaClass.MUSIC,
        )

    def _browse_chapter_tracks(self, card, chapter_key: str) -> BrowseMediaSource:
        """Browse a chapter's tracks."""
        chapter = card.chapters.get(chapter_key)
        if chapter is None:
            raise Unresolvable(f"Chapter {chapter_key} not found in card {card.id}")

        children: list[BrowseMediaSource] = []
        if chapter.tracks:
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{card.id}+{chapter_key}+{track.key}",
                    media_class=MediaClass.MUSIC,
                    media_content_type=MediaType.MUSIC,
                    title=track.title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=track.icon,
                )
                for track in chapter.tracks.values()
            ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{card.id}+{chapter_key}",
            media_class=MediaClass.MUSIC,
            media_content_type=MediaType.MUSIC,
            title=chapter.title,
            can_play=True,
            can_expand=False,
            children=children,
            children_media_class=MediaClass.MUSIC,
        )


def _parse_identifier(identifier: str) -> tuple[str, str | None, str | None]:
    """Parse a media source identifier."""
    parts = identifier.split("+")
    card_id = parts[0]
    chapter_key = parts[1] if len(parts) >= 2 else None
    track_key = parts[2] if len(parts) >= 3 else None
    return card_id, chapter_key, track_key
