"""Constants for the Harvst irrigation control panel integration."""
from __future__ import annotations

DOMAIN = "harvst"

# CONF_HOST / CONF_USERNAME / CONF_PASSWORD come from homeassistant.const;
# this integration only defines the option keys that are its own.
CONF_ZONE_RUNTIME = "zone_max_runtime"

DEFAULT_ZONE_MAX_RUNTIME = 3600  # seconds; safety cap sent as `time=` on switch turn_on

# Sentinel value the control panel uses on the /events SSE feed to mean
# "sensor not connected / no reading available".
UNAVAILABLE_SENTINEL = -13

# The `cc` (current draw) channel uses INT32_MIN instead of -13.
CURRENT_UNAVAILABLE_SENTINEL = -2147483647

# Number of physical zones and aux relays exposed by the control panel UI.
ZONE_COUNT = 2
AUX_COUNT = 3

MANUFACTURER = "Harvst"
MODEL = "Irrigation Control Panel"

UPDATE_EVENT = "new_readings"
