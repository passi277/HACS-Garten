"""Fixtures for Garten tests."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garten.const import (
    CONF_CAMERA,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    CONF_PROBE_NAME,
    CONF_PROBES,
    DOMAIN,
    SUBENTRY_KITCHEN,
)

CORE_1 = "sensor.meater_2_innentemperatur"
AMBIENT_1 = "sensor.meater_2_umgebungstemperatur"
CORE_2 = "sensor.meater_plus_innentemperatur"
KITCHEN_ID = "kitchen_subentry_id"


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
    """Return a Garten entry with one outdoor kitchen and two probes."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garten",
        unique_id=DOMAIN,
        data={},
        subentries_data=[
            ConfigSubentryData(
                subentry_id=KITCHEN_ID,
                subentry_type=SUBENTRY_KITCHEN,
                title="Outdoor-Küche",
                unique_id=None,
                data={
                    CONF_PROBES: [
                        {
                            CONF_PROBE_NAME: "Meater 2",
                            CONF_PROBE_CORE: CORE_1,
                            CONF_PROBE_AMBIENT: AMBIENT_1,
                        },
                        {CONF_PROBE_NAME: "Meater plus", CONF_PROBE_CORE: CORE_2},
                    ],
                    CONF_CAMERA: "camera.outdoor_kuche",
                },
            )
        ],
    )
