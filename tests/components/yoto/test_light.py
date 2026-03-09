"""Tests for the Yoto light platform."""

from unittest.mock import MagicMock

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

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
            day_ambient_colour="#ff0000",
            night_ambient_colour="#0000ff",
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


async def test_light_on_with_rgb(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test light on with RGB colour."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("light.my_yoto_day_ambient_colour")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert ColorMode.RGB in state.attributes[ATTR_SUPPORTED_COLOR_MODES]


async def test_light_off_when_colour_is_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test light off when colour is #0."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_ambient_colour="#0",
            night_ambient_colour="#0000ff",
        ),
    )

    state = hass.states.get("light.my_yoto_day_ambient_colour")
    assert state is not None
    assert state.state == STATE_OFF


async def test_night_ambient_colour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test the night ambient colour."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("light.my_yoto_night_ambient_colour")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (0, 0, 255)


async def test_turn_on_with_rgb(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning on with RGB colour."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.my_yoto_day_ambient_colour",
            ATTR_RGB_COLOR: (0, 255, 128),
        },
        blocking=True,
    )

    mock_yoto_manager.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.set_player_config.call_args
    assert call_args[0][0] == PLAYER_ID
    config = call_args[0][1]
    assert config.day_ambient_colour == "#00ff80"


async def test_turn_on_without_rgb_uses_white(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning on without RGB defaults to white."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_ambient_colour="#0",
            night_ambient_colour="#0000ff",
        ),
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.my_yoto_day_ambient_colour"},
        blocking=True,
    )

    call_args = mock_yoto_manager.set_player_config.call_args
    config = call_args[0][1]
    assert config.day_ambient_colour == "#ffffff"


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning off."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.my_yoto_day_ambient_colour"},
        blocking=True,
    )

    call_args = mock_yoto_manager.set_player_config.call_args
    config = call_args[0][1]
    assert config.day_ambient_colour == "#0"
