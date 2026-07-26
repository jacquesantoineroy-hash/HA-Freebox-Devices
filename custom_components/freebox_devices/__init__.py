"""Intégration Freebox Devices : présence, signal Wifi et blacklist par
appareil, en parlant directement à l'API locale de la Freebox (pas de
service intermédiaire)."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CARD_JS_FILENAME,
    CARD_URL_PATH,
    CARD_VERSION,
    CONF_APP_TOKEN,
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
)
from .coordinator import FreeboxDevicesCoordinator
from .freebox_client import FreeboxApiError, FreeboxLocalClient, FreeboxPermissionError
from .parental_coordinator import FreeboxParentalCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Sert le fichier www/freebox-table-card.js en statique et l'injecte
    automatiquement dans le frontend, pour éviter d'avoir à ajouter la
    ressource à la main dans Paramètres > Tableaux de bord > Ressources.
    Idempotent (utile en cas de reload de l'intégration ou de second
    config entry) via un flag dans hass.data.
    """
    flag = f"{DOMAIN}_frontend_registered"
    if hass.data.get(flag):
        return
    hass.data[flag] = True

    www_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(www_path), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{CARD_URL_PATH}/{CARD_JS_FILENAME}?v={CARD_VERSION}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_register_frontend_card(hass)

    session = async_get_clientsession(hass, verify_ssl=False)
    client = FreeboxLocalClient(session, entry.data[CONF_HOST], entry.data[CONF_PORT])

    try:
        await client.async_open_session(entry.data[CONF_APP_TOKEN])
    except FreeboxPermissionError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except FreeboxApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    # Device "hub" représentant la Freebox elle-même : chaque appareil LAN
    # (créé dans entity.py via via_device=(DOMAIN, entry.entry_id)) s'y
    # rattache, ce qui évite l'avertissement HA "via_device inexistant" et
    # regroupe proprement tous les appareils sous la Freebox dans la page
    # Appareils.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Freebox ({entry.data[CONF_HOST]})",
        manufacturer="Freebox SAS",
        model="Freebox Server",
    )

    coordinator = FreeboxDevicesCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    # Coordinator contrôle parental séparé : la permission Freebox OS
    # "Contrôle parental" est accordée indépendamment de "Modification des
    # réglages" (déjà requise pour le verrou Wifi) — si elle n'est pas
    # encore accordée par l'utilisateur, on ne bloque PAS tout le reste de
    # l'intégration pour autant (présence/signal/verrou Wifi continuent de
    # fonctionner), on se contente de logguer et de démarrer avec une liste
    # de profils vide ; le coordinator retentera à son prochain cycle.
    parental_coordinator = FreeboxParentalCoordinator(hass, entry, client)
    try:
        await parental_coordinator.async_config_entry_first_refresh()
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Contrôle parental indisponible pour l'instant (permission "
            "'Contrôle parental' à accorder dans Freebox OS ? cf. README) — "
            "le reste de l'intégration fonctionne normalement."
        )

    # Référence croisée pour que le coordinator des appareils puisse calculer
    # l'accès web par appareil sans appel API supplémentaire (cf.
    # coordinator.py) — posée après coup, une fois les deux coordinators
    # construits, peu importe que le premier refresh parental ait échoué
    # (coordinator.data reste alors simplement {}).
    coordinator.parental_coordinator = parental_coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "devices": coordinator,
        "parental": parental_coordinator,
    }

    await async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
