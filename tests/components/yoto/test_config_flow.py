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
    """Test user flow initiates device code auth."""
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
    """Test user flow creates a config entry on success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS

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
    """Test auth failure aborts."""

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
    """Test single instance abort when already configured."""
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
    """Test reauth flow updates the token."""
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
    """Test reauth failure aborts with error."""

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


async def test_options_flow_default_scan_interval(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow shows the default scan interval."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_sets_scan_interval(
    hass: HomeAssistant,
    mock_yoto_manager: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow saves the scan interval."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"scan_interval": 10},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {"scan_interval": 10}
