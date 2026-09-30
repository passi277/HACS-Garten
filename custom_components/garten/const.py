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
SUBENTRY_POOL: Final = "pool"

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

# Pool subentry data keys
CONF_POOL_PUMP: Final = "pump_entity"
CONF_POOL_POWER: Final = "power_entity"
CONF_POOL_TEMPERATURE: Final = "temperature_entity"
CONF_POOL_PH: Final = "ph_entity"
CONF_POOL_ORP: Final = "orp_entity"
CONF_POOL_CHLORINE: Final = "chlorine_entity"
CONF_POOL_SALT: Final = "salt_entity"
CONF_POOL_LAST_MEASUREMENT: Final = "last_measurement_entity"
CONF_POOL_GUIDANCE: Final = "guidance_entity"
CONF_POOL_RECOMMENDED_RUNTIME: Final = "recommended_runtime_entity"
CONF_POOL_SOLAR_SURPLUS: Final = "solar_surplus_entity"

DEFAULT_CHAMBER_TOLERANCE: Final = 15
DEFAULT_BACKWASH_INTERVAL_H: Final = 50
DEFAULT_BACKWASH_MAX_DAYS: Final = 14
DEFAULT_ELECTRICITY_PRICE: Final = 0.30
MEASUREMENT_STALE_HOURS: Final = 12

# Select option for a probe that is not attached to any grill
NO_GRILL: Final = "none"

EVENT_KITCHEN: Final = f"{DOMAIN}_kitchen_event"
EVENT_POOL: Final = f"{DOMAIN}_pool_event"

# Dashboard card served by the integration
FRONTEND_URL_BASE: Final = f"/{DOMAIN}_static"
POOL_CARD_FILE: Final = "garten-pool-card.js"

# Version 1 only (migrated to grills and probes in version 2)
LEGACY_SUBENTRY_KITCHEN: Final = "kitchen"
LEGACY_CONF_PROBES: Final = "probes"
LEGACY_CONF_PROBE_NAME: Final = "name"
