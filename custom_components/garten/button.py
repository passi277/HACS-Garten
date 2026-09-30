"""Button entities for the Garten integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GartenConfigEntry
from .entity import GrillEntity, PoolEntity
from .kitchen.manager import GrillState, KitchenManager
from .pool.manager import PoolManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GartenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities."""
    kitchen = entry.runtime_data.kitchen
    for grill_id, grill in kitchen.grills.items():
        async_add_entities(
            [StartSessionButton(kitchen, grill), StopSessionButton(kitchen, grill)],
            config_subentry_id=grill_id,
        )
    for pool_id, pool in entry.runtime_data.pools.items():
        async_add_entities([BackwashDoneButton(pool)], config_subentry_id=pool_id)


class StartSessionButton(GrillEntity, ButtonEntity):
    """Start (or restart) a cooking session, e.g. to preheat."""

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "session_start")

    async def async_press(self) -> None:
        """Start a session."""
        self.manager.start_session(self.grill.subentry_id)


class StopSessionButton(GrillEntity, ButtonEntity):
    """End the cooking session and release the probes."""

    def __init__(self, manager: KitchenManager, grill: GrillState) -> None:
        super().__init__(manager, grill, "session_stop")

    async def async_press(self) -> None:
        """End the session."""
        self.manager.stop_session(self.grill.subentry_id)


class BackwashDoneButton(PoolEntity, ButtonEntity):
    """Record that the filter was backwashed."""

    def __init__(self, pool: PoolManager) -> None:
        super().__init__(pool, "backwash_done")

    async def async_press(self) -> None:
        """Reset the backwash counter."""
        self.pool.record_backwash()
