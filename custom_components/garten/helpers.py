"""Helpers shared by all areas of the Garten integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter


def read_float(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return the numeric state of an entity, None if missing or unavailable."""
    if not entity_id or (state := hass.states.get(entity_id)) is None:
        return None
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


def read_temperature(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return the temperature of a sensor or weather entity in °C."""
    if not entity_id or (state := hass.states.get(entity_id)) is None:
        return None
    if split_entity_id(entity_id)[0] == "weather":
        raw = state.attributes.get("temperature")
        unit = state.attributes.get("temperature_unit")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
    else:
        if (value := read_float(hass, entity_id)) is None:
            return None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN):
        value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    return value


def read_datetime(hass: HomeAssistant, entity_id: str | None) -> datetime | None:
    """Return the state of a timestamp entity as an aware datetime."""
    if not entity_id or (state := hass.states.get(entity_id)) is None:
        return None
    if (value := dt_util.parse_datetime(state.state)) is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return value


def read_text(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Return the state of an entity as text, None if missing or unavailable."""
    if not entity_id or (state := hass.states.get(entity_id)) is None:
        return None
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    return state.state


def is_on(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Return True if the entity is on."""
    return (
        bool(entity_id)
        and (state := hass.states.get(entity_id)) is not None
        and (state.state == "on")
    )
