"""Runtime state of one outdoor kitchen (one config subentry)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from ..const import (
    CONF_CHAMBER_TOLERANCE,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    CONF_PROBE_NAME,
    CONF_PROBES,
    DEFAULT_CHAMBER_TOLERANCE,
    EVENT_KITCHEN,
)
from ..storage import GartenStore
from .estimator import ProbePhase, ProbeTracker
from .profiles import (
    DEFAULT_TARGET,
    FOOD_PROFILES,
    METHOD_CHAMBER_DEFAULTS,
    PROFILE_CUSTOM,
    STALL_METHODS,
    CookingMethod,
)

_LOGGER = logging.getLogger(__name__)

TICK_INTERVAL = timedelta(seconds=30)
MAX_SESSION_HISTORY = 20

EVENT_NEAR_DONE = "near_done"
EVENT_TARGET_REACHED = "target_reached"
EVENT_STALL = "stall_detected"
EVENT_CHAMBER_DEVIATION = "chamber_deviation"
EVENT_PROBE_OFFLINE = "probe_offline"
EVENT_SESSION_STARTED = "session_started"
EVENT_SESSION_ENDED = "session_ended"

KITCHEN_EVENT_TYPES = [
    EVENT_SESSION_STARTED,
    EVENT_NEAR_DONE,
    EVENT_TARGET_REACHED,
    EVENT_STALL,
    EVENT_CHAMBER_DEVIATION,
    EVENT_PROBE_OFFLINE,
    EVENT_SESSION_ENDED,
]


def read_temperature(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return the state of a temperature entity in °C, None if unavailable."""
    if not entity_id or (state := hass.states.get(entity_id)) is None:
        return None
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        value = float(state.state)
    except ValueError:
        return None
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN):
        value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    return value


@dataclass
class Probe:
    """Configuration and live state of one probe."""

    index: int
    name: str
    core_entity: str
    ambient_entity: str | None
    profile: str = PROFILE_CUSTOM
    target: float = DEFAULT_TARGET
    tracker: ProbeTracker = field(default_factory=ProbeTracker)
    available: bool = False
    phase: ProbePhase | None = None
    fired: set[str] = field(default_factory=set)

    @property
    def temperature(self) -> float | None:
        """Latest core temperature, None while the probe is offline."""
        return self.tracker.current if self.available else None


