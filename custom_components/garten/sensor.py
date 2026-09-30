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
from .entity import KitchenEntity, ProbeEntity
from .kitchen.controller import KitchenController, Probe
from .kitchen.estimator import ProbePhase

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    for subentry_id, controller in entry.runtime_data.kitchens.items():
        entities: list[SensorEntity] = [SessionDurationSensor(controller)]
        if any(p.ambient_entity for p in controller.probes):
            entities.append(ChamberTemperatureSensor(controller))
        for probe in controller.probes:
            entities.extend(
                (
                    CoreTemperatureSensor(controller, probe),
                    ProgressSensor(controller, probe),
                    RemainingTimeSensor(controller, probe),
                    PhaseSensor(controller, probe),
                )
            )
        async_add_entities(entities, config_subentry_id=subentry_id)


class SessionDurationSensor(KitchenEntity, SensorEntity):
    """Minutes since the cooking session started."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "session_duration")

    @property
    def native_value(self) -> int | None:
        """Return the session duration."""
        if (duration := self.controller.session_duration) is None:
            return None
        return int(duration.total_seconds() // 60)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose session start and the last finished session."""
        start = self.controller.session_start
        return {
            "session_start": start.isoformat() if start else None,
            "last_session": self.controller.last_session,
        }


class ChamberTemperatureSensor(KitchenEntity, SensorEntity):
    """Cooking chamber temperature measured by the probes' ambient sensors."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 0

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "chamber_temperature")

    @property
    def native_value(self) -> float | None:
        """Return the chamber temperature."""
        return self.controller.chamber_temperature


class CoreTemperatureSensor(ProbeEntity, SensorEntity):
    """Core temperature of a probe (mirrored from the source sensor)."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "core_temperature")

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


class ProgressSensor(ProbeEntity, SensorEntity):
    """Progress from start temperature to target in percent."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "progress")

    @property
    def native_value(self) -> float | None:
        """Return the progress."""
        if not self.controller.session_active or not self.probe.available:
            return None
        return self.probe.tracker.progress(self.probe.target)


class RemainingTimeSensor(ProbeEntity, SensorEntity):
    """Estimated minutes until the target temperature is reached."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "remaining_time")

    @property
    def native_value(self) -> float | None:
        """Return the estimated remaining time."""
        if not self.controller.session_active or not self.probe.available:
            return None
        return self.probe.tracker.remaining_minutes(self.probe.target)


class PhaseSensor(ProbeEntity, SensorEntity):
    """Cooking phase of a probe."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [p.value for p in ProbePhase]

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "phase")

    @property
    def native_value(self) -> str | None:
        """Return the phase."""
        return self.probe.phase.value if self.probe.phase else None
