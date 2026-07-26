"""Client HTTP natif pour l'API locale de la Freebox (sans passer par un relais).

Couvre : appairage (app_token), session (challenge HMAC-SHA1), liste des
appareils LAN, signal Wifi par appareil, et bascule de la blacklist Wifi
(mac_filter).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from typing import Any

import aiohttp

from .const import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    API_VERSION_MAIN,
    API_VERSION_WIFI,
    DEVICE_NAME,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = 15


class FreeboxApiError(Exception):
    """Erreur générique de l'API Freebox."""


class FreeboxAuthRequired(FreeboxApiError):
    """Session absente ou expirée : il faut se reconnecter."""


class FreeboxPermissionError(FreeboxApiError):
    """Droits insuffisants (permission non accordée dans Freebox OS)."""


class FreeboxPairingDenied(FreeboxApiError):
    """L'appairage a été refusé (ou a expiré) sur la façade de la Freebox."""


class FreeboxLocalClient:
    """Client pour https://{host}:{port}/api/v8|v10/."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self._host = host
        self._port = port
        self._session_token: str | None = None
        self.app_token: str | None = None

    # ------------------------------------------------------------------ #
    # Bas niveau
    # ------------------------------------------------------------------ #

    def _url(self, path: str, api_version: str = API_VERSION_MAIN) -> str:
        return f"https://{self._host}:{self._port}/api/{api_version}/{path}"

    async def _raw(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        authenticated: bool = True,
    ) -> Any:
        headers = {}
        if authenticated:
            if not self._session_token:
                raise FreeboxAuthRequired("Pas de session ouverte")
            headers["X-Fbx-App-Auth"] = self._session_token

        try:
            async with asyncio.timeout(_TIMEOUT):
                async with self._session.request(
                    method, url, json=json_body, headers=headers, ssl=False
                ) as resp:
                    payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FreeboxApiError(f"Freebox injoignable ({url}): {err}") from err

        if not payload.get("success", False):
            error_code = payload.get("error_code")
            msg = payload.get("msg", "erreur inconnue")
            if error_code in ("auth_required", "invalid_token"):
                self._session_token = None
                raise FreeboxAuthRequired(msg)
            if error_code == "insufficient_rights":
                raise FreeboxPermissionError(
                    "Droits insuffisants : accorde la permission "
                    "'Modification des réglages de la Freebox' à cette "
                    "application dans Freebox OS > Paramètres > Gestion des "
                    f"accès > Applications ({msg})"
                )
            raise FreeboxApiError(f"{url} -> {error_code}: {msg}")

        return payload.get("result")

    async def _authenticated(
        self, method: str, path: str, *, api_version: str = API_VERSION_MAIN, json_body=None
    ) -> Any:
        """Requête authentifiée avec une tentative de ré-ouverture de session."""
        url = self._url(path, api_version)
        try:
            return await self._raw(method, url, json_body=json_body, authenticated=True)
        except FreeboxAuthRequired:
            if not self.app_token:
                raise
            await self.async_open_session(self.app_token)
            return await self._raw(method, url, json_body=json_body, authenticated=True)

    # ------------------------------------------------------------------ #
    # Appairage (aucune session requise)
    # ------------------------------------------------------------------ #

    async def async_request_authorization(self) -> tuple[str, int]:
        """Démarre l'appairage. L'utilisateur doit valider sur la façade
        (flèche droite) de la Freebox. Retourne (app_token, track_id)."""
        result = await self._raw(
            "POST",
            self._url("login/authorize/"),
            json_body={
                "app_id": APP_ID,
                "app_name": APP_NAME,
                "app_version": APP_VERSION,
                "device_name": DEVICE_NAME,
            },
            authenticated=False,
        )
        return result["app_token"], result["track_id"]

    async def async_get_authorization_status(self, track_id: int) -> str:
        result = await self._raw(
            "GET",
            self._url(f"login/authorize/{track_id}"),
            authenticated=False,
        )
        return result["status"]

    # ------------------------------------------------------------------ #
    # Session
    # ------------------------------------------------------------------ #

    async def async_open_session(self, app_token: str) -> None:
        self.app_token = app_token
        challenge_data = await self._raw(
            "GET", self._url("login/"), authenticated=False
        )
        challenge = challenge_data["challenge"]
        password = hmac.new(
            app_token.encode(), challenge.encode(), hashlib.sha1
        ).hexdigest()
        result = await self._raw(
            "POST",
            self._url("login/session/"),
            json_body={"app_id": APP_ID, "password": password},
            authenticated=False,
        )
        self._session_token = result["session_token"]

    # ------------------------------------------------------------------ #
    # Appareils LAN
    # ------------------------------------------------------------------ #

    @staticmethod
    def extract_mac(host: dict) -> str | None:
        l2 = host.get("l2ident") or {}
        mac = l2.get("id") or host.get("mac")
        return mac.upper() if mac else None

    @staticmethod
    def extract_ip(host: dict) -> str | None:
        for conn in host.get("l3connectivities", []) or []:
            if conn.get("af") == "ipv4" and conn.get("active"):
                return conn.get("addr")
        for conn in host.get("l3connectivities", []) or []:
            if conn.get("af") == "ipv4":
                return conn.get("addr")
        return None

    async def async_get_raw_hosts(self) -> list[dict]:
        """Fusionne les hosts de toutes les interfaces LAN (dédupliqués par MAC)."""
        interfaces = await self._authenticated("GET", "lan/browser/interfaces/")
        hosts_by_mac: dict[str, dict] = {}
        for iface in interfaces or []:
            name = iface.get("name")
            if not name:
                continue
            hosts = await self._authenticated("GET", f"lan/browser/{name}/")
            for host in hosts or []:
                mac = self.extract_mac(host)
                if mac:
                    hosts_by_mac[mac] = host
        return list(hosts_by_mac.values())

    async def async_get_wifi_signals(self) -> dict[str, int]:
        """MAC (upper) -> signal dBm, pour les stations Wifi actuellement associées."""
        signals: dict[str, int] = {}
        try:
            aps = await self._authenticated(
                "GET", "wifi/ap/", api_version=API_VERSION_WIFI
            )
        except FreeboxApiError as err:
            _LOGGER.debug("wifi/ap/ indisponible: %s", err)
            return signals

        for ap in aps or []:
            ap_id = ap.get("id")
            if ap_id is None:
                continue
            try:
                stations = await self._authenticated(
                    "GET",
                    f"wifi/ap/{ap_id}/stations/",
                    api_version=API_VERSION_WIFI,
                )
            except FreeboxApiError as err:
                _LOGGER.debug("wifi/ap/%s/stations/ indisponible: %s", ap_id, err)
                continue
            for station in stations or []:
                mac = (
                    station.get("mac")
                    or (station.get("id") if isinstance(station.get("id"), str) else None)
                )
                if not mac:
                    continue
                signal = (
                    station.get("signal")
                    or station.get("rssi")
                    or (station.get("rx", {}) or {}).get("signal")
                )
                if signal is not None:
                    signals[mac.upper()] = signal
        return signals

    # ------------------------------------------------------------------ #
    # Blacklist Wifi (mac_filter)
    # ------------------------------------------------------------------ #

    async def async_get_mac_filter_entries(self) -> list[dict]:
        return await self._authenticated("GET", "wifi/mac_filter/") or []

    async def _async_ensure_filter_enabled(self) -> None:
        config = await self._authenticated("GET", "wifi/config/")
        if config.get("mac_filter_state") != "blacklist":
            await self._authenticated(
                "PUT", "wifi/config/", json_body={"mac_filter_state": "blacklist"}
            )

    async def async_toggle_mac_filter(self, mac: str) -> bool:
        """Bascule le blacklist Wifi d'un appareil. Retourne le nouvel état blocked."""
        mac = mac.upper()
        entries = await self.async_get_mac_filter_entries()
        for entry in entries:
            if (entry.get("mac") or "").upper() == mac:
                await self._authenticated(
                    "DELETE", f"wifi/mac_filter/{entry['id']}"
                )
                return False

        await self._async_ensure_filter_enabled()
        await self._authenticated(
            "POST",
            "wifi/mac_filter/",
            json_body={"mac": mac, "comment": "Bascule via Home Assistant", "type": "blacklist"},
        )
        return True
