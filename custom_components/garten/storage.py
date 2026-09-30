"""Persistent storage shared by all areas of one Garten config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION

SAVE_DELAY = 5


class GartenStore:
    """Thin wrapper around ``Store`` keyed by subentry id."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._data: dict[str, Any] = {}

    async def async_load(self) -> None:
        """Load data from disk."""
        self._data = await self._store.async_load() or {}

    def get(self, key: str) -> dict[str, Any]:
        """Return the stored dict for ``key`` (empty if unknown)."""
        return self._data.get(key, {})

    def set(self, key: str, value: dict[str, Any]) -> None:
        """Replace the dict for ``key`` and schedule a write."""
        self._data[key] = value
        self._store.async_delay_save(lambda: self._data, SAVE_DELAY)

    def remove_except(self, keys: set[str]) -> None:
        """Drop data of subentries that no longer exist."""
        stale = set(self._data) - keys
        if stale:
            for key in stale:
                del self._data[key]
            self._store.async_delay_save(lambda: self._data, SAVE_DELAY)

    async def async_flush(self) -> None:
        """Write pending changes immediately."""
        await self._store.async_save(self._data)

    async def async_remove(self) -> None:
        """Delete the storage file."""
        await self._store.async_remove()
