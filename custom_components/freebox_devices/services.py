"""Service `freebox_devices.definir_plage_horaire` : bloque/autorise un
profil de contrôle parental sur une plage horaire précise, certains jours
de la semaine, en modifiant uniquement les créneaux concernés du planning
existant (30 min de résolution côté Freebox) — le reste du planning n'est
pas touché.

⚠️ Ordre des jours dans le tableau `mapping` de la Freebox non documenté
officiellement (cf. dev.freebox.fr/sdk/os/parental/) : implémenté en
supposant l'ordre ISO (lundi=0 ... dimanche=6), comme le reste de l'API
Freebox (cf. jours de la semaine côté Freebox OS). **Non vérifiable depuis
le sandbox de développement (pas d'accès réseau à la Freebox)** — à
confirmer lors du premier test réel : si le service décale les jours
d'un cran, corriger `_DAY_INDEX` ci-dessous en conséquence.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN
from .freebox_client import FreeboxLocalClient

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TIME_RANGE = "definir_plage_horaire"
SERVICE_TOGGLE_WEB_ACCESS = "couper_acces_web"

# Préfixe utilisé pour marquer les profils créés à la volée par ce service
# (pour distinguer "profil géré automatiquement pour un blocage individuel"
# d'un vrai profil que l'utilisateur a configuré lui-même sur la Freebox).
_PERSONAL_FILTER_PREFIX = "[HA] "

_DAY_INDEX = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

SERVICE_SET_TIME_RANGE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("jours"): vol.All(
            cv.ensure_list, [vol.In(_DAY_INDEX)]
        ),
        vol.Required("heure_debut"): cv.time,
        vol.Required("heure_fin"): cv.time,
        vol.Required("mode"): vol.In(["allowed", "denied", "webonly"]),
    }
)


SERVICE_TOGGLE_WEB_ACCESS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("bloquer"): cv.boolean,
    }
)


def _resolve_device_mac(hass: HomeAssistant, entity_id: str) -> tuple[str, str, str | None]:
    """Retrouve (mac, config_entry_id, nom) de l'appareil Freebox propriétaire
    de `entity_id` (peu importe la plateforme : device_tracker/lock/sensor
    partagent tous le même device_info identifiers={(DOMAIN, mac)})."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if entry is None or entry.device_id is None:
        raise vol.Invalid(f"{entity_id} introuvable ou sans appareil associé")

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(entry.device_id)
    if device is None:
        raise vol.Invalid(f"Appareil introuvable pour {entity_id}")

    for domain, ident in device.identifiers:
        if domain == DOMAIN and not ident.startswith("parental_"):
            name = device.name_by_user or device.name
            return ident, entry.config_entry_id, name

    raise vol.Invalid(
        f"{entity_id} n'est pas une entité d'un appareil Freebox Devices "
        "(attendu : device_tracker/lock/sensor d'un appareil LAN)"
    )


def _resolve_filter_id(hass: HomeAssistant, entity_id: str) -> int:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or not entry.unique_id.startswith("parental_"):
        raise vol.Invalid(
            f"{entity_id} n'est pas une entité d'un profil de contrôle "
            "parental Freebox (attendu : capteur 'État' ou sélecteur "
            "'Mode' d'un profil)"
        )
    # unique_id format: parental_{id}_etat / parental_{id}_mode / parental_{id}_pause
    parts = entry.unique_id.split("_")
    return int(parts[1])


def _client_for_entity(hass: HomeAssistant, entity_id: str) -> tuple[int, FreeboxLocalClient]:
    filter_id = _resolve_filter_id(hass, entity_id)
    registry = er.async_get(hass)
    entry_id = registry.async_get(entity_id).config_entry_id
    client = hass.data[DOMAIN][entry_id]["parental"].client
    return filter_id, client


async def async_setup_services(hass: HomeAssistant) -> None:
    """Enregistre le service au niveau du domaine (une seule fois, même si
    plusieurs entrées de configuration existent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_TIME_RANGE):
        return

    async def _handle_set_time_range(call: ServiceCall) -> None:
        entity_id = call.data["entity_id"]
        filter_id, client = _client_for_entity(hass, entity_id)

        planning = await client.async_get_parental_planning(filter_id)
        resolution = planning["resolution"]
        mapping = list(planning["mapping"])

        start_slot = _time_to_slot(call.data["heure_debut"], resolution)
        end_slot = _time_to_slot(call.data["heure_fin"], resolution)
        mode = call.data["mode"]

        for jour in call.data["jours"]:
            day_offset = _DAY_INDEX[jour] * resolution
            for slot in range(start_slot, end_slot):
                mapping[day_offset + slot] = mode

        await client.async_set_parental_planning(
            filter_id,
            cdayranges=planning.get("cdayranges", []),
            resolution=resolution,
            mapping=mapping,
        )
        _LOGGER.info(
            "Plage horaire mise à jour pour le profil %s (%s, %s-%s, %s)",
            filter_id,
            call.data["jours"],
            call.data["heure_debut"],
            call.data["heure_fin"],
            mode,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TIME_RANGE,
        _handle_set_time_range,
        schema=SERVICE_SET_TIME_RANGE_SCHEMA,
    )

    async def _handle_toggle_web_access(call: ServiceCall) -> None:
        entity_id = call.data["entity_id"]
        bloquer = call.data["bloquer"]
        mac, entry_id, device_name = _resolve_device_mac(hass, entity_id)
        parental_coordinator = hass.data[DOMAIN][entry_id]["parental"]
        client: FreeboxLocalClient = parental_coordinator.client

        mac_upper = mac.upper()
        filters = await client.async_get_parental_filters()
        covering = next(
            (
                f
                for f in filters
                if mac_upper in [(m or "").upper() for m in (f.get("macs") or [])]
            ),
            None,
        )

        if covering is None:
            if not bloquer:
                # Aucun profil ne couvre l'appareil : il est déjà "autorisé"
                # par défaut, rien à faire pour le rétablir.
                return
            covering = await client.async_create_parental_filter(
                desc=f"{_PERSONAL_FILTER_PREFIX}{device_name or mac}",
                macs=[mac_upper],
            )
            _LOGGER.info(
                "Profil de contrôle parental créé à la volée pour %s (mac %s, id %s)",
                device_name or mac,
                mac_upper,
                covering["id"],
            )

        filter_id = covering["id"]
        if bloquer:
            await client.async_update_parental_filter(
                filter_id, forced=True, forced_mode="denied"
            )
        else:
            await client.async_update_parental_filter(
                filter_id, forced=False, tmp_mode_expire=0
            )

        await parental_coordinator.async_request_refresh()
        _LOGGER.info(
            "Accès web %s pour %s (profil %s)",
            "coupé" if bloquer else "rétabli",
            device_name or mac,
            filter_id,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TOGGLE_WEB_ACCESS,
        _handle_toggle_web_access,
        schema=SERVICE_TOGGLE_WEB_ACCESS_SCHEMA,
    )


def _time_to_slot(value, resolution: int) -> int:
    """Convertit un `datetime.time` en index de créneau (résolution 48 =
    créneaux de 30 min)."""
    slots_per_hour = resolution / 24
    return int((value.hour + value.minute / 60) * slots_per_hour)
