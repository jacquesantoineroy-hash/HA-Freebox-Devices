"""Un lock 'Verrou Wifi' par appareil LAN — verrouillé = coupé (blacklisté),
déverrouillé = autorisé. Remplace l'ancien switch (2026-07-26, demande
utilisateur : rendu natif en cadenas plutôt qu'un simple bouton on/off,
cf. recherche : le domaine `lock` est le choix sémantique recommandé par la
communauté HA pour du contrôle d'accès, avec rendu cadenas natif dans les
cartes "entities" et le dialogue "plus d'infos")."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_BLOCKED, ATTR_HOSTNAME, DOMAIN
from .coordinator import FreeboxDevicesCoordinator
from .entity import FreeboxDeviceEntity
from .freebox_client import FreeboxApiError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FreeboxDevicesCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_macs: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_macs = set(coordinator.data) - known_macs
        if not new_macs:
            return
        known_macs.update(new_macs)
        async_add_entities(FreeboxWifiLock(coordinator, mac) for mac in new_macs)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()


class FreeboxWifiLock(FreeboxDeviceEntity, LockEntity):
    """Verrouillé = appareil coupé du Wifi (blacklisté), déverrouillé = autorisé."""

    _attr_translation_key = "wifi_verrou"

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_blacklist"

    @property
    def is_locked(self) -> bool:
        return bool(self._device.get(ATTR_BLOCKED))

    async def async_lock(self, **kwargs: Any) -> None:
        await self._async_set_blocked(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._async_set_blocked(False)

    async def _async_set_blocked(self, target_blocked: bool) -> None:
        if bool(self._device.get(ATTR_BLOCKED)) == target_blocked:
            return
        try:
            await self.coordinator.client.async_toggle_mac_filter(self._mac)
        except FreeboxApiError as err:
            _LOGGER.error(
                "Échec bascule blacklist pour %s (%s): %s",
                self._device.get(ATTR_HOSTNAME, self._mac),
                self._mac,
                err,
            )
            return
        await self.coordinator.async_request_refresh()
