"""Thin async client for the Harvst irrigation control panel's local HTTP API.

The control panel exposes no documented/JSON API. Everything here was
reverse engineered from the device's own web UI (HTML forms and inline
JavaScript served by the panel itself):

  GET  /                                   -> home page, live values pushed via SSE
  GET  /events                             -> text/event-stream, event "new_readings"
                                               with a JSON payload of current sensor/
                                               relay readings (see coordinator.py)
  GET  /control?device=pump&state=on
           &zone={1|2}&time={seconds}      -> manually run a zone for N seconds
                                               (the "Water now" buttons on /w1 /w2)
  GET  /control?device=pump&state=off
           &zone={1|2}                     -> stop a zone early (inferred: the panel
                                               only exposes the "on" form; "off" is
                                               the natural counterpart and matches the
                                               device=/state= shape used elsewhere)
  GET  /control?do=clear{1|2}              -> clear the "last watered" timestamp
  GET  /control?do=x{1|2|3}On|Off          -> toggle an aux relay (the on/off switch
                                               on /x1 /x2 /x3 uses exactly this)
  GET  /control?do=clear_x{1|2|3}          -> clear an aux relay's "last run" timestamp
  GET  /settings                           -> device ID + firmware version (HTML)

There is no standalone "pump only" endpoint - the panel always fires the pump
together with a zone's valve. The 3 aux relays are general purpose; Harvst's own
UI lets you wire one to "Pump zone 1/2" (see the Aux "Use output" dropdown), which
is the panel's own mechanism for exposing the pump independently of a zone.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEVICE_ID_RE = re.compile(r"Device ID:\s*<div>([^<]+)</div>")
FIRMWARE_RE = re.compile(r"<td>Firmware</td>\s*<td>([^<]+)</td>")


class HarvstApiError(Exception):
    """Raised when a request to the control panel fails."""


class HarvstAuthError(HarvstApiError):
    """Raised when the control panel rejects our credentials."""


class HarvstClient:
    """Talks to a single Harvst control panel over the local network."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self.host = host
        self._auth = aiohttp.BasicAuth(username, password) if username else None

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._session

    @property
    def base_url(self) -> str:
        return f"http://{self.host}"

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.get(
                url,
                params=params,
                auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    raise HarvstAuthError(f"{url} rejected credentials ({resp.status})")
                resp.raise_for_status()
                return await resp.text(errors="ignore")
        except HarvstAuthError:
            raise
        except aiohttp.ClientError as err:
            raise HarvstApiError(f"Error requesting {url}: {err}") from err
        except TimeoutError as err:
            raise HarvstApiError(f"Timeout requesting {url}") from err

    async def async_test_connection(self) -> None:
        """Raise HarvstApiError/HarvstAuthError if the panel can't be reached."""
        await self._get("/")

    async def async_get_device_info(self) -> dict[str, str]:
        """Scrape the device ID and firmware version off the /settings page."""
        html = await self._get("/settings")
        device_id_match = DEVICE_ID_RE.search(html)
        firmware_match = FIRMWARE_RE.search(html)
        return {
            "device_id": device_id_match.group(1).strip() if device_id_match else self.host,
            "firmware": firmware_match.group(1).strip() if firmware_match else "unknown",
        }

    async def async_water_zone_on(self, zone: int, duration: int) -> None:
        """Start watering `zone` for `duration` seconds."""
        await self._get(
            "/control",
            {"device": "pump", "state": "on", "zone": zone, "time": duration},
        )

    async def async_water_zone_off(self, zone: int) -> None:
        """Stop watering `zone` early."""
        await self._get("/control", {"device": "pump", "state": "off", "zone": zone})

    async def async_clear_zone_last_watered(self, zone: int) -> None:
        await self._get("/control", {"do": f"clear{zone}"})

    async def async_aux_on(self, aux: int) -> None:
        await self._get("/control", {"do": f"x{aux}On"})

    async def async_aux_off(self, aux: int) -> None:
        await self._get("/control", {"do": f"x{aux}Off"})

    async def async_clear_aux_last_run(self, aux: int) -> None:
        await self._get("/control", {"do": f"clear_x{aux}"})
