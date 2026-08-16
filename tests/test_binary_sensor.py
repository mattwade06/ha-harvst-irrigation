"""Tests for custom_components.harvst.binary_sensor."""
from unittest.mock import MagicMock

from custom_components.harvst.binary_sensor import HarvstZoneWateringBinarySensor
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
