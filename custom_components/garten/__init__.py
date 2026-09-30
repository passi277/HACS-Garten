"""The Garten integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import SUBENTRY_KITCHEN
from .kitchen.controller import KitchenController
from .storage import GartenStore

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
    kitchens: dict[str, KitchenController] = field(default_factory=dict)


type GartenConfigEntry = ConfigEntry[GartenData]


async def async_setup_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> bool:
    """Set up Garten from a config entry."""
    store = GartenStore(hass, entry.entry_id)
    await store.async_load()
    data = GartenData(store=store)

    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_KITCHEN:
            controller = KitchenController(hass, subentry, store)
            controller.async_start()
            data.kitchens[subentry.subentry_id] = controller
    store.remove_except(set(entry.subentries))
    _async_remove_stale_probe_entities(hass, entry, data)

    entry.runtime_data = data
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for controller in entry.runtime_data.kitchens.values():
            controller.async_stop()
        await entry.runtime_data.store.async_flush()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: GartenConfigEntry) -> None:
    """Delete stored data when the integration is removed."""
    await GartenStore(hass, entry.entry_id).async_remove()


@callback
def _async_remove_stale_probe_entities(
    hass: HomeAssistant, entry: GartenConfigEntry, data: GartenData
) -> None:
    """Remove entities of probes that were removed from a kitchen."""
    ent_reg = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        controller = data.kitchens.get(reg_entry.config_subentry_id or "")
        if controller is None:
            continue
        rest = reg_entry.unique_id.removeprefix(f"{controller.subentry.subentry_id}_")
        if not rest.startswith("probe"):
            continue
        index = rest.removeprefix("probe").split("_", 1)[0]
        if index.isdigit() and int(index) >= len(controller.probes):
            ent_reg.async_remove(reg_entry.entity_id)


async def _async_update_listener(hass: HomeAssistant, entry: GartenConfigEntry) -> None:
    """Reload when areas (subentries) are added, changed or removed."""
    await hass.config_entries.async_reload(entry.entry_id)
