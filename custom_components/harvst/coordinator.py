"""Push-based data coordinator for a Harvst control panel.

The panel streams live readings over Server-Sent Events at /events as a
"new_readings" event, e.g.:

    event: new_readings
    data: {"te":24.0,"teAve":4,"ti":-13,"ta":-13,"h":-13,"isr":0,
            "ts_1":-13,"ts_2":-13,"s1":-13,"s2":-13,"x1":0,"x2":0,"x3":0,
            "cc":-2147483647}

Field meanings, reverse engineered from the panel's own page markup/JS and
the layout of its /settings page:
    te    - wired temperature probe ("T1 / silver bullet"), degrees C
    teAve - temperature probe rolling average, degrees C
    ta    - second wired temp probe (ds18b20_ta), degrees C
    h     - wired humidity probe (dht22), percent
    cc    - instantaneous current draw, mA (shown as "Power use")
    x1/x2/x3 - aux relay 1/2/3 output state, 0=off 1=on
    isr, ts_1, ts_2, s1, s2 - additional sensor bus channels (battery
        internal resistance, valve test readings, moisture/humidity probes
        assignable per zone); not surfaced as entities as their exact
        semantics couldn't be confirmed against this firmware.

`-13` is the panel's sentinel for "no sensor connected on this channel".

The panel does not appear to broadcast whether a zone is currently
watering, so that state is tracked locally in `zone_watering` below,
set by the switch entities (HarvstZoneSwitch) whenever they issue a
command, so every entity can read it from one place.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import HarvstClient
from .const import DOMAIN, UNAVAILABLE_SENTINEL, UPDATE_EVENT, ZONE_COUNT

_LOGGER = logging.getLogger(__name__)

_MIN_BACKOFF = 5
_MAX_BACKOFF = 300
_SSE_IDLE_TIMEOUT = 120


def reading(
    payload: dict[str, Any] | None, key: str, sentinel: int = UNAVAILABLE_SENTINEL
) -> float | None:
    """Pull a numeric reading out of an SSE payload, honoring the sentinel.

    Most channels use -13 for "not connected". The `cc` (current draw)
    channel instead uses INT32_MIN (-2147483647) before the panel has taken
    a reading, matching the INT32_MAX sentinels ("2147483647") used for
    unset values elsewhere in the panel's own /settings page.
    """
    if not payload:
        return None
    value = payload.get(key)
    if value is None or value == sentinel:
        return None
    return value


class HarvstCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns the SSE connection and the last known state of a control panel."""

    def __init__(self, hass: HomeAssistant, client: HarvstClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.client = client
        self.zone_watering: dict[int, bool] = dict.fromkeys(range(1, ZONE_COUNT + 1), False)
        self._sse_task: asyncio.Task | None = None

    async def async_start(self) -> None:
        self._sse_task = self.hass.loop.create_task(self._sse_loop())

    async def async_stop(self) -> None:
        if self._sse_task is not None:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None

    def set_zone_watering(self, zone: int, watering: bool) -> None:
        """Record locally-tracked watering state and notify listeners."""
        self.zone_watering[zone] = watering
        self.async_update_listeners()

    async def _sse_loop(self) -> None:
        backoff = _MIN_BACKOFF
        url = f"{self.client.base_url}/events"
        while True:
            try:
                timeout = aiohttp.ClientTimeout(
                    total=None, sock_connect=15, sock_read=_SSE_IDLE_TIMEOUT
                )
                async with self.client.session.get(
                    url, headers={"Accept": "text/event-stream"}, timeout=timeout
                ) as resp:
                    resp.raise_for_status()
                    backoff = _MIN_BACKOFF
                    self.last_update_success = True
                    await self._consume(resp)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - keep the loop alive on any error
                _LOGGER.debug("Harvst SSE connection to %s dropped: %s", url, err)
                if self.last_update_success:
                    self.last_update_success = False
                    self.async_update_listeners()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)

    async def _consume(self, resp: aiohttp.ClientResponse) -> None:
        event_type: str | None = None
        async for raw_line in resp.content:
            line = raw_line.decode("utf-8", "ignore").rstrip("\r\n")
            if not line:
                event_type = None
                continue
            if line.startswith(":"):
                continue  # SSE comment/heartbeat
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                if event_type != UPDATE_EVENT:
                    continue
                try:
                    payload = json.loads(data_str)
                except ValueError:
                    _LOGGER.debug("Ignoring malformed new_readings payload: %s", data_str)
                    continue
                self.async_set_updated_data(payload)
