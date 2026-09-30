"""Base entities for the Garten integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .kitchen.controller import KitchenController, Probe


class KitchenEntity(Entity):
    """Entity belonging to an outdoor kitchen device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: KitchenController, key: str) -> None:
        self.controller = controller
        subentry_id = controller.subentry.subentry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=controller.title,
            manufacturer=MANUFACTURER,
            model="Outdoor-Küche",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller updates."""
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))


class ProbeEntity(KitchenEntity):
    """Entity belonging to one probe of an outdoor kitchen."""

    def __init__(self, controller: KitchenController, probe: Probe, key: str) -> None:
        super().__init__(controller, f"probe_{key}")
        self.probe = probe
        self._attr_unique_id = (
            f"{controller.subentry.subentry_id}_probe{probe.index}_{key}"
        )
        self._attr_translation_placeholders = {"probe": probe.name}
