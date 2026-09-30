"""Binary sensor entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import GrillEntity, ProbeEntity
from .kitchen.estimator import ProbePhase
from .kitchen.manager import GrillState, KitchenManager, ProbeState

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    kitchen = entry.runtime_data.kitchen
    for grill_id, grill in kitchen.grills.items():
        async_add_entities(
            [ChamberDeviationBinarySensor(kitchen, grill)], config_subentry_id=grill_id
        )
    for probe_id, probe in kitchen.probes.items():
        async_add_entities(
            [TargetReachedBinarySensor(kitchen, probe)], config_subentry_id=probe_id
        )


class ChamberDeviationBinarySensor(GrillEntity, BinarySensorEntity):
    """On when the chamber temperature leaves the tolerated range."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "chamber_deviation")

    @property
    def is_on(self) -> bool:
        """Return True if the chamber is out of range."""
        return self.grill.chamber_deviation


class TargetReachedBinarySensor(ProbeEntity, BinarySensorEntity):
    """On when the probe has reached its target temperature."""

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "target_reached")

    @property
    def is_on(self) -> bool:
        """Return True if the target was reached."""
        return self.probe.phase in (ProbePhase.TARGET_REACHED, ProbePhase.RESTING)
