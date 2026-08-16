"""Tests for custom_components.harvst.config_flow."""
import aiohttp
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.harvst.const import DOMAIN

HOST = "192.168.1.140"
BASE = f"http://{HOST}"
NEW_HOST = "192.168.1.150"
NEW_BASE = f"http://{NEW_HOST}"

SETTINGS_HTML = """
<div class="device-id">Device ID: <div>D01992BD9710</div></div>
<table class="table-data"><tr><td>Firmware</td><td>2024060601</td></tr></table>
"""

OTHER_SETTINGS_HTML = """
<div class="device-id">Device ID: <div>D0AAAAAAAAAA</div></div>
<table class="table-data"><tr><td>Firmware</td><td>2024060601</td></tr></table>
"""


async def test_user_flow_success(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/")
    aioclient_mock.get(f"{BASE}/settings", text=SETTINGS_HTML)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": HOST})

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"]["host"] == HOST
    assert result2["title"] == f"Harvst ({HOST})"


async def test_user_flow_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/", exc=aiohttp.ClientConnectionError)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": HOST})

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/", status=401)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": HOST})

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_updates_host(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    aioclient_mock.get(f"{NEW_BASE}/")
    aioclient_mock.get(f"{NEW_BASE}/settings", text=SETTINGS_HTML)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": NEW_HOST}
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data["host"] == NEW_HOST

    # A successful reconfigure schedules a real entry reload, which starts a
    # live HarvstCoordinator (and its background SSE task) against the new
    # host. Let that finish, then unload so the task gets cancelled cleanly
    # rather than left running past the end of the test.
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reconfigure_rejects_different_device(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    aioclient_mock.get(f"{NEW_BASE}/")
    aioclient_mock.get(f"{NEW_BASE}/settings", text=OTHER_SETTINGS_HTML)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": NEW_HOST}
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "wrong_device"
    assert entry.data["host"] == HOST


async def test_reconfigure_cannot_connect_shows_form_again(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    aioclient_mock.get(f"{NEW_BASE}/", exc=aiohttp.ClientConnectionError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": NEW_HOST}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert entry.data["host"] == HOST
