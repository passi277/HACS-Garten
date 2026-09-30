"""Pure temperature tracking logic for a single meat probe.

Kept free of Home Assistant imports so it can be unit tested in isolation.
Timestamps are plain seconds (e.g. ``datetime.timestamp()``), temperatures °C.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum

HISTORY_SECONDS = 30 * 60
SLOPE_WINDOW_SECONDS = 10 * 60
MIN_SLOPE_SPAN_SECONDS = 2 * 60
MIN_SLOPE = 0.02  # °C per minute; below this no remaining time is estimated

NEAR_DONE_DELTA = 5.0
RESTING_DROP = 1.0

STALL_WINDOW_SECONDS = 15 * 60
STALL_MAX_RISE = 0.5
STALL_MIN_TEMP = 60.0
STALL_MAX_TEMP = 80.0


class ProbePhase(StrEnum):
    """Phase of a cook as seen by one probe."""

    IDLE = "idle"
    HEATING = "heating"
    COOKING = "cooking"
    STALL = "stall"
    NEAR_DONE = "near_done"
    TARGET_REACHED = "target_reached"
    RESTING = "resting"


@dataclass(slots=True)
class Sample:
    """One temperature reading."""

    ts: float
    temp: float


class ProbeTracker:
    """Keep a short temperature history and derive cook metrics from it."""

    def __init__(self) -> None:
        self._samples: deque[Sample] = deque()
        self.start_temp: float | None = None
        self.peak: float | None = None
        self.reached = False

    def reset(self) -> None:
        """Forget everything, e.g. when a new session starts."""
        self._samples.clear()
        self.start_temp = None
        self.peak = None
        self.reached = False

    @property
    def current(self) -> float | None:
        """Return the latest temperature."""
        return self._samples[-1].temp if self._samples else None

    def add(self, ts: float, temp: float) -> None:
        """Record a reading and drop history older than the retention window."""
        if self._samples and ts < self._samples[-1].ts:
            return
        self._samples.append(Sample(ts, temp))
        if self.start_temp is None:
            self.start_temp = temp
        if self.peak is None or temp > self.peak:
            self.peak = temp
        while self._samples and self._samples[0].ts < ts - HISTORY_SECONDS:
            self._samples.popleft()

    def slope(self, window: float = SLOPE_WINDOW_SECONDS) -> float | None:
        """Least-squares slope in °C per minute over the last ``window`` seconds."""
        if not self._samples:
            return None
        now = self._samples[-1].ts
        points = [s for s in self._samples if s.ts >= now - window]
        if len(points) < 2 or points[-1].ts - points[0].ts < MIN_SLOPE_SPAN_SECONDS:
            return None
        n = len(points)
        mean_t = sum(p.ts for p in points) / n
        mean_y = sum(p.temp for p in points) / n
        var = sum((p.ts - mean_t) ** 2 for p in points)
        if var == 0:
            return None
        cov = sum((p.ts - mean_t) * (p.temp - mean_y) for p in points)
        return cov / var * 60

    def rise_over(self, window: float) -> float | None:
        """Temperature change over ``window`` seconds, None if history is shorter."""
        if not self._samples:
            return None
        now = self._samples[-1].ts
        if self._samples[0].ts > now - window:
            return None
        before = next(s for s in reversed(self._samples) if s.ts <= now - window)
        return self._samples[-1].temp - before.temp

    def remaining_minutes(self, target: float) -> float | None:
        """Estimate minutes until ``target`` is reached at the current rate."""
        current = self.current
        if current is None:
            return None
        if current >= target:
            return 0.0
        slope = self.slope()
        if slope is None or slope < MIN_SLOPE:
            return None
        return (target - current) / slope

    def progress(self, target: float) -> float | None:
        """Progress from the start temperature to ``target`` in percent."""
        current = self.current
        if current is None or self.start_temp is None:
            return None
        if self.reached or current >= target:
            return 100.0
        span = target - self.start_temp
        if span <= 0:
            return 100.0
        return max(0.0, min(100.0, (current - self.start_temp) / span * 100))

    def is_stalled(self) -> bool:
        """Return True if the core temperature plateaus in the typical stall range."""
        current = self.current
        if current is None or not STALL_MIN_TEMP <= current <= STALL_MAX_TEMP:
            return False
        rise = self.rise_over(STALL_WINDOW_SECONDS)
        return rise is not None and rise < STALL_MAX_RISE

    def phase(
        self, target: float, *, stall_possible: bool, heating: bool
    ) -> ProbePhase | None:
        """Derive the current phase; latches ``reached`` once target is hit."""
        current = self.current
        if current is None:
            return None
        if current >= target:
            self.reached = True
        if self.reached:
            if self.peak is not None and current <= self.peak - RESTING_DROP:
                return ProbePhase.RESTING
            return ProbePhase.TARGET_REACHED
        if current >= target - NEAR_DONE_DELTA:
            return ProbePhase.NEAR_DONE
        if stall_possible and self.is_stalled():
            return ProbePhase.STALL
        if heating:
            return ProbePhase.HEATING
        return ProbePhase.COOKING
