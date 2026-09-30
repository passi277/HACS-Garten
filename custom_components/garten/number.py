"""Number entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import KitchenEntity, ProbeEntity
from .kitchen.controller import KitchenController, Probe

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    for subentry_id, controller in entry.runtime_data.kitchens.items():
        entities: list[NumberEntity] = [ChamberTargetNumber(controller)]
        entities.extend(ProbeTargetNumber(controller, p) for p in controller.probes)
        async_add_entities(entities, config_subentry_id=subentry_id)


class _TemperatureNumber(NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0


class ChamberTargetNumber(KitchenEntity, _TemperatureNumber):
    """Desired temperature of the grill / smoker chamber."""

    _attr_native_max_value = 450
    _attr_native_step = 5

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "chamber_target")

    @property
    def native_value(self) -> float | None:
        """Return the chamber target."""
        return self.controller.chamber_target

    async def async_set_native_value(self, value: float) -> None:
        """Set the chamber target."""
        self.controller.set_chamber_target(value)


class ProbeTargetNumber(ProbeEntity, _TemperatureNumber):
    """Target core temperature of a probe."""

    _attr_native_max_value = 120
    _attr_native_step = 1

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "target")

    @property
    def native_value(self) -> float:
        """Return the target core temperature."""
        return self.probe.target

    async def async_set_native_value(self, value: float) -> None:
        """Set the target core temperature."""
        self.controller.set_target(self.probe.index, value)
