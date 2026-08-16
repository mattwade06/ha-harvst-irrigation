"""Shared base entity for Harvst entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HarvstCoordinator


class HarvstEntity(CoordinatorEntity[HarvstCoordinator]):
    """Base entity tying every Harvst entity to the same device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HarvstCoordinator, unique_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.host)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="Harvst control panel",
            configuration_url=coordinator.client.base_url,
        )
