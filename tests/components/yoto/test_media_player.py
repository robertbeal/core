"""Tests for the Yoto media_player platform."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

PLAYER_ID = "player-1"
ENTITY_ID = f"media_player.my_yoto"


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
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(playback_status="playing")
    }

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
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(playback_status="paused")
    }

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
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(online=False)
    }

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
    mock_yoto_manager.players = {
        PLAYER_ID: _make_player(volume=8)
    }

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
