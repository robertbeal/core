"""Tests for the Yoto select platform."""

import json
from unittest.mock import MagicMock, patch

from yoto_api import YotoPlayer, YotoPlayerConfig

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
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


async def test_battery_saver_displays_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test battery saver select shows the correct human-readable option."""
    player = _make_player()
    player.config.display_dim_timeout = "60"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_yoto_battery_saver")
    assert state is not None
    assert state.state == "60"


async def test_battery_saver_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test battery saver shows off when value is 0."""
    player = _make_player()
    player.config.display_dim_timeout = "0"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_yoto_battery_saver")
    assert state is not None
    assert state.state == "0"


async def test_battery_saver_unknown_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test battery saver is unknown when not set."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("select.my_yoto_battery_saver")
    assert state is not None
    assert state.state == "unknown"


async def test_battery_saver_has_correct_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test battery saver exposes the expected options."""
    player = _make_player()
    player.config.display_dim_timeout = "60"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_yoto_battery_saver")
    assert state is not None
    assert state.attributes["options"] == ["0", "15", "30", "60", "180", "300"]


async def test_set_battery_saver(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setting battery saver sends correct API payload."""
    player = _make_player()
    player.config.display_dim_timeout = "60"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_yoto_manager.api.BASE_URL = "https://api.yotoplay.com"
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.components.yoto.coordinator.requests.put") as mock_put:
        mock_put.return_value.json.return_value = {}
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.my_yoto_battery_saver", ATTR_OPTION: "300"},
            blocking=True,
        )

    mock_put.assert_called_once()
    call_args = mock_put.call_args
    assert call_args[0][0] == f"https://api.yotoplay.com/device-v2/{PLAYER_ID}/config"
    body = json.loads(call_args[1]["data"])
    assert body == {"deviceId": PLAYER_ID, "config": {"displayDimTimeout": "300"}}


async def test_auto_power_off_displays_current_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test auto power off select shows the correct option."""
    player = _make_player()
    player.config.shutdown_timeout = "3600"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_yoto_auto_power_off")
    assert state is not None
    assert state.state == "3600"


async def test_auto_power_off_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test auto power off shows off when value is 0."""
    player = _make_player()
    player.config.shutdown_timeout = "0"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_yoto_auto_power_off")
    assert state is not None
    assert state.state == "0"


async def test_auto_power_off_unknown_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test auto power off is unknown when not set."""
    await _setup_player(hass, mock_config_entry, mock_yoto_manager)

    state = hass.states.get("select.my_yoto_auto_power_off")
    assert state is not None
    assert state.state == "unknown"


async def test_auto_power_off_has_correct_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test auto power off exposes the expected options."""
    player = _make_player()
    player.config.shutdown_timeout = "3600"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.my_yoto_auto_power_off")
    assert state is not None
    assert state.attributes["options"] == ["0", "900", "1800", "3600", "7200", "10800"]


async def test_set_auto_power_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test setting auto power off sends correct API payload."""
    player = _make_player()
    player.config.shutdown_timeout = "3600"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_yoto_manager.api.BASE_URL = "https://api.yotoplay.com"
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.components.yoto.coordinator.requests.put") as mock_put:
        mock_put.return_value.json.return_value = {}
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: "select.my_yoto_auto_power_off", ATTR_OPTION: "7200"},
            blocking=True,
        )

    mock_put.assert_called_once()
    call_args = mock_put.call_args
    assert call_args[0][0] == f"https://api.yotoplay.com/device-v2/{PLAYER_ID}/config"
    body = json.loads(call_args[1]["data"])
    assert body == {"deviceId": PLAYER_ID, "config": {"shutdownTimeout": "7200"}}


async def test_select_entities_are_config_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test select entities are in the config category."""
    player = _make_player()
    player.config.display_dim_timeout = "60"
    player.config.shutdown_timeout = "3600"
    mock_yoto_manager.players = {PLAYER_ID: player}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    entry = ent_reg.async_get("select.my_yoto_battery_saver")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG

    entry = ent_reg.async_get("select.my_yoto_auto_power_off")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG
