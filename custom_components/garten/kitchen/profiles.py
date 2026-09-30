"""Cooking methods and food profiles for the outdoor kitchen."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CookingMethod(StrEnum):
    """How the food is cooked."""

    OFF = "off"
    GAS_GRILL = "gas_grill"
    SMOKER = "smoker"
    SUCKLING_PIG = "suckling_pig"
    DUTCH_OVEN = "dutch_oven"
    ELECTRIC_HOB = "electric_hob"


# Default cooking chamber temperature in °C per method (None: not applicable).
METHOD_CHAMBER_DEFAULTS: dict[CookingMethod, float | None] = {
    CookingMethod.OFF: None,
    CookingMethod.GAS_GRILL: 220,
    CookingMethod.SMOKER: 110,
    CookingMethod.SUCKLING_PIG: 160,
    CookingMethod.DUTCH_OVEN: 180,
    CookingMethod.ELECTRIC_HOB: None,
}

# Low & slow methods where the core temperature typically stalls.
STALL_METHODS: frozenset[CookingMethod] = frozenset(
    {CookingMethod.SMOKER, CookingMethod.SUCKLING_PIG}
)


@dataclass(frozen=True, slots=True)
class FoodProfile:
    """Target core temperature for a kind of food."""

    key: str
    target: float


PROFILE_CUSTOM = "custom"

FOOD_PROFILES: dict[str, FoodProfile] = {
    p.key: p
    for p in (
        FoodProfile("beef_rare", 50),
        FoodProfile("beef_medium_rare", 54),
        FoodProfile("beef_medium", 58),
        FoodProfile("beef_well_done", 65),
        FoodProfile("brisket", 95),
        FoodProfile("pulled_pork", 93),
        FoodProfile("spare_ribs", 90),
        FoodProfile("pork_loin", 62),
        FoodProfile("suckling_pig", 75),
        FoodProfile("chicken", 74),
        FoodProfile("chicken_thigh", 82),
        FoodProfile("turkey", 74),
        FoodProfile("duck_breast", 57),
        FoodProfile("lamb_leg", 62),
        FoodProfile("sausage", 72),
        FoodProfile("salmon", 52),
        FoodProfile("fish_white", 55),
        FoodProfile("bread", 96),
    )
}

PROFILE_OPTIONS: list[str] = [PROFILE_CUSTOM, *FOOD_PROFILES]

DEFAULT_TARGET = 60.0
