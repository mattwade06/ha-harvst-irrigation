"""Tests for custom_components.harvst.coordinator."""
from unittest.mock import MagicMock

from custom_components.harvst.const import CURRENT_UNAVAILABLE_SENTINEL
from custom_components.harvst.coordinator import HarvstCoordinator, reading


def test_reading_none_payload():
    assert reading(None, "te") is None


def test_reading_missing_key():
    assert reading({}, "te") is None


def test_reading_sentinel_is_unavailable():
    assert reading({"te": -13}, "te") is None


def test_reading_returns_value():
    assert reading({"te": 24.0}, "te") == 24.0


def test_reading_custom_sentinel():
    assert reading({"cc": CURRENT_UNAVAILABLE_SENTINEL}, "cc", CURRENT_UNAVAILABLE_SENTINEL) is None
    assert reading({"cc": 120}, "cc", CURRENT_UNAVAILABLE_SENTINEL) == 120


class _FakeContent:
    """Mimics aiohttp's StreamReader enough for line-by-line SSE parsing."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for line in self._lines:
            yield line


class _FakeResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self.content = _FakeContent(lines)


async def test_consume_updates_data_on_new_readings(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    lines = [
        b"event: new_readings\n",
        b'data: {"te": 24.0, "x1": 1}\n',
        b"\n",
    ]

    await coordinator._consume(_FakeResponse(lines))

    assert coordinator.data == {"te": 24.0, "x1": 1}


async def test_consume_ignores_other_event_types(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    lines = [
        b"event: message\n",
        b'data: {"ignored": true}\n',
        b"\n",
    ]

    await coordinator._consume(_FakeResponse(lines))

    assert coordinator.data is None


async def test_consume_ignores_malformed_json(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    lines = [
        b"event: new_readings\n",
        b"data: {not json}\n",
        b"\n",
    ]

    await coordinator._consume(_FakeResponse(lines))

    assert coordinator.data is None


def test_set_zone_watering_updates_state(hass):
    client = MagicMock()
    client.host = "192.168.1.140"
    coordinator = HarvstCoordinator(hass, client)

    assert coordinator.zone_watering[1] is False
    coordinator.set_zone_watering(1, True)
    assert coordinator.zone_watering[1] is True
