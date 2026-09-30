"""Tests for migrating version 1 outdoor kitchens into grills and probes."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garten.const import (
    CONF_CAMERA,
    CONF_CHAMBER_TOLERANCE,
    CONF_GRILL_TYPE,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    DOMAIN,
    SUBENTRY_GRILL,
    SUBENTRY_PROBE,
)

from .conftest import AMBIENT_1, CORE_1, CORE_2, set_temp


def _v1_entry() -> MockConfigEntry:
    """Two v1 kitchens as created with version 0.1.0 (probe CORE_1 used twice)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garten",
        unique_id=DOMAIN,
        version=1,
        data={},
        subentries_data=[
            ConfigSubentryData(
                subentry_id="kitchen_1",
                subentry_type="kitchen",
                title="Outdoor-Küche",
                unique_id=None,
                data={
                    "probes": [
                        {
                            "name": "Meater 2",
                            CONF_PROBE_CORE: CORE_1,
                            CONF_PROBE_AMBIENT: AMBIENT_1,
                        },
                        {"name": "Meater plus", CONF_PROBE_CORE: CORE_2},
                    ],
                    CONF_CHAMBER_TOLERANCE: 20,
                    CONF_CAMERA: "camera.outdoor_kuche",
                },
            ),
            ConfigSubentryData(
                subentry_id="kitchen_2",
                subentry_type="kitchen",
                title="Outdoor-Küche",
                unique_id=None,
                data={
                    "probes": [
                        {"name": "Sonde 1", CONF_PROBE_CORE: CORE_1},
                        {"name": "Meater 2", CONF_PROBE_CORE: "sensor.extra_probe"},
                    ],
                    CONF_CHAMBER_TOLERANCE: 15,
                },
            ),
        ],
    )


async def test_migrate_kitchens(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Kitchens become grills, probes become deduplicated probe subentries."""
    entry = _v1_entry()
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {
            "kitchen_1": {
                "method": "suckling_pig",
                "chamber_target": 170,
                "session_start": "2026-09-30T08:00:00+00:00",
                "probes": {
                    CORE_1: {"profile": "suckling_pig", "target": 75.0, "fired": []},
                    CORE_2: {"profile": "custom", "target": 61.0, "fired": []},
                },
                "sessions": [{"duration_min": 300, "method": "suckling_pig"}],
            },
            "kitchen_2": {"method": "off", "chamber_target": None},
        },
    }
    set_temp(hass, CORE_1, 20)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    subentries = list(entry.subentries.values())
    assert all(s.subentry_type in (SUBENTRY_GRILL, SUBENTRY_PROBE) for s in subentries)

    grills = {s.title: s for s in subentries if s.subentry_type == SUBENTRY_GRILL}
    assert set(grills) == {"Outdoor-Küche", "Outdoor-Küche 2"}
    assert dict(grills["Outdoor-Küche"].data) == {
        CONF_GRILL_TYPE: "suckling_pig_grill",
        CONF_CHAMBER_TOLERANCE: 20,
        CONF_CAMERA: "camera.outdoor_kuche",
    }
    assert grills["Outdoor-Küche 2"].data[CONF_GRILL_TYPE] == "gas_grill"

    probes = {s.title: s for s in subentries if s.subentry_type == SUBENTRY_PROBE}
    # CORE_1 appeared in both kitchens -> one probe; duplicate names get a suffix
    assert set(probes) == {"Meater 2", "Meater plus", "Meater 2 2"}
    assert dict(probes["Meater 2"].data) == {
        CONF_PROBE_CORE: CORE_1,
        CONF_PROBE_AMBIENT: AMBIENT_1,
    }
    assert probes["Meater 2 2"].data[CONF_PROBE_CORE] == "sensor.extra_probe"

    # Stored settings were carried over; the running session was not
    kitchen = entry.runtime_data.kitchen
    pig = kitchen.grills[grills["Outdoor-Küche"].subentry_id]
    assert pig.chamber_target == 170
    assert not pig.session_active
    assert pig.sessions == [{"duration_min": 300, "method": "suckling_pig"}]
    meater = kitchen.probes[probes["Meater 2"].subentry_id]
    assert meater.profile == "suckling_pig"
    assert meater.target == 75.0
    assert meater.grill_id is None
    assert kitchen.grills[grills["Outdoor-Küche 2"].subentry_id].chamber_target == 220

    # Old kitchen data is gone from storage
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    assert "kitchen_1" not in stored
    assert "kitchen_2" not in stored

    # Entities of the new devices exist
    assert hass.states.get("select.meater_2_grill").attributes["options"] == [
        "none",
        "Outdoor-Küche",
        "Outdoor-Küche 2",
    ]


async def test_future_version_is_rejected(hass: HomeAssistant) -> None:
    """Downgrades from an unknown future version fail cleanly."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, version=3, data={})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
