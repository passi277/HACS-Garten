"""Tests for grills, probes, their assignment and the cooking logic."""

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

from custom_components.garten.const import (
    CONF_OUTDOOR_TEMPERATURE,
    DOMAIN,
    EVENT_KITCHEN,
)

from .conftest import (
    AMBIENT_1,
    CORE_1,
    CORE_2,
    OUTDOOR,
    PIG_GRILL_ID,
    PROBE_1_ID,
    SMOKER_CHAMBER,
    set_temp,
)

# Grill "Spanferkelgrill"
PIG_CHAMBER_TARGET = "number.spanferkelgrill_chamber_target"
PIG_CHAMBER_TEMP = "sensor.spanferkelgrill_chamber_temperature"
PIG_OUTDOOR = "sensor.spanferkelgrill_outdoor_temperature"
PIG_PROBES = "sensor.spanferkelgrill_attached_probes"
PIG_DURATION = "sensor.spanferkelgrill_session_duration"
PIG_DEVIATION = "binary_sensor.spanferkelgrill_chamber_out_of_range"
PIG_START = "button.spanferkelgrill_start_session"
PIG_STOP = "button.spanferkelgrill_end_session"
PIG_EVENT = "event.spanferkelgrill_grill_event"
# Grill "Smoker"
SMOKER_CHAMBER_TEMP = "sensor.smoker_chamber_temperature"
SMOKER_DURATION = "sensor.smoker_session_duration"
SMOKER_PROBES = "sensor.smoker_attached_probes"
# Probe "Meater 2"
P1_GRILL = "select.meater_2_grill"
P1_FOOD = "select.meater_2_food"
P1_TARGET = "number.meater_2_target_temperature"
P1_CORE = "sensor.meater_2_core_temperature"
P1_AMBIENT = "sensor.meater_2_ambient_temperature"
P1_PROGRESS = "sensor.meater_2_progress"
P1_REMAINING = "sensor.meater_2_remaining_time"
P1_PHASE = "sensor.meater_2_phase"
P1_REACHED = "binary_sensor.meater_2_target_reached"
# Probe "Meater plus"
P2_GRILL = "select.meater_plus_grill"
P2_PHASE = "sensor.meater_plus_phase"


@pytest.fixture
async def setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the integration with cold probes."""
    set_temp(hass, CORE_1, 20)
    set_temp(hass, AMBIENT_1, 25)
    set_temp(hass, CORE_2, 21)
    set_temp(hass, SMOKER_CHAMBER, 30)
    set_temp(hass, OUTDOOR, 14.5)
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


async def test_separate_devices(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Each grill and each probe is its own device with its own entities."""
    dev_reg = dr.async_get(hass)
    grill = dev_reg.async_get_device(identifiers={(DOMAIN, PIG_GRILL_ID)})
    probe = dev_reg.async_get_device(identifiers={(DOMAIN, PROBE_1_ID)})
    assert grill.name == "Spanferkelgrill"
    assert grill.model == "Grill"
    assert grill.model_id == "suckling_pig_grill"
    assert probe.name == "Meater 2"
    assert probe.model == "Sonde"

    assert hass.states.get(PIG_CHAMBER_TARGET).state == "160.0"
    assert hass.states.get(PIG_CHAMBER_TEMP).state == "unknown"
    assert hass.states.get(PIG_OUTDOOR).state == "14.5"
    assert hass.states.get(PIG_PROBES).state == "0"
    assert hass.states.get(PIG_DURATION).state == "unknown"
    assert hass.states.get(PIG_DURATION).attributes["camera_entity"] == (
        "camera.outdoor_kuche"
    )
    assert hass.states.get(SMOKER_CHAMBER_TEMP).state == "30.0"

    assert hass.states.get(P1_GRILL).state == "none"
    assert hass.states.get(P1_GRILL).attributes["options"] == [
        "none",
        "Smoker",
        "Spanferkelgrill",
    ]
    assert hass.states.get(P1_CORE).state == "20.0"
    assert hass.states.get(P1_AMBIENT).state == "25.0"
    assert hass.states.get(P1_PHASE).state == "idle"
    assert hass.states.get(P1_PROGRESS).state == "unknown"
    # Probe without ambient sensor has no ambient entity
    assert hass.states.get("sensor.meater_plus_ambient_temperature") is None
    assert hass.states.get(P2_PHASE).state == "idle"


