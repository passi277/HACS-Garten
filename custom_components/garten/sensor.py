"""Sensor entities for the Garten integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .const import CONF_POOL_POWER, CONF_POOL_SOLAR_SURPLUS
from .entity import GrillEntity, PoolEntity, ProbeEntity
from .kitchen.estimator import ProbePhase
from .kitchen.manager import GrillState, KitchenManager, ProbeState
from .pool.energy import EnergyMeter
from .pool.manager import PoolManager
from .pool.quality import RANGES, Quality

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    kitchen = entry.runtime_data.kitchen
    for grill_id, grill in kitchen.grills.items():
        grill_entities: list[SensorEntity] = [
            ChamberTemperatureSensor(kitchen, grill),
            AssignedProbesSensor(kitchen, grill),
            SessionDurationSensor(kitchen, grill),
        ]
        if kitchen.outdoor_entity:
            grill_entities.append(OutdoorTemperatureSensor(kitchen, grill))
        async_add_entities(grill_entities, config_subentry_id=grill_id)
    for probe_id, probe in kitchen.probes.items():
        probe_entities: list[SensorEntity] = [
            CoreTemperatureSensor(kitchen, probe),
            ProgressSensor(kitchen, probe),
            RemainingTimeSensor(kitchen, probe),
            PhaseSensor(kitchen, probe),
        ]
        if probe.ambient_entity:
            probe_entities.append(AmbientTemperatureSensor(kitchen, probe))
        async_add_entities(probe_entities, config_subentry_id=probe_id)
    for pool_id, pool in entry.runtime_data.pools.items():
        async_add_entities(_pool_sensors(pool), config_subentry_id=pool_id)


def _pool_sensors(pool: PoolManager) -> list[SensorEntity]:
    # The water quality sensor always exists: the dashboard card is bound to it.
    entities: list[SensorEntity] = [
        WaterQualitySensor(pool),
        PumpRuntimeTodaySensor(pool),
        BackwashHoursSensor(pool),
        LastBackwashSensor(pool),
    ]
    entities.extend(ParameterStatusSensor(pool, p) for p in pool.parameters)
    if pool.source(CONF_POOL_POWER):
        entities.extend((EnergyTodaySensor(pool), EnergyYearSensor(pool)))
        entities.append(CostTodaySensor(pool))
        if pool.source(CONF_POOL_SOLAR_SURPLUS):
            entities.extend((SolarShareTodaySensor(pool), SolarShareYearSensor(pool)))
            entities.append(SolarSavingsYearSensor(pool))
    return entities


class _TemperatureSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1


# --------------------------------------------------------------------- grill


class ChamberTemperatureSensor(GrillEntity, _TemperatureSensor):
    """Grill chamber temperature (own sensor, else ambient of attached probes)."""

    _attr_suggested_display_precision = 0

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "chamber_temperature")

    @property
    def native_value(self) -> float | None:
        """Return the chamber temperature."""
        return self.grill.chamber_temperature


class OutdoorTemperatureSensor(GrillEntity, _TemperatureSensor):
    """Outdoor (weather) temperature shown next to the grill."""

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "outdoor_temperature")

    @property
    def native_value(self) -> float | None:
        """Return the outdoor temperature."""
        return self.manager.outdoor_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the source entity."""
        return {"source": self.manager.outdoor_entity}


class AssignedProbesSensor(GrillEntity, SensorEntity):
    """Number of probes attached to the grill."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "assigned_probes")

    @property
    def native_value(self) -> int:
        """Return the number of attached probes."""
        return len(self.manager.probes_of(self.grill.subentry_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the names of the attached probes."""
        return {
            "probes": [p.name for p in self.manager.probes_of(self.grill.subentry_id)]
        }


class SessionDurationSensor(GrillEntity, SensorEntity):
    """Minutes since the cooking session started."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "session_duration")

    @property
    def native_value(self) -> int | None:
        """Return the session duration."""
        if (duration := self.grill.session_duration) is None:
            return None
        return int(duration.total_seconds() // 60)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose grill type, session start, last session and linked devices."""
        start = self.grill.session_start
        return {
            "grill_type": self.grill.grill_type.value,
            "session_start": start.isoformat() if start else None,
            "last_session": self.grill.last_session,
            **self.grill.linked_entities,
        }


# --------------------------------------------------------------------- probe


class CoreTemperatureSensor(ProbeEntity, _TemperatureSensor):
    """Core temperature of the probe."""

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "core_temperature")

    @property
    def native_value(self) -> float | None:
        """Return the core temperature."""
        return self.probe.temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the source entity and the rate of rise."""
        slope = self.probe.tracker.slope() if self.probe.available else None
        return {
            "source": self.probe.core_entity,
            "rate_per_minute": round(slope, 2) if slope is not None else None,
        }


class AmbientTemperatureSensor(ProbeEntity, _TemperatureSensor):
    """Ambient temperature measured by the probe (e.g. at the grill grate)."""

    _attr_suggested_display_precision = 0

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "ambient_temperature")

    @property
    def native_value(self) -> float | None:
        """Return the ambient temperature."""
        return self.probe.ambient_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the source entity."""
        return {"source": self.probe.ambient_entity}


class _SessionProbeSensor(ProbeEntity, SensorEntity):
    """Value that only exists while the probe is in an active session."""

    @property
    def _in_session(self) -> bool:
        grill = self.manager.grills.get(self.probe.grill_id or "")
        return grill is not None and grill.session_active and self.probe.available


