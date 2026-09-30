"""Tests for the pure probe tracking logic."""

from __future__ import annotations

import pytest

from custom_components.garten.kitchen.estimator import ProbePhase, ProbeTracker


def _feed(tracker: ProbeTracker, start: float, rate_per_min: float, minutes: int):
    """Feed one reading per minute rising at ``rate_per_min``."""
    for minute in range(minutes + 1):
        tracker.add(minute * 60.0, start + rate_per_min * minute)


def test_slope_and_remaining_time() -> None:
    """A steady rise gives the matching slope and a linear time estimate."""
    tracker = ProbeTracker()
    _feed(tracker, 20, 1.0, 20)
    assert tracker.slope() == pytest.approx(1.0)
    assert tracker.current == 40
    assert tracker.remaining_minutes(60) == pytest.approx(20)
    assert tracker.remaining_minutes(30) == 0.0


def test_no_estimate_without_enough_history_or_rise() -> None:
    """Short histories and flat curves give no estimate."""
    tracker = ProbeTracker()
    tracker.add(0, 20)
    tracker.add(30, 21)
    assert tracker.slope() is None
    assert tracker.remaining_minutes(60) is None

    flat = ProbeTracker()
    _feed(flat, 40, 0.0, 10)
    assert flat.remaining_minutes(60) is None


def test_progress() -> None:
    """Progress runs from the start temperature to the target."""
    tracker = ProbeTracker()
    _feed(tracker, 20, 1.0, 20)
    assert tracker.progress(60) == pytest.approx(50)
    assert tracker.progress(40) == 100


def test_old_samples_are_dropped() -> None:
    """History is limited to the retention window."""
    tracker = ProbeTracker()
    _feed(tracker, 20, 0.1, 60)
    assert tracker.rise_over(45 * 60) is None
    assert tracker.rise_over(15 * 60) == pytest.approx(1.5)


def test_stall_detection() -> None:
    """A plateau in the stall range is detected, but only there."""
    tracker = ProbeTracker()
    _feed(tracker, 70, 0.01, 20)
    assert tracker.is_stalled()
    assert tracker.phase(95, stall_possible=True, heating=False) == ProbePhase.STALL
    assert tracker.phase(95, stall_possible=False, heating=False) == ProbePhase.COOKING

    cold = ProbeTracker()
    _feed(cold, 40, 0.0, 20)
    assert not cold.is_stalled()


def test_phase_sequence() -> None:
    """Phases progress from heating to resting."""
    tracker = ProbeTracker()
    tracker.add(0, 20)
    assert tracker.phase(60, stall_possible=False, heating=True) == ProbePhase.HEATING
    assert tracker.phase(60, stall_possible=False, heating=False) == ProbePhase.COOKING
    tracker.add(60, 56)
    assert (
        tracker.phase(60, stall_possible=False, heating=False) == ProbePhase.NEAR_DONE
    )
    tracker.add(120, 61)
    assert (
        tracker.phase(60, stall_possible=False, heating=False)
        == ProbePhase.TARGET_REACHED
    )
    # Slight dip below target stays "reached" (latched) until it drops from peak.
    tracker.add(180, 60.5)
    assert (
        tracker.phase(60, stall_possible=False, heating=False)
        == ProbePhase.TARGET_REACHED
    )
    tracker.add(240, 59.5)
    assert tracker.phase(60, stall_possible=False, heating=False) == ProbePhase.RESTING


def test_out_of_order_samples_are_ignored() -> None:
    """Older timestamps than the last sample are dropped."""
    tracker = ProbeTracker()
    tracker.add(100, 30)
    tracker.add(50, 99)
    assert tracker.current == 30
