"""Grill types and food profiles for the outdoor kitchen."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GrillType(StrEnum):
    """Kind of cooking appliance."""

    SUCKLING_PIG_GRILL = "suckling_pig_grill"
    SMOKER = "smoker"
    GAS_GRILL = "gas_grill"
    CHARCOAL_GRILL = "charcoal_grill"
    DUTCH_OVEN = "dutch_oven"
    ELECTRIC_HOB = "electric_hob"
    PIZZA_OVEN = "pizza_oven"
    OTHER = "other"


# Default cooking chamber temperature in °C per grill type (None: not applicable).
GRILL_CHAMBER_DEFAULTS: dict[GrillType, float | None] = {
    GrillType.SUCKLING_PIG_GRILL: 160.0,
    GrillType.SMOKER: 110.0,
    GrillType.GAS_GRILL: 220.0,
    GrillType.CHARCOAL_GRILL: 200.0,
    GrillType.DUTCH_OVEN: 180.0,
    GrillType.ELECTRIC_HOB: None,
    GrillType.PIZZA_OVEN: 350.0,
    GrillType.OTHER: None,
}

# Low & slow grills where the core temperature typically stalls.
STALL_GRILL_TYPES: frozenset[GrillType] = frozenset(
    {GrillType.SMOKER, GrillType.SUCKLING_PIG_GRILL}
)

# Cooking methods of version 1 kitchens mapped to grill types.
LEGACY_METHOD_GRILL_TYPES: dict[str, GrillType] = {
    "suckling_pig": GrillType.SUCKLING_PIG_GRILL,
    "smoker": GrillType.SMOKER,
    "gas_grill": GrillType.GAS_GRILL,
    "dutch_oven": GrillType.DUTCH_OVEN,
    "electric_hob": GrillType.ELECTRIC_HOB,
}


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
        FoodProfile("roe_deer_saddle", 54),
        FoodProfile("roe_deer_leg", 62),
        FoodProfile("red_deer_saddle", 55),
        FoodProfile("red_deer_leg", 64),
        FoodProfile("wild_boar_saddle", 62),
        FoodProfile("wild_boar_leg", 72),
        FoodProfile("wild_boar_shoulder_pulled", 90),
        FoodProfile("hare", 65),
        FoodProfile("wild_duck_breast", 58),
        FoodProfile("sausage", 72),
        FoodProfile("salmon", 52),
        FoodProfile("fish_white", 55),
        FoodProfile("bread", 96),
    )
}

PROFILE_OPTIONS: list[str] = [PROFILE_CUSTOM, *FOOD_PROFILES]

DEFAULT_TARGET = 60.0
