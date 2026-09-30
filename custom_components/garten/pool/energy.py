"""Energy metering of the pool pump (pure logic, no Home Assistant imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# Gaps longer than this (e.g. Home Assistant was down) are not integrated.
MAX_GAP_SECONDS = 15 * 60


def solar_power(pump_w: float, surplus_w: float | None) -> float:
    """Part of the pump power covered by solar.

    ``surplus_w`` is the power still exported after all consumers, including
    the pump. A negative surplus means grid import.
    """
    if surplus_w is None or pump_w <= 0:
        return 0.0
    return max(0.0, min(pump_w, pump_w + surplus_w))


@dataclass
class EnergyMeter:
    """Integrate pump and solar power into kWh per day and per year."""

    day: date | None = None
    day_kwh: float = 0.0
    day_solar_kwh: float = 0.0
    year: int | None = None
    year_kwh: float = 0.0
    year_solar_kwh: float = 0.0
    _last: datetime | None = None
    _power: float = 0.0
    _solar: float = 0.0

    def update(self, now: datetime, power_w: float | None, solar_w: float) -> None:
        """Account the previous reading up to ``now`` and store the new one."""
        self._roll(now)
        if self._last is not None:
            seconds = (now - self._last).total_seconds()
            if 0 < seconds <= MAX_GAP_SECONDS:
                kwh = self._power * seconds / 3_600_000
                solar_kwh = self._solar * seconds / 3_600_000
                self.day_kwh += kwh
                self.year_kwh += kwh
                self.day_solar_kwh += solar_kwh
                self.year_solar_kwh += solar_kwh
        self._last = now
        self._power = max(0.0, power_w or 0.0)
        self._solar = max(0.0, min(solar_w, self._power))

    def _roll(self, now: datetime) -> None:
        today = now.date()
        if self.day != today:
            self.day = today
            self.day_kwh = self.day_solar_kwh = 0.0
        if self.year != today.year:
            self.year = today.year
            self.year_kwh = self.year_solar_kwh = 0.0

    @staticmethod
    def share(total: float, solar: float) -> float | None:
        """Solar share in percent, None without consumption."""
        return solar / total * 100 if total > 0 else None

    def as_dict(self) -> dict[str, Any]:
        """Serialize the counters (not the running reading)."""
        return {
            "day": self.day.isoformat() if self.day else None,
            "day_kwh": self.day_kwh,
            "day_solar_kwh": self.day_solar_kwh,
            "year": self.year,
            "year_kwh": self.year_kwh,
            "year_solar_kwh": self.year_solar_kwh,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnergyMeter:
        """Restore counters."""
        return cls(
            day=date.fromisoformat(data["day"]) if data.get("day") else None,
            day_kwh=data.get("day_kwh", 0.0),
            day_solar_kwh=data.get("day_solar_kwh", 0.0),
            year=data.get("year"),
            year_kwh=data.get("year_kwh", 0.0),
            year_solar_kwh=data.get("year_solar_kwh", 0.0),
        )
