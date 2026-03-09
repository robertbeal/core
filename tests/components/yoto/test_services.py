"""Tests for Yoto service actions."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.yoto.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

SERVICE_UPDATE = "update"
ATTR_CONFIG_ENTRY = "config_entry"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration and load platforms."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_update_service_triggers_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test update service triggers a coordinator refresh."""
    await _setup(hass, mock_config_entry)

    mock_yoto_manager.update_players_status.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE,
        {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id},
        blocking=True,
    )

    mock_yoto_manager.update_players_status.assert_called_once()


async def test_update_service_invalid_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yoto_manager: MagicMock,
) -> None:
    """Test update service with invalid entry raises an error."""
    await _setup(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE,
            {ATTR_CONFIG_ENTRY: "invalid-entry-id"},
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"
