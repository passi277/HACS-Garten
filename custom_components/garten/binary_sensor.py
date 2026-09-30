"""Binary sensor entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import KitchenEntity, ProbeEntity
from .kitchen.controller import KitchenController, Probe
from .kitchen.estimator import ProbePhase

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    for subentry_id, controller in entry.runtime_data.kitchens.items():
        entities: list[BinarySensorEntity] = [
            TargetReachedBinarySensor(controller, p) for p in controller.probes
        ]
        if any(p.ambient_entity for p in controller.probes):
            entities.append(ChamberDeviationBinarySensor(controller))
        async_add_entities(entities, config_subentry_id=subentry_id)


class ChamberDeviationBinarySensor(KitchenEntity, BinarySensorEntity):
    """On when the chamber temperature leaves the tolerated range."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "chamber_deviation")

    @property
    def is_on(self) -> bool:
        """Return True if the chamber is out of range."""
        return self.controller.chamber_deviation


class TargetReachedBinarySensor(ProbeEntity, BinarySensorEntity):
    """On when the probe has reached its target temperature."""

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "target_reached")

    @property
    def is_on(self) -> bool:
        """Return True if the target was reached."""
        return self.probe.phase in (ProbePhase.TARGET_REACHED, ProbePhase.RESTING)
