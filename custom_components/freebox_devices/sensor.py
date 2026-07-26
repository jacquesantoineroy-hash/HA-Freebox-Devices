"""Sensors de l'intégration : 'Signal Wifi (dBm)' par appareil LAN (None si
filaire ou éteint), et 'État' par profil de contrôle parental."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_FILTER_STATE,
    ATTR_HOSTS,
    ATTR_MACS,
    ATTR_NEXT_CHANGE,
    ATTR_RX_RATE,
    ATTR_SCHEDULING_MODE,
    ATTR_SIGNAL,
    ATTR_TX_RATE,
    ATTR_WEB_ACCESS,
    ATTR_WIFI,
    DOMAIN,
    PARENTAL_STATE_ALLOWED,
    PARENTAL_STATE_DENIED,
    PARENTAL_STATE_WEBONLY,
)
from .coordinator import FreeboxDevicesCoordinator
from .entity import FreeboxDeviceEntity
from .parental_coordinator import FreeboxParentalCoordinator
from .parental_entity import FreeboxParentalEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]

    devices_coordinator: FreeboxDevicesCoordinator = data["devices"]
    known_macs: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_macs = set(devices_coordinator.data) - known_macs
        if not new_macs:
            return
        known_macs.update(new_macs)
        async_add_entities(
            entity_cls(devices_coordinator, mac)
            for mac in new_macs
            for entity_cls in (
                FreeboxSignalSensor,
                FreeboxRxRateSensor,
                FreeboxTxRateSensor,
                FreeboxWebAccessSensor,
            )
        )

    entry.async_on_unload(devices_coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()

    parental_coordinator: FreeboxParentalCoordinator = data["parental"]
    known_filter_ids: set[int] = set()

    @callback
    def _add_new_profiles() -> None:
        new_ids = set(parental_coordinator.data) - known_filter_ids
        if not new_ids:
            return
        known_filter_ids.update(new_ids)
        async_add_entities(
            FreeboxParentalStateSensor(parental_coordinator, fid) for fid in new_ids
        )

    entry.async_on_unload(parental_coordinator.async_add_listener(_add_new_profiles))
    _add_new_profiles()


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

    @property
    def icon(self) -> str:
        """Icône à barres selon la force du signal (HA n'affiche pas
        automatiquement une icône graduée pour device_class signal_strength,
        cf. recherche : seul le composant mobile_app le fait nativement)."""
        signal = self.native_value
        if signal is None:
            return "mdi:wifi-strength-off-outline"
        if signal >= -60:
            return "mdi:wifi-strength-4"
        if signal >= -70:
            return "mdi:wifi-strength-3"
        if signal >= -75:
            return "mdi:wifi-strength-2"
        return "mdi:wifi-strength-1"


class _FreeboxRateSensor(FreeboxDeviceEntity, SensorEntity):
    """Base commune débit descendant/montant — None si filaire (même
    limitation que le signal : l'API Freebox n'expose ces débits que pour
    les stations Wifi, cf. `wifi/ap/{id}/stations/`)."""

    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
    _attr_suggested_display_precision = 0
    _attr_entity_category = None
    _attr_suggested_unit_of_measurement = UnitOfDataRate.KILOBYTES_PER_SECOND

    _attr_key: str  # défini par les sous-classes

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_{self._attr_key}"

    @property
    def native_value(self) -> int | None:
        device = self._device
        if not device.get(ATTR_WIFI):
            return None
        return device.get(self._attr_key)


class FreeboxRxRateSensor(_FreeboxRateSensor):
    """Débit descendant (Freebox -> appareil)."""

    _attr_translation_key = "debit_descendant"
    _attr_icon = "mdi:download-network-outline"
    _attr_key = ATTR_TX_RATE  # cf. remarque sur les libellés dans freebox_client.py

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_debit_descendant"


class FreeboxTxRateSensor(_FreeboxRateSensor):
    """Débit montant (appareil -> Freebox)."""

    _attr_translation_key = "debit_montant"
    _attr_icon = "mdi:upload-network-outline"
    _attr_key = ATTR_RX_RATE  # cf. remarque sur les libellés dans freebox_client.py

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_debit_montant"


class FreeboxWebAccessSensor(FreeboxDeviceEntity, SensorEntity):
    """Accès web de l'appareil selon le contrôle parental (allowed/denied/
    webonly). "allowed" si l'appareil n'est couvert par aucun profil de
    contrôle parental (= pas de restriction, comportement par défaut)."""

    _attr_translation_key = "acces_web"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [PARENTAL_STATE_ALLOWED, PARENTAL_STATE_DENIED, PARENTAL_STATE_WEBONLY]
    _attr_entity_category = None

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_acces_web"

    @property
    def native_value(self) -> str:
        return self._device.get(ATTR_WEB_ACCESS) or PARENTAL_STATE_ALLOWED

    @property
    def icon(self) -> str:
        state = self.native_value
        if state == PARENTAL_STATE_DENIED:
            return "mdi:web-off"
        if state == PARENTAL_STATE_WEBONLY:
            return "mdi:web-check"
        return "mdi:web"


class FreeboxParentalStateSensor(FreeboxParentalEntity, SensorEntity):
    """État courant d'accès du profil (allowed/denied/webonly), avec le
    détail des appareils couverts et le temps avant le prochain changement
    en attributs."""

    _attr_translation_key = "etat_profil"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [PARENTAL_STATE_ALLOWED, PARENTAL_STATE_DENIED, "webonly"]

    def __init__(self, coordinator: FreeboxParentalCoordinator, filter_id: int) -> None:
        super().__init__(coordinator, filter_id)
        self._attr_unique_id = f"parental_{filter_id}_etat"

    @property
    def native_value(self) -> str | None:
        return self._profile.get(ATTR_FILTER_STATE)

    @property
    def icon(self) -> str:
        state = self.native_value
        if state == PARENTAL_STATE_DENIED:
            return "mdi:account-cancel"
        if state == "webonly":
            return "mdi:account-alert"
        return "mdi:account-check"

    @property
    def extra_state_attributes(self) -> dict:
        profile = self._profile
        return {
            "hosts": profile.get(ATTR_HOSTS),
            "macs": profile.get(ATTR_MACS),
            "mode_actuel": profile.get(ATTR_SCHEDULING_MODE),
            "secondes_avant_changement": profile.get(ATTR_NEXT_CHANGE),
        }
