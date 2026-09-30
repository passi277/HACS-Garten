"""Button entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import KitchenEntity
from .kitchen.controller import KitchenController

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities."""
    for subentry_id, controller in entry.runtime_data.kitchens.items():
        async_add_entities(
            [StartSessionButton(controller), StopSessionButton(controller)],
            config_subentry_id=subentry_id,
        )


class StartSessionButton(KitchenEntity, ButtonEntity):
    """Start (or restart) a cooking session."""

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "session_start")

    async def async_press(self) -> None:
        """Start a session."""
        self.controller.start_session()


class StopSessionButton(KitchenEntity, ButtonEntity):
    """End the cooking session."""

    def __init__(self, controller: KitchenController) -> None:
        super().__init__(controller, "session_stop")

    async def async_press(self) -> None:
        """End the session."""
        self.controller.stop_session()
