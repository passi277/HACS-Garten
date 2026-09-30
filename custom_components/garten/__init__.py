"""The Garten integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CAMERA,
    CONF_CHAMBER_TOLERANCE,
    CONF_GRILL_TYPE,
    CONF_LIGHT,
    CONF_POWER_SWITCH,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    LEGACY_CONF_PROBE_NAME,
    LEGACY_CONF_PROBES,
    LEGACY_SUBENTRY_KITCHEN,
    SUBENTRY_GRILL,
    SUBENTRY_PROBE,
)
from .kitchen.manager import KitchenManager
from .kitchen.profiles import (
    DEFAULT_TARGET,
    GRILL_CHAMBER_DEFAULTS,
    LEGACY_METHOD_GRILL_TYPES,
    PROFILE_CUSTOM,
    GrillType,
)
from .storage import GartenStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


@dataclass
class GartenData:
    """Runtime data of a Garten config entry."""

    store: GartenStore
    kitchen: KitchenManager


type GartenConfigEntry = ConfigEntry[GartenData]


async def async_setup_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> bool:
    """Set up Garten from a config entry."""
    store = GartenStore(hass, entry.entry_id)
    await store.async_load()
    store.remove_except(set(entry.subentries))

    kitchen = KitchenManager(hass, entry, store)
    kitchen.async_start()
    entry.runtime_data = GartenData(store=store, kitchen=kitchen)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.kitchen.async_stop()
        await entry.runtime_data.store.async_flush()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> None:
    """Delete stored data when the integration is removed."""
    await GartenStore(hass, entry.entry_id).async_remove()


async def _async_update_listener(hass: HomeAssistant, entry: GartenConfigEntry) -> None:
    """Reload when settings or subentries (grills, probes) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _unique_title(title: str, taken: set[str]) -> str:
    candidate, number = title, 2
    while candidate.casefold() in taken:
        candidate = f"{title} {number}"
        number += 1
    taken.add(candidate.casefold())
    return candidate


async def async_migrate_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> bool:
    """Migrate old entries.

    Version 1 had "kitchen" subentries bundling one cooking method with its
    probes. Version 2 splits them into independent grill and probe subentries.
    """
    if entry.version > 2:
        return False
    if entry.version == 1:
        await _async_migrate_kitchens(hass, entry)
        hass.config_entries.async_update_entry(entry, version=2)
    _LOGGER.debug("Migrated Garten entry to version %s", entry.version)
    return True


async def _async_migrate_kitchens(hass: HomeAssistant, entry: ConfigEntry) -> None:
    store = GartenStore(hass, entry.entry_id)
    await store.async_load()
    grill_titles: set[str] = set()
    probe_titles: set[str] = set()
    probes_by_core: set[str] = set()

    for kitchen in list(entry.subentries.values()):
        if kitchen.subentry_type != LEGACY_SUBENTRY_KITCHEN:
            continue
        old: dict[str, Any] = store.get(kitchen.subentry_id)
        grill_type = LEGACY_METHOD_GRILL_TYPES.get(
            old.get("method", ""), GrillType.GAS_GRILL
        )
        grill_data: dict[str, Any] = {CONF_GRILL_TYPE: grill_type.value}
        for key in (CONF_CHAMBER_TOLERANCE, CONF_CAMERA, CONF_LIGHT, CONF_POWER_SWITCH):
            if key in kitchen.data:
                grill_data[key] = kitchen.data[key]
        grill = ConfigSubentry(
            data=MappingProxyType(grill_data),
            subentry_type=SUBENTRY_GRILL,
            title=_unique_title(kitchen.title, grill_titles),
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, grill)
        store.set(
            grill.subentry_id,
            {
                "chamber_target": old.get("chamber_target")
                or GRILL_CHAMBER_DEFAULTS[grill_type],
                "session_start": None,
                "sessions": old.get("sessions", []),
            },
        )

        old_probes: dict[str, Any] = old.get("probes", {})
        for old_probe in kitchen.data.get(LEGACY_CONF_PROBES, []):
            core = old_probe[CONF_PROBE_CORE]
            if core in probes_by_core:
                continue
            probes_by_core.add(core)
            probe_data = {CONF_PROBE_CORE: core}
            if ambient := old_probe.get(CONF_PROBE_AMBIENT):
                probe_data[CONF_PROBE_AMBIENT] = ambient
            probe = ConfigSubentry(
                data=MappingProxyType(probe_data),
                subentry_type=SUBENTRY_PROBE,
                title=_unique_title(old_probe[LEGACY_CONF_PROBE_NAME], probe_titles),
                unique_id=None,
            )
            hass.config_entries.async_add_subentry(entry, probe)
            stored = old_probes.get(core, {})
            store.set(
                probe.subentry_id,
                {
                    "grill_id": None,
                    "profile": stored.get("profile", PROFILE_CUSTOM),
                    "target": stored.get("target", DEFAULT_TARGET),
                    "fired": [],
                },
            )

        hass.config_entries.async_remove_subentry(entry, kitchen.subentry_id)
        _LOGGER.info(
            "Converted outdoor kitchen '%s' into grill '%s'", kitchen.title, grill.title
        )

    store.remove_except(set(entry.subentries))
    await store.async_flush()