class KitchenController:
    """Track probes and cooking state of one outdoor kitchen."""

    def __init__(
        self, hass: HomeAssistant, subentry: ConfigSubentry, store: GartenStore
    ) -> None:
        self.hass = hass
        self.subentry = subentry
        self._store = store
        data = subentry.data
        self.tolerance: float = data.get(
            CONF_CHAMBER_TOLERANCE, DEFAULT_CHAMBER_TOLERANCE
        )
        self.probes: list[Probe] = [
            Probe(
                index=index,
                name=probe[CONF_PROBE_NAME],
                core_entity=probe[CONF_PROBE_CORE],
                ambient_entity=probe.get(CONF_PROBE_AMBIENT),
            )
            for index, probe in enumerate(data.get(CONF_PROBES, []))
        ]
        self.method = CookingMethod.OFF
        self.chamber_target: float | None = None
        self.chamber_temperature: float | None = None
        self.chamber_reached = False
        self.chamber_deviation = False
        self.session_start: datetime | None = None
        self.sessions: list[dict[str, Any]] = []
        self._listeners: list[CALLBACK_TYPE] = []
        self._event_listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._unsub_tick: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ setup

    @property
    def title(self) -> str:
        """Name of the kitchen."""
        return self.subentry.title

    @property
    def session_active(self) -> bool:
        """Return True while a cooking session runs."""
        return self.session_start is not None

    @callback
    def async_start(self) -> None:
        """Restore state and start listening to the source entities."""
        self._restore()
        entities = [p.core_entity for p in self.probes] + [
            p.ambient_entity for p in self.probes if p.ambient_entity
        ]
        if entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, entities, self._handle_source_change
                )
            )
        if self.session_active:
            self._start_tick()
        self._sample(notify=False)

    @callback
    def async_stop(self) -> None:
        """Stop listening."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._stop_tick()

    @callback
    def add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register a callback invoked whenever state changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def add_event_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> CALLBACK_TYPE:
        """Register a callback for kitchen events."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    # ---------------------------------------------------------------- actions

    @callback
    def set_method(self, method: CookingMethod) -> None:
        """Change the cooking method; starts or ends the session accordingly."""
        if method == self.method:
            return
        self.method = method
        default = METHOD_CHAMBER_DEFAULTS[method]
        self.chamber_target = default
        self.chamber_reached = False
        self.chamber_deviation = False
        if method == CookingMethod.OFF:
            if self.session_active:
                self.stop_session()
                return
        elif not self.session_active:
            self.start_session()
            return
        self._changed()

    @callback
    def set_chamber_target(self, value: float) -> None:
        """Set the desired cooking chamber temperature."""
        self.chamber_target = value
        self.chamber_reached = False
        self.chamber_deviation = False
        self._changed()

    @callback
    def set_profile(self, index: int, profile: str) -> None:
        """Select a food profile, which also sets the probe target."""
        probe = self.probes[index]
        probe.profile = profile
        if (food := FOOD_PROFILES.get(profile)) is not None:
            self._apply_target(probe, food.target)
        self._changed()

    @callback
    def set_target(self, index: int, value: float) -> None:
        """Override the target core temperature of a probe."""
        self._apply_target(self.probes[index], value)
        self._changed()

    @callback
    def start_session(self) -> None:
        """Start a new cooking session (restarts a running one)."""
        self.session_start = dt_util.utcnow()
        self.chamber_reached = False
        self.chamber_deviation = False
        for probe in self.probes:
            probe.tracker.reset()
            probe.fired.clear()
        self._start_tick()
        self._fire(EVENT_SESSION_STARTED)
        self._sample(notify=False)
        self._changed()

    @callback
    def stop_session(self) -> None:
        """End the running session and store it in the history."""
        if self.session_start is None:
            return
        end = dt_util.utcnow()
        record = {
            "start": self.session_start.isoformat(),
            "end": end.isoformat(),
            "duration_min": round((end - self.session_start).total_seconds() / 60),
            "method": self.method.value,
            "probes": [
                {
                    "name": p.name,
                    "profile": p.profile,
                    "target": p.target,
                    "max_temperature": p.tracker.peak,
                }
                for p in self.probes
            ],
        }
        self.sessions = [record, *self.sessions][:MAX_SESSION_HISTORY]
        self.session_start = None
        self.chamber_reached = False
        self.chamber_deviation = False
        self._stop_tick()
        self._fire(EVENT_SESSION_ENDED, duration_min=record["duration_min"])
        self._changed()

    # ------------------------------------------------------------ derived data

    @property
    def session_duration(self) -> timedelta | None:
        """Time since the session started."""
        if self.session_start is None:
            return None
        return dt_util.utcnow() - self.session_start

    @property
    def last_session(self) -> dict[str, Any] | None:
        """Most recently finished session."""
        return self.sessions[0] if self.sessions else None

    # --------------------------------------------------------------- internals

    def _apply_target(self, probe: Probe, value: float) -> None:
        value = float(value)
        if value != probe.target:
            probe.target = value
            probe.tracker.reached = False
            probe.fired.discard(EVENT_NEAR_DONE)
            probe.fired.discard(EVENT_TARGET_REACHED)

    def _start_tick(self) -> None:
        if self._unsub_tick is None:
            self._unsub_tick = async_track_time_interval(
                self.hass, self._handle_tick, TICK_INTERVAL
            )

    def _stop_tick(self) -> None:
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:
        self._sample()

    @callback
    def _handle_tick(self, now: datetime) -> None:
        # Periodic sampling keeps the history alive while temperatures plateau
        # (sources do not report unchanged values).
        self._sample()

    def _sample(self, notify: bool = True) -> None:
        ts = dt_util.utcnow().timestamp()
        for probe in self.probes:
            temp = read_temperature(self.hass, probe.core_entity)
            was_available = probe.available
            probe.available = temp is not None
            if temp is not None:
                probe.tracker.add(ts, temp)
            elif was_available and self.session_active:
                self._fire(EVENT_PROBE_OFFLINE, probe)
        self.chamber_temperature = next(
            (
                t
                for p in self.probes
                if (t := read_temperature(self.hass, p.ambient_entity)) is not None
            ),
            None,
        )
        if notify:
            self._changed(save=False)
        else:
            self._evaluate()

    def _evaluate(self) -> None:
        active = self.session_active
        chamber_diff: float | None = None
        if (
            active
            and self.chamber_target is not None
            and self.chamber_temperature is not None
        ):
            chamber_diff = self.chamber_temperature - self.chamber_target
            if abs(chamber_diff) <= self.tolerance:
                self.chamber_reached = True
        deviation = (
            chamber_diff is not None
            and self.chamber_reached
            and abs(chamber_diff) > self.tolerance
        )
        if deviation and not self.chamber_deviation:
            self._fire(
                EVENT_CHAMBER_DEVIATION,
                chamber_temperature=self.chamber_temperature,
                chamber_target=self.chamber_target,
            )
        self.chamber_deviation = deviation
        heating = chamber_diff is not None and not self.chamber_reached

        for probe in self.probes:
            if not probe.available:
                probe.phase = None
                continue
            if not active:
                probe.phase = ProbePhase.IDLE
                continue
            probe.phase = probe.tracker.phase(
                probe.target,
                stall_possible=self.method in STALL_METHODS,
                heating=heating,
            )
            if probe.phase == ProbePhase.NEAR_DONE:
                self._fire_once(probe, EVENT_NEAR_DONE)
            elif probe.phase == ProbePhase.STALL:
                self._fire_once(probe, EVENT_STALL)
            elif probe.phase in (ProbePhase.TARGET_REACHED, ProbePhase.RESTING):
                self._fire_once(probe, EVENT_TARGET_REACHED)

    def _fire_once(self, probe: Probe, event_type: str) -> None:
        if event_type not in probe.fired:
            probe.fired.add(event_type)
            self._fire(event_type, probe)
            self._save()

    def _fire(self, event_type: str, probe: Probe | None = None, **extra: Any) -> None:
        data: dict[str, Any] = {"kitchen": self.title, "method": self.method.value}
        if probe is not None:
            data |= {
                "probe": probe.name,
                "profile": probe.profile,
                "temperature": probe.tracker.current,
                "target": probe.target,
            }
        data |= extra
        _LOGGER.debug("%s: %s %s", self.title, event_type, data)
        self.hass.bus.async_fire(
            EVENT_KITCHEN,
            {"type": event_type, "subentry_id": self.subentry.subentry_id, **data},
        )
        for listener in list(self._event_listeners):
            listener(event_type, data)

    def _changed(self, save: bool = True) -> None:
        self._evaluate()
        if save:
            self._save()
        for listener in list(self._listeners):
            listener()

    def _save(self) -> None:
        self._store.set(
            self.subentry.subentry_id,
            {
                "method": self.method.value,
                "chamber_target": self.chamber_target,
                "session_start": (
                    self.session_start.isoformat() if self.session_start else None
                ),
                "probes": {
                    p.core_entity: {
                        "profile": p.profile,
                        "target": p.target,
                        "fired": sorted(p.fired),
                    }
                    for p in self.probes
                },
                "sessions": self.sessions,
            },
        )

    def _restore(self) -> None:
        data = self._store.get(self.subentry.subentry_id)
        if not data:
            return
        try:
            self.method = CookingMethod(data.get("method", CookingMethod.OFF))
        except ValueError:
            self.method = CookingMethod.OFF
        self.chamber_target = data.get("chamber_target")
        if start := data.get("session_start"):
            self.session_start = dt_util.parse_datetime(start)
        stored_probes = data.get("probes", {})
        for probe in self.probes:
            if stored := stored_probes.get(probe.core_entity):
                probe.profile = stored.get("profile", PROFILE_CUSTOM)
                probe.target = stored.get("target", DEFAULT_TARGET)
                if self.session_active:
                    probe.fired = set(stored.get("fired", []))
                    probe.tracker.reached = EVENT_TARGET_REACHED in probe.fired
        self.sessions = data.get("sessions", [])
