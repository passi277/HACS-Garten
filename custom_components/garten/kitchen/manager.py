"""Runtime state of the outdoor kitchen: grills, probes and their assignment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
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

from ..const import (
    CONF_CAMERA,
    CONF_CHAMBER_ENTITY,
    CONF_CHAMBER_TOLERANCE,
    CONF_GRILL_TYPE,
    CONF_LIGHT,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_POWER_SWITCH,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    DEFAULT_CHAMBER_TOLERANCE,
    EVENT_KITCHEN,
    SUBENTRY_GRILL,
    SUBENTRY_PROBE,
)
from ..helpers import read_temperature
from ..storage import GartenStore
from .estimator import ProbePhase, ProbeTracker
from .profiles import (
    DEFAULT_TARGET,
    FOOD_PROFILES,
    GRILL_CHAMBER_DEFAULTS,
    PROFILE_CUSTOM,
    STALL_GRILL_TYPES,
    GrillType,
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

type EventListener = Callable[[str, dict[str, Any]], None]


@dataclass
class GrillState:
    """Configuration and live state of one grill."""

    subentry_id: str
    name: str
    grill_type: GrillType
    chamber_entity: str | None
    tolerance: float
    linked_entities: dict[str, str]
    chamber_target: float | None = None
    chamber_temperature: float | None = None
    chamber_reached: bool = False
    chamber_deviation: bool = False
    session_start: datetime | None = None
    sessions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def session_active(self) -> bool:
        """Return True while a cooking session runs."""
        return self.session_start is not None

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

    @property
    def heating(self) -> bool:
        """Return True while the chamber has not yet reached its target range."""
        return (
            self.session_active
            and self.chamber_target is not None
            and self.chamber_temperature is not None
            and not self.chamber_reached
        )


@dataclass
class ProbeState:
    """Configuration and live state of one probe."""

    subentry_id: str
    name: str
    core_entity: str
    ambient_entity: str | None
    grill_id: str | None = None
    profile: str = PROFILE_CUSTOM
    target: float = DEFAULT_TARGET
    tracker: ProbeTracker = field(default_factory=ProbeTracker)
    available: bool = False
    ambient_temperature: float | None = None
    phase: ProbePhase | None = None
    fired: set[str] = field(default_factory=set)

    @property
    def temperature(self) -> float | None:
        """Latest core temperature, None while the probe is offline."""
        return self.tracker.current if self.available else None


def _grill_from_subentry(subentry: ConfigSubentry) -> GrillState:
    data = subentry.data
    try:
        grill_type = GrillType(data.get(CONF_GRILL_TYPE, GrillType.OTHER))
    except ValueError:
        grill_type = GrillType.OTHER
    return GrillState(
        subentry_id=subentry.subentry_id,
        name=subentry.title,
        grill_type=grill_type,
        chamber_entity=data.get(CONF_CHAMBER_ENTITY),
        tolerance=data.get(CONF_CHAMBER_TOLERANCE, DEFAULT_CHAMBER_TOLERANCE),
        linked_entities={
            key: data[key]
            for key in (CONF_CAMERA, CONF_LIGHT, CONF_POWER_SWITCH)
            if data.get(key)
        },
        chamber_target=GRILL_CHAMBER_DEFAULTS[grill_type],
    )


def _probe_from_subentry(subentry: ConfigSubentry) -> ProbeState:
    return ProbeState(
        subentry_id=subentry.subentry_id,
        name=subentry.title,
        core_entity=subentry.data[CONF_PROBE_CORE],
        ambient_entity=subentry.data.get(CONF_PROBE_AMBIENT),
    )


class KitchenManager:
    """Track grills, probes and cook sessions of one Garten entry."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, store: GartenStore
    ) -> None:
        self.hass = hass
        self._store = store
        self.outdoor_entity: str | None = entry.data.get(CONF_OUTDOOR_TEMPERATURE)
        self.outdoor_temperature: float | None = None
        self.grills: dict[str, GrillState] = {
            s.subentry_id: _grill_from_subentry(s)
            for s in entry.subentries.values()
            if s.subentry_type == SUBENTRY_GRILL
        }
        self.probes: dict[str, ProbeState] = {
            s.subentry_id: _probe_from_subentry(s)
            for s in entry.subentries.values()
            if s.subentry_type == SUBENTRY_PROBE
        }
        self._listeners: list[CALLBACK_TYPE] = []
        self._event_listeners: dict[str, list[EventListener]] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._unsub_tick: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ setup

    @callback
    def async_start(self) -> None:
        """Restore state and start listening to the source entities."""
        self._restore()
        entities = {
            entity_id
            for entity_id in (
                self.outdoor_entity,
                *(g.chamber_entity for g in self.grills.values()),
                *(p.core_entity for p in self.probes.values()),
                *(p.ambient_entity for p in self.probes.values()),
            )
            if entity_id
        }
        if entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, sorted(entities), self._handle_source_change
                )
            )
        self._update_tick()
        self._sample(notify=False)

    @callback
    def async_stop(self) -> None:
        """Stop listening."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None

    @callback
    def add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register a callback invoked whenever state changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def add_event_listener(
        self, grill_id: str, listener: EventListener
    ) -> CALLBACK_TYPE:
        """Register a callback for events of one grill."""
        listeners = self._event_listeners.setdefault(grill_id, [])
        listeners.append(listener)
        return lambda: listeners.remove(listener)

    # ------------------------------------------------------------ derived data

    def probes_of(self, grill_id: str) -> list[ProbeState]:
        """Return the probes currently attached to a grill."""
        return [p for p in self.probes.values() if p.grill_id == grill_id]

    def grill_by_name(self, name: str) -> GrillState | None:
        """Look up a grill by its name."""
        return next((g for g in self.grills.values() if g.name == name), None)

    # ---------------------------------------------------------------- actions

    @callback
    def assign_probe(self, probe_id: str, grill_id: str | None) -> None:
        """Attach a probe to a grill (None: detach).

        Attaching starts the grill's session if needed; detaching the last
        probe ends it.
        """
        probe = self.probes[probe_id]
        if grill_id is not None and grill_id not in self.grills:
            raise ValueError(f"Unknown grill {grill_id}")
        old_grill_id = probe.grill_id
        if grill_id == old_grill_id:
            return
        if (
            old_grill_id is not None
            and self.grills[old_grill_id].session_active
            and self.probes_of(old_grill_id) == [probe]
        ):
            # Last probe leaves: record the session while the probe is still in it
            self.stop_session(old_grill_id)
        probe.grill_id = grill_id
        probe.tracker.reset()
        probe.fired.clear()
        if grill_id is not None and not self.grills[grill_id].session_active:
            self.start_session(grill_id)
        self._sample(notify=False)
        self._changed()

    @callback
    def set_chamber_target(self, grill_id: str, value: float) -> None:
        """Set the desired cooking chamber temperature."""
        grill = self.grills[grill_id]
        grill.chamber_target = float(value)
        grill.chamber_reached = False
        grill.chamber_deviation = False
        self._changed()

    @callback
    def set_profile(self, probe_id: str, profile: str) -> None:
        """Select a food profile, which also sets the probe target."""
        probe = self.probes[probe_id]
        probe.profile = profile
        if (food := FOOD_PROFILES.get(profile)) is not None:
            self._apply_target(probe, food.target)
        self._changed()

    @callback
    def set_target(self, probe_id: str, value: float) -> None:
        """Override the target core temperature of a probe."""
        self._apply_target(self.probes[probe_id], value)
        self._changed()

    @callback
    def start_session(self, grill_id: str) -> None:
        """Start a new cooking session on a grill (restarts a running one)."""
        grill = self.grills[grill_id]
        grill.session_start = dt_util.utcnow()
        grill.chamber_reached = False
        grill.chamber_deviation = False
        for probe in self.probes_of(grill_id):
            probe.tracker.reset()
            probe.fired.clear()
        self._update_tick()
        self._fire(grill, EVENT_SESSION_STARTED)
        self._sample(notify=False)
        self._changed()

    @callback
    def stop_session(self, grill_id: str) -> None:
        """End the session of a grill, detach its probes and store the history."""
        grill = self.grills[grill_id]
        if grill.session_start is None:
            return
        end = dt_util.utcnow()
        probes = self.probes_of(grill_id)
        record = {
            "start": grill.session_start.isoformat(),
            "end": end.isoformat(),
            "duration_min": round((end - grill.session_start).total_seconds() / 60),
            "grill_type": grill.grill_type.value,
            "outdoor_temperature": self.outdoor_temperature,
            "probes": [
                {
                    "name": p.name,
                    "profile": p.profile,
                    "target": p.target,
                    "max_temperature": p.tracker.peak,
                }
                for p in probes
            ],
        }
        grill.sessions = [record, *grill.sessions][:MAX_SESSION_HISTORY]
        grill.session_start = None
        grill.chamber_reached = False
        grill.chamber_deviation = False
        for probe in probes:
            probe.grill_id = None
        self._update_tick()
        self._fire(grill, EVENT_SESSION_ENDED, duration_min=record["duration_min"])
        self._changed()

    # --------------------------------------------------------------- internals

    def _apply_target(self, probe: ProbeState, value: float) -> None:
        value = float(value)
        if value != probe.target:
            probe.target = value
            probe.tracker.reached = False
            probe.fired.discard(EVENT_NEAR_DONE)
            probe.fired.discard(EVENT_TARGET_REACHED)

    def _update_tick(self) -> None:
        """Run the periodic sampler only while a session is active."""
        active = any(g.session_active for g in self.grills.values())
        if active and self._unsub_tick is None:
            self._unsub_tick = async_track_time_interval(
                self.hass, self._handle_tick, TICK_INTERVAL
            )
        elif not active and self._unsub_tick is not None:
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
        self.outdoor_temperature = read_temperature(self.hass, self.outdoor_entity)
        for probe in self.probes.values():
            temp = read_temperature(self.hass, probe.core_entity)
            was_available = probe.available
            probe.available = temp is not None
            probe.ambient_temperature = read_temperature(
                self.hass, probe.ambient_entity
            )
            if temp is not None:
                probe.tracker.add(ts, temp)
            elif (
                was_available
                and (grill := self.grills.get(probe.grill_id or ""))
                and grill.session_active
            ):
                self._fire(grill, EVENT_PROBE_OFFLINE, probe)
        for grill in self.grills.values():
            grill.chamber_temperature = read_temperature(
                self.hass, grill.chamber_entity
            )
            if grill.chamber_temperature is None:
                grill.chamber_temperature = next(
                    (
                        p.ambient_temperature
                        for p in self.probes_of(grill.subentry_id)
                        if p.ambient_temperature is not None
                    ),
                    None,
                )
        if notify:
            self._changed(save=False)
        else:
            self._evaluate()

    def _evaluate(self) -> None:
        for grill in self.grills.values():
            self._evaluate_chamber(grill)
        for probe in self.probes.values():
            grill = self.grills.get(probe.grill_id or "")
            if not probe.available:
                probe.phase = None
                continue
            if grill is None or not grill.session_active:
                probe.phase = ProbePhase.IDLE
                continue
            probe.phase = probe.tracker.phase(
                probe.target,
                stall_possible=grill.grill_type in STALL_GRILL_TYPES,
                heating=grill.heating,
            )
            if probe.phase == ProbePhase.NEAR_DONE:
                self._fire_once(grill, probe, EVENT_NEAR_DONE)
            elif probe.phase == ProbePhase.STALL:
                self._fire_once(grill, probe, EVENT_STALL)
            elif probe.phase in (ProbePhase.TARGET_REACHED, ProbePhase.RESTING):
                self._fire_once(grill, probe, EVENT_TARGET_REACHED)

    def _evaluate_chamber(self, grill: GrillState) -> None:
        diff: float | None = None
        if (
            grill.session_active
            and grill.chamber_target is not None
            and grill.chamber_temperature is not None
        ):
            diff = grill.chamber_temperature - grill.chamber_target
            if abs(diff) <= grill.tolerance:
                grill.chamber_reached = True
        deviation = (
            diff is not None and grill.chamber_reached and abs(diff) > grill.tolerance
        )
        if deviation and not grill.chamber_deviation:
            self._fire(
                grill,
                EVENT_CHAMBER_DEVIATION,
                chamber_temperature=grill.chamber_temperature,
                chamber_target=grill.chamber_target,
            )
        grill.chamber_deviation = deviation

    def _fire_once(self, grill: GrillState, probe: ProbeState, event_type: str) -> None:
        if event_type not in probe.fired:
            probe.fired.add(event_type)
            self._fire(grill, event_type, probe)
            self._save()

    def _fire(
        self,
        grill: GrillState,
        event_type: str,
        probe: ProbeState | None = None,
        **extra: Any,
    ) -> None:
        data: dict[str, Any] = {
            "grill": grill.name,
            "grill_type": grill.grill_type.value,
            "outdoor_temperature": self.outdoor_temperature,
        }
        if probe is not None:
            data |= {
                "probe": probe.name,
                "profile": probe.profile,
                "temperature": probe.tracker.current,
                "target": probe.target,
            }
        data |= extra
        _LOGGER.debug("%s: %s %s", grill.name, event_type, data)
        self.hass.bus.async_fire(
            EVENT_KITCHEN,
            {"type": event_type, "grill_id": grill.subentry_id, **data},
        )
        for listener in list(self._event_listeners.get(grill.subentry_id, [])):
            listener(event_type, data)

    def _changed(self, save: bool = True) -> None:
        self._evaluate()
        if save:
            self._save()
        for listener in list(self._listeners):
            listener()

    def _save(self) -> None:
        for grill in self.grills.values():
            self._store.set(
                grill.subentry_id,
                {
                    "chamber_target": grill.chamber_target,
                    "session_start": (
                        grill.session_start.isoformat() if grill.session_start else None
                    ),
                    "sessions": grill.sessions,
                },
            )
        for probe in self.probes.values():
            self._store.set(
                probe.subentry_id,
                {
                    "grill_id": probe.grill_id,
                    "profile": probe.profile,
                    "target": probe.target,
                    "fired": sorted(probe.fired),
                },
            )

    def _restore(self) -> None:
        for grill in self.grills.values():
            if not (data := self._store.get(grill.subentry_id)):
                continue
            if "chamber_target" in data:
                grill.chamber_target = data["chamber_target"]
            if start := data.get("session_start"):
                grill.session_start = dt_util.parse_datetime(start)
            grill.sessions = data.get("sessions", [])
        for probe in self.probes.values():
            if not (data := self._store.get(probe.subentry_id)):
                continue
            probe.profile = data.get("profile", PROFILE_CUSTOM)
            probe.target = data.get("target", DEFAULT_TARGET)
            grill = self.grills.get(data.get("grill_id") or "")
            if grill is not None and grill.session_active:
                probe.grill_id = grill.subentry_id
                probe.fired = set(data.get("fired", []))
                probe.tracker.reached = EVENT_TARGET_REACHED in probe.fired
