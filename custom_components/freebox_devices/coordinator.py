"""DataUpdateCoordinator : interroge la Freebox en direct toutes les N secondes.

Reprend la logique validée sur le relais Pi : la Freebox indique
explicitement `connectivity_type` ("wifi"/"ethernet") tant qu'un appareil est
actif, mais n'expose plus rien une fois l'appareil inactif. On mémorise donc
la dernière valeur connue par MAC dans le storage HA (persistant entre
redémarrages), avec un repli sur host_type (smartphone/tablet -> wifi) pour
les MAC jamais vues actives.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_ACTIVE,
    ATTR_BLOCKED,
    ATTR_CONNECTIVITY_TYPE,
    ATTR_FILTER_STATE,
    ATTR_HOST_TYPE,
    ATTR_HOSTNAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_MACS,
    ATTR_RX_RATE,
    ATTR_SIGNAL,
    ATTR_TX_RATE,
    ATTR_VENDOR,
    ATTR_WEB_ACCESS,
    ATTR_WIFI,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_DEVICE,
    STORAGE_KEY_KNOWN_MACS_TEMPLATE,
    STORAGE_KEY_TEMPLATE,
    STORAGE_VERSION,
)
from .freebox_client import FreeboxLocalClient

_LOGGER = logging.getLogger(__name__)

_WIFI_HOST_TYPE_FALLBACK = ("smartphone", "tablet")


class FreeboxDevicesCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Poll la Freebox et expose les appareils indexés par MAC."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: FreeboxLocalClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.client = client
        # Référence optionnelle posée par __init__.py après coup (ordre de
        # création : devices coordinator d'abord, parental ensuite) — permet
        # de calculer l'accès web par appareil sans appel API supplémentaire
        # (simple lecture en mémoire de coordinator.data déjà à jour).
        self.parental_coordinator = None
        self._store: Store = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry.entry_id)
        )
        self._conn_cache: dict[str, str] = {}
        self._cache_loaded = False
        self._cache_dirty = False

        # Stockage séparé du cache de connectivité pour ne pas risquer de
        # corrompre les données déjà en prod (schéma différent : une liste
        # de MAC déjà vues, pas un dict MAC -> type).
        self._known_macs_store: Store = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_KNOWN_MACS_TEMPLATE.format(entry_id=entry.entry_id),
        )
        self._known_macs: set[str] = set()
        self._known_macs_loaded = False
        self._known_macs_dirty = False

    async def _async_load_cache(self) -> None:
        if self._cache_loaded:
            return
        self._conn_cache = await self._store.async_load() or {}
        self._cache_loaded = True

    async def _async_save_cache_if_dirty(self) -> None:
        if self._cache_dirty:
            await self._store.async_save(self._conn_cache)
            self._cache_dirty = False

    async def _async_load_known_macs(self) -> None:
        if self._known_macs_loaded:
            return
        stored = await self._known_macs_store.async_load()
        self._known_macs = set(stored or [])
        self._known_macs_loaded = True

    async def _async_save_known_macs_if_dirty(self) -> None:
        if self._known_macs_dirty:
            await self._known_macs_store.async_save(sorted(self._known_macs))
            self._known_macs_dirty = False

    def _fire_new_device_events(self, devices: dict[str, dict]) -> None:
        """Émet un événement HA pour chaque MAC jamais vue auparavant
        (persistant entre redémarrages). Au tout premier démarrage de
        l'intégration, tous les appareils déjà connus de la Freebox
        déclenchent l'événement d'un coup — comportement attendu, pas un bug
        (même comportement que l'ancien script sur le Pi)."""
        new_macs = set(devices) - self._known_macs
        if not new_macs:
            return
        for mac in new_macs:
            device = devices[mac]
            self.hass.bus.async_fire(
                EVENT_NEW_DEVICE,
                {
                    "mac": mac,
                    "hostname": device.get(ATTR_HOSTNAME),
                    "ip": device.get(ATTR_IP),
                    "vendor": device.get(ATTR_VENDOR),
                },
            )
        self._known_macs.update(new_macs)
        self._known_macs_dirty = True

    async def _async_update_data(self) -> dict[str, dict]:
        await self._async_load_cache()
        await self._async_load_known_macs()

        try:
            hosts = await self.client.async_get_raw_hosts()
            wifi_stats = await self.client.async_get_wifi_station_stats()
            mac_filter_entries = await self.client.async_get_mac_filter_entries()
        except Exception as err:  # noqa: BLE001 - remonté proprement à HA
            raise UpdateFailed(str(err)) from err

        blocked_macs = {
            (entry.get("mac") or "").upper()
            for entry in mac_filter_entries
            if entry.get("type") == "blacklist"
        }

        # Accès web par profil de contrôle parental — simple lecture en
        # mémoire du coordinator parental déjà à jour (pas d'appel API en
        # plus). None si le coordinator n'est pas encore branché ou si la
        # permission "Contrôle parental" n'est pas accordée.
        web_access_by_mac: dict[str, str] = {}
        if self.parental_coordinator is not None:
            for profile in self.parental_coordinator.data.values():
                state = profile.get(ATTR_FILTER_STATE)
                for pmac in profile.get(ATTR_MACS, []) or []:
                    web_access_by_mac[pmac.upper()] = state

        devices: dict[str, dict] = {}
        for host in hosts:
            mac = self.client.extract_mac(host)
            if not mac:
                continue

            ap = host.get("access_point") or {}
            fresh_conn_type = ap.get("connectivity_type")
            if fresh_conn_type:
                conn_type = fresh_conn_type
                if self._conn_cache.get(mac) != conn_type:
                    self._conn_cache[mac] = conn_type
                    self._cache_dirty = True
            else:
                cached_type = self._conn_cache.get(mac)
                if cached_type:
                    conn_type = cached_type
                elif host.get("host_type") in _WIFI_HOST_TYPE_FALLBACK:
                    conn_type = "wifi"
                else:
                    conn_type = None

            stats = wifi_stats.get(mac, {})
            devices[mac] = {
                ATTR_MAC: mac,
                ATTR_HOSTNAME: host.get("primary_name") or "Inconnu",
                ATTR_IP: self.client.extract_ip(host),
                ATTR_ACTIVE: bool(host.get("active")),
                ATTR_WIFI: conn_type == "wifi",
                ATTR_CONNECTIVITY_TYPE: conn_type,
                ATTR_HOST_TYPE: host.get("host_type"),
                ATTR_VENDOR: host.get("vendor_name"),
                ATTR_BLOCKED: mac in blocked_macs,
                ATTR_TX_RATE: stats.get(ATTR_TX_RATE),
                ATTR_RX_RATE: stats.get(ATTR_RX_RATE),
                ATTR_WEB_ACCESS: web_access_by_mac.get(mac),
                ATTR_SIGNAL: stats.get(ATTR_SIGNAL),
            }

        await self._async_save_cache_if_dirty()

        # Ne déclenche les événements "nouvel appareil" qu'une fois le cache
        # de connectivité chargé et rempli — sinon le tout premier
        # rafraîchissement après une mise à jour de l'intégration (avant que
        # le store known_macs existe) déclencherait un événement pour
        # littéralement tous les appareils déjà connus, même ceux présents
        # depuis longtemps. C'est le comportement voulu au tout premier
        # démarrage de l'intégration (cf. docstring), donc rien à changer
        # ici — le commentaire sert à ne pas "corriger" ça par erreur plus
        # tard.
        self._fire_new_device_events(devices)
        await self._async_save_known_macs_if_dirty()

        return devices
