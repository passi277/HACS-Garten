"""Event entities for the Garten integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import KitchenEntity
from .kitchen.controller import KITCHEN_EVENT_TYPES, KitchenController

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event entities."""
    for subentry_id, controller in entry.runtime_data.kitchens.items():
        async_add_entities(
            [KitchenEventEntity(controller)], config_subentry_id=subentry_id
        )


class KitchenEventEntity(KitchenEntity, EventEntity):
    """Fires on cook milestones: target reached, stall, chamber deviation, ..."""

    _attr_event_types = KITCHEN_EVENT_TYPES

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "kitchen_event")

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller events (not to plain state updates)."""
        self.async_on_remove(self.controller.add_event_listener(self._handle_event))

    @callback
    def _handle_event(self, event_type: str, data: dict[str, Any]) -> None:
        self._trigger_event(event_type, data)
        self.async_write_ha_state()
