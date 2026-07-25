"""Un switch 'Wifi autorisé' par appareil LAN (ON = pas blacklisté, OFF = coupé)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
        async_add_entities(
            FreeboxBlacklistSwitch(coordinator, mac) for mac in new_macs
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()


class FreeboxBlacklistSwitch(FreeboxDeviceEntity, SwitchEntity):
    """ON = appareil autorisé sur le Wifi, OFF = coupé (blacklisté)."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "wifi_autorise"
    _attr_icon = "mdi:wifi-lock-open"

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_blacklist"

    @property
    def is_on(self) -> bool:
        return not bool(self._device.get(ATTR_BLOCKED))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_blocked(True)

    async def async_turn_on(self, **kwargs: Any) -> None:
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
