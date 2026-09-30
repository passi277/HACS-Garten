"""Rating of pool water values (pure logic, no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Quality(StrEnum):
    """Traffic light rating of a water value."""

    OK = "ok"
    CHECK = "check"
    CRITICAL = "critical"


_SEVERITY = {Quality.OK: 0, Quality.CHECK: 1, Quality.CRITICAL: 2}


@dataclass(frozen=True, slots=True)
class Range:
    """Values inside ok_* are fine, inside check_* need attention, else critical."""

    ok_min: float
    ok_max: float
    check_min: float
    check_max: float

    def as_list(self) -> list[float]:
        """Return the bounds for the dashboard card."""
        return [self.check_min, self.ok_min, self.ok_max, self.check_max]


PH = "ph"
ORP = "orp"
CHLORINE = "chlorine"
SALT = "salt"

# Defaults follow the ranges used by Blue Riiot / Blue Connect.
RANGES: dict[str, Range] = {
    PH: Range(7.2, 7.6, 6.8, 8.0),
    ORP: Range(650, 800, 400, 900),
    CHLORINE: Range(0.5, 1.5, 0.2, 3.0),
    SALT: Range(3.0, 4.5, 2.5, 6.0),
}


def rate(parameter: str, value: float | None) -> Quality | None:
    """Rate one water value, None if there is no value."""
    if value is None:
        return None
    limits = RANGES[parameter]
    if limits.ok_min <= value <= limits.ok_max:
        return Quality.OK
    if limits.check_min <= value <= limits.check_max:
        return Quality.CHECK
    return Quality.CRITICAL


def worst(qualities: Iterable[Quality | None]) -> Quality | None:
    """Return the worst rating, None if nothing was rated."""
    rated = [q for q in qualities if q is not None]
    return max(rated, key=_SEVERITY.__getitem__) if rated else None


def is_worse(new: Quality | None, old: Quality | None) -> bool:
    """Return True if ``new`` is a worse rating than ``old``."""
    if new is None:
        return False
    return _SEVERITY[new] > (_SEVERITY[old] if old is not None else 0)
