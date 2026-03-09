"""Tests for the Yoto media_player platform."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer
from yoto_api.Card import Card, Chapter, Track

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

PLAYER_ID = "player-1"
ENTITY_ID = "media_player.my_yoto"


def _make_player(**overrides: object) -> YotoPlayer:
    """Create a YotoPlayer with sensible defaults."""
    defaults = {
        "id": PLAYER_ID,
        "name": "My Yoto",
        "device_type": "v3",
        "online": True,
        "firmware_version": "1.2.3",
    }
    return YotoPlayer(**{**defaults, **overrides})


async def test_media_player_idle_when_online(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Player should be idle when online but not playing."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player()}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.IDLE


async def test_media_player_playing_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Player should reflect playing state."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player(playback_status="playing")}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING


async def test_media_player_paused_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Player should reflect paused state."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player(playback_status="paused")}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.PAUSED


async def test_media_player_off_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Player should be off when offline."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player(online=False)}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.OFF


async def test_media_player_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Volume should be normalised from 0-16 to 0.0-1.0."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player(volume=8)}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["volume_level"] == 0.5


async def test_media_player_track_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Media title and duration should be exposed."""
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(
            playback_status="playing",
            track_title="The Gruffalo",
            track_length=120,
            track_position=30,
        )
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_title"] == "The Gruffalo"
    assert state.attributes["media_duration"] == 120
    assert state.attributes["media_position"] == 30


