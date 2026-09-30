"""Tests for the pool subentry, its entities and the dashboard card."""

from __future__ import annotations

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.garten.const import (
    CONF_CAMERA,
    CONF_POOL_GUIDANCE,
    CONF_POOL_LAST_MEASUREMENT,
    CONF_POOL_ORP,
    CONF_POOL_PH,
    CONF_POOL_POWER,
    CONF_POOL_PUMP,
    CONF_POOL_RECOMMENDED_RUNTIME,
    CONF_POOL_SOLAR_SURPLUS,
    CONF_POOL_TEMPERATURE,
    DOMAIN,
    EVENT_POOL,
    SUBENTRY_POOL,
)

POOL_ID = "pool_1"
PUMP = "switch.pumpe"
POWER = "sensor.pumpe_leistung"
TEMP = "sensor.wasser_temperatur"
PH = "sensor.wasser_ph"
ORP = "sensor.wasser_orp"
LAST = "sensor.wasser_messung"
GUIDANCE = "sensor.wasser_hinweis"
RECOMMENDED = "sensor.wasser_laufzeit_empfohlen"
SURPLUS = "sensor.solar_ueberschuss"

QUALITY = "sensor.pool_water_quality"
PH_STATUS = "sensor.pool_ph_status"
ORP_STATUS = "sensor.pool_redox_status"
RUNTIME = "sensor.pool_pump_runtime_today"
BACKWASH_HOURS = "sensor.pool_pump_hours_since_backwash"
LAST_BACKWASH = "sensor.pool_last_backwash"
ENERGY_TODAY = "sensor.pool_energy_today"
SOLAR_TODAY = "sensor.pool_solar_share_today"
COST_TODAY = "sensor.pool_electricity_cost_today"
SAVINGS = "sensor.pool_solar_savings_this_year"
BACKWASH_DUE = "binary_sensor.pool_backwash_due"
STALE = "binary_sensor.pool_measurement_stale"
BACKWASHED = "button.pool_backwashed"
INTERVAL = "number.pool_backwash_after_pump_hours"
MAX_DAYS = "number.pool_backwash_at_the_latest_after"
PRICE = "number.pool_electricity_price"
EVENT_ENTITY = "event.pool_pool_event"

POOL_DATA = {
    CONF_POOL_PUMP: PUMP,
    CONF_POOL_POWER: POWER,
    CONF_POOL_TEMPERATURE: TEMP,
    CONF_POOL_PH: PH,
    CONF_POOL_ORP: ORP,
    CONF_POOL_LAST_MEASUREMENT: LAST,
    CONF_POOL_GUIDANCE: GUIDANCE,
    CONF_POOL_RECOMMENDED_RUNTIME: RECOMMENDED,
    CONF_POOL_SOLAR_SURPLUS: SURPLUS,
    CONF_CAMERA: "camera.pool",
}


@pytest.fixture
def pool_entry() -> MockConfigEntry:
    """Garten entry with one pool."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garten",
        unique_id=DOMAIN,
        version=2,
        data={},
        subentries_data=[
            {
                "subentry_id": POOL_ID,
                "subentry_type": SUBENTRY_POOL,
                "title": "Pool",
                "unique_id": None,
                "data": POOL_DATA,
            }
        ],
    )


def _set_sources(hass: HomeAssistant, *, pump: str = "off", power: float = 0) -> None:
    hass.states.async_set(PUMP, pump)
    hass.states.async_set(POWER, str(power), {"unit_of_measurement": "W"})
    hass.states.async_set(TEMP, "21.6", {"unit_of_measurement": "°C"})
    hass.states.async_set(PH, "7.0")
    hass.states.async_set(ORP, "700")
    hass.states.async_set(LAST, dt_util.utcnow().isoformat())
    hass.states.async_set(GUIDANCE, "pH-Wert zu niedrig: 258 g pH+ hinzufügen")
    hass.states.async_set(RECOMMENDED, "10.8", {"unit_of_measurement": "h"})
    hass.states.async_set(SURPLUS, "100", {"unit_of_measurement": "W"})


@pytest.fixture
async def setup(hass: HomeAssistant, pool_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the pool."""
    _set_sources(hass)
    pool_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(pool_entry.entry_id)
    await hass.async_block_till_done()
    return pool_entry


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: int):
    for _ in range(minutes):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


def _types(events) -> list[str]:
    return [e.data["type"] for e in events]


