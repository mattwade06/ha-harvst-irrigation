"""Tests for custom_components.harvst.api."""
import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.harvst.api import HarvstApiError, HarvstAuthError, HarvstClient

HOST = "192.168.1.140"
BASE = f"http://{HOST}"

SETTINGS_HTML = """
<div class="box">
    <div class="device-id">Device ID: <div>D01992BD9710</div></div>
</div>
<table class="table-data">
<tr><td>Firmware</td><td>2024060601</td></tr>
</table>
"""


async def test_water_zone_on_sends_expected_params(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/control")
    client = HarvstClient(async_get_clientsession(hass), HOST)

    await client.async_water_zone_on(1, 30)

    assert len(aioclient_mock.mock_calls) == 1
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["device"] == "pump"
    assert url.query["state"] == "on"
    assert url.query["zone"] == "1"
    assert url.query["time"] == "30"


async def test_water_zone_off_sends_expected_params(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/control")
    client = HarvstClient(async_get_clientsession(hass), HOST)

    await client.async_water_zone_off(2)

    url = aioclient_mock.mock_calls[0][1]
    assert url.query["device"] == "pump"
    assert url.query["state"] == "off"
    assert url.query["zone"] == "2"
    assert "time" not in url.query


async def test_aux_on_off_and_clear(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/control")
    client = HarvstClient(async_get_clientsession(hass), HOST)

    await client.async_aux_on(1)
    await client.async_aux_off(1)
    await client.async_clear_aux_last_run(1)
    await client.async_clear_zone_last_watered(2)

    dos = [call[1].query["do"] for call in aioclient_mock.mock_calls]
    assert dos == ["x1On", "x1Off", "clear_x1", "clear2"]


async def test_get_device_info_parses_html(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/settings", text=SETTINGS_HTML)
    client = HarvstClient(async_get_clientsession(hass), HOST)

    info = await client.async_get_device_info()

    assert info["device_id"] == "D01992BD9710"
    assert info["firmware"] == "2024060601"


async def test_get_device_info_falls_back_to_host(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/settings", text="<html>no useful data</html>")
    client = HarvstClient(async_get_clientsession(hass), HOST)

    info = await client.async_get_device_info()

    assert info["device_id"] == HOST
    assert info["firmware"] == "unknown"


async def test_auth_error_on_401(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/", status=401)
    client = HarvstClient(async_get_clientsession(hass), HOST)

    with pytest.raises(HarvstAuthError):
        await client.async_test_connection()


async def test_connection_error_raises_api_error(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/", exc=aiohttp.ClientConnectionError)
    client = HarvstClient(async_get_clientsession(hass), HOST)

    with pytest.raises(HarvstApiError):
        await client.async_test_connection()
