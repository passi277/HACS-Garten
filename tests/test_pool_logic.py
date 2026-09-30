"""Tests for the pure pool logic: water quality rating and energy metering."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.garten.pool.energy import EnergyMeter, solar_power
from custom_components.garten.pool.quality import (
    ORP,
    PH,
    Quality,
    is_worse,
    rate,
    worst,
)


@pytest.mark.parametrize(
    ("parameter", "value", "expected"),
    [
        (PH, 7.4, Quality.OK),
        (PH, 7.2, Quality.OK),
        (PH, 7.0, Quality.CHECK),
        (PH, 7.9, Quality.CHECK),
        (PH, 6.5, Quality.CRITICAL),
        (ORP, 700, Quality.OK),
        (ORP, 527, Quality.CHECK),
        (ORP, 350, Quality.CRITICAL),
        (PH, None, None),
    ],
)
def test_rate(parameter: str, value: float | None, expected: Quality | None) -> None:
    """Values are rated against the ok / check ranges."""
    assert rate(parameter, value) is expected


def test_worst_and_is_worse() -> None:
    """The overall rating is the worst one; only worsening counts."""
    assert worst([Quality.OK, None, Quality.CHECK]) is Quality.CHECK
    assert worst([None]) is None
    assert is_worse(Quality.CHECK, Quality.OK)
    assert is_worse(Quality.CHECK, None)
    assert not is_worse(Quality.OK, None)
    assert not is_worse(Quality.OK, Quality.CRITICAL)
    assert not is_worse(None, Quality.OK)


@pytest.mark.parametrize(
    ("pump", "surplus", "expected"),
    [
        (600, 100, 600),  # exporting while the pump runs: all solar
        (600, -200, 400),  # importing 200 W: 400 W from solar
        (600, -800, 0),  # importing more than the pump: no solar
        (600, None, 0),  # no surplus sensor
        (0, 500, 0),  # pump off
    ],
)
def test_solar_power(pump: float, surplus: float | None, expected: float) -> None:
    """The solar part of the pump power is derived from the surplus."""
    assert solar_power(pump, surplus) == expected


def test_energy_meter_integrates_and_resets() -> None:
    """Energy is integrated per interval and reset per day and year."""
    meter = EnergyMeter()
    start = datetime(2026, 12, 31, 22, 0)
    meter.update(start, 600, 400)
    for minute in range(1, 61):
        meter.update(start + timedelta(minutes=minute), 600, 400)
    assert meter.day_kwh == pytest.approx(0.6)
    assert meter.day_solar_kwh == pytest.approx(0.4)
    assert EnergyMeter.share(meter.day_kwh, meter.day_solar_kwh) == pytest.approx(
        66.67, abs=0.01
    )

    # A long gap (Home Assistant was down) is not integrated
    meter.update(start + timedelta(hours=1, minutes=30), 600, 400)
    assert meter.day_kwh == pytest.approx(0.6)

    # New year: day and year counters restart
    meter.update(datetime(2027, 1, 1, 0, 1), 0, 0)
    assert meter.day_kwh == 0
    assert meter.year_kwh == 0
    assert meter.year == 2027

    restored = EnergyMeter.from_dict(meter.as_dict())
    assert restored.day == meter.day
    assert restored.year == 2027
    assert EnergyMeter.share(0, 0) is None
