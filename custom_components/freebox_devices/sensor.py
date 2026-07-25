"""Un sensor 'Signal Wifi (dBm)' par appareil LAN (None si filaire ou éteint)."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SIGNAL, ATTR_WIFI, DOMAIN
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
        async_add_entities(FreeboxSignalSensor(coordinator, mac) for mac in new_macs)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()


class FreeboxSignalSensor(FreeboxDeviceEntity, SensorEntity):
    """Signal Wifi de l'appareil, en dBm. None si filaire (comportement attendu)."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_translation_key = "signal_wifi"
    _attr_entity_category = None

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_signal"

    @property
    def native_value(self) -> int | None:
        device = self._device
        if not device.get(ATTR_WIFI):
            return None
        return device.get(ATTR_SIGNAL)
