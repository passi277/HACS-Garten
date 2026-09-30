"""Sensor entities for the Garten integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
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
