"""Runtime state of one pool (one config subentry)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigSubentry
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
    CONF_POOL_CHLORINE,
    CONF_POOL_GUIDANCE,
    CONF_POOL_LAST_MEASUREMENT,
    CONF_POOL_ORP,
    CONF_POOL_PH,
    CONF_POOL_POWER,
    CONF_POOL_PUMP,
    CONF_POOL_RECOMMENDED_RUNTIME,
    CONF_POOL_SALT,
    CONF_POOL_SOLAR_SURPLUS,
    CONF_POOL_TEMPERATURE,
    DEFAULT_BACKWASH_INTERVAL_H,
    DEFAULT_BACKWASH_MAX_DAYS,
    DEFAULT_ELECTRICITY_PRICE,
    EVENT_POOL,
    MEASUREMENT_STALE_HOURS,
)
from ..helpers import is_on, read_datetime, read_float, read_temperature, read_text
from ..storage import GartenStore
from .energy import EnergyMeter, solar_power
from .quality import CHLORINE, ORP, PH, SALT, Quality, is_worse, rate, worst

_LOGGER = logging.getLogger(__name__)

TICK_INTERVAL = timedelta(seconds=60)
PERIODIC_SAVE = timedelta(minutes=10)
# Runtime gaps longer than this (e.g. Home Assistant was down) are not counted.
MAX_RUNTIME_GAP = timedelta(minutes=15)

EVENT_BACKWASH_DUE = "backwash_due"
EVENT_QUALITY_CHANGED = "water_quality_changed"
EVENT_MEASUREMENT_STALE = "measurement_stale"
EVENT_BACKWASH_DONE = "backwash_done"

POOL_EVENT_TYPES = [
    EVENT_QUALITY_CHANGED,
    EVENT_MEASUREMENT_STALE,
    EVENT_BACKWASH_DUE,
    EVENT_BACKWASH_DONE,
]

# Water parameter -> subentry key of its source sensor
PARAMETER_SOURCES: dict[str, str] = {
    PH: CONF_POOL_PH,
    ORP: CONF_POOL_ORP,
    CHLORINE: CONF_POOL_CHLORINE,
    SALT: CONF_POOL_SALT,
}

type EventListener = Callable[[str, dict[str, Any]], None]


class PoolManager:
    """Track pump, water values, backwash and energy of one pool."""

    def __init__(
        self, hass: HomeAssistant, subentry: ConfigSubentry, store: GartenStore
    ) -> None:
        self.hass = hass
        self.subentry = subentry
        self._store = store
        data = subentry.data
        self.sources: dict[str, str] = {
            key: value for key, value in data.items() if isinstance(value, str)
        }
        self.parameters: list[str] = [
            param for param, key in PARAMETER_SOURCES.items() if data.get(key)
        ]

        # Live values
        self.pump_on = False
        self.power: float | None = None
        self.temperature: float | None = None
        self.values: dict[str, float | None] = dict.fromkeys(self.parameters)
        self.qualities: dict[str, Quality | None] = dict.fromkeys(self.parameters)
        self.quality: Quality | None = None
        self.guidance: str | None = None
        self.recommended_runtime_h: float | None = None
        self.last_measurement: datetime | None = None
        self.stale = False

        # Accumulated / persisted state
        self.runtime_day = dt_util.now().date()
        self.runtime_today_s = 0.0
        self.backwash_s = 0.0
        self.last_backwash: datetime | None = None
        self.backwash_interval_h: float = DEFAULT_BACKWASH_INTERVAL_H
        self.backwash_max_days: float = DEFAULT_BACKWASH_MAX_DAYS
        self.price: float = DEFAULT_ELECTRICITY_PRICE
        self.backwash_due = False
        self.meter = EnergyMeter()

        self._last_sample: datetime | None = None
        self._last_save: datetime | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._event_listeners: list[EventListener] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------ setup

    @property
    def subentry_id(self) -> str:
        """Id of the pool subentry."""
        return self.subentry.subentry_id

    @property
    def name(self) -> str:
        """Name of the pool."""
        return self.subentry.title

    def source(self, key: str) -> str | None:
        """Configured source entity for a subentry key."""
        return self.sources.get(key)

    @callback
    def async_start(self) -> None:
        """Restore state and start listening to the source entities."""
        self._restore()
        entities = sorted(set(self.sources.values()) - {self.source(CONF_CAMERA)})
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, entities, self._handle_source_change
            )
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_tick, TICK_INTERVAL)
        )
        self._sample(initial=True)

    @callback
    def async_stop(self) -> None:
        """Stop listening and account the running interval."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._account(dt_util.now())
        self._save()

    @callback
    def add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register a callback invoked whenever state changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def add_event_listener(self, listener: EventListener) -> CALLBACK_TYPE:
        """Register a callback for pool events."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    @callback
    def async_update_listeners(self) -> None:
        """Let all entities write their state again."""
        self._changed(save=False)

    # ------------------------------------------------------------ derived data

    @property
    def runtime_today_h(self) -> float:
        """Pump runtime today in hours."""
        return self.runtime_today_s / 3600

    @property
    def backwash_hours(self) -> float:
        """Pump hours since the last backwash."""
        return self.backwash_s / 3600

    @property
    def days_since_backwash(self) -> float | None:
        """Days since the last recorded backwash."""
        if self.last_backwash is None:
            return None
        return (dt_util.utcnow() - self.last_backwash).total_seconds() / 86400

    @property
    def cost_today(self) -> float:
        """Grid energy cost of the pump today."""
        return (self.meter.day_kwh - self.meter.day_solar_kwh) * self.price

    @property
    def savings_year(self) -> float:
        """Money saved this year by running the pump on solar."""
        return self.meter.year_solar_kwh * self.price

    # ---------------------------------------------------------------- actions

    @callback
    def record_backwash(self) -> None:
        """Mark the filter as backwashed now."""
        hours = round(self.backwash_hours, 1)
        self._account(dt_util.now())
        self.backwash_s = 0.0
        self.last_backwash = dt_util.utcnow()
        self._fire(EVENT_BACKWASH_DONE, pump_hours=hours)
        self._evaluate()
        self._changed(save=True)

    @callback
    def set_backwash_interval(self, hours: float) -> None:
        """Pump hours after which a backwash is due."""
        self.backwash_interval_h = hours
        self._evaluate()
        self._changed(save=True)

    @callback
    def set_backwash_max_days(self, days: float) -> None:
        """Days after which a backwash is due regardless of pump hours."""
        self.backwash_max_days = days
        self._evaluate()
        self._changed(save=True)

    @callback
    def set_price(self, price: float) -> None:
        """Electricity price per kWh."""
        self.price = price
        self._changed(save=True)

    # --------------------------------------------------------------- internals

    @callback
    def _handle_source_change(self, event: Event[EventStateChangedData]) -> None:
        self._sample()

    @callback
    def _handle_tick(self, now: datetime) -> None:
        self._sample()

    def _account(self, now: datetime) -> None:
        """Add the time since the last sample to runtime and energy counters."""
        if now.date() != self.runtime_day:
            self.runtime_day = now.date()
            self.runtime_today_s = 0.0
        if self._last_sample is not None and self.pump_on:
            elapsed = now - self._last_sample
            if timedelta(0) < elapsed <= MAX_RUNTIME_GAP:
                self.runtime_today_s += elapsed.total_seconds()
                self.backwash_s += elapsed.total_seconds()
        self._last_sample = now

    def _sample(self, initial: bool = False) -> None:
        now = dt_util.now()
        # Account the elapsed interval with the previous pump state first
        self._account(now)
        hass = self.hass
        self.pump_on = is_on(hass, self.source(CONF_POOL_PUMP))
        self.power = read_float(hass, self.source(CONF_POOL_POWER))
        pump_w = self.power or 0.0
        surplus = read_float(hass, self.source(CONF_POOL_SOLAR_SURPLUS))
        self.meter.update(now, pump_w, solar_power(pump_w, surplus))

        self.temperature = read_temperature(hass, self.source(CONF_POOL_TEMPERATURE))
        for param in self.parameters:
            value = read_float(hass, self.source(PARAMETER_SOURCES[param]))
            self.values[param] = value
            self.qualities[param] = rate(param, value)
        self.guidance = read_text(hass, self.source(CONF_POOL_GUIDANCE))
        self.recommended_runtime_h = read_float(
            hass, self.source(CONF_POOL_RECOMMENDED_RUNTIME)
        )
        self.last_measurement = read_datetime(
            hass, self.source(CONF_POOL_LAST_MEASUREMENT)
        )
        self._evaluate(initial)

        save = self._last_save is None or now - self._last_save >= PERIODIC_SAVE
        self._changed(save=save)

    def _evaluate(self, initial: bool = False) -> None:
        quality = worst(self.qualities.values())
        if not initial and is_worse(quality, self.quality):
            self._fire(
                EVENT_QUALITY_CHANGED,
                quality=quality.value if quality else None,
                previous=self.quality.value if self.quality else None,
                values=dict(self.values),
            )
        self.quality = quality

        stale = self.last_measurement is not None and (
            dt_util.utcnow() - self.last_measurement
            > timedelta(hours=MEASUREMENT_STALE_HOURS)
        )
        if stale and not self.stale and not initial:
            self._fire(
                EVENT_MEASUREMENT_STALE,
                last_measurement=self.last_measurement.isoformat(),
            )
        self.stale = stale

        days = self.days_since_backwash
        due = self.backwash_hours >= self.backwash_interval_h or (
            days is not None and days >= self.backwash_max_days
        )
        if due and not self.backwash_due:
            self._fire(
                EVENT_BACKWASH_DUE,
                pump_hours=round(self.backwash_hours, 1),
                days=round(days, 1) if days is not None else None,
            )
        self.backwash_due = due

    def _fire(self, event_type: str, **extra: Any) -> None:
        data: dict[str, Any] = {"pool": self.name, **extra}
        _LOGGER.debug("%s: %s %s", self.name, event_type, data)
        self.hass.bus.async_fire(
            EVENT_POOL, {"type": event_type, "pool_id": self.subentry_id, **data}
        )
        for listener in list(self._event_listeners):
            listener(event_type, data)

    def _changed(self, save: bool) -> None:
        if save:
            self._save()
        for listener in list(self._listeners):
            listener()

    def _save(self) -> None:
        self._last_save = dt_util.now()
        self._store.set(
            self.subentry_id,
            {
                "runtime_day": self.runtime_day.isoformat(),
                "runtime_today_s": self.runtime_today_s,
                "backwash_s": self.backwash_s,
                "last_backwash": (
                    self.last_backwash.isoformat() if self.last_backwash else None
                ),
                "backwash_interval_h": self.backwash_interval_h,
                "backwash_max_days": self.backwash_max_days,
                "price": self.price,
                "backwash_due": self.backwash_due,
                "stale": self.stale,
                "quality": self.quality.value if self.quality else None,
                "meter": self.meter.as_dict(),
            },
        )

    def _restore(self) -> None:
        if not (data := self._store.get(self.subentry_id)):
            return
        if day := data.get("runtime_day"):
            self.runtime_day = datetime.fromisoformat(day).date()
        self.runtime_today_s = data.get("runtime_today_s", 0.0)
        self.backwash_s = data.get("backwash_s", 0.0)
        if last := data.get("last_backwash"):
            self.last_backwash = dt_util.parse_datetime(last)
        self.backwash_interval_h = data.get(
            "backwash_interval_h", DEFAULT_BACKWASH_INTERVAL_H
        )
        self.backwash_max_days = data.get(
            "backwash_max_days", DEFAULT_BACKWASH_MAX_DAYS
        )
        self.price = data.get("price", DEFAULT_ELECTRICITY_PRICE)
        self.backwash_due = data.get("backwash_due", False)
        self.stale = data.get("stale", False)
        if quality := data.get("quality"):
            self.quality = Quality(quality)
        if meter := data.get("meter"):
            self.meter = EnergyMeter.from_dict(meter)
