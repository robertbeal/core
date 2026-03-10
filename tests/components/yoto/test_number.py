"""Tests for the Yoto number platform."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
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
            day_max_volume_limit=10,
            night_max_volume_limit=6,
            day_display_brightness="80",
            night_display_brightness="auto",
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


async def test_day_max_volume_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the day max volume limit number."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("number.my_yoto_day_max_volume_limit")
    assert state is not None
    assert state.state == "10.0"


async def test_night_max_volume_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the night max volume limit number."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("number.my_yoto_night_max_volume_limit")
    assert state is not None
    assert state.state == "6.0"


async def test_day_display_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the day display brightness number."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("number.my_yoto_day_display_brightness")
    assert state is not None
    assert state.state == "80.0"


async def test_night_display_brightness_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test night display brightness reports 100 when set to auto."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("number.my_yoto_night_display_brightness")
    assert state is not None
    assert state.state == "100.0"


async def test_set_max_volume_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setting the max volume limit."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.my_yoto_day_max_volume_limit", ATTR_VALUE: 12},
        blocking=True,
    )

    mock_yoto_manager.api.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.api.set_player_config.call_args
    assert call_args.kwargs["player_id"] == PLAYER_ID
    config = call_args.kwargs["config"]
    assert config.day_max_volume_limit == 12


async def test_set_display_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setting the display brightness."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.my_yoto_day_display_brightness", ATTR_VALUE: 50},
        blocking=True,
    )

    call_args = mock_yoto_manager.api.set_player_config.call_args
    config = call_args.kwargs["config"]
    assert config.day_display_brightness == 50


async def test_number_entities_are_config_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test number entities are in the config category."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("number.my_yoto_day_max_volume_limit")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG


async def test_sleep_timer_seconds_remaining(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the sleep timer reports remaining seconds."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        sleep_timer_seconds_remaining=120,
    )

    state = hass.states.get("number.my_yoto_sleep_timer")
    assert state is not None
    assert state.state == "120.0"


async def test_set_sleep_timer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setting the sleep timer."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.my_yoto_sleep_timer", ATTR_VALUE: 300},
        blocking=True,
    )

    mock_yoto_manager.set_sleep.assert_called_once_with(PLAYER_ID, 300)
