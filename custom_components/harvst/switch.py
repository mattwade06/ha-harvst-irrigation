"""Switch entities for a Harvst control panel.

Two families of switch, matched to what the panel actually exposes:

* Zone switches (1-2) turn on a zone's pump + valve for a bounded duration
  (`/control?device=pump&state=on&zone=N&time=S`) and turn it off early
  (`state=off`, inferred - see api.py). The panel has no "zone running"
  telemetry, so state is tracked locally here and auto-clears when the
  requested duration elapses, mirroring what the hardware itself does.
  These are the entities meant to be driven by an irrigation blueprint.

* Aux switches (1-3) toggle the panel's general purpose relay outputs
  (`/control?do=xNOn` / `xNOff`) and reflect real state pushed back on the
  /events feed (`x1`/`x2`/`x3`). If you've wired an aux relay to the pump
  itself (Aux page -> "Use output" -> "Pump zone 1/2"), its switch becomes
  a standalone pump control independent of a zone's valve.
"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import HarvstConfigEntry
from .const import AUX_COUNT, CONF_ZONE_RUNTIME, DEFAULT_ZONE_MAX_RUNTIME, ZONE_COUNT
from .entity import HarvstEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: HarvstConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[SwitchEntity] = [
        HarvstZoneSwitch(coordinator, entry, zone) for zone in range(1, ZONE_COUNT + 1)
    ]
    entities += [
        HarvstAuxSwitch(coordinator, entry.entry_id, aux) for aux in range(1, AUX_COUNT + 1)
    ]
    async_add_entities(entities)


class HarvstZoneSwitch(HarvstEntity, SwitchEntity):
    """Runs a zone's pump + valve for a bounded duration."""

    def __init__(self, coordinator, entry: HarvstConfigEntry, zone: int) -> None:
        super().__init__(coordinator, f"{entry.entry_id}_zone{zone}")
        self._entry = entry
        self._zone = zone
        self._attr_translation_key = "zone"
        self._attr_translation_placeholders = {"zone": str(zone)}
        self._unsub_auto_off = None

    @property
    def is_on(self) -> bool:
        return self.coordinator.zone_watering.get(self._zone, False)

    @property
    def available(self) -> bool:
        # Locally tracked, so usable even while the SSE feed is reconnecting.
        return True

    async def async_turn_on(self, **kwargs) -> None:
        duration = self._entry.options.get(CONF_ZONE_RUNTIME, DEFAULT_ZONE_MAX_RUNTIME)
        await self.coordinator.client.async_water_zone_on(self._zone, duration)
        self._cancel_auto_off()
        self.coordinator.set_zone_watering(self._zone, True)
        self._unsub_auto_off = async_call_later(self.hass, duration, self._async_auto_off)

    async def async_turn_off(self, **kwargs) -> None:
        self._cancel_auto_off()
        await self.coordinator.client.async_water_zone_off(self._zone)
        self.coordinator.set_zone_watering(self._zone, False)

    async def _async_auto_off(self, _now) -> None:
        self._unsub_auto_off = None
        self.coordinator.set_zone_watering(self._zone, False)

    def _cancel_auto_off(self) -> None:
        if self._unsub_auto_off is not None:
            self._unsub_auto_off()
            self._unsub_auto_off = None

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_auto_off()
        await super().async_will_remove_from_hass()


class HarvstAuxSwitch(HarvstEntity, SwitchEntity):
    """A general purpose aux relay output, reflecting real panel state."""

    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry_id: str, aux: int) -> None:
        super().__init__(coordinator, f"{entry_id}_aux{aux}")
        self._aux = aux
        self._attr_translation_key = "aux"
        self._attr_translation_placeholders = {"aux": str(aux)}

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        if not data:
            return False
        return bool(data.get(f"x{self._aux}"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.async_aux_on(self._aux)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.async_aux_off(self._aux)
