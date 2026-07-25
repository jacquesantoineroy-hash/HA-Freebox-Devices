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
    ATTR_HOST_TYPE,
    ATTR_HOSTNAME,
    ATTR_IP,
    ATTR_MAC,
    ATTR_SIGNAL,
    ATTR_VENDOR,
    ATTR_WIFI,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
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
        self._store: Store = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry.entry_id)
        )
        self._conn_cache: dict[str, str] = {}
        self._cache_loaded = False
        self._cache_dirty = False

    async def _async_load_cache(self) -> None:
        if self._cache_loaded:
            return
        self._conn_cache = await self._store.async_load() or {}
        self._cache_loaded = True

    async def _async_save_cache_if_dirty(self) -> None:
        if self._cache_dirty:
            await self._store.async_save(self._conn_cache)
            self._cache_dirty = False

    async def _async_update_data(self) -> dict[str, dict]:
        await self._async_load_cache()

        try:
            hosts = await self.client.async_get_raw_hosts()
            signals = await self.client.async_get_wifi_signals()
            mac_filter_entries = await self.client.async_get_mac_filter_entries()
        except Exception as err:  # noqa: BLE001 - remonté proprement à HA
            raise UpdateFailed(str(err)) from err

        blocked_macs = {
            (entry.get("mac") or "").upper()
            for entry in mac_filter_entries
            if entry.get("type") == "blacklist"
        }

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
                ATTR_SIGNAL: signals.get(mac),
            }

        await self._async_save_cache_if_dirty()
        return devices