async def test_mirror_and_unit_conversion(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Source changes are mirrored; Fahrenheit sources are converted."""
    set_temp(hass, CORE_1, 42.5)
    await hass.async_block_till_done()
    assert hass.states.get(P1_CORE).state == "42.5"

    hass.states.async_set(CORE_1, "212", {"unit_of_measurement": "°F"})
    await hass.async_block_till_done()
    assert float(hass.states.get(P1_CORE).state) == pytest.approx(100)

    hass.states.async_set(CORE_1, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(P1_CORE).state == "unknown"
    assert hass.states.get(P1_PHASE).state == "unknown"


async def test_wild_profile_sets_target(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Game profiles set the target; manual override keeps the profile."""
    await _select(hass, P1_FOOD, "wild_boar_leg")
    assert hass.states.get(P1_TARGET).state == "72.0"
    await _select(hass, P1_FOOD, "roe_deer_saddle")
    assert hass.states.get(P1_TARGET).state == "54.0"
    await _set_number(hass, P1_TARGET, 55)
    assert hass.states.get(P1_TARGET).state == "55.0"
    assert hass.states.get(P1_FOOD).state == "roe_deer_saddle"


async def test_assign_probe_runs_cook(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Attaching a probe starts the session; detaching the last one ends it."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, P1_FOOD, "suckling_pig")  # 75 °C

    await _select(hass, P1_GRILL, "Spanferkelgrill")
    assert hass.states.get(P1_GRILL).state == "Spanferkelgrill"
    assert hass.states.get(PIG_PROBES).state == "1"
    assert hass.states.get(PIG_PROBES).attributes["probes"] == ["Meater 2"]
    assert hass.states.get(PIG_DURATION).state == "0"
    assert _types(events) == ["session_started"]
    # Chamber comes from the probe's ambient sensor and is still cold
    assert hass.states.get(PIG_CHAMBER_TEMP).state == "25.0"
    assert hass.states.get(P1_PHASE).state == "heating"
    assert hass.states.get(P1_PROGRESS).state == "0.0"

    set_temp(hass, AMBIENT_1, 158)
    for minute in range(1, 11):
        freezer.tick(timedelta(minutes=1))
        set_temp(hass, CORE_1, 20 + 4 * minute)
        await hass.async_block_till_done()
    assert hass.states.get(P1_PHASE).state == "cooking"
    assert float(hass.states.get(P1_REMAINING).state) == pytest.approx(3.75, abs=0.1)
    assert float(hass.states.get(P1_PROGRESS).state) == pytest.approx(72.7, abs=0.1)
    assert hass.states.get(PIG_DURATION).state == "10"

    set_temp(hass, CORE_1, 71)
    await hass.async_block_till_done()
    assert hass.states.get(P1_PHASE).state == "near_done"
    set_temp(hass, CORE_1, 75.2)
    await hass.async_block_till_done()
    assert hass.states.get(P1_PHASE).state == "target_reached"
    assert hass.states.get(P1_REACHED).state == "on"
    assert _types(events) == ["session_started", "near_done", "target_reached"]
    reached = events[-1].data
    assert reached["grill"] == "Spanferkelgrill"
    assert reached["grill_type"] == "suckling_pig_grill"
    assert reached["probe"] == "Meater 2"
    assert reached["target"] == 75
    assert reached["outdoor_temperature"] == 14.5
    assert hass.states.get(PIG_EVENT).attributes["event_type"] == "target_reached"

    await _select(hass, P1_GRILL, "none")
    assert hass.states.get(PIG_DURATION).state == "unknown"
    assert hass.states.get(PIG_PROBES).state == "0"
    assert hass.states.get(P1_PHASE).state == "idle"
    last = hass.states.get(PIG_DURATION).attributes["last_session"]
    assert last["grill_type"] == "suckling_pig_grill"
    assert last["outdoor_temperature"] == 14.5
    assert last["probes"][0]["name"] == "Meater 2"
    assert last["probes"][0]["max_temperature"] == 75.2
    assert _types(events)[-1] == "session_ended"


async def test_two_probes_and_stop_button(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Removing one of two probes keeps the session; the stop button frees all."""
    await _select(hass, P1_GRILL, "Spanferkelgrill")
    await _select(hass, P2_GRILL, "Spanferkelgrill")
    assert hass.states.get(PIG_PROBES).state == "2"

    await _select(hass, P2_GRILL, "none")
    assert hass.states.get(PIG_DURATION).state == "0"
    await _select(hass, P2_GRILL, "Spanferkelgrill")

    await _press(hass, PIG_STOP)
    assert hass.states.get(PIG_DURATION).state == "unknown"
    assert hass.states.get(P1_GRILL).state == "none"
    assert hass.states.get(P2_GRILL).state == "none"


async def test_move_probe_between_grills(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Moving the only probe ends the old grill's session and starts the new one."""
    await _select(hass, P1_GRILL, "Spanferkelgrill")
    await _select(hass, P1_GRILL, "Smoker")
    assert hass.states.get(PIG_DURATION).state == "unknown"
    assert hass.states.get(SMOKER_DURATION).state == "0"
    assert hass.states.get(SMOKER_PROBES).attributes["probes"] == ["Meater 2"]


async def test_preheat_without_probe(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """A session can be started without a probe, e.g. to preheat."""
    await _press(hass, PIG_START)
    assert hass.states.get(PIG_DURATION).state == "0"
    assert hass.states.get(PIG_PROBES).state == "0"


async def test_smoker_own_chamber_sensor_and_stall(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """The smoker uses its own chamber sensor and detects a stall."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, P1_FOOD, "wild_boar_shoulder_pulled")  # 90 °C
    set_temp(hass, SMOKER_CHAMBER, 112)
    set_temp(hass, AMBIENT_1, 60)  # probe ambient is ignored for the smoker
    set_temp(hass, CORE_1, 70)
    await _select(hass, P1_GRILL, "Smoker")
    assert hass.states.get(SMOKER_CHAMBER_TEMP).state == "112.0"
    assert hass.states.get(P1_PHASE).state == "cooking"

    for _ in range(40):  # 20 minutes of 30 s ticks without source updates
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(P1_PHASE).state == "stall"
    assert hass.states.get(P1_REMAINING).state == "unknown"
    assert "stall_detected" in _types(events)


async def test_no_stall_on_gas_like_grills(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Grill types without low & slow cooking never report a stall."""
    hass.config_entries.async_update_subentry(
        setup,
        setup.subentries[PIG_GRILL_ID],
        data={"grill_type": "gas_grill"},
    )
    await hass.async_block_till_done()
    set_temp(hass, AMBIENT_1, 220)
    set_temp(hass, CORE_1, 70)
    await _select(hass, P1_FOOD, "pulled_pork")
    await _select(hass, P1_GRILL, "Spanferkelgrill")
    for _ in range(40):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert hass.states.get(P1_PHASE).state == "cooking"


async def test_chamber_deviation(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Deviation is only reported once the chamber reached its target range."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, P1_GRILL, "Spanferkelgrill")  # 160 °C target
    assert hass.states.get(PIG_DEVIATION).state == "off"

    set_temp(hass, AMBIENT_1, 155)
    await hass.async_block_till_done()
    set_temp(hass, AMBIENT_1, 190)
    await hass.async_block_till_done()
    assert hass.states.get(PIG_DEVIATION).state == "on"
    assert _types(events).count("chamber_deviation") == 1

    set_temp(hass, AMBIENT_1, 162)
    await hass.async_block_till_done()
    assert hass.states.get(PIG_DEVIATION).state == "off"

    await _set_number(hass, PIG_CHAMBER_TARGET, 200)
    assert hass.states.get(PIG_DEVIATION).state == "off"
    assert hass.states.get(P1_PHASE).state == "heating"


async def test_probe_offline_event(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """A probe dropping out during a session fires an event once."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, P2_GRILL, "Spanferkelgrill")
    hass.states.async_set(CORE_2, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(CORE_2, "unavailable", {"x": 1})
    await hass.async_block_till_done()
    assert _types(events) == ["session_started", "probe_offline"]
    assert events[-1].data["probe"] == "Meater plus"


async def test_state_restored_after_reload(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Assignment, profile and running session survive a reload without re-firing."""
    events = async_capture_events(hass, EVENT_KITCHEN)
    await _select(hass, P1_FOOD, "red_deer_leg")  # 64 °C
    await _select(hass, P1_GRILL, "Spanferkelgrill")
    await _set_number(hass, PIG_CHAMBER_TARGET, 150)
    set_temp(hass, CORE_1, 65)
    await hass.async_block_till_done()
    assert _types(events) == ["session_started", "target_reached"]

    assert await hass.config_entries.async_reload(setup.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(P1_GRILL).state == "Spanferkelgrill"
    assert hass.states.get(P1_FOOD).state == "red_deer_leg"
    assert hass.states.get(P1_TARGET).state == "64.0"
    assert hass.states.get(PIG_CHAMBER_TARGET).state == "150.0"
    assert hass.states.get(PIG_DURATION).state == "0"
    assert hass.states.get(P1_PHASE).state == "target_reached"
    assert _types(events) == ["session_started", "target_reached"]


async def test_outdoor_temperature_from_weather(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A weather entity can provide the outdoor temperature."""
    hass.states.async_set(
        "weather.garten",
        "sunny",
        {"temperature": 68, "temperature_unit": "°F"},
    )
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={CONF_OUTDOOR_TEMPERATURE: "weather.garten"}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(PIG_OUTDOOR).state) == pytest.approx(20)


async def test_unload(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """The entry unloads cleanly."""
    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()
    set_temp(hass, CORE_1, 50)
    await hass.async_block_till_done()
    assert hass.states.get(P1_CORE).state == "unavailable"
