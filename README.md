# Harvst Irrigation for Home Assistant

A HACS-installable Home Assistant custom integration for the [Harvst](https://harvst.co) greenhouse
irrigation control panel — the small solar/mains-powered box that runs a pump, up to two watering
zones, three auxiliary relays, and a wired temperature probe.

The panel doesn't publish a documented API, so this integration talks to the same local HTTP
endpoints its own web UI uses. See [How this was reverse engineered](#how-this-was-reverse-engineered)
below for exactly what was found and how.

## What you get

| Entity | Domain | Notes |
|---|---|---|
| Temperature | `sensor` | Wired "silver bullet" probe (`T1`), °C |
| Current draw | `sensor` | Instantaneous draw in mA, disabled by default |
| Zone 1 / Zone 2 watering | `binary_sensor` | On while a zone is actively watering (locally tracked, see below) |
| Pump running | `binary_sensor` | On/off straight from the panel's own `pump_state` telemetry |
| Zone 1 / Zone 2 | `switch` | Turns a zone's pump + valve on/off — use these with an irrigation blueprint |
| Aux 1 / Aux 2 / Aux 3 | `switch` | The panel's general-purpose relay outputs, disabled by default |

All entities hang off one device per control panel, identified by the panel's own Device ID.

### Using it with a garden watering blueprint

The Zone 1 / Zone 2 switches are plain `switch` entities with no special timing baked in beyond a
safety-cap runtime (configurable in the integration's Options, default 1 hour), so they drop
straight into Home Assistant's built-in [Garden Watering
blueprint](https://www.home-assistant.io/blueprints/deploy/) (or any similar one) as the valve
switches. Point the blueprint's "pump switch" field at one of the Aux switches **only if** you've
wired that aux relay to your pump directly (see [Aux switches and the
pump](#aux-switches-and-the-pump) below) — otherwise leave it unset, since Zone 1/2 already run the
pump themselves.

### Zone safety cutoff

Every `switch.turn_on` call sends a `time=` value straight to the panel itself, not just to Home
Assistant — so the cutoff is enforced by the panel's own firmware, not by anything running on your
HA instance. If HA crashes, loses network, or never gets around to sending a turn-off command
mid-cycle, the zone still stops on its own once that many seconds pass. Set how long that is under
**Settings → Devices & services → Harvst → Configure** ("Zone safety cutoff"), default 1 hour.
Automations that manage their own timing (like the blueprint above) still turn zones off earlier
than this on their own — this setting is just the worst-case backstop.

## Installation via HACS

1. In Home Assistant, go to **HACS → Integrations**.
2. Click the **⋮** menu (top right) → **Custom repositories**.
3. Add this repository's URL (`https://github.com/mattwade06/ha-harvst-irrigation`) with category
   **Integration**.
4. Find **Harvst Irrigation** in HACS and click **Download**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**, search for **Harvst**, and enter your
   control panel's IP address or hostname (e.g. `192.168.1.140`).

If your panel has a device password set (Settings page → "Device WiFi password" on the panel
itself), enter it as the username/password during setup; leave both blank otherwise.

The panel's address is fully configurable in the integration's config flow — it doesn't need to be
`192.168.1.140`, that's just this developer's greenhouse. If it changes later (e.g. a DHCP
reassignment), you don't need to remove and re-add the integration: go to **Settings → Devices &
services → Harvst Irrigation → ⋮ → Reconfigure** and enter the new address. Reconfigure is for
pointing at the *same* panel under a new address — it checks the panel's device ID hasn't changed
and refuses to proceed if it has, since that means the address now points at different hardware.

## Known limitations

- **No standalone pump control.** The panel always fires the pump together with a zone's valve
  when you run a zone — there's no "pump only" endpoint anywhere in its UI. The only way to control
  the pump independently of a zone is the panel's own mechanism: assign one of the 3 aux relays to
  "Pump zone 1" or "Pump zone 2" on that aux's settings page, then that aux's switch becomes a
  standalone pump control (see below).
- **Zone watering status is tracked locally, not read from the device — but pump state is real.**
  The panel's live event feed doesn't say *which* zone is running (it has one physical pump serving
  both), so per-zone `binary_sensor`/`switch` state reflects commands this integration has sent, not
  a live per-zone readback. The separate "Pump running" `binary_sensor`, however, is read straight
  from the panel's own `pump_state` telemetry, confirmed by live testing (see below) — and this
  integration also uses it to clear a zone's watering state the moment the pump actually stops,
  rather than waiting out the switch's own timer, so a backpressure fault or over-current cutoff
  shows up in Home Assistant immediately instead of after the fact.

### Aux switches and the pump

On the panel itself, each Aux page (`/x1`, `/x2`, `/x3`) has a "Use output" dropdown that can be set
to "Output N" (a generic relay) or "Pump zone 1" / "Pump zone 2" (wires that aux directly to the
pump). If you set one that way, the matching `switch.harvst_aux_n` entity in Home Assistant becomes
an independent pump toggle you can wire into a blueprint's pump field. Aux switches are disabled by
default in the entity registry since most installs don't use them — enable the ones you need.

## How this was reverse engineered

The panel serves a small set of server-rendered HTML pages plus a live event stream; there's no
JSON API. Everything below was found by reading the HTML/JS the panel itself serves (view source,
no decompilation or credentials involved):

- `GET /` — home page. Live readings arrive over `GET /events`, a `text/event-stream` connection
  the page's own JS opens with `new EventSource('/events')`. Events named `new_readings` carry a
  JSON payload, e.g.:

  ```json
  {"te":24.0,"teAve":4,"ti":-13,"ta":-13,"h":-13,"isr":0,
   "ts_1":-13,"ts_2":-13,"s1":-13,"s2":-13,"x1":0,"x2":0,"x3":0,"cc":-2147483647}
  ```

  `te` is the wired temperature probe (°C) — this is the "Temperature (silver bullet)" reading
  shown on the home page and what the `sensor.temperature` entity uses. `x1`/`x2`/`x3` are the aux
  relay states (0/1). `cc` is instantaneous current draw in mA. `-13` is the panel's sentinel for
  "nothing connected on this channel"; `cc` instead uses `-2147483647` (`INT32_MIN`) before a
  reading is available, matching the `INT32_MAX` sentinels used for "unset" elsewhere on the
  panel's own Settings page (e.g. "Pump back pressure: 1000 / 2147483647").

  A `pump_state` field (1/0) also shows up on the single event immediately following a pump state
  change - confirmed by live testing:

  ```
  -> GET /control?device=pump&state=on&zone=1&time=30
  <- event: new_readings / data: {"pump_state":1, ...}
  -> GET /control?device=pump&state=off&zone=1
  <- event: new_readings / data: {"pump_state":0, ...}
  ```

  It doesn't appear on every event, only on the one right after a change, and it's global (one
  pump, no per-zone breakdown) - see `binary_sensor.pump_running` above.

- `GET /w1`, `GET /w2` — Zone 1 / Zone 2 settings pages. The "Water now" buttons on these pages are
  plain links: `/control?device=pump&state=on&zone={1|2}&time={10|20|30|60|300}` (seconds). This
  integration's zone switches use the same call with a configurable duration, and call
  `state=off&zone={1|2}` to stop early — confirmed working by live testing: turning a zone on for 30s
  and calling `state=off` after ~15s produced an immediate `pump_state:0` event and updated the
  zone's "Last watered" timestamp, rather than waiting out the full 30 seconds.
  `/control?do=clear1` / `clear2` clears the "last watered" timestamp shown on those pages.

- `GET /x1`, `GET /x2`, `GET /x3` — Aux relay settings pages. Each has an on/off toggle wired to
  `/control?do=x1On` / `/control?do=x1Off` (and `x2`/`x3` equivalents) via a small inline
  `XMLHttpRequest` in the page's own JS — this is exactly what the Aux switches in this integration
  call. `/control?do=clear_x1` (etc.) clears that aux's "last run" timestamp.

- `GET /settings` — device settings and system info page. Used once at setup to read the panel's
  Device ID (`Device ID: <div>...</div>` in the page HTML) so the config entry has a stable unique
  ID, and the firmware version for diagnostics.

- `GET /hbus-devices` — lists wired sensors on the panel's 3-pin sensor bus. Confirms the wired
  temperature probe is a "Silver bullet temperature sensor" and that zone valves are driven as
  "Latching valve controller" devices on the same bus.

The zone `state=on`/`state=off` sequence above and the aux `On`/`Off` toggles have both been
exercised against real hardware; everything else (settings parsing, sensor field mapping) comes
from reading the panel's own UI markup rather than live testing. If your firmware behaves
differently, please open an issue with what you're seeing.

## Development

```bash
pip install -r requirements_test.txt
pytest
ruff check custom_components tests
```

CI runs lint, tests (on the Python versions Home Assistant currently supports), `hassfest`, and
HACS repository validation on every push and pull request. Every push to `main` that passes CI
automatically cuts a new GitHub Release, which HACS picks up as an available update.

## License

[MIT](LICENSE)
