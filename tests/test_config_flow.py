"""Tests for the Garten config flow and the grill / probe subentry flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garten.const import (
    CONF_CHAMBER_ENTITY,
    CONF_CHAMBER_TOLERANCE,
    CONF_GRILL_TYPE,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    DOMAIN,
    SUBENTRY_GRILL,
    SUBENTRY_PROBE,
)

from .conftest import (
    AMBIENT_1,
    CORE_1,
    CORE_2,
    OUTDOOR,
    PROBE_2_ID,
    SMOKER_CHAMBER,
)


async def test_create_entry(hass: HomeAssistant) -> None:
    """The user step creates the single Garten entry with the outdoor sensor."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_TEMPERATURE: OUTDOOR}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garten"
    assert result["data"] == {CONF_OUTDOOR_TEMPERATURE: OUTDOOR}
    assert result["result"].version == 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_outdoor_temperature(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The outdoor temperature can be changed to a weather entity."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OUTDOOR_TEMPERATURE: "weather.garten"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_OUTDOOR_TEMPERATURE: "weather.garten"}


async def _start(hass: HomeAssistant, entry: MockConfigEntry, subentry_type: str):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, subentry_type), context={"source": SOURCE_USER}
    )


async def test_add_grill(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Grills are added with a unique, non-reserved name."""
    config_entry.add_to_hass(hass)

    result = await _start(hass, config_entry, SUBENTRY_GRILL)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: " smoker ", CONF_GRILL_TYPE: "smoker", CONF_CHAMBER_TOLERANCE: 10},
    )
    assert result["errors"] == {CONF_NAME: "name_exists"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "None", CONF_GRILL_TYPE: "smoker", CONF_CHAMBER_TOLERANCE: 10},
    )
    assert result["errors"] == {CONF_NAME: "name_reserved"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Dutch Oven",
            CONF_GRILL_TYPE: "dutch_oven",
            CONF_CHAMBER_TOLERANCE: 10,
            CONF_CHAMBER_ENTITY: SMOKER_CHAMBER,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    grill = next(s for s in config_entry.subentries.values() if s.title == "Dutch Oven")
    assert grill.subentry_type == SUBENTRY_GRILL
    assert dict(grill.data) == {
        CONF_GRILL_TYPE: "dutch_oven",
        CONF_CHAMBER_TOLERANCE: 10,
        CONF_CHAMBER_ENTITY: SMOKER_CHAMBER,
    }


async def test_add_probe(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Probes need an unused core sensor and a different ambient sensor."""
    config_entry.add_to_hass(hass)

    result = await _start(hass, config_entry, SUBENTRY_PROBE)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Neue Sonde", CONF_PROBE_CORE: CORE_1}
    )
    assert result["errors"] == {CONF_PROBE_CORE: "core_in_use"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Neue Sonde",
            CONF_PROBE_CORE: "sensor.neu",
            CONF_PROBE_AMBIENT: "sensor.neu",
        },
    )
    assert result["errors"] == {CONF_PROBE_AMBIENT: "same_as_core"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Neue Sonde", CONF_PROBE_CORE: "sensor.neu"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    probe = next(s for s in config_entry.subentries.values() if s.title == "Neue Sonde")
    assert dict(probe.data) == {CONF_PROBE_CORE: "sensor.neu"}


async def test_reconfigure_probe(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A probe can be renamed and get an ambient sensor; the entry reloads."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_PROBE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": PROBE_2_ID},
    )
    assert result["step_id"] == "reconfigure"

    # Keeping its own core sensor is fine, taking the other probe's is not
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Meater plus", CONF_PROBE_CORE: CORE_1}
    )
    assert result["errors"] == {CONF_PROBE_CORE: "core_in_use"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Wildsonde",
            CONF_PROBE_CORE: CORE_2,
            CONF_PROBE_AMBIENT: AMBIENT_1,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    subentry = config_entry.subentries[PROBE_2_ID]
    assert subentry.title == "Wildsonde"
    assert dict(subentry.data) == {
        CONF_PROBE_CORE: CORE_2,
        CONF_PROBE_AMBIENT: AMBIENT_1,
    }
    # Reloaded: the probe now also has an ambient temperature sensor
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{PROBE_2_ID}_ambient_temperature"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).attributes["source"] == AMBIENT_1
