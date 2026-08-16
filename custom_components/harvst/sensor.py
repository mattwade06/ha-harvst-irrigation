"""Sensor entities for a Harvst control panel."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HarvstConfigEntry
from .const import CURRENT_UNAVAILABLE_SENTINEL
from .coordinator import reading
from .entity import HarvstEntity

TEMPERATURE_DESCRIPTION = SensorEntityDescription(
    key="te",
    translation_key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)

CURRENT_DESCRIPTION = SensorEntityDescription(
    key="cc",
    translation_key="current",
    device_class=SensorDeviceClass.CURRENT,
    native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    state_class=SensorStateClass.MEASUREMENT,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HarvstConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            HarvstSensor(coordinator, entry.entry_id, TEMPERATURE_DESCRIPTION),
            HarvstSensor(coordinator, entry.entry_id, CURRENT_DESCRIPTION),
        ]
    )


class HarvstSensor(HarvstEntity, SensorEntity):
    """A single reading pulled out of the /events SSE payload."""

    def __init__(self, coordinator, entry_id: str, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, f"{entry_id}_{description.key}")
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        sentinel = (
            CURRENT_UNAVAILABLE_SENTINEL
            if self.entity_description.key == "cc"
            else -13
        )
        return reading(self.coordinator.data, self.entity_description.key, sentinel)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None
