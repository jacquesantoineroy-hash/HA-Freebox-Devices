"""Classe de base commune : regroupe les entités sous un même appareil HA."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_HOSTNAME, ATTR_VENDOR, DOMAIN
from .coordinator import FreeboxDevicesCoordinator


class FreeboxDeviceEntity(CoordinatorEntity[FreeboxDevicesCoordinator]):
    """Entité liée à un appareil LAN précis (identifié par sa MAC)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac

    @property
    def _device(self) -> dict:
        return self.coordinator.data.get(self._mac, {})

    @property
    def available(self) -> bool:
        return super().available and self._mac in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=device.get(ATTR_HOSTNAME) or self._mac,
            manufacturer=device.get(ATTR_VENDOR) or "Inconnu",
            via_device=(DOMAIN, self.coordinator.entry.entry_id),
        )
