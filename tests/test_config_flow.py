"""Tests for the Garten config flow and kitchen subentry flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garten.const import (
    CONF_CAMERA,
    CONF_CHAMBER_TOLERANCE,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    CONF_PROBE_NAME,
    CONF_PROBES,
    DOMAIN,
    SUBENTRY_KITCHEN,
)

from .conftest import AMBIENT_1, CORE_1, CORE_2, KITCHEN_ID


async def test_create_entry(hass: HomeAssistant) -> None:
    """The user step creates the single Garten entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garten"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _form(**probes: dict) -> dict:
    form = {
        CONF_NAME: "Outdoor-Küche",
        CONF_CHAMBER_TOLERANCE: 10,
        "probe_1": {},
        "probe_2": {},
        "probe_3": {},
        "probe_4": {},
    }
    form.update(probes)
    return form


async def test_add_kitchen(hass: HomeAssistant) -> None:
    """A kitchen subentry is created from the form."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_KITCHEN), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Same core sensor twice, and ambient without core
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _form(
            probe_1={CONF_PROBE_CORE: CORE_1},
            probe_2={CONF_PROBE_CORE: CORE_1},
            probe_3={CONF_PROBE_AMBIENT: AMBIENT_1},
        ),
    )
    assert result["errors"] == {
        "probe_2": "duplicate_probe",
        "probe_3": "core_required",
    }

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _form(
            probe_1={
                CONF_PROBE_NAME: "Meater 2",
                CONF_PROBE_CORE: CORE_1,
                CONF_PROBE_AMBIENT: AMBIENT_1,
            },
            probe_3={CONF_PROBE_CORE: CORE_2},
        ),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Outdoor-Küche"
    assert subentry.data[CONF_PROBES] == [
        {
            CONF_PROBE_NAME: "Meater 2",
            CONF_PROBE_CORE: CORE_1,
            CONF_PROBE_AMBIENT: AMBIENT_1,
        },
        {CONF_PROBE_NAME: "Sonde 3", CONF_PROBE_CORE: CORE_2},
    ]
    assert subentry.data[CONF_CHAMBER_TOLERANCE] == 10


async def test_reconfigure_kitchen(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Reconfiguring keeps existing values as suggestions and updates data."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_KITCHEN),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": KITCHEN_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _form(probe_1={CONF_PROBE_NAME: "Brisket", CONF_PROBE_CORE: CORE_2})
        | {CONF_NAME: "Grillplatz", CONF_CAMERA: "camera.grill"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    subentry = config_entry.subentries[KITCHEN_ID]
    assert subentry.title == "Grillplatz"
    assert subentry.data[CONF_PROBES] == [
        {CONF_PROBE_NAME: "Brisket", CONF_PROBE_CORE: CORE_2}
    ]
    assert subentry.data[CONF_CAMERA] == "camera.grill"
    # Entry was reloaded: probe slot 1 now mirrors the new sensor under its new name
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{KITCHEN_ID}_probe0_core_temperature"
    )
    state = hass.states.get(entity_id)
    assert state.attributes["friendly_name"] == "Grillplatz Brisket core temperature"
    assert state.attributes["source"] == CORE_2
    # The removed second probe leaves no stale entities behind
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{KITCHEN_ID}_probe1_core_temperature"
        )
        is None
    )
