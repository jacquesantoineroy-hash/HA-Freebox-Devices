"""Présence par appareil LAN (device_tracker), basée sur l'état `active`
renvoyé par la Freebox (lan/browser). Délai de déconnexion de 1-2 minutes
côté Freebox, connexion signalée quasi immédiatement (cf. doc officielle
core `freebox`)."""
from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ACTIVE,
    ATTR_CONNECTIVITY_TYPE,
    ATTR_HOST_TYPE,
    ATTR_HOSTNAME,
    ATTR_IP,
    ATTR_VENDOR,
    DOMAIN,
)
from .coordinator import FreeboxDevicesCoordinator
from .entity import FreeboxDeviceEntity


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
            FreeboxDeviceTracker(coordinator, mac) for mac in new_macs
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()


class FreeboxDeviceTracker(FreeboxDeviceEntity, ScannerEntity):
    """Présence d'un appareil du LAN."""

    _attr_name = None  # entité principale de l'appareil : pas de suffixe de nom

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_tracker"

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        return bool(self._device.get(ATTR_ACTIVE))

    @property
    def ip_address(self) -> str | None:
        return self._device.get(ATTR_IP)

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def hostname(self) -> str | None:
        return self._device.get(ATTR_HOSTNAME)

    @property
    def extra_state_attributes(self) -> dict:
        device = self._device
        return {
            "vendor": device.get(ATTR_VENDOR),
            "host_type": device.get(ATTR_HOST_TYPE),
            "connectivity_type": device.get(ATTR_CONNECTIVITY_TYPE),
        }

    @property
    def icon(self) -> str:
        """Icône reflétant le mode de connexion (wifi/ethernet), grisée si
        l'appareil est absent."""
        if not self.is_connected:
            return "mdi:lan-disconnect"
        connectivity = self._device.get(ATTR_CONNECTIVITY_TYPE)
        if connectivity == "wifi":
            return "mdi:wifi"
        if connectivity == "ethernet":
            return "mdi:ethernet"
        return "mdi:help-network"
