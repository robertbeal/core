"""Tests for the Yoto switch platform."""

import datetime
from unittest.mock import MagicMock

from yoto_api import YotoPlayer, YotoPlayerConfig
from yoto_api.YotoPlayer import Alarm

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
    """Test day auto brightness is on when display brightness is auto."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("switch.my_yoto_day_auto_brightness")
    assert state is not None
    assert state.state == "on"


async def test_night_auto_brightness_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test night auto brightness is off when display brightness is a number."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("switch.my_yoto_night_auto_brightness")
    assert state is not None
    assert state.state == "off"


async def test_turn_on_sets_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning on sets display brightness to auto."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_yoto_night_auto_brightness"},
        blocking=True,
    )

    mock_yoto_manager.api.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.api.set_player_config.call_args
    assert call_args.kwargs["player_id"] == PLAYER_ID
    config = call_args.kwargs["config"]
    assert config.night_display_brightness == "auto"


async def test_turn_off_auto_restores_previous_manual_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning off auto restores the previous manual brightness value.

    When the user had brightness at 60, enabling then disabling auto
    should restore 60 rather than setting to 0.
    """
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    # Night brightness starts at "60" (manual). Turn auto ON first.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_yoto_night_auto_brightness"},
        blocking=True,
    )

    # Now turn auto OFF — should restore "60"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_yoto_night_auto_brightness"},
        blocking=True,
    )

    call_args = mock_yoto_manager.api.set_player_config.call_args
    assert call_args.kwargs["player_id"] == PLAYER_ID
    config = call_args.kwargs["config"]
    assert config.night_display_brightness == "60"


async def test_turn_off_auto_defaults_to_50_when_no_previous_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning off auto defaults to 50 when there was no manual value.

    When the player config started as auto (no stored manual value),
    disabling auto should fall back to 50%.
    """
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_yoto_day_auto_brightness"},
        blocking=True,
    )

    call_args = mock_yoto_manager.api.set_player_config.call_args
    config = call_args.kwargs["config"]
    assert config.day_display_brightness == "50"


async def test_switch_entities_are_config_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test switch entities are in the config category."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("switch.my_yoto_day_auto_brightness")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG


async def test_end_of_track_sleep_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test end of track sleep is on when timer matches remaining track time."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        track_length=180,
        track_position=60,
        sleep_timer_seconds_remaining=120,
    )

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state is not None
    assert state.state == "on"


async def test_end_of_track_sleep_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test end of track sleep is off when timer does not match."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        track_length=180,
        track_position=60,
        sleep_timer_seconds_remaining=0,
    )

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state is not None
    assert state.state == "off"


async def test_end_of_track_sleep_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning on sets sleep timer to remaining track time."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        track_length=180,
        track_position=60,
        sleep_timer_seconds_remaining=0,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_yoto_end_of_track_sleep"},
        blocking=True,
    )

    mock_yoto_manager.set_sleep.assert_called_once_with(PLAYER_ID, 120)


async def test_end_of_track_sleep_turn_on_persists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning on optimistically updates entity state to on."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        track_length=180,
        track_position=60,
        sleep_timer_seconds_remaining=0,
    )

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_yoto_end_of_track_sleep"},
        blocking=True,
    )

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state.state == "on"


async def test_end_of_track_sleep_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning off sets sleep timer to zero."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        track_length=180,
        track_position=60,
        sleep_timer_seconds_remaining=120,
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_yoto_end_of_track_sleep"},
        blocking=True,
    )

    mock_yoto_manager.set_sleep.assert_called_once_with(PLAYER_ID, 0)


async def test_end_of_track_sleep_turn_off_persists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning off optimistically updates entity state to off."""
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        track_length=180,
        track_position=60,
        sleep_timer_seconds_remaining=120,
    )

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state.state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_yoto_end_of_track_sleep"},
        blocking=True,
    )

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state.state == "off"


async def test_alarm_enabled_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test alarm switch shows enabled state."""
    alarm = Alarm(
        enabled=True,
        time=datetime.time(7, 0),
        volume=8,
        sound_id="4OD25",
        days_enabled=127,
    )
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_display_brightness="auto",
            night_display_brightness="60",
            alarms=[alarm],
        ),
    )

    state = hass.states.get("switch.my_yoto_alarm_1")
    assert state is not None
    assert state.state == "on"


async def test_alarm_disabled_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test alarm switch shows disabled state."""
    alarm = Alarm(enabled=False, time=datetime.time(7, 0))
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_display_brightness="auto",
            night_display_brightness="60",
            alarms=[alarm],
        ),
    )

    state = hass.states.get("switch.my_yoto_alarm_1")
    assert state is not None
    assert state.state == "off"


async def test_multiple_alarm_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test multiple alarms create numbered switch entities."""
    alarms = [
        Alarm(enabled=True, time=datetime.time(7, 0)),
        Alarm(enabled=False, time=datetime.time(8, 30)),
    ]
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_display_brightness="auto",
            night_display_brightness="60",
            alarms=alarms,
        ),
    )

    state1 = hass.states.get("switch.my_yoto_alarm_1")
    assert state1 is not None
    assert state1.state == "on"

    state2 = hass.states.get("switch.my_yoto_alarm_2")
    assert state2 is not None
    assert state2.state == "off"


async def test_alarm_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning on an alarm switch enables the alarm."""
    alarm = Alarm(enabled=False, time=datetime.time(7, 0))
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_display_brightness="auto",
            night_display_brightness="60",
            alarms=[alarm],
        ),
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_yoto_alarm_1"},
        blocking=True,
    )

    mock_yoto_manager.api.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.api.set_player_config.call_args
    assert call_args.kwargs["player_id"] == PLAYER_ID
    config = call_args.kwargs["config"]
    assert config.alarms[0].enabled is True


async def test_alarm_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test turning off an alarm switch disables the alarm."""
    alarm = Alarm(enabled=True, time=datetime.time(7, 0))
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_display_brightness="auto",
            night_display_brightness="60",
            alarms=[alarm],
        ),
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_yoto_alarm_1"},
        blocking=True,
    )

    mock_yoto_manager.api.set_player_config.assert_called_once()
    call_args = mock_yoto_manager.api.set_player_config.call_args
    assert call_args.kwargs["player_id"] == PLAYER_ID
    config = call_args.kwargs["config"]
    assert config.alarms[0].enabled is False


async def test_no_alarm_switches_when_no_alarms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test no alarm switches are created when config has no alarms."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("switch.my_yoto_alarm_1")
    assert state is None


async def test_alarm_switch_is_config_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test alarm switches are in the config category."""
    alarm = Alarm(enabled=True, time=datetime.time(7, 0))
    await _setup_player(
        hass,
        mock_config_entry,
        mock_yoto_manager,
        config=YotoPlayerConfig(
            day_display_brightness="auto",
            night_display_brightness="60",
            alarms=[alarm],
        ),
    )

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("switch.my_yoto_alarm_1")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG


async def test_end_of_track_sleep_unavailable_when_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test end of track sleep is unavailable when no track is playing.

    When the player is idle, track_length and track_position are None.
    The switch cannot function without a playing track, so it should
    report as unavailable rather than silently ignoring toggle actions.
    """
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("switch.my_yoto_end_of_track_sleep")
    assert state is not None
    assert state.state == "unavailable"
