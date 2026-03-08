"""Tests for the Yoto switch platform."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    EntityCategory,
)
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
            day_display_brightness="auto",
            night_display_brightness="60",
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


async def test_day_auto_brightness_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Day auto brightness should be on when display brightness is 'auto'."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("switch.my_yoto_day_auto_brightness")
    assert state is not None
    assert state.state == "on"


async def test_night_auto_brightness_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Night auto brightness should be off when display brightness is a number."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("switch.my_yoto_night_auto_brightness")
    assert state is not None
    assert state.state == "off"


async def test_turn_on_sets_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Turning on should set display brightness to 'auto'."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_yoto_night_auto_brightness"},
        blocking=True,
    )

    mock_yoto_manager.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.set_player_config.call_args
    assert call_args[0][0] == PLAYER_ID
    config = call_args[0][1]
    assert config.night_display_brightness == "auto"


async def test_turn_off_sets_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Turning off should set display brightness to '0'."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_yoto_day_auto_brightness"},
        blocking=True,
    )

    mock_yoto_manager.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.set_player_config.call_args
    assert call_args[0][0] == PLAYER_ID
    config = call_args[0][1]
    assert config.day_display_brightness == "0"


async def test_switch_entities_are_config_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Switch entities should be in the config entity category."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("switch.my_yoto_day_auto_brightness")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG
