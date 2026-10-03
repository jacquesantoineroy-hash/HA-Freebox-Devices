"""Écran de veille Vision : ce que la télé affiche quand personne ne la regarde.

Une télé inscrite demande ici, toutes les minutes, de quoi remplir ses
tableaux : l'heure, la météo et la vigilance Météo-France, l'état de la
maison selon Vision, et les entités que la maison a choisies dans
« Écran de veille : entités » (une par ligne ou séparées par des virgules,
`entity_id|Titre` pour renommer). Même porte que le relevé : l'identifiant et
le secret de l'appareil, rien d'autre.
"""
from __future__ import annotations

import datetime
import time
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import PcParentalCoordinator

URL_VEILLE = "/api/pc_parental/veille"
EN_LIGNE_S = 120

NIVEAUX = ("Vert", "Jaune", "Orange", "Rouge")
PHENOMENES = (
    "Vent violent", "Pluie-inondation", "Orages", "Neige-verglas", "Inondation",
    "Canicule", "Grand-froid", "Avalanches", "Vagues-submersion",
)

OUVERTURES = ("door", "garage_door", "opening", "window", "gate", "lock")


def _coordinateur(hass: HomeAssistant) -> PcParentalCoordinator | None:
    entrees = list(hass.data.get(DOMAIN, {}).values())
    return entrees[0] if entrees else None


def _entite_meteo(hass: HomeAssistant) -> str:
    candidats = [s.entity_id for s in hass.states.async_all("weather")]
    for e in candidats:
        if "meteo_france" in e:
            return e
    return candidats[0] if candidats else ""


def _entite_vigilance(hass: HomeAssistant) -> str:
    for s in hass.states.async_all("sensor"):
        if any(p in s.attributes for p in PHENOMENES[:3]):
            return s.entity_id
    return ""


def _nombre(valeur: Any) -> float | None:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _joli(valeur: Any, decimales: int = 1) -> str:
    n = _nombre(valeur)
    if n is None:
        return str(valeur if valeur is not None else "")
    if abs(n - round(n)) < 0.05:
        return str(int(round(n)))
    return ("{:." + str(decimales) + "f}").format(n).replace(".", ",")


def _vigilance(hass: HomeAssistant) -> dict[str, Any]:
    eid = _entite_vigilance(hass)
    etat = hass.states.get(eid) if eid else None
    if etat is None:
        return {"niveau": "", "details": {}, "rang": 0}
    niveau = str(etat.state or "Vert")
    details = {p: str(etat.attributes.get(p)) for p in PHENOMENES if p in etat.attributes}
    rang = NIVEAUX.index(niveau) if niveau in NIVEAUX else 0
    return {"niveau": niveau, "details": details, "rang": rang}


async def _meteo(hass: HomeAssistant) -> dict[str, Any]:
    eid = _entite_meteo(hass)
    etat = hass.states.get(eid) if eid else None
    if etat is None:
        return {}
    a = etat.attributes
    sortie: dict[str, Any] = {
        "etat": str(etat.state),
        "temperature": _nombre(a.get("temperature")),
        "ressenti": _nombre(a.get("apparent_temperature")),
        "humidite": _nombre(a.get("humidity")),
        "vent": _nombre(a.get("wind_speed")),
        "rafales": _nombre(a.get("wind_gust_speed")),
        "pression": _nombre(a.get("pressure")),
        "previsions": [],
    }
    try:
        reponse = await hass.services.async_call(
            "weather", "get_forecasts", {"type": "daily"},
            target={"entity_id": eid}, blocking=True, return_response=True,
        )
        for p in ((reponse or {}).get(eid) or {}).get("forecast") or []:
            sortie["previsions"].append({
                "jour": str(p.get("datetime") or "")[:10],
                "etat": str(p.get("condition") or ""),
                "max": _nombre(p.get("temperature")),
                "min": _nombre(p.get("templow")),
                "pluie": _nombre(p.get("precipitation_probability")),
            })
            if len(sortie["previsions"]) >= 5:
                break
    except Exception:  # noqa: BLE001 - sans prévisions, la météo du moment suffit
        pass
    return sortie


def _tuile(hass: HomeAssistant, entree: str) -> dict[str, Any] | None:
    morceaux = [m.strip() for m in entree.split("|")]
    eid = morceaux[0]
    titre = morceaux[1] if len(morceaux) > 1 and morceaux[1] else ""
    etat = hass.states.get(eid)
    if etat is None:
        return None
    a = etat.attributes
    classe = str(a.get("device_class") or "")
    domaine = eid.split(".")[0]
    valeur = str(etat.state)
    unite = str(a.get("unit_of_measurement") or "")
    alerte = False
    if domaine == "climate":
        valeur = _joli(a.get("current_temperature"))
        unite = "°C"
        cible = a.get("temperature")
        detail = "consigne {} °C".format(_joli(cible)) if cible is not None else ""
        if a.get("hvac_action"):
            detail = "{} · {}".format(detail, a.get("hvac_action")) if detail else str(a.get("hvac_action"))
    elif domaine in ("binary_sensor", "input_boolean", "switch"):
        allume = etat.state == "on"
        if classe in OUVERTURES:
            valeur = "Ouvert" if allume else "Fermé"
            alerte = allume
        elif classe in ("problem", "smoke", "gas", "safety", "moisture"):
            valeur = "Alerte" if allume else "OK"
            alerte = allume
        else:
            valeur = "Actif" if allume else "Inactif"
        detail = ""
    else:
        if _nombre(etat.state) is not None:
            valeur = _joli(etat.state)
        elif valeur in ("unknown", "unavailable", "None"):
            valeur = "—"
        alerte = valeur.lower() in ("ouvert", "oui", "alerte", "allumé")
        detail = ""
    return {
        "id": eid,
        "titre": titre or str(a.get("friendly_name") or eid),
        "valeur": valeur,
        "unite": unite,
        "detail": detail,
        "icone": str(a.get("icon") or ""),
        "classe": classe,
        "alerte": alerte,
    }


def _maison(hass: HomeAssistant, coord: PcParentalCoordinator) -> list[dict[str, Any]]:
    store = coord.store
    par_personne: dict[str, dict[str, Any]] = {}
    for pc in store.pcs.values():
        if not pc.get("enabled", True):
            continue
        personne = str(pc.get("person") or "")
        etat_p = hass.states.get(personne) if personne else None
        prenom = str(etat_p.name) if etat_p is not None and etat_p.name else "Sans personne"
        if prenom.lower() == "affichage":
            continue
        try:
            evalue = store.evaluate(pc)
            usage = store.usage_du_jour(pc)
        except Exception:  # noqa: BLE001
            continue
        vu = float(pc.get("last_seen") or 0)
        agent = pc.get("agent") or {}
        bloc = par_personne.setdefault(prenom, {"prenom": prenom, "appareils": [], "minutes": 0})
        bloc["minutes"] += int(usage.get("actif", 0)) // 60
        bloc["appareils"].append({
            "nom": str(pc.get("name") or ""),
            "android": pc.get("platform") == "android",
            "en_ligne": vu > 0 and time.time() - vu < EN_LIGNE_S,
            "verrouille": bool(evalue.get("locked")),
            "inactif_s": int(agent.get("idle_seconds") or 0),
        })
    return sorted(par_personne.values(), key=lambda p: p["prenom"].lower())


_cache_courbe: dict[str, Any] = {"quand": 0.0, "cle": "", "valeur": None}
COURBE_HEURES = 24
COURBE_PAS_S = 15 * 60


def _entites_courbe(hass: HomeAssistant, coord: PcParentalCoordinator) -> list[str]:
    """Les deux températures à comparer : celles choisies, sinon les deux
    premières tuiles de température (dehors puis dedans)."""
    choisies = [e.split("|")[0].strip() for e in (coord.store.veille_courbe or []) if e.strip()]
    if len(choisies) >= 2:
        return choisies[:2]
    temperatures = []
    for entree in coord.store.veille_entites:
        eid = entree.split("|")[0].strip()
        etat = hass.states.get(eid)
        if etat is not None and str(etat.attributes.get("device_class") or "") == "temperature":
            temperatures.append(eid)
    return temperatures[:2]


