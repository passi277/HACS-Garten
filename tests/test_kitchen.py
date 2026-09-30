"""Tests for the outdoor kitchen entities and cooking logic."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.garten.const import DOMAIN, EVENT_KITCHEN

from .conftest import AMBIENT_1, CORE_1, CORE_2, KITCHEN_ID, set_temp

METHOD = "select.outdoor_kuche_cooking_method"
PROFILE_1 = "select.outdoor_kuche_meater_2_food"
TARGET_1 = "number.outdoor_kuche_meater_2_target_temperature"
CHAMBER_TARGET = "number.outdoor_kuche_chamber_target"
CORE_TEMP_1 = "sensor.outdoor_kuche_meater_2_core_temperature"
PHASE_1 = "sensor.outdoor_kuche_meater_2_phase"
PHASE_2 = "sensor.outdoor_kuche_meater_plus_phase"
PROGRESS_1 = "sensor.outdoor_kuche_meater_2_progress"
REMAINING_1 = "sensor.outdoor_kuche_meater_2_remaining_time"
REACHED_1 = "binary_sensor.outdoor_kuche_meater_2_target_reached"
CHAMBER_TEMP = "sensor.outdoor_kuche_chamber_temperature"
CHAMBER_DEVIATION = "binary_sensor.outdoor_kuche_chamber_out_of_range"
DURATION = "sensor.outdoor_kuche_session_duration"
START = "button.outdoor_kuche_start_session"
STOP = "button.outdoor_kuche_end_session"
EVENT_ENTITY = "event.outdoor_kuche_kitchen_event"


@pytest.fixture
async def setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the integration with warm-ish probes."""
    set_temp(hass, CORE_1, 20)
    set_temp(hass, AMBIENT_1, 25)
    set_temp(hass, CORE_2, 21)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def _select(hass: HomeAssistant, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": option}, True
    )


async def _set_number(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": value}, True
    )


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, True)


def _types(events: list[Event]) -> list[str]:
    return [e.data["type"] for e in events]


