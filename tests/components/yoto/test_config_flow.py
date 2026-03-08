"""Tests for the Yoto config flow."""

from threading import Event
from unittest.mock import MagicMock

from yoto_api import AuthenticationError

from homeassistant.components.yoto.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_initiates_device_code(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_yoto_manager_config_flow: MagicMock,
) -> None:
    """Test that starting the user flow initiates device code auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"
    assert result["progress_action"] == "wait_for_auth"
    mock_yoto_manager_config_flow.device_code_flow_start.assert_called_once()


async def test_user_flow_creates_entry_on_success(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_yoto_manager_config_flow: MagicMock,
    device_auth_event: Event,
) -> None:
    """Test that completing device code auth creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    # Signal that auth completed successfully
    device_auth_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Yoto"
    assert result["data"] == {CONF_TOKEN: "mock-refresh-token"}


async def test_user_flow_auth_failure(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_yoto_manager_config_flow: MagicMock,
    device_auth_event: Event,
) -> None:
    """Test that auth failure aborts."""

    def mock_complete_with_error() -> None:
        device_auth_event.wait()
        raise AuthenticationError

    mock_yoto_manager_config_flow.device_code_flow_complete = mock_complete_with_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS

    device_auth_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_user_flow_single_instance(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_yoto_manager_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we abort if already configured (single_config_entry)."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_yoto_manager_config_flow: MagicMock,
    device_auth_event: Event,
) -> None:
    """Test that reauth flow updates the token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "old-refresh-token"},
        unique_id="old-refresh-token",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "reauth_confirm"

    device_auth_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_auth_failure(
    hass: HomeAssistant,
    mock_yoto_manager_config_flow: MagicMock,
    device_auth_event: Event,
) -> None:
    """Test that reauth failure aborts with error."""

    def mock_complete_with_error() -> None:
        device_auth_event.wait()
        raise AuthenticationError

    mock_yoto_manager_config_flow.device_code_flow_complete = mock_complete_with_error

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: "old-refresh-token"},
        unique_id="old-refresh-token",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "reauth_confirm"

    device_auth_event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"
