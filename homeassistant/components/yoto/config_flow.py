from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from yoto_api import YotoManager

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import callback

from .const import CLIENT_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YotoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Yoto config flow."""

    _manager: YotoManager
    _auth_data: dict[str, Any]
    _login_task: asyncio.Task[None] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> YotoOptionsFlowHandler:
        """Get the options flow."""
        return YotoOptionsFlowHandler()

    async def _async_wait_for_auth(self) -> None:
        """Wait for device code auth."""
        await self.hass.async_add_executor_job(self._manager.device_code_flow_complete)

    def _auth_succeeded(self) -> bool:
        """Check if the manager obtained a valid token."""
        return (
            hasattr(self._manager, "token")
            and self._manager.token is not None
            and self._manager.token.refresh_token is not None
        )

    def _start_login_task(self) -> asyncio.Task[None]:
        """Start the login background task."""
        self._login_task = self.hass.async_create_task(self._async_wait_for_auth())
        return self._login_task

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not self._login_task:
            self._manager = await self.hass.async_add_executor_job(
                YotoManager, CLIENT_ID
            )
            self._auth_data = await self.hass.async_add_executor_job(
                self._manager.device_code_flow_start
            )

        login_task = self._login_task or self._start_login_task()

        if login_task.done():
            if login_task.exception() and not self._auth_succeeded():
                return self.async_show_progress_done(next_step_id="user_error")
            return self.async_show_progress_done(next_step_id="user_finish")

        return self.async_show_progress(
            step_id="user",
            progress_action="wait_for_auth",
            description_placeholders={
                "url": self._auth_data["verification_uri_complete"],
                "code": self._auth_data["user_code"],
            },
            progress_task=login_task,
        )

    async def async_step_user_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle successful authentication."""
        refresh_token = self._manager.token.refresh_token

        await self.async_set_unique_id(refresh_token)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Yoto",
            data={CONF_TOKEN: refresh_token},
        )

    async def async_step_user_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication failure."""
        return self.async_abort(reason="invalid_auth")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        if not self._login_task:
            self._manager = await self.hass.async_add_executor_job(
                YotoManager, CLIENT_ID
            )
            self._auth_data = await self.hass.async_add_executor_job(
                self._manager.device_code_flow_start
            )

        login_task = self._login_task or self._start_login_task()

        if login_task.done():
            if login_task.exception() and not self._auth_succeeded():
                return self.async_show_progress_done(next_step_id="reauth_error")
            return self.async_show_progress_done(next_step_id="reauth_finish")

        return self.async_show_progress(
            step_id="reauth_confirm",
            progress_action="wait_for_auth",
            description_placeholders={
                "url": self._auth_data["verification_uri_complete"],
                "code": self._auth_data["user_code"],
            },
            progress_task=login_task,
        )

    async def async_step_reauth_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle successful re-authentication."""
        reauth_entry = self._get_reauth_entry()
        refresh_token = self._manager.token.refresh_token

        return self.async_update_reload_and_abort(
            reauth_entry,
            data_updates={CONF_TOKEN: refresh_token},
        )

    async def async_step_reauth_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication failure."""
        return self.async_abort(reason="invalid_auth")


class YotoOptionsFlowHandler(OptionsFlowWithReload):
    """Handle Yoto options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(int, vol.Range(min=1, max=60)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