class ProgressSensor(_SessionProbeSensor):
    """Progress from start temperature to target in percent."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "progress")

    @property
    def native_value(self) -> float | None:
        """Return the progress."""
        if not self._in_session:
            return None
        return self.probe.tracker.progress(self.probe.target)


class RemainingTimeSensor(_SessionProbeSensor):
    """Estimated minutes until the target temperature is reached."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "remaining_time")

    @property
    def native_value(self) -> float | None:
        """Return the estimated remaining time."""
        if not self._in_session:
            return None
        return self.probe.tracker.remaining_minutes(self.probe.target)


class PhaseSensor(ProbeEntity, SensorEntity):
    """Cooking phase of the probe."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [p.value for p in ProbePhase]

    def __init__(self, manager: KitchenManager, probe: ProbeState) -> None:
        super().__init__(manager, probe, "phase")

    @property
    def native_value(self) -> str | None:
        """Return the phase."""
        return self.probe.phase.value if self.probe.phase else None


# ---------------------------------------------------------------------- pool

QUALITY_OPTIONS = [q.value for q in Quality]


class WaterQualitySensor(PoolEntity, SensorEntity):
    """Overall water quality (worst of all rated values).

    Its attributes also carry everything the pool dashboard card needs.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = QUALITY_OPTIONS

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "water_quality")

    @property
    def native_value(self) -> str | None:
        """Return the overall rating."""
        return self.pool.quality.value if self.pool.quality else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose values, ranges and the entities used by the dashboard card."""
        pool = self.pool
        return {
            "pool_name": pool.name,
            "values": dict(pool.values),
            "ranges": {p: RANGES[p].as_list() for p in pool.parameters},
            "guidance": pool.guidance,
            "last_measurement": (
                pool.last_measurement.isoformat() if pool.last_measurement else None
            ),
            "card_entities": self._card_entities(),
            "card_sources": dict(pool.sources),
        }

    def _card_entities(self) -> dict[str, str]:
        registry = er.async_get(self.hass)
        return (
            {
                reg.translation_key: reg.entity_id
                for reg in er.async_entries_for_config_entry(
                    registry, self.registry_entry.config_entry_id
                )
                if reg.config_subentry_id == self.pool.subentry_id
                and reg.translation_key
            }
            if self.registry_entry
            else {}
        )


class ParameterStatusSensor(PoolEntity, SensorEntity):
    """Rating of one water value (pH, redox, chlorine, salt)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = QUALITY_OPTIONS

    def __init__(self, pool: PoolManager, parameter: str) -> None:
        super().__init__(pool, f"{parameter}_status")
        self.parameter = parameter

    @property
    def native_value(self) -> str | None:
        """Return the rating."""
        quality = self.pool.qualities.get(self.parameter)
        return quality.value if quality else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the value and the ok range."""
        limits = RANGES[self.parameter]
        return {
            "value": self.pool.values.get(self.parameter),
            "ok_min": limits.ok_min,
            "ok_max": limits.ok_max,
        }


class _HoursSensor(PoolEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_suggested_display_precision = 1


class PumpRuntimeTodaySensor(_HoursSensor):
    """Pump runtime today."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "runtime_today")

    @property
    def native_value(self) -> float:
        """Return the runtime in hours."""
        return round(self.pool.runtime_today_h, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the recommended runtime."""
        return {"recommended_runtime": self.pool.recommended_runtime_h}


class BackwashHoursSensor(_HoursSensor):
    """Pump hours since the last backwash."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "backwash_hours")

    @property
    def native_value(self) -> float:
        """Return the pump hours."""
        return round(self.pool.backwash_hours, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the backwash limits."""
        days = self.pool.days_since_backwash
        return {
            "interval_hours": self.pool.backwash_interval_h,
            "max_days": self.pool.backwash_max_days,
            "days_since_backwash": round(days, 1) if days is not None else None,
        }


class LastBackwashSensor(PoolEntity, SensorEntity):
    """When the filter was last backwashed."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "last_backwash")

    @property
    def native_value(self) -> datetime | None:
        """Return the last backwash."""
        return self.pool.last_backwash


class _EnergySensor(PoolEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2


class EnergyTodaySensor(_EnergySensor):
    """Pump energy today."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "energy_today")

    @property
    def native_value(self) -> float:
        """Return kWh today."""
        return round(self.pool.meter.day_kwh, 4)


class EnergyYearSensor(_EnergySensor):
    """Pump energy this year."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "energy_year")

    @property
    def native_value(self) -> float:
        """Return kWh this year."""
        return round(self.pool.meter.year_kwh, 3)


class _ShareSensor(PoolEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0


class SolarShareTodaySensor(_ShareSensor):
    """Share of today's pump energy covered by solar."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "solar_share_today")

    @property
    def native_value(self) -> float | None:
        """Return the solar share today."""
        meter = self.pool.meter
        return EnergyMeter.share(meter.day_kwh, meter.day_solar_kwh)


class SolarShareYearSensor(_ShareSensor):
    """Share of this year's pump energy covered by solar."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "solar_share_year")

    @property
    def native_value(self) -> float | None:
        """Return the solar share this year."""
        meter = self.pool.meter
        return EnergyMeter.share(meter.year_kwh, meter.year_solar_kwh)


class _MoneySensor(PoolEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2


class CostTodaySensor(_MoneySensor):
    """Grid electricity cost of the pump today."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "cost_today")

    @property
    def native_value(self) -> float:
        """Return the cost today."""
        return round(self.pool.cost_today, 4)


class SolarSavingsYearSensor(_MoneySensor):
    """Money saved this year by running the pump on solar."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "solar_savings_year")

    @property
    def native_value(self) -> float:
        """Return the savings this year."""
        return round(self.pool.savings_year, 2)
