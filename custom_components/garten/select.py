"""Select entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .const import NO_GRILL
from .entity import ProbeEntity
from .kitchen.manager import KitchenManager, ProbeState
from .kitchen.profiles import PROFILE_OPTIONS

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    kitchen = entry.runtime_data.kitchen
    for probe_id, probe in kitchen.probes.items():
        async_add_entities(
            [ProbeGrillSelect(kitchen, probe), ProbeProfileSelect(kitchen, probe)],
            config_subentry_id=probe_id,
        )


class ProbeGrillSelect(ProbeEntity, SelectEntity):
    """Grill the probe is currently used on; attaching starts a session."""

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "grill")
        self._attr_options = [
            NO_GRILL,
            *sorted(g.name for g in manager.grills.values()),
        ]

    @property
    def current_option(self) -> str:
        """Return the grill the probe is attached to."""
        grill = self.manager.grills.get(self.probe.grill_id or "")
        return grill.name if grill else NO_GRILL

    async def async_select_option(self, option: str) -> None:
        """Attach the probe to a grill or detach it."""
        grill = self.manager.grill_by_name(option)
        self.manager.assign_probe(
            self.probe.subentry_id, grill.subentry_id if grill else None
        )


class ProbeProfileSelect(ProbeEntity, SelectEntity):
    """Food the probe is in; sets the target core temperature."""

    _attr_options = PROFILE_OPTIONS

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "profile")

    @property
    def current_option(self) -> str:
        """Return the selected food profile."""
        return self.probe.profile

    async def async_select_option(self, option: str) -> None:
        """Select a food profile."""
        self.manager.set_profile(self.probe.subentry_id, option)
