"""Config flow for the Garten integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import voluptuous as vol

from .const import (
    CONF_CAMERA,
    CONF_CHAMBER_ENTITY,
    CONF_CHAMBER_TOLERANCE,
    CONF_GRILL_TYPE,
    CONF_LIGHT,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_POOL_CHLORINE,
    CONF_POOL_GUIDANCE,
    CONF_POOL_LAST_MEASUREMENT,
    CONF_POOL_ORP,
    CONF_POOL_PH,
    CONF_POOL_POWER,
    CONF_POOL_PUMP,
    CONF_POOL_RECOMMENDED_RUNTIME,
    CONF_POOL_SALT,
    CONF_POOL_SOLAR_SURPLUS,
    CONF_POOL_TEMPERATURE,
    CONF_POWER_SWITCH,
    CONF_PROBE_AMBIENT,
    CONF_PROBE_CORE,
    DEFAULT_CHAMBER_TOLERANCE,
    DOMAIN,
    NAME,
    NO_GRILL,
    SUBENTRY_GRILL,
    SUBENTRY_POOL,
    SUBENTRY_PROBE,
)
from .kitchen.profiles import GrillType

_TEMPERATURE_SENSOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.TEMPERATURE)
)
_SENSOR = EntitySelector(EntitySelectorConfig(domain="sensor"))
_OUTDOOR_TEMPERATURE = EntitySelector(
    EntitySelectorConfig(
        filter=[
            EntityFilterSelectorConfig(
                domain="sensor", device_class=SensorDeviceClass.TEMPERATURE
            ),
            EntityFilterSelectorConfig(domain="weather"),
        ]
    )
)


def _outdoor_schema() -> vol.Schema:
    return vol.Schema({vol.Optional(CONF_OUTDOOR_TEMPERATURE): _OUTDOOR_TEMPERATURE})


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional values."""
    return {key: value for key, value in user_input.items() if value not in (None, "")}


class GartenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single Garten entry; grills and probes are subentries."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data=_clean(user_input))
        return self.async_show_form(step_id="user", data_schema=_outdoor_schema())

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the garden settings (outdoor temperature)."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_and_abort(entry, data=_clean(user_input))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _outdoor_schema(), dict(entry.data)
            ),
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the things that can be added to the garden."""
        return {
            SUBENTRY_GRILL: GrillSubentryFlow,
            SUBENTRY_PROBE: ProbeSubentryFlow,
            SUBENTRY_POOL: PoolSubentryFlow,
        }


class _GartenSubentryFlow(ConfigSubentryFlow):
    """Shared add/reconfigure handling for grills and probes."""

    subentry_type: str

    def _schema(self) -> vol.Schema:
        raise NotImplementedError

    def _validate(
        self, user_input: dict[str, Any], others: list[ConfigSubentry]
    ) -> dict[str, str]:
        raise NotImplementedError

    def _others(self, exclude: str | None) -> list[ConfigSubentry]:
        return [
            s
            for s in self._get_entry().subentries.values()
            if s.subentry_type == self.subentry_type and s.subentry_id != exclude
        ]

    def _validate_name(
        self, user_input: dict[str, Any], others: list[ConfigSubentry]
    ) -> dict[str, str]:
        name = user_input[CONF_NAME].strip()
        user_input[CONF_NAME] = name
        if name.casefold() in {s.title.casefold() for s in others}:
            return {CONF_NAME: "name_exists"}
        return {}

    def _split(self, user_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        data = _clean(user_input)
        return data.pop(CONF_NAME), data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new item."""
        errors: dict[str, str] = {}
        schema = self._schema()
        if user_input is not None:
            errors = self._validate(user_input, self._others(None))
            if not errors:
                title, data = self._split(user_input)
                return self.async_create_entry(title=title, data=data)
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change an existing item."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate(user_input, self._others(subentry.subentry_id))
            if not errors:
                title, data = self._split(user_input)
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=title, data=data
                )
            suggested = user_input
        else:
            suggested = {CONF_NAME: subentry.title, **subentry.data}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(self._schema(), suggested),
            errors=errors,
        )


class GrillSubentryFlow(_GartenSubentryFlow):
    """Add or reconfigure a grill (suckling pig grill, smoker, ...)."""

    subentry_type = SUBENTRY_GRILL

    def _schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_GRILL_TYPE): SelectSelector(
                    SelectSelectorConfig(
                        options=[t.value for t in GrillType],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_GRILL_TYPE,
                    )
                ),
                vol.Optional(CONF_CHAMBER_ENTITY): _TEMPERATURE_SENSOR,
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

    def _validate(
        self, user_input: dict[str, Any], others: list[ConfigSubentry]
    ) -> dict[str, str]:
        if user_input[CONF_NAME].strip().casefold() == NO_GRILL:
            return {CONF_NAME: "name_reserved"}
        return self._validate_name(user_input, others)


class ProbeSubentryFlow(_GartenSubentryFlow):
    """Add or reconfigure a meat probe."""

    subentry_type = SUBENTRY_PROBE

    def _schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_PROBE_CORE): _TEMPERATURE_SENSOR,
                vol.Optional(CONF_PROBE_AMBIENT): _TEMPERATURE_SENSOR,
            }
        )

    def _validate(
        self, user_input: dict[str, Any], others: list[ConfigSubentry]
    ) -> dict[str, str]:
        if errors := self._validate_name(user_input, others):
            return errors
        core = user_input[CONF_PROBE_CORE]
        if core in {s.data.get(CONF_PROBE_CORE) for s in others}:
            return {CONF_PROBE_CORE: "core_in_use"}
        if core == user_input.get(CONF_PROBE_AMBIENT):
            return {CONF_PROBE_AMBIENT: "same_as_core"}
        return {}


class PoolSubentryFlow(_GartenSubentryFlow):
    """Add or reconfigure a pool with its pump and water sensors."""

    subentry_type = SUBENTRY_POOL

    def _schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_POOL_PUMP): EntitySelector(
                    EntitySelectorConfig(domain=["switch", "input_boolean"])
                ),
                vol.Optional(CONF_POOL_POWER): EntitySelector(
                    EntitySelectorConfig(
                        domain="sensor", device_class=SensorDeviceClass.POWER
                    )
                ),
                vol.Optional(CONF_POOL_TEMPERATURE): _TEMPERATURE_SENSOR,
                vol.Optional(CONF_POOL_PH): _SENSOR,
                vol.Optional(CONF_POOL_ORP): _SENSOR,
                vol.Optional(CONF_POOL_CHLORINE): _SENSOR,
                vol.Optional(CONF_POOL_SALT): _SENSOR,
                vol.Optional(CONF_POOL_LAST_MEASUREMENT): _SENSOR,
                vol.Optional(CONF_POOL_GUIDANCE): _SENSOR,
                vol.Optional(CONF_POOL_RECOMMENDED_RUNTIME): _SENSOR,
                vol.Optional(CONF_POOL_SOLAR_SURPLUS): _SENSOR,
                vol.Optional(CONF_CAMERA): EntitySelector(
                    EntitySelectorConfig(domain="camera")
                ),
            }
        )

    def _validate(
        self, user_input: dict[str, Any], others: list[ConfigSubentry]
    ) -> dict[str, str]:
        return self._validate_name(user_input, others)
