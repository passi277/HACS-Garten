"""Event entities for the Garten integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import GrillEntity
from .kitchen.manager import KITCHEN_EVENT_TYPES, GrillState, KitchenManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up event entities."""
    kitchen = entry.runtime_data.kitchen
    for grill_id, grill in kitchen.grills.items():
        async_add_entities(
            [GrillEventEntity(kitchen, grill)], config_subentry_id=grill_id
        )


class GrillEventEntity(GrillEntity, EventEntity):
    """Fires on cook milestones: target reached, stall, chamber deviation, ..."""

    _attr_event_types = KITCHEN_EVENT_TYPES

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "grill_event")

    async def async_added_to_hass(self) -> None:
        """Subscribe to events of this grill (not to plain state updates)."""
        self.async_on_remove(
            self.manager.add_event_listener(self.grill.subentry_id, self._handle_event)
        )

    @callback
    def _handle_event(self, event_type: str, data: dict[str, Any]) -> None:
        self._trigger_event(event_type, data)
        self.async_write_ha_state()
