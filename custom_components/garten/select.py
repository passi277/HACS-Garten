"""Select entities for the Garten integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .const import CONF_CAMERA, CONF_LIGHT, CONF_POWER_SWITCH
from .entity import KitchenEntity, ProbeEntity
from .kitchen.controller import KitchenController, Probe
from .kitchen.profiles import PROFILE_OPTIONS, CookingMethod

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    for subentry_id, controller in entry.runtime_data.kitchens.items():
        entities: list[SelectEntity] = [CookingMethodSelect(controller)]
        entities.extend(ProfileSelect(controller, p) for p in controller.probes)
        async_add_entities(entities, config_subentry_id=subentry_id)


class CookingMethodSelect(KitchenEntity, SelectEntity):
    """Cooking method (gas grill, smoker, ...) of the kitchen."""

    _attr_options = [m.value for m in CookingMethod]

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "cooking_method")

    @property
    def current_option(self) -> str:
        """Return the active cooking method."""
        return self.controller.method.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose linked devices for dashboards (e.g. the floorplan card)."""
        data = self.controller.subentry.data
        return {
            key: data[key]
            for key in (CONF_CAMERA, CONF_LIGHT, CONF_POWER_SWITCH)
            if data.get(key)
        }

    async def async_select_option(self, option: str) -> None:
        """Change the cooking method."""
        self.controller.set_method(CookingMethod(option))


class ProfileSelect(ProbeEntity, SelectEntity):
    """Food profile of a probe; sets the target core temperature."""

    _attr_options = PROFILE_OPTIONS

    def __init__(self, controller: KitchenController, probe: Probe) -> None:
        super().__init__(controller, probe, "profile")

    @property
    def current_option(self) -> str:
        """Return the selected food profile."""
        return self.probe.profile

    async def async_select_option(self, option: str) -> None:
        """Select a food profile."""
        self.controller.set_profile(self.probe.index, option)
