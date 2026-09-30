"""Number entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import GrillEntity, PoolEntity, ProbeEntity
from .kitchen.manager import GrillState, KitchenManager, ProbeState
from .pool.manager import PoolManager

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
    for pool_id, pool in entry.runtime_data.pools.items():
        async_add_entities(
            [
                BackwashIntervalNumber(pool),
                BackwashMaxDaysNumber(pool),
                ElectricityPriceNumber(pool),
            ],
            config_subentry_id=pool_id,
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


class _PoolSettingNumber(PoolEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX


class BackwashIntervalNumber(_PoolSettingNumber):
    """Pump hours after which a backwash is due."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_native_min_value = 5
    _attr_native_max_value = 500
    _attr_native_step = 1

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "backwash_interval")

    @property
    def native_value(self) -> float:
        """Return the interval."""
        return self.pool.backwash_interval_h

    async def async_set_native_value(self, value: float) -> None:
        """Set the interval."""
        self.pool.set_backwash_interval(value)


class BackwashMaxDaysNumber(_PoolSettingNumber):
    """Days after which a backwash is due regardless of pump hours."""

    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_native_min_value = 1
    _attr_native_max_value = 90
    _attr_native_step = 1

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "backwash_max_days")

    @property
    def native_value(self) -> float:
        """Return the maximum days."""
        return self.pool.backwash_max_days

    async def async_set_native_value(self, value: float) -> None:
        """Set the maximum days."""
        self.pool.set_backwash_max_days(value)


class ElectricityPriceNumber(_PoolSettingNumber):
    """Electricity price used for cost and savings."""

    _attr_native_unit_of_measurement = "EUR/kWh"
    _attr_native_min_value = 0
    _attr_native_max_value = 2
    _attr_native_step = 0.01

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "electricity_price")

    @property
    def native_value(self) -> float:
        """Return the price."""
        return self.pool.price

    async def async_set_native_value(self, value: float) -> None:
        """Set the price."""
        self.pool.set_price(value)
