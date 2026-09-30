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
from .entity import GrillEntity, ProbeEntity
from .kitchen.manager import GrillState, KitchenManager, ProbeState

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    kitchen = entry.runtime_data.kitchen
    for grill_id, grill in kitchen.grills.items():
        async_add_entities(
            [ChamberTargetNumber(kitchen, grill)], config_subentry_id=grill_id
        )
    for probe_id, probe in kitchen.probes.items():
        async_add_entities(
            [ProbeTargetNumber(kitchen, probe)], config_subentry_id=probe_id
        )


class _TemperatureNumber(NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0


class ChamberTargetNumber(GrillEntity, _TemperatureNumber):
    """Desired temperature of the grill chamber."""

    _attr_native_max_value = 500
    _attr_native_step = 5

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "chamber_target")

    @property
    def native_value(self) -> float | None:
        """Return the chamber target."""
        return self.grill.chamber_target

    async def async_set_native_value(self, value: float) -> None:
        """Set the chamber target."""
        self.manager.set_chamber_target(self.grill.subentry_id, value)


class ProbeTargetNumber(ProbeEntity, _TemperatureNumber):
    """Target core temperature of a probe."""

    _attr_native_max_value = 120
    _attr_native_step = 1

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "target")

    @property
    def native_value(self) -> float:
        """Return the target core temperature."""
        return self.probe.target

    async def async_set_native_value(self, value: float) -> None:
        """Set the target core temperature."""
        self.manager.set_target(self.probe.subentry_id, value)
