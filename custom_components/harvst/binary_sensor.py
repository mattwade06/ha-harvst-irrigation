"""Binary sensors reporting whether a zone is currently watering.

The control panel does not broadcast zone-running state over its /events
SSE feed, so this reflects the state tracked locally by the matching
HarvstZoneSwitch (see switch.py) whenever it issues a water-on/water-off
command or a timed run expires.
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
    async_add_entities(
        HarvstZoneWateringBinarySensor(coordinator, entry.entry_id, zone)
        for zone in range(1, ZONE_COUNT + 1)
    )


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