async def test_entities_and_device(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """All entities are created on one device per kitchen."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, KITCHEN_ID)})
    assert device is not None
    assert device.name == "Outdoor-Küche"

    assert hass.states.get(METHOD).state == "off"
    assert hass.states.get(METHOD).attributes["camera_entity"] == "camera.outdoor_kuche"
    assert hass.states.get(CORE_TEMP_1).state == "20.0"
    assert hass.states.get(CHAMBER_TEMP).state == "25.0"
    assert hass.states.get(PHASE_1).state == "idle"
    assert hass.states.get(PROGRESS_1).state == "unknown"
    assert hass.states.get(DURATION).state == "unknown"
    assert hass.states.get(CHAMBER_DEVIATION).state == "off"
    assert hass.states.get(EVENT_ENTITY) is not None
    assert hass.states.get(START) is not None
    # Second probe has no ambient sensor but gets its own set of entities
    assert hass.states.get(PHASE_2).state == "idle"


async def test_mirror_and_unit_conversion(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Source changes are mirrored; Fahrenheit sources are converted."""
    set_temp(hass, CORE_1, 42.5)
    await hass.async_block_till_done()
    assert hass.states.get(CORE_TEMP_1).state == "42.5"

    hass.states.async_set(CORE_1, "212", {"unit_of_measurement": "°F"})
    await hass.async_block_till_done()
    assert float(hass.states.get(CORE_TEMP_1).state) == pytest.approx(100)

    hass.states.async_set(CORE_1, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(CORE_TEMP_1).state == "unknown"
    assert hass.states.get(PHASE_1).state == "unknown"


async def test_profile_sets_target(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Choosing a food profile sets the target; manual override is kept."""
    await _select(hass, PROFILE_1, "pulled_pork")
    assert hass.states.get(TARGET_1).state == "93.0"
    await _set_number(hass, TARGET_1, 91)
    assert hass.states.get(TARGET_1).state == "91.0"
    assert hass.states.get(PROFILE_1).state == "pulled_pork"


async def test_cook_session_flow(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """A full cook: session start, heating, near done, reached, resting, end."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, PROFILE_1, "beef_medium")  # 58 °C

    await _select(hass, METHOD, "gas_grill")
    assert hass.states.get(CHAMBER_TARGET).state == "220"
    assert hass.states.get(DURATION).state == "0"
    assert _types(events) == ["session_started"]
    # Chamber is still cold -> heating
    assert hass.states.get(PHASE_1).state == "heating"
    assert hass.states.get(PROGRESS_1).state == "0.0"

    set_temp(hass, AMBIENT_1, 215)
    for minute in range(1, 11):
        freezer.tick(timedelta(minutes=1))
        set_temp(hass, CORE_1, 20 + 3 * minute)
        await hass.async_block_till_done()
    assert hass.states.get(PHASE_1).state == "cooking"
    assert float(hass.states.get(REMAINING_1).state) == pytest.approx(2.67, abs=0.1)
    assert float(hass.states.get(PROGRESS_1).state) == pytest.approx(78.9, abs=0.1)
    assert hass.states.get(DURATION).state == "10"

    set_temp(hass, CORE_1, 54)
    await hass.async_block_till_done()
    assert hass.states.get(PHASE_1).state == "near_done"
    set_temp(hass, CORE_1, 58.4)
    await hass.async_block_till_done()
    assert hass.states.get(PHASE_1).state == "target_reached"
    assert hass.states.get(REACHED_1).state == "on"
    set_temp(hass, CORE_1, 57)
    await hass.async_block_till_done()
    assert hass.states.get(PHASE_1).state == "resting"
    assert hass.states.get(REACHED_1).state == "on"

    assert _types(events) == ["session_started", "near_done", "target_reached"]
    reached = events[-1].data
    assert reached["probe"] == "Meater 2"
    assert reached["target"] == 58
    assert reached["kitchen"] == "Outdoor-Küche"
    assert hass.states.get(EVENT_ENTITY).attributes["event_type"] == "target_reached"

    await _press(hass, STOP)
    assert hass.states.get(METHOD).state == "gas_grill"
    assert hass.states.get(PHASE_1).state == "idle"
    assert hass.states.get(DURATION).state == "unknown"
    last = hass.states.get(DURATION).attributes["last_session"]
    assert last["method"] == "gas_grill"
    assert last["probes"][0]["max_temperature"] == 58.4
    assert _types(events)[-1] == "session_ended"


async def test_method_off_ends_session(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Switching the method off ends the session."""
    await _select(hass, METHOD, "dutch_oven")
    assert hass.states.get(DURATION).state == "0"
    await _select(hass, METHOD, "off")
    assert hass.states.get(DURATION).state == "unknown"
    assert hass.states.get(CHAMBER_TARGET).state == "unknown"


async def test_stall_detected_with_periodic_sampling(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """A smoker stall is detected even if the source never changes."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, PROFILE_1, "pulled_pork")
    set_temp(hass, AMBIENT_1, 110)
    set_temp(hass, CORE_1, 70)
    await _select(hass, METHOD, "smoker")
    assert hass.states.get(PHASE_1).state == "cooking"

    for _ in range(40):  # 20 minutes of 30 s ticks without source updates
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(PHASE_1).state == "stall"
    assert hass.states.get(REMAINING_1).state == "unknown"
    assert "stall_detected" in _types(events)


async def test_chamber_deviation(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Deviation is only reported once the chamber reached its target range."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, METHOD, "smoker")  # 110 °C
    assert hass.states.get(CHAMBER_DEVIATION).state == "off"

    set_temp(hass, AMBIENT_1, 105)
    await hass.async_block_till_done()
    set_temp(hass, AMBIENT_1, 140)
    await hass.async_block_till_done()
    assert hass.states.get(CHAMBER_DEVIATION).state == "on"
    assert _types(events).count("chamber_deviation") == 1

    set_temp(hass, AMBIENT_1, 112)
    await hass.async_block_till_done()
    assert hass.states.get(CHAMBER_DEVIATION).state == "off"

    await _set_number(hass, CHAMBER_TARGET, 150)
    # New target not reached yet -> heating, no deviation
    assert hass.states.get(CHAMBER_DEVIATION).state == "off"
    assert hass.states.get(PHASE_1).state == "heating"


async def test_probe_offline_event(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """A probe dropping out during a session fires an event once."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _press(hass, START)
    hass.states.async_set(CORE_2, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(CORE_2, "unavailable", {"x": 1})
    await hass.async_block_till_done()
    assert _types(events) == ["session_started", "probe_offline"]
    assert events[-1].data["probe"] == "Meater plus"


async def test_state_restored_after_reload(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Method, targets and running session survive a reload without re-firing."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, PROFILE_1, "chicken")
    await _select(hass, METHOD, "gas_grill")
    set_temp(hass, CORE_1, 75)
    await hass.async_block_till_done()
    assert _types(events) == ["session_started", "target_reached"]

    assert await hass.config_entries.async_reload(setup.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(METHOD).state == "gas_grill"
    assert hass.states.get(PROFILE_1).state == "chicken"
    assert hass.states.get(TARGET_1).state == "74.0"
    assert hass.states.get(DURATION).state == "0"
    assert hass.states.get(PHASE_1).state == "target_reached"
    assert _types(events) == ["session_started", "target_reached"]


async def test_unload(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """The entry unloads cleanly."""
    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()
    set_temp(hass, CORE_1, 50)
    await hass.async_block_till_done()
    assert hass.states.get(CORE_TEMP_1).state == "unavailable"
