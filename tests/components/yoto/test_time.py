"""Tests for the Yoto time platform."""

import datetime
from unittest.mock import MagicMock

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

PLAYER_ID = "player-1"


def _make_player(**overrides: object) -> YotoPlayer:
    """Create a YotoPlayer with sensible defaults including config."""
    defaults = {
        "id": PLAYER_ID,
        "name": "My Yoto",
        "device_type": "v3",
        "online": True,
        "firmware_version": "1.2.3",
        "config": YotoPlayerConfig(
            day_mode_time=datetime.time(7, 0),
            night_mode_time=datetime.time(19, 30),
        ),
    }
    return YotoPlayer(**{**defaults, **overrides})


async def _setup_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
    **player_overrides: object,
) -> None:
    """Set up hass with a single player entity."""
    mock_yoto_manager.players = {PLAYER_ID: _make_player(**player_overrides)}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_day_mode_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the day mode time."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("time.my_yoto_day_mode_time")
    assert state is not None
    assert state.state == "07:00:00"


async def test_night_mode_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the night mode time."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("time.my_yoto_night_mode_time")
    assert state is not None
    assert state.state == "19:30:00"


async def test_time_unknown_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test time unknown when config value is None."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(day_mode_time=None, night_mode_time=None),
    )

    state = hass.states.get("time.my_yoto_day_mode_time")
    assert state is not None
    assert state.state == "unknown"


async def test_set_day_mode_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setting day mode time."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "time.my_yoto_day_mode_time", "time": "06:30:00"},
        blocking=True,
    )

    mock_yoto_manager.api.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.api.set_player_config.call_args
    assert call_args.kwargs["player_id"] == PLAYER_ID
    config = call_args.kwargs["config"]
    assert config.day_mode_time == datetime.time(6, 30)


async def test_time_entities_are_config_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test time entities have config entity category."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("time.my_yoto_day_mode_time")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG
