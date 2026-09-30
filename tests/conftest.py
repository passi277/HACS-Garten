"""Fixtures for Garten tests."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garten.const import (
    CONF_CAMERA,
    CONF_CHAMBER_ENTITY,
    CONF_GRILL_TYPE,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    DOMAIN,
    SUBENTRY_GRILL,
    SUBENTRY_PROBE,
)

CORE_1 = "sensor.meater_2_innentemperatur"
AMBIENT_1 = "sensor.meater_2_umgebungstemperatur"
CORE_2 = "sensor.meater_plus_innentemperatur"
SMOKER_CHAMBER = "sensor.smoker_thermometer"
OUTDOOR = "sensor.temperatur_draussen"

PIG_GRILL_ID = "grill_pig"
SMOKER_ID = "grill_smoker"
PROBE_1_ID = "probe_meater_2"
PROBE_2_ID = "probe_meater_plus"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the custom integration in all tests."""


def set_temp(hass: HomeAssistant, entity_id: str, value: float | str) -> None:
    """Set a temperature source state."""
    hass.states.async_set(
        entity_id,
        str(value),
        {
            "unit_of_measurement": UnitOfTemperature.CELSIUS,
            "device_class": "temperature",
        },
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a Garten entry with two grills and two probes."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garten",
        unique_id=DOMAIN,
        version=2,
        data={CONF_OUTDOOR_TEMPERATURE: OUTDOOR},
        subentries_data=[
            ConfigSubentryData(
                subentry_id=PIG_GRILL_ID,
                subentry_type=SUBENTRY_GRILL,
                title="Spanferkelgrill",
                unique_id=None,
                data={
                    CONF_GRILL_TYPE: "suckling_pig_grill",
                    CONF_CAMERA: "camera.outdoor_kuche",
                },
            ),
            ConfigSubentryData(
                subentry_id=SMOKER_ID,
                subentry_type=SUBENTRY_GRILL,
                title="Smoker",
                unique_id=None,
                data={CONF_GRILL_TYPE: "smoker", CONF_CHAMBER_ENTITY: SMOKER_CHAMBER},
            ),
            ConfigSubentryData(
                subentry_id=PROBE_1_ID,
                subentry_type=SUBENTRY_PROBE,
                title="Meater 2",
                unique_id=None,
                data={CONF_PROBE_CORE: CORE_1, CONF_PROBE_AMBIENT: AMBIENT_1},
            ),
            ConfigSubentryData(
                subentry_id=PROBE_2_ID,
                subentry_type=SUBENTRY_PROBE,
                title="Meater plus",
                unique_id=None,
                data={CONF_PROBE_CORE: CORE_2},
            ),
        ],
    )
