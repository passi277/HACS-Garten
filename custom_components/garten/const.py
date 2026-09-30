"""Constants for the Garten integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "garten"
NAME: Final = "Garten"
MANUFACTURER: Final = "Garten"

STORAGE_VERSION: Final = 1

# Main entry data
CONF_OUTDOOR_TEMPERATURE: Final = "outdoor_temperature_entity"

SUBENTRY_GRILL: Final = "grill"
SUBENTRY_PROBE: Final = "probe"

# Grill subentry data keys
CONF_GRILL_TYPE: Final = "grill_type"
CONF_CHAMBER_ENTITY: Final = "chamber_entity"
CONF_CHAMBER_TOLERANCE: Final = "chamber_tolerance"
CONF_CAMERA: Final = "camera_entity"
CONF_LIGHT: Final = "light_entity"
CONF_POWER_SWITCH: Final = "power_switch_entity"

# Probe subentry data keys
CONF_PROBE_CORE: Final = "core_entity"
CONF_PROBE_AMBIENT: Final = "ambient_entity"

DEFAULT_CHAMBER_TOLERANCE: Final = 15

# Select option for a probe that is not attached to any grill
NO_GRILL: Final = "none"

EVENT_KITCHEN: Final = f"{DOMAIN}_kitchen_event"

# Version 1 only (migrated to grills and probes in version 2)
LEGACY_SUBENTRY_KITCHEN: Final = "kitchen"
LEGACY_CONF_PROBES: Final = "probes"
LEGACY_CONF_PROBE_NAME: Final = "name"
