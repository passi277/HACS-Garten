"""Binary sensor entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .const import CONF_POOL_LAST_MEASUREMENT
from .entity import GrillEntity, PoolEntity, ProbeEntity
from .kitchen.estimator import ProbePhase
from .kitchen.manager import GrillState, KitchenManager, ProbeState
from .pool.manager import PoolManager

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
    for pool_id, pool in entry.runtime_data.pools.items():
        pool_entities: list[BinarySensorEntity] = [BackwashDueBinarySensor(pool)]
        if pool.source(CONF_POOL_LAST_MEASUREMENT):
            pool_entities.append(MeasurementStaleBinarySensor(pool))
        async_add_entities(pool_entities, config_subentry_id=pool_id)


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


class BackwashDueBinarySensor(PoolEntity, BinarySensorEntity):
    """On when the filter should be backwashed."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "backwash_due")

    @property
    def is_on(self) -> bool:
        """Return True if a backwash is due."""
        return self.pool.backwash_due


class MeasurementStaleBinarySensor(PoolEntity, BinarySensorEntity):
    """On when the last water measurement is too old."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "measurement_stale")

    @property
    def is_on(self) -> bool:
        """Return True if the measurement is stale."""
        return self.pool.stale
