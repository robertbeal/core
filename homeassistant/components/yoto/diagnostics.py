"""Diagnostics support for the Yoto integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import YotoConfigEntry

TO_REDACT = {"id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: YotoConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data.coordinator

    players_data = {}
    for player_id, player in coordinator.data.items():
        players_data[player_id] = player.__dict__

    return async_redact_data({"players": players_data}, TO_REDACT)
