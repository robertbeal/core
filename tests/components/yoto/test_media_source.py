"""Tests for the Yoto media source."""

from unittest.mock import MagicMock

from homeassistant.components.media_source import (
    URI_SCHEME,
    PlayMedia,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.components.yoto.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MEDIA_SOURCE_DOMAIN = "media_source"


def _make_card(
    card_id: str = "card1",
    title: str = "My Card",
    author: str = "Author",
    cover_image_large: str = "https://example.com/cover.jpg",
) -> MagicMock:
    """Create a mock Card object."""
    card = MagicMock()
    card.id = card_id
    card.title = title
    card.author = author
    card.cover_image_large = cover_image_large
    card.chapters = {}
    return card


def _make_chapter(key: str = "1", title: str = "Chapter 1") -> MagicMock:
    """Create a mock Chapter object."""
    chapter = MagicMock()
    chapter.key = key
    chapter.title = title
    chapter.icon = f"https://example.com/icon-{key}.png"
    chapter.tracks = {}
    return chapter


def _make_track(
    key: str = "01",
    title: str = "Track 1",
    fmt: str = "aac",
    track_url: str = "https://secure-media.yotoplay.com/signed-url?token=abc123",
) -> MagicMock:
    """Create a mock Track object."""
    track = MagicMock()
    track.key = key
    track.title = title
    track.format = fmt
    track.trackUrl = track_url
    track.icon = f"https://example.com/track-icon-{key}.png"
    return track


async def _setup_media_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Set up the Yoto integration and media source component."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, MEDIA_SOURCE_DOMAIN, {})
    await hass.async_block_till_done()


async def test_browse_media_root_shows_library(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test browsing root returns library cards."""
    card = _make_card()
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")

    assert result.title == "Yoto Library"
    assert len(result.children) == 1
    assert result.children[0].title == "My Card"


async def test_browse_media_card_shows_chapters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test browsing a card returns its chapters."""
    card = _make_card()
    chapter = _make_chapter(key="1", title="Introduction")
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/card1")

    assert result.title == "My Card"
    assert len(result.children) == 1
    assert result.children[0].title == "Introduction"


async def test_browse_media_fetches_card_details_when_chapters_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test browsing a card with no chapters triggers a detail fetch."""
    card = _make_card()
    card.chapters = {}
    mock_yoto_manager.library = {"card1": card}

    def populate_chapters(card_id: str) -> None:
        chapter = _make_chapter(key="1", title="Fetched Chapter")
        mock_yoto_manager.library["card1"].chapters = {"1": chapter}

    mock_yoto_manager.update_card_detail.side_effect = populate_chapters

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/card1")

    mock_yoto_manager.update_card_detail.assert_called_once_with("card1")
    assert len(result.children) == 1
    assert result.children[0].title == "Fetched Chapter"


async def test_resolve_media_returns_track_url_and_mime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test resolving a media item returns the track URL and MIME type."""
    card = _make_card()
    chapter = _make_chapter(key="1")
    track = _make_track(key="01", fmt="aac")
    chapter.tracks = {"01": track}
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/card1+1+01", None)

    assert isinstance(result, PlayMedia)
    assert result.url == "https://secure-media.yotoplay.com/signed-url?token=abc123"
    assert result.mime_type == "audio/aac"


async def test_resolve_media_always_refetches_card_details(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test that resolve always re-fetches card details to get fresh signed URLs.

    Yoto streams are signed S3/CloudFront URLs that expire after ~1 hour,
    so we must always request fresh URLs rather than using cached ones.
    """
    card = _make_card()
    chapter = _make_chapter(key="1")
    track = _make_track(
        key="01", fmt="mp3", track_url="https://secure-media.yotoplay.com/old-url"
    )
    chapter.tracks = {"01": track}
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    fresh_url = "https://secure-media.yotoplay.com/fresh-signed-url?token=new123"

    def update_with_fresh_url(card_id: str) -> None:
        card.chapters["1"].tracks["01"].trackUrl = fresh_url

    mock_yoto_manager.update_card_detail.side_effect = update_with_fresh_url

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/card1+1+01", None)

    mock_yoto_manager.update_card_detail.assert_called_once_with("card1")
    assert result.url == fresh_url


async def test_resolve_media_mp3_mime_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test that mp3 format resolves to audio/mpeg MIME type."""
    card = _make_card()
    chapter = _make_chapter(key="1")
    track = _make_track(key="01", fmt="mp3")
    chapter.tracks = {"01": track}
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/card1+1+01", None)

    assert result.mime_type == "audio/mpeg"


async def test_resolve_media_opus_mime_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test that opus format resolves to audio/opus MIME type."""
    card = _make_card()
    chapter = _make_chapter(key="1")
    track = _make_track(key="01", fmt="opus")
    chapter.tracks = {"01": track}
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/card1+1+01", None)

    assert result.mime_type == "audio/opus"


async def test_resolve_media_defaults_chapter_and_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test resolving with only card ID defaults to the first chapter and track."""
    card = _make_card()
    chapter = _make_chapter(key="1")
    track = _make_track(key="01")
    chapter.tracks = {"01": track}
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/card1", None)

    assert isinstance(result, PlayMedia)


async def test_resolve_media_with_chapter_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test resolving with card+chapter defaults to the first track."""
    card = _make_card()
    chapter = _make_chapter(key="1")
    track = _make_track(key="01")
    chapter.tracks = {"01": track}
    card.chapters = {"1": chapter}
    mock_yoto_manager.library = {"card1": card}

    await _setup_media_source(hass, mock_config_entry, mock_yoto_manager)

    result = await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/card1+1", None)

    assert isinstance(result, PlayMedia)
