"""Config flow for the Garten integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
import voluptuous as vol

from .const import (
    CONF_CAMERA,
    CONF_CHAMBER_TOLERANCE,
    CONF_LIGHT,
    CONF_POWER_SWITCH,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    CONF_PROBE_NAME,
    CONF_PROBES,
    DEFAULT_CHAMBER_TOLERANCE,
    DOMAIN,
    MAX_PROBES,
    NAME,
    SUBENTRY_KITCHEN,
)

DEFAULT_KITCHEN_NAME = "Outdoor-Küche"

_TEMPERATURE_SENSOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.TEMPERATURE)
)


class GartenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Garten entry; areas are added as subentries."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user")

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the areas that can be added."""
        return {SUBENTRY_KITCHEN: KitchenSubentryFlow}


def _probe_key(number: int) -> str:
    return f"probe_{number}"


def _kitchen_schema() -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=DEFAULT_KITCHEN_NAME): TextSelector(),
    }
    for number in range(1, MAX_PROBES + 1):
        core = (
            vol.Required(CONF_PROBE_CORE)
            if number == 1
            else vol.Optional(CONF_PROBE_CORE)
        )
        schema[vol.Required(_probe_key(number))] = section(
            vol.Schema(
                {
                    vol.Optional(CONF_PROBE_NAME): TextSelector(),
                    core: _TEMPERATURE_SENSOR,
                    vol.Optional(CONF_PROBE_AMBIENT): _TEMPERATURE_SENSOR,
                }
            ),
            {"collapsed": number > 1},
        )
    schema.update(
        {
            vol.Required(
                CONF_CHAMBER_TOLERANCE, default=DEFAULT_CHAMBER_TOLERANCE
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=50,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTemperature.CELSIUS,
                )
            ),
            vol.Optional(CONF_CAMERA): EntitySelector(
                EntitySelectorConfig(domain="camera")
            ),
            vol.Optional(CONF_LIGHT): EntitySelector(
                EntitySelectorConfig(domain="light")
            ),
            vol.Optional(CONF_POWER_SWITCH): EntitySelector(
                EntitySelectorConfig(domain="switch")
            ),
        }
    )
    return vol.Schema(schema)


def _form_to_data(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Convert form input into subentry data; return (data, errors)."""
    errors: dict[str, str] = {}
    probes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number in range(1, MAX_PROBES + 1):
        key = _probe_key(number)
        values = user_input.get(key) or {}
        core = values.get(CONF_PROBE_CORE)
        if not core:
            if values.get(CONF_PROBE_AMBIENT):
                errors[key] = "core_required"
            continue
        if core in seen:
            errors[key] = "duplicate_probe"
            continue
        seen.add(core)
        probe = {
            CONF_PROBE_NAME: (values.get(CONF_PROBE_NAME) or "").strip()
            or f"Sonde {number}",
            CONF_PROBE_CORE: core,
        }
        if ambient := values.get(CONF_PROBE_AMBIENT):
            probe[CONF_PROBE_AMBIENT] = ambient
        probes.append(probe)
    if not probes and not errors:
        errors["base"] = "no_probe"

    data: dict[str, Any] = {
        CONF_PROBES: probes,
        CONF_CHAMBER_TOLERANCE: user_input.get(
            CONF_CHAMBER_TOLERANCE, DEFAULT_CHAMBER_TOLERANCE
        ),
    }
    for key in (CONF_CAMERA, CONF_LIGHT, CONF_POWER_SWITCH):
        if value := user_input.get(key):
            data[key] = value
    return data, errors


def _data_to_form(title: str, data: dict[str, Any]) -> dict[str, Any]:
    """Convert stored subentry data back into form values."""
    form: dict[str, Any] = {CONF_NAME: title}
    for number in range(1, MAX_PROBES + 1):
        form[_probe_key(number)] = {}
    for number, probe in enumerate(data.get(CONF_PROBES, []), start=1):
        form[_probe_key(number)] = dict(probe)
    for key in (CONF_CHAMBER_TOLERANCE, CONF_CAMERA, CONF_LIGHT, CONF_POWER_SWITCH):
        if key in data:
            form[key] = data[key]
    return form


class KitchenSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure an outdoor kitchen."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add an outdoor kitchen."""
        errors: dict[str, str] = {}
        schema = _kitchen_schema()
        if user_input is not None:
            data, errors = _form_to_data(user_input)
            if not errors:
                return self.async_create_entry(title=user_input[CONF_NAME], data=data)
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change probes and linked devices of an outdoor kitchen."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _form_to_data(user_input)
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_NAME],
                    data=data,
                )
            suggested = user_input
        else:
            suggested = _data_to_form(subentry.title, dict(subentry.data))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _kitchen_schema(), suggested
            ),
            errors=errors,
        )
