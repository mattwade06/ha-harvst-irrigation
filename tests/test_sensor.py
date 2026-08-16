"""Tests for custom_components.harvst.sensor."""
from unittest.mock import MagicMock

from custom_components.harvst.coordinator import HarvstCoordinator
from custom_components.harvst.sensor import CURRENT_DESCRIPTION, TEMPERATURE_DESCRIPTION, HarvstSensor


async def test_temperature_sensor_reads_te_field(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)
    sensor = HarvstSensor(coordinator, "entry123", TEMPERATURE_DESCRIPTION)

    assert sensor.native_value is None
    assert sensor.available is False

    coordinator.async_set_updated_data({"te": 21.5})

    assert sensor.native_value == 21.5
    assert sensor.available is True


async def test_temperature_sensor_treats_sentinel_as_unavailable(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)
    sensor = HarvstSensor(coordinator, "entry123", TEMPERATURE_DESCRIPTION)

    coordinator.async_set_updated_data({"te": -13})

    assert sensor.native_value is None
    assert sensor.available is False


async def test_current_sensor_uses_int32_min_sentinel(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)
    sensor = HarvstSensor(coordinator, "entry123", CURRENT_DESCRIPTION)

    coordinator.async_set_updated_data({"cc": -2147483647})
    assert sensor.native_value is None

    coordinator.async_set_updated_data({"cc": 340})
    assert sensor.native_value == 340
