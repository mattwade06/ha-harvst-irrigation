"""Tests for custom_components.harvst.config_flow."""
import aiohttp
from homeassistant.data_entry_flow import FlowResultType

from custom_components.harvst.const import DOMAIN

HOST = "192.168.1.140"
BASE = f"http://{HOST}"

SETTINGS_HTML = """
<div class="device-id">Device ID: <div>D01992BD9710</div></div>
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
