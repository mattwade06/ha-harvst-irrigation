"""The Harvst irrigation control panel integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HarvstClient
from .coordinator import HarvstCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]

type HarvstConfigEntry = ConfigEntry[HarvstRuntimeData]


@dataclass
class HarvstRuntimeData:
    client: HarvstClient
    coordinator: HarvstCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: HarvstConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = HarvstClient(
        session,
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME) or None,
        entry.data.get(CONF_PASSWORD) or None,
    )

    coordinator = HarvstCoordinator(hass, client)
    await coordinator.async_start()

    entry.runtime_data = HarvstRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HarvstConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.async_stop()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: HarvstConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
