"""Intégration Freebox Devices : présence, signal Wifi et blacklist par
appareil, en parlant directement à l'API locale de la Freebox (pas de
service intermédiaire)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_APP_TOKEN, CONF_HOST, CONF_PORT, DOMAIN
from .coordinator import FreeboxDevicesCoordinator
from .freebox_client import FreeboxApiError, FreeboxLocalClient, FreeboxPermissionError

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
