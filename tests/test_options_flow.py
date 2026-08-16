"""Tests for custom_components.harvst.config_flow.HarvstOptionsFlow."""
import aiohttp
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.harvst.const import CONF_ZONE_RUNTIME, DOMAIN

HOST = "192.168.1.140"
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


async def test_options_flow_updates_host_and_runtime(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    aioclient_mock.get(f"{NEW_BASE}/")
    aioclient_mock.get(f"{NEW_BASE}/settings", text=SETTINGS_HTML)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {"host": NEW_HOST, "zone_max_runtime": 1800}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data["host"] == NEW_HOST
    assert entry.options[CONF_ZONE_RUNTIME] == 1800


async def test_options_flow_rejects_different_device(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    aioclient_mock.get(f"{NEW_BASE}/")
    aioclient_mock.get(f"{NEW_BASE}/settings", text=OTHER_SETTINGS_HTML)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {"host": NEW_HOST, "zone_max_runtime": 3600}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "wrong_device"}
    assert entry.data["host"] == HOST


async def test_options_flow_cannot_connect(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    aioclient_mock.get(f"{NEW_BASE}/", exc=aiohttp.ClientConnectionError)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {"host": NEW_HOST, "zone_max_runtime": 3600}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert entry.data["host"] == HOST


async def test_options_flow_skips_validation_when_host_unchanged(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="D01992BD9710", data={"host": HOST})
    entry.add_to_hass(hass)

    # No aioclient_mock routes registered at all: if the flow incorrectly
    # tried to re-validate an unchanged connection, this would blow up
    # loudly instead of silently passing.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {"host": HOST, "zone_max_runtime": 900}
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ZONE_RUNTIME] == 900
