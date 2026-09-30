"""Base entities for the Garten integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .kitchen.manager import GrillState, KitchenManager, ProbeState


class KitchenEntity(Entity):
    """Entity of the outdoor kitchen, updated by the kitchen manager."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, manager: KitchenManager, subentry_id: str, key: str, device: DeviceInfo
    ) -> None:
        self.manager = manager
        self._attr_translation_key = key
        self._attr_unique_id = f"{subentry_id}_{key}"
        self._attr_device_info = device

    async def async_added_to_hass(self) -> None:
        """Subscribe to manager updates."""
        self.async_on_remove(self.manager.add_listener(self.async_write_ha_state))


class GrillEntity(KitchenEntity):
    """Entity belonging to a grill device."""

    def __init__(self, manager: KitchenManager, grill: GrillState, key: str) -> None:
        super().__init__(
            manager,
            grill.subentry_id,
            key,
            DeviceInfo(
                identifiers={(DOMAIN, grill.subentry_id)},
                name=grill.name,
                manufacturer=MANUFACTURER,
                model="Grill",
                model_id=grill.grill_type.value,
            ),
        )
        self.grill = grill


class ProbeEntity(KitchenEntity):
    """Entity belonging to a probe device."""

    def __init__(self, manager: KitchenManager, probe: ProbeState, key: str) -> None:
        super().__init__(
            manager,
            probe.subentry_id,
            key,
            DeviceInfo(
                identifiers={(DOMAIN, probe.subentry_id)},
                name=probe.name,
                manufacturer=MANUFACTURER,
                model="Sonde",
            ),
        )
        self.probe = probe