def _serie(hass: HomeAssistant, eid: str, debut, fin) -> list[list[float]]:
    """Une température toutes les quinze minutes sur la période : [horodatage, valeur]."""
    from homeassistant.components.recorder import history

    etats = history.state_changes_during_period(
        hass, debut, fin, eid, no_attributes=True, include_start_time_state=True,
    ).get(eid) or []
    points: list[tuple[float, float]] = []
    for s in etats:
        v = _nombre(s.state)
        if v is None:
            continue
        points.append((s.last_updated.timestamp(), v))
    if not points:
        return []
    # Échantillonnage régulier : la dernière valeur connue à chaque pas.
    sortie: list[list[float]] = []
    t = debut.timestamp()
    fin_s = fin.timestamp()
    i = 0
    courant = points[0][1]
    while t <= fin_s:
        while i < len(points) and points[i][0] <= t:
            courant = points[i][1]
            i += 1
        sortie.append([round(t), round(courant, 1)])
        t += COURBE_PAS_S
    return sortie


async def _courbe(hass: HomeAssistant, coord: PcParentalCoordinator) -> dict[str, Any]:
    entites = _entites_courbe(hass, coord)
    if len(entites) < 2:
        return {}
    cle = "|".join(entites)
    if _cache_courbe["valeur"] is not None and _cache_courbe["cle"] == cle and time.time() - _cache_courbe["quand"] < 300:
        return _cache_courbe["valeur"]
    fin = dt_util.utcnow()
    debut = fin - datetime.timedelta(hours=COURBE_HEURES)
    try:
        from homeassistant.components.recorder import get_instance

        series = [
            await get_instance(hass).async_add_executor_job(_serie, hass, eid, debut, fin)
            for eid in entites
        ]
    except Exception:  # noqa: BLE001 - sans historique, pas de courbe, rien d'autre ne casse
        return {}
    noms = []
    for eid in entites:
        titre = ""
        for entree in coord.store.veille_entites:
            morceaux = entree.split("|")
            if morceaux[0].strip() == eid and len(morceaux) > 1:
                titre = morceaux[1].strip()
        etat = hass.states.get(eid)
        noms.append(titre or str((etat.attributes.get("friendly_name") if etat else None) or eid))
    valeur = {
        "heures": COURBE_HEURES,
        "series": [
            {"id": eid, "nom": nom, "points": pts}
            for eid, nom, pts in zip(entites, noms, series)
        ],
    }
    _cache_courbe.update({"quand": time.time(), "cle": cle, "valeur": valeur})
    return valeur


async def etat_veille(hass: HomeAssistant, coord: PcParentalCoordinator) -> dict[str, Any]:
    tuiles = []
    for entree in coord.store.veille_entites:
        t = _tuile(hass, entree)
        if t:
            tuiles.append(t)
    return {
        "ok": True,
        "heure": dt_util.now().isoformat(),
        "meteo": await _meteo(hass),
        "vigilance": _vigilance(hass),
        "tuiles": tuiles,
        "maison": _maison(hass, coord),
        "courbe": await _courbe(hass, coord),
    }


class PcParentalVeilleView(HomeAssistantView):
    url = URL_VEILLE
    name = "api:pc_parental:veille"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        try:
            corps: dict[str, Any] = await request.json()
        except ValueError:
            return self.json({"ok": False, "error": "json"}, status_code=400)
        coord = _coordinateur(self.hass)
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        moi = coord.store.by_secret(str(corps.get("id") or ""), str(corps.get("secret") or ""))
        if moi is None:
            return self.json({"ok": False, "error": "auth"}, status_code=401)
        return self.json(await etat_veille(self.hass, coord))
