"""Binary sensors reporting pump/zone watering state.

The panel doesn't say *which* zone is watering over its /events SSE feed,
but it does broadcast a global `pump_state` field (confirmed by live
testing) on the event immediately following a state change - see
coordinator.py. HarvstPumpRunningBinarySensor reflects that real telemetry
directly. HarvstZoneWateringBinarySensor still reflects the coordinator's
locally-tracked per-zone state (see switch.py), since the panel has one
physical pump for both zones and pump_state can't tell them apart.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HarvstConfigEntry
from .const import ZONE_COUNT
from .entity import HarvstEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HarvstConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = [
        HarvstZoneWateringBinarySensor(coordinator, entry.entry_id, zone)
        for zone in range(1, ZONE_COUNT + 1)
    ]
    entities.append(HarvstPumpRunningBinarySensor(coordinator, entry.entry_id))
    async_add_entities(entities)


class HarvstZoneWateringBinarySensor(HarvstEntity, BinarySensorEntity):
    """Is this zone currently watering?"""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, entry_id: str, zone: int) -> None:
        super().__init__(coordinator, f"{entry_id}_zone{zone}_watering")
        self._zone = zone
        self._attr_translation_key = "zone_watering"
        self._attr_translation_placeholders = {"zone": str(zone)}

    @property
    def is_on(self) -> bool:
        return self.coordinator.zone_watering.get(self._zone, False)

    @property
    def available(self) -> bool:
        # Local state, not dependent on the SSE feed being healthy.
        return True


class HarvstPumpRunningBinarySensor(HarvstEntity, BinarySensorEntity):
    """Is the physical pump currently running, per the panel's own telemetry."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator, f"{entry_id}_pump_running")
        self._attr_translation_key = "pump_running"

    @property
    def is_on(self) -> bool:
        return self.coordinator.pump_running

    @property
    def available(self) -> bool:
        # pump_running defaults to False rather than unknown (see
        # coordinator.py), so this only needs to track the SSE connection.
        return super().available