async def _setup_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    **player_overrides: object,
) -> None:
    """Set up hass with a single player entity."""
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(playback_status="playing", **player_overrides)
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_media_pause(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Pause service should call pause_player on the manager."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_pause",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_yoto_manager.pause_player.assert_called_once_with(PLAYER_ID)


async def test_media_play(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Play service should call resume_player on the manager."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_play",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_yoto_manager.resume_player.assert_called_once_with(PLAYER_ID)


async def test_media_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Stop service should call stop_player on the manager."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_stop",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_yoto_manager.stop_player.assert_called_once_with(PLAYER_ID)


async def test_set_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Set volume should call set_volume with value mapped to 0-100."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "volume_set",
        {ATTR_ENTITY_ID: ENTITY_ID, "volume_level": 0.5},
        blocking=True,
    )

    mock_yoto_manager.set_volume.assert_called_once_with(PLAYER_ID, 50)


async def test_play_media(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Play media service should call play_card with the card ID."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "card",
            "media_content_id": "7JtVV",
        },
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(PLAYER_ID, "7JtVV")


async def test_device_class_and_volume_step(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Player should be classified as a speaker with 1/16 volume step."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["device_class"] == MediaPlayerDeviceClass.SPEAKER


CARD_ID = "7JtVV"


async def test_library_metadata_when_card_in_library(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Library metadata should be exposed when the active card is in the library."""
    mock_yoto_manager.library = {
        CARD_ID: Card(
            id=CARD_ID,
            title="The Gruffalo",
            author="Julia Donaldson",
            cover_image_large="https://example.com/gruffalo.jpg",
        )
    }
    await _setup_player(hass, mock_config_entry, mock_yoto_manager, card_id=CARD_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_artist"] == "Julia Donaldson"
    assert state.attributes["media_album_name"] == "The Gruffalo"
    assert state.attributes["entity_picture"] == "https://example.com/gruffalo.jpg"


async def test_library_metadata_missing_when_no_card(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Library metadata should be absent when no card is playing."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get(ENTITY_ID)
    assert "media_artist" not in state.attributes
    assert "media_album_name" not in state.attributes


async def test_media_title_combines_chapter_and_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Media title should combine chapter and track when they differ."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        chapter_title="Chapter 1",
        track_title="The Dark Forest",
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_title"] == "Chapter 1 - The Dark Forest"


async def test_media_title_shows_chapter_only_when_same_as_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Media title should show chapter only when it matches the track title."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        chapter_title="The Gruffalo",
        track_title="The Gruffalo",
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_title"] == "The Gruffalo"


async def test_media_title_shows_chapter_when_no_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Media title should fall back to chapter title when there is no track title."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        chapter_title="Chapter 1",
        track_title=None,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_title"] == "Chapter 1"


async def test_media_content_id_composite(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Content ID should combine card, chapter, and track keys."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        card_id="7JtVV",
        chapter_key="C02",
        track_key="T01",
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_content_id"] == "7JtVV+C02+T01"


async def test_media_content_id_none_when_incomplete(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Content ID should be absent when card/chapter/track keys are missing."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        card_id="7JtVV",
        chapter_key=None,
        track_key=None,
    )

    state = hass.states.get(ENTITY_ID)
    assert "media_content_id" not in state.attributes


async def test_play_media_with_chapter_and_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Play media should parse card+chapter+track format."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "7JtVV+C02+T01",
        },
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        PLAYER_ID, "7JtVV", chapterKey="C02", trackKey="T01"
    )


async def test_play_media_with_chapter_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Play media should parse card+chapter format."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "7JtVV+C02",
        },
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        PLAYER_ID, "7JtVV", chapterKey="C02"
    )


async def test_play_media_with_seconds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Play media should parse card+chapter+track+seconds format."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "play_media",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "7JtVV+C02+T01+30",
        },
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        PLAYER_ID, "7JtVV", chapterKey="C02", trackKey="T01", secondsIn=30
    )


async def test_seek(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Seek should replay the current card from the given position."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        card_id="7JtVV",
        chapter_key="C02",
        track_key="T01",
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_seek",
        {ATTR_ENTITY_ID: ENTITY_ID, "seek_position": 45.0},
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        PLAYER_ID, "7JtVV", chapterKey="C02", trackKey="T01", secondsIn=45
    )


async def test_next_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Next track should increment chapter and track keys."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        card_id="7JtVV",
        chapter_key="2",
        track_key="3",
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_next_track",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        PLAYER_ID, "7JtVV", chapterKey="3", trackKey="4"
    )


async def test_previous_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Previous track should decrement chapter and track keys."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        card_id="7JtVV",
        chapter_key="2",
        track_key="3",
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        "media_previous_track",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_yoto_manager.play_card.assert_called_once_with(
        PLAYER_ID, "7JtVV", chapterKey="1", trackKey="2"
    )


async def test_browse_media_root_shows_library(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing root should list all cards from the library."""
    mock_yoto_manager.library = {
        "card1": Card(
            id="card1",
            title="The Gruffalo",
            cover_image_large="https://example.com/gruffalo.jpg",
        ),
        "card2": Card(
            id="card2",
            title="Room on the Broom",
            cover_image_large="https://example.com/broom.jpg",
        ),
    }
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    result = response["result"]
    assert result["title"] == "Yoto Library"
    assert len(result["children"]) == 2
    assert result["children"][0]["title"] == "The Gruffalo"
    assert result["children"][0]["can_play"] is True
    assert result["children"][0]["can_expand"] is True
    assert result["children"][0]["thumbnail"] == "https://example.com/gruffalo.jpg"
    assert result["children"][1]["title"] == "Room on the Broom"


async def test_browse_media_card_shows_chapters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a card should list its chapters."""
    mock_yoto_manager.library = {
        "card1": Card(
            id="card1",
            title="The Gruffalo",
            chapters={
                "1": Chapter(
                    key="1", title="Chapter 1", icon="https://example.com/ch1.png"
                ),
                "2": Chapter(
                    key="2", title="Chapter 2", icon="https://example.com/ch2.png"
                ),
            },
        ),
    }
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "card1",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    result = response["result"]
    assert result["title"] == "The Gruffalo"
    assert len(result["children"]) == 2
    assert result["children"][0]["title"] == "Chapter 1"
    assert result["children"][0]["can_play"] is True
    assert result["children"][0]["can_expand"] is False
    assert result["children"][0]["media_content_id"] == "card1+1"
    assert result["children"][0]["thumbnail"] == "https://example.com/ch1.png"


async def test_browse_media_fetches_card_details(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a card should fetch its chapter details if not already loaded."""
    mock_yoto_manager.library = {
        "card1": Card(id="card1", title="The Gruffalo"),
    }
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "card1",
        }
    )
    await client.receive_json()

    mock_yoto_manager.update_card_detail.assert_called_once_with("card1")


async def test_browse_media_chapters_expandable_when_tracks_exist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Chapters should be expandable when they have tracks."""
    mock_yoto_manager.library = {
        "card1": Card(
            id="card1",
            title="The Gruffalo",
            chapters={
                "1": Chapter(
                    key="1",
                    title="Chapter 1",
                    tracks={
                        "01": Track(key="01", title="Track 1"),
                    },
                ),
            },
        ),
    }
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "card1",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"]["children"][0]["can_expand"] is True


async def test_browse_media_chapter_shows_tracks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Browsing a chapter should list its tracks."""
    mock_yoto_manager.library = {
        "card1": Card(
            id="card1",
            title="The Gruffalo",
            chapters={
                "1": Chapter(
                    key="1",
                    title="Chapter 1",
                    icon="https://example.com/ch1.png",
                    tracks={
                        "01": Track(
                            key="01",
                            title="Track 1",
                            icon="https://example.com/t1.png",
                        ),
                        "02": Track(
                            key="02",
                            title="Track 2",
                            icon="https://example.com/t2.png",
                        ),
                    },
                ),
            },
        ),
    }
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "music",
            "media_content_id": "card1+1",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    result = response["result"]
    assert result["title"] == "Chapter 1"
    assert len(result["children"]) == 2
    assert result["children"][0]["title"] == "Track 1"
    assert result["children"][0]["can_play"] is True
    assert result["children"][0]["can_expand"] is False
    assert result["children"][0]["media_content_id"] == "card1+1+01"
    assert result["children"][0]["thumbnail"] == "https://example.com/t1.png"


async def test_extra_state_attributes_chapter_and_track_icons(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Extra state attributes should include chapter and track icons from the library."""
    mock_yoto_manager.library = {
        CARD_ID: Card(
            id=CARD_ID,
            title="The Gruffalo",
            chapters={
                "C01": Chapter(
                    key="C01",
                    title="Chapter 1",
                    icon="https://example.com/ch1.png",
                    tracks={
                        "T01": Track(
                            key="T01",
                            title="Track 1",
                            icon="https://example.com/t1.png",
                        ),
                    },
                ),
            },
        )
    }
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        card_id=CARD_ID,
        chapter_key="C01",
        track_key="T01",
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["media_chapter_icon"] == "https://example.com/ch1.png"
    assert state.attributes["media_track_icon"] == "https://example.com/t1.png"


async def test_extra_state_attributes_empty_when_no_library_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Extra state attributes should not include icons when library data is absent."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get(ENTITY_ID)
    assert "media_chapter_icon" not in state.attributes
    assert "media_track_icon" not in state.attributes