async def test_add_pool_flow(hass: HomeAssistant) -> None:
    """A pool is added with a unique name; empty optional fields are dropped."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, version=2, data={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_POOL), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Pool", CONF_POOL_PUMP: PUMP, CONF_POOL_PH: PH},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    pool = next(iter(entry.subentries.values()))
    assert pool.title == "Pool"
    assert dict(pool.data) == {CONF_POOL_PUMP: PUMP, CONF_POOL_PH: PH}

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_POOL), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "pool", CONF_POOL_PUMP: PUMP}
    )
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_reconfigure_pool(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Removing sources on reconfigure removes their entities after reload."""
    result = await hass.config_entries.subentries.async_init(
        (setup.entry_id, SUBENTRY_POOL),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": POOL_ID},
    )
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Pool", CONF_POOL_PUMP: PUMP, CONF_POOL_PH: PH}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert dict(setup.subentries[POOL_ID].data) == {
        CONF_POOL_PUMP: PUMP,
        CONF_POOL_PH: PH,
    }
    attrs = hass.states.get(QUALITY).attributes
    assert set(attrs["values"]) == {"ph"}
    assert "energy_today" not in attrs["card_entities"]


async def test_entities_and_card_attributes(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """The pool device exposes ratings and everything the card needs."""
    quality = hass.states.get(QUALITY)
    assert quality.state == "check"  # pH 7.0 is below the ok range
    assert hass.states.get(PH_STATUS).state == "check"
    assert hass.states.get(ORP_STATUS).state == "ok"
    attrs = quality.attributes
    assert attrs["pool_name"] == "Pool"
    assert attrs["values"] == {"ph": 7.0, "orp": 700.0}
    assert attrs["ranges"]["ph"] == [6.8, 7.2, 7.6, 8.0]
    assert attrs["guidance"] == "pH-Wert zu niedrig: 258 g pH+ hinzufügen"
    assert attrs["card_sources"][CONF_POOL_PUMP] == PUMP
    assert attrs["card_sources"][CONF_CAMERA] == "camera.pool"
    cards = attrs["card_entities"]
    assert cards["water_quality"] == QUALITY
    assert cards["runtime_today"] == RUNTIME
    assert cards["backwash_done"] == BACKWASHED
    assert cards["solar_share_today"] == SOLAR_TODAY
    for entity_id in cards.values():
        assert hass.states.get(entity_id) is not None, entity_id

    assert hass.states.get(STALE).state == "off"
    assert hass.states.get(BACKWASH_DUE).state == "off"
    assert hass.states.get(LAST_BACKWASH).state == "unknown"
    assert hass.states.get(INTERVAL).state == "50"
    assert hass.states.get(MAX_DAYS).state == "14"
    assert hass.states.get(PRICE).state == "0.3"


async def test_runtime_energy_and_solar(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Runtime, energy and solar share accumulate only while the pump runs."""
    await _tick(hass, freezer, 30)
    assert float(hass.states.get(RUNTIME).state) == 0

    hass.states.async_set(PUMP, "on")
    hass.states.async_set(POWER, "600", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await _tick(hass, freezer, 30)  # 30 min fully on solar
    hass.states.async_set(SURPLUS, "-300", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await _tick(hass, freezer, 30)  # 30 min with 300 W from solar

    assert float(hass.states.get(RUNTIME).state) == pytest.approx(1.0, abs=0.02)
    assert float(hass.states.get(BACKWASH_HOURS).state) == pytest.approx(1.0, abs=0.02)
    assert float(hass.states.get(ENERGY_TODAY).state) == pytest.approx(0.6, abs=0.01)
    assert float(hass.states.get(SOLAR_TODAY).state) == pytest.approx(75, abs=1)
    # Grid part 0.15 kWh at 0.30 €/kWh
    assert float(hass.states.get(COST_TODAY).state) == pytest.approx(0.045, abs=0.002)
    assert float(hass.states.get(SAVINGS).state) == pytest.approx(0.14, abs=0.01)

    await hass.services.async_call(
        "number", "set_value", {"entity_id": PRICE, "value": 0.4}, True
    )
    assert float(hass.states.get(COST_TODAY).state) == pytest.approx(0.06, abs=0.002)


async def test_runtime_resets_at_midnight(
    hass: HomeAssistant, pool_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Runtime today restarts after midnight; backwash hours keep counting."""
    freezer.move_to(
        datetime(2026, 7, 1, 23, 30, tzinfo=dt_util.get_default_time_zone())
    )
    _set_sources(hass, pump="on", power=500)
    pool_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(pool_entry.entry_id)
    await hass.async_block_till_done()

    await _tick(hass, freezer, 29)
    assert float(hass.states.get(RUNTIME).state) == pytest.approx(0.48, abs=0.02)
    await _tick(hass, freezer, 31)
    assert float(hass.states.get(RUNTIME).state) == pytest.approx(0.5, abs=0.02)
    assert float(hass.states.get(BACKWASH_HOURS).state) == pytest.approx(1.0, abs=0.02)


async def test_backwash_due_and_reset(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Backwash is due after the pump hours; the button resets the counter."""
    events = async_capture_events(hass, EVENT_POOL)
    await hass.services.async_call(
        "number", "set_value", {"entity_id": INTERVAL, "value": 5}, True
    )
    hass.states.async_set(PUMP, "on")
    await hass.async_block_till_done()
    await _tick(hass, freezer, 5 * 60 + 1)

    assert hass.states.get(BACKWASH_DUE).state == "on"
    assert _types(events) == ["backwash_due"]
    assert hass.states.get(EVENT_ENTITY).attributes["event_type"] == "backwash_due"

    await hass.services.async_call("button", "press", {"entity_id": BACKWASHED}, True)
    assert hass.states.get(BACKWASH_DUE).state == "off"
    assert float(hass.states.get(BACKWASH_HOURS).state) == 0
    assert hass.states.get(LAST_BACKWASH).state != "unknown"
    assert _types(events) == ["backwash_due", "backwash_done"]
    assert events[-1].data["pump_hours"] == pytest.approx(5.0, abs=0.1)


async def test_backwash_due_after_days(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Backwash is also due after the maximum number of days."""
    await hass.services.async_call("button", "press", {"entity_id": BACKWASHED}, True)
    await hass.services.async_call(
        "number", "set_value", {"entity_id": MAX_DAYS, "value": 2}, True
    )
    freezer.tick(timedelta(days=2, minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(BACKWASH_DUE).state == "on"


async def test_quality_worsening_and_stale_events(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Worsening water quality and stale measurements fire events once."""
    events = async_capture_events(hass, EVENT_POOL)
    hass.states.async_set(ORP, "350")
    await hass.async_block_till_done()
    assert hass.states.get(QUALITY).state == "critical"
    assert _types(events) == ["water_quality_changed"]
    assert events[0].data["quality"] == "critical"
    assert events[0].data["previous"] == "check"

    # Improving does not fire
    hass.states.async_set(ORP, "700")
    hass.states.async_set(PH, "7.4")
    await hass.async_block_till_done()
    assert hass.states.get(QUALITY).state == "ok"
    assert _types(events) == ["water_quality_changed"]

    await _tick(hass, freezer, 12 * 60 + 2)
    assert hass.states.get(STALE).state == "on"
    assert _types(events) == ["water_quality_changed", "measurement_stale"]


async def test_state_restored_after_reload(
    hass: HomeAssistant, setup: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """Counters and settings survive a reload."""
    await hass.services.async_call(
        "number", "set_value", {"entity_id": PRICE, "value": 0.35}, True
    )
    hass.states.async_set(PUMP, "on")
    hass.states.async_set(POWER, "600", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await _tick(hass, freezer, 60)

    assert await hass.config_entries.async_reload(setup.entry_id)
    await hass.async_block_till_done()
    assert float(hass.states.get(RUNTIME).state) == pytest.approx(1.0, abs=0.02)
    assert float(hass.states.get(BACKWASH_HOURS).state) == pytest.approx(1.0, abs=0.02)
    assert float(hass.states.get(ENERGY_TODAY).state) == pytest.approx(0.6, abs=0.01)
    assert hass.states.get(PRICE).state == "0.35"


async def test_card_is_served(
    hass: HomeAssistant, setup: MockConfigEntry, hass_client
) -> None:
    """The dashboard card is served by the integration."""
    client = await hass_client()
    response = await client.get("/garten_static/garten-pool-card.js")
    assert response.status == 200
    assert "garten-pool-card" in await response.text()


async def test_disabled_entities_survive_reload(
    hass: HomeAssistant, setup: MockConfigEntry
) -> None:
    """Entities disabled by the user are not treated as orphaned."""
    registry = er.async_get(hass)
    registry.async_update_entity(COST_TODAY, disabled_by=er.RegistryEntryDisabler.USER)
    assert await hass.config_entries.async_reload(setup.entry_id)
    await hass.async_block_till_done()
    entry = registry.async_get(COST_TODAY)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.USER
