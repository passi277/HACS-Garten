"""Constants for the Garten integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "garten"
NAME: Final = "Garten"
MANUFACTURER: Final = "Garten"

STORAGE_VERSION: Final = 1

SUBENTRY_KITCHEN: Final = "kitchen"

# Kitchen subentry data keys
CONF_PROBES: Final = "probes"
CONF_PROBE_NAME: Final = "name"
CONF_PROBE_CORE: Final = "core_entity"
CONF_PROBE_AMBIENT: Final = "ambient_entity"
CONF_CAMERA: Final = "camera_entity"
CONF_LIGHT: Final = "light_entity"
CONF_POWER_SWITCH: Final = "power_switch_entity"
CONF_CHAMBER_TOLERANCE: Final = "chamber_tolerance"

MAX_PROBES: Final = 4
DEFAULT_CHAMBER_TOLERANCE: Final = 15

EVENT_KITCHEN: Final = f"{DOMAIN}_kitchen_event"
