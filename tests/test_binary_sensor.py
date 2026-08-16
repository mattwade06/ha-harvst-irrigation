"""Tests for custom_components.harvst.binary_sensor."""
from unittest.mock import MagicMock

from custom_components.harvst.binary_sensor import (
    HarvstPumpRunningBinarySensor,
    HarvstZoneWateringBinarySensor,
)
from custom_components.harvst.coordinator import HarvstCoordinator


async def test_binary_sensor_reflects_coordinator_state(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    sensor1 = HarvstZoneWateringBinarySensor(coordinator, "entry123", 1)
    sensor2 = HarvstZoneWateringBinarySensor(coordinator, "entry123", 2)

    assert sensor1.is_on is False
    assert sensor2.is_on is False

    coordinator.set_zone_watering(1, True)

    assert sensor1.is_on is True
    assert sensor2.is_on is False
    assert sensor1.available is True


async def test_pump_running_binary_sensor_reflects_telemetry(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    sensor = HarvstPumpRunningBinarySensor(coordinator, "entry123")

    assert sensor.is_on is None
    assert sensor.available is False

    coordinator.pump_running = True
    assert sensor.is_on is True
    assert sensor.available is True

    coordinator.pump_running = False
    assert sensor.is_on is False
    assert sensor.available is True
