"""Tests for custom_components.harvst.switch."""
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.harvst.const import CONF_ZONE_RUNTIME, DOMAIN
from custom_components.harvst.coordinator import HarvstCoordinator
from custom_components.harvst.switch import HarvstAuxSwitch, HarvstZoneSwitch


def _make_entry(hass, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.140"}, options=options or {})
    entry.add_to_hass(hass)
    return entry


async def test_zone_switch_turn_on_then_off(hass):
    client = AsyncMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)
    entry = _make_entry(hass, {CONF_ZONE_RUNTIME: 5})

    switch = HarvstZoneSwitch(coordinator, entry, 1)
    switch.hass = hass

    assert switch.is_on is False

    await switch.async_turn_on()
    client.async_water_zone_on.assert_awaited_once_with(1, 5)
    assert switch.is_on is True

    await switch.async_turn_off()
    client.async_water_zone_off.assert_awaited_once_with(1)
    assert switch.is_on is False


async def test_zone_switch_defaults_runtime_when_no_option_set(hass):
    client = AsyncMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)
    entry = _make_entry(hass)

    switch = HarvstZoneSwitch(coordinator, entry, 2)
    switch.hass = hass

    await switch.async_turn_on()
    client.async_water_zone_on.assert_awaited_once_with(2, 3600)
    await switch.async_turn_off()


async def test_zone_switch_does_not_affect_other_zone(hass):
    client = AsyncMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)
    entry = _make_entry(hass, {CONF_ZONE_RUNTIME: 5})

    zone1 = HarvstZoneSwitch(coordinator, entry, 1)
    zone1.hass = hass
    zone2 = HarvstZoneSwitch(coordinator, entry, 2)
    zone2.hass = hass

    await zone1.async_turn_on()
    assert zone1.is_on is True
    assert zone2.is_on is False
    await zone1.async_turn_off()


async def test_aux_switch_reflects_sse_state(hass):
    client = AsyncMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    aux = HarvstAuxSwitch(coordinator, "entry123", 1)

    assert aux.is_on is False

    coordinator.async_set_updated_data({"x1": 1, "x2": 0, "x3": 0})
    assert aux.is_on is True

    coordinator.async_set_updated_data({"x1": 0, "x2": 0, "x3": 0})
    assert aux.is_on is False


async def test_aux_switch_turn_on_off_calls_client(hass):
    client = AsyncMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    aux = HarvstAuxSwitch(coordinator, "entry123", 2)

    await aux.async_turn_on()
    client.async_aux_on.assert_awaited_once_with(2)

    await aux.async_turn_off()
    client.async_aux_off.assert_awaited_once_with(2)
