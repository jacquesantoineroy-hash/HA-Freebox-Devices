"""Espace parents de Vision : l'application, et le tableau de bord.

Un appareil portant l'étiquette « Parents » voit, depuis l'application,
l'état de tous les appareils de la maison et agit dessus : ouvrir un moment,
fermer, lever une dérogation, envoyer un mot. Même règle d'accès que la
réponse aux demandes de temps : le secret de l'appareil, et l'étiquette.

Le tableau de bord Home Assistant lit et agit par la même porte, mais avec
le compte Home Assistant d'un administrateur : ce que le téléphone d'un
parent montre, le tableau le montre aussi, et avec les mêmes gestes.
"""
from __future__ import annotations

import time
from typing import Any

from aiohttp import web
from homeassistant.components import persistent_notification
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from . import demandes, labels
from .const import DOMAIN, MODE_LOCKED, MODE_OPEN
from .coordinator import PcParentalCoordinator
from .planner import next_lock

URL_PARENT = "/api/pc_parental/parent"
URL_MAISON = "/api/pc_parental/maison"
EN_LIGNE_S = 120


def _hm(secondes: Any) -> str:
    s = int(secondes or 0)
    s = s - 86400 * (s // 86400)
    h, reste = divmod(s, 3600)
    return "{:02d}:{:02d}".format(h, reste // 60)


def _prenom(hass: HomeAssistant, pc: dict[str, Any]) -> str:
    etat = hass.states.get(str(pc.get("person") or ""))
    if etat is not None and etat.name:
        return str(etat.name)
    return ""


def _libelles(pc: dict[str, Any], genre: str, noms: list[str]) -> list[dict[str, str]]:
    """Noms lisibles pour ce que l'agent bloque : « Roblox » plutôt qu'un paquet."""
    vus = pc.get("apps_vues" if genre == "apps" else "sites_vus") or {}
    sortie = []
    deja = set()
    for nom in noms:
        fiche = vus.get(nom) if isinstance(vus, dict) else None
        lib = str((fiche or {}).get("libelle") or "") if isinstance(fiche, dict) else ""
        # Les membres d'une famille (cdn, sous-domaines) n'apportent rien au parent.
        if genre == "sites" and nom.count(".") > 1 and not lib:
            continue
        cle = (lib or nom).lower()
        if cle in deja:
            continue
        deja.add(cle)
        sortie.append({"nom": nom, "libelle": lib or nom})
    sortie.sort(key=lambda x: x["libelle"].lower())
    return sortie


def _plages(pc: dict[str, Any], maintenant_s: int, jour: int) -> list[dict[str, Any]]:
    sortie = []
    for regle in pc.get("rules") or []:
        if not isinstance(regle, dict):
            continue
        jours = list(regle.get("weekdays") or [True] * 7)
        debut = int(regle.get("start") or 0)
        fin = int(regle.get("end") or 0)
        aujourd_hui = bool(jours[jour]) if jour < len(jours) else True
        if debut <= fin:
            actif = aujourd_hui and debut <= maintenant_s < fin
        else:
            # Plage de nuit : commence la veille au soir, finit ce matin.
            veille = jours[(jour - 1) if jour else 6] if len(jours) == 7 else True
            actif = (aujourd_hui and maintenant_s >= debut) or (bool(veille) and maintenant_s < fin)
        sortie.append({
            "id": regle.get("id"),
            "nom": str(regle.get("name") or ""),
            "debut": _hm(debut),
            "fin": _hm(fin),
            "jours": [bool(j) for j in jours],
            "aujourdhui": aujourd_hui,
            "actif": bool(regle.get("enabled", True)) and actif,
            "active": bool(regle.get("enabled", True)),
            "portee": str(regle.get("portee") or "session"),
            "etiquettes": list(regle.get("etiquettes") or []),
        })
    return sortie


ROLES = ("parents", "enfants", "affichage")


def _categories(hass: HomeAssistant, coord: PcParentalCoordinator) -> list[dict[str, Any]]:
    """Les étiquettes qui classent des applis et des sites, avec leur contenu."""
    store = coord.store
    contenu: dict[str, dict[str, list]] = {}
    libelles: dict[str, str] = {}
    for pc in store.pcs.values():
        for nom, fiche in (pc.get("apps_vues") or {}).items():
            if isinstance(fiche, dict) and fiche.get("libelle"):
                libelles.setdefault(nom, str(fiche["libelle"]))
    for genre in ("apps", "sites"):
        for nom, ets in (store.etiquettes.get(genre) or {}).items():
            for e in ets or []:
                bloc = contenu.setdefault(str(e), {"apps": [], "sites": []})
                bloc[genre].append(nom)
    noms = set(contenu)
    noms.update(e for e in labels.vocabulaire(hass) if e)
    noms.update(e for e in store.bannis if store._est_etiquette(e))
    divert = {e.lower() for e in (store.divertissement or [])}
    sortie = []
    for nom in sorted(noms, key=lambda s: s.lower()):
        if nom.lower() in ROLES:
            continue
        bloc = contenu.get(nom, {"apps": [], "sites": []})
        apps = sorted(({"nom": a, "libelle": libelles.get(a, a)} for a in bloc["apps"]), key=lambda x: x["libelle"].lower())
        sites = sorted(s for s in bloc["sites"] if s.count(".") == 1) or sorted(bloc["sites"])
        sortie.append({
            "nom": nom,
            "maison": store.est_banni(nom),
            "securite": nom.lower() in ("dangereux", "contournement", "pub & traçage", "pub & tracage"),
            "age": nom.lower() in ("pegi 12", "pegi 16", "pegi 18", "adulte"),
            "divertissement": nom.lower() in divert,
            "apps": apps,
            "sites": sites,
        })
    return sortie


def _etat_categorie(store, pc: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
    """Ce que vaut une catégorie pour cet appareil : le choix du parent, et
    ce qui est réellement appliqué (la maison, la moyenne ou le planning
    peuvent la couper par-dessus)."""
    nom = c["nom"]
    bas = nom.lower()
    bloques = {str(b).lower() for b in (pc.get("bloques") or [])}
    autorises = {str(b).lower() for b in (pc.get("autorises") or [])}
    choix = "bloquer" if bas in bloques else ("autoriser" if bas in autorises else "neutre")
    code, texte = "", ""
    if c.get("maison"):
        code = "securite" if c.get("securite") else "maison"
        texte = "Interdit pour toute la maison."
    else:
        try:
            if store.moyenne_ferme(pc, [nom]):
                personne = str(pc.get("person") or "")
                cfg = store.moyennes.get(personne) or {}
                valeur = store.moyenne_de(personne) or 0.0
                code, texte = "moyenne", "Coupé par la règle de moyenne ({:g} sous {:g}).".format(valeur, float(cfg.get("seuil") or 12))
            else:
                regle = store.plage_ferme(pc, nom)
                if regle:
                    code, texte = "plage", "Coupé en ce moment par le planning « {} ».".format(regle.get("name") or "plage")
        except Exception:  # noqa: BLE001
            pass
    if not code and choix == "bloquer":
        code = "age" if c.get("age") else "regle"
        texte = "Coupé par les parents."
    return {"choix": choix, "coupe": bool(code), "code": code, "raison": texte, "verrou": code in ("securite", "maison", "moyenne", "plage")}


def _etats_etiquettes(pc: dict[str, Any], categories: list[dict[str, Any]], store=None) -> dict[str, Any]:
    etats = {}
    for c in categories:
        if store is None:
            bloques = {str(b).lower() for b in (pc.get("bloques") or [])}
            etats[c["nom"]] = "bloquer" if c["nom"].lower() in bloques else "neutre"
        else:
            etats[c["nom"]] = _etat_categorie(store, pc, c)
    return etats


def _fiche(hass: HomeAssistant, coord: PcParentalCoordinator, pc: dict[str, Any], parents: list[str]) -> dict[str, Any]:
    etat = coord.store.evaluate(pc)
    maintenant = coord.local_now()
    local = maintenant.replace(tzinfo=None)
    agent = pc.get("agent") or {}
    bloque = coord.store.effectif(pc)
    vu = float(pc.get("last_seen") or 0)
    suivant = etat.get("next_change")
    prochain_verrou = None if etat["locked"] else next_lock(pc.get("rules") or [], local)
    override = etat.get("override") or None
    usage = coord.store.usage_du_jour(pc)
    focus = str(agent.get("focus") or "")
    vues = pc.get("apps_vues") or {}
    fiche_focus = vues.get(focus) if focus else None
    if focus and fiche_focus is None:
        # L'agent dit « robloxplayerbeta », le catalogue connaît « RobloxPlayerBeta ».
        bas = focus.lower().removesuffix(".exe")
        fiche_focus = next((f for n, f in vues.items() if str(n).lower().removesuffix(".exe") == bas), None)
    etiquettes = [e for e in labels.noms_du_pc(hass, pc["id"]) if e.lower() != "parents"]
    return {
        "id": pc["id"],
        "nom": str(pc.get("name") or pc["id"]),
        "prenom": _prenom(hass, pc),
        "personne": str(pc.get("person") or ""),
        "android": pc.get("platform") == "android",
        "parent": pc["id"] in parents,
        "en_ligne": vu > 0 and time.time() - vu < EN_LIGNE_S,
        "vu": int(vu),
        "verrouille": bool(etat["locked"]),
        "source": str(etat.get("source") or ""),
        "planning_ferme": etat.get("planning") == MODE_LOCKED,
        "derogation": {
            "mode": override.get("mode"),
            "fin": int(float(override.get("until") or 0)),
        } if override else None,
        "prochain": suivant.isoformat() if suivant else "",
        "prochain_verrou": prochain_verrou.isoformat() if prochain_verrou else "",
        "focus": focus,
        "focus_libelle": str((fiche_focus or {}).get("libelle") or "") if isinstance(fiche_focus, dict) else "",
        "inactif_s": int(agent.get("idle_seconds") or 0),
        "usage": {"actif": int(usage.get("actif", 0)) // 60, "ouvert": int(usage.get("ouvert", 0)) // 60},
        "etiquettes": etiquettes,
        "apps": _libelles(pc, "apps", list(bloque.get("apps") or [])),
        "sites": _libelles(pc, "sites", list(bloque.get("sites") or [])),
        "motifs": list(bloque.get("motifs") or []),
        "raisons": dict(bloque.get("raisons") or {}),
        "plages": _plages(pc, sum([local.hour * 3600, local.minute * 60]), local.weekday()),
        "demande": pc.get("demande") or None,
        "demandes": demandes.en_attente(pc),
    }


def _personnes(hass: HomeAssistant, coord: PcParentalCoordinator) -> list[dict[str, Any]]:
    """Qui vit ici : les personnes qu'un appareil désigne, et leurs réglages."""
    store = coord.store
    sortie = []
    vues = set()
    for pc in store.pcs.values():
        personne = str(pc.get("person") or "")
        if not personne or personne in vues:
            continue
        vues.add(personne)
        cle = personne.split(".")[-1]
        etat = hass.states.get(personne)
        moyenne = store.moyennes.get(personne) or {}
        sortie.append({
            "entite": personne,
            "cle": cle,
            "prenom": str(etat.name) if etat is not None and etat.name else cle,
            "photo": str((etat.attributes or {}).get("entity_picture") or "") if etat is not None else "",
            "moyenne": {
                "active": bool(moyenne.get("active", False)),
                "ignore": bool(moyenne.get("ignore", False)),
                "seuil": float(moyenne.get("seuil") or 12),
                "valeur": store.moyenne_de(personne),
                "etat": store.etat_moyenne(personne),
            } if moyenne else None,
        })
    sortie.sort(key=lambda p: p["prenom"].lower())
    return sortie


def etat_maison(hass: HomeAssistant, coord: PcParentalCoordinator, moi_id: str | None = None) -> dict[str, Any]:
    """Tout ce qu'un parent voit : appareils, demandes, catégories, personnes."""
    parents = labels.pcs_avec(hass, coord.store.pcs, "Parents")
    categories = _categories(hass, coord)
    appareils = []
    for pc in coord.store.pcs.values():
        if not pc.get("enabled", True) and pc["id"] != moi_id:
            continue
        try:
            fiche = _fiche(hass, coord, pc, parents)
            fiche["etiquettes_etat"] = _etats_etiquettes(pc, categories, coord.store)
            appareils.append(fiche)
        except Exception:  # noqa: BLE001 - une fiche cassée ne cache pas les autres
            continue
    appareils.sort(key=lambda a: (a["parent"], not a["en_ligne"], (a["prenom"] or a["nom"]).lower()))
    attente = []
    for a in appareils:
        for d in a.get("demandes") or []:
            attente.append(dict(d, prenom=a.get("prenom") or a.get("nom"), pc=a["id"]))
    attente.sort(key=lambda d: d.get("ts") or 0, reverse=True)
    return {
        "ok": True,
        "appareils": appareils,
        "demandes": attente,
        "categories": categories,
        "personnes": _personnes(hass, coord),
    }


class _Refus(Exception):
    """Une action refusée, avec le code HTTP et le message à renvoyer."""

    def __init__(self, status: int, erreur: str, retour: str = "") -> None:
        super().__init__(erreur)
        self.status = status
        self.erreur = erreur
        self.retour = retour


async def agir(
    hass: HomeAssistant,
    coord: PcParentalCoordinator,
    cible: dict[str, Any],
    corps: dict[str, Any],
    qui: str,
    moi_id: str | None = None,
) -> str:
    """Un geste de parent sur un appareil. Renvoie la phrase à afficher.

    Même code pour l'application et pour le tableau de bord : un parent qui
    ouvre trente minutes depuis son téléphone ou depuis Home Assistant fait
    exactement la même chose, et l'enfant reçoit le même mot.
    """
    action = str(corps.get("action") or "")
    try:
        minutes = max(0, min(720, int(corps.get("minutes") or 0)))
    except (TypeError, ValueError):
        minutes = 0
    retour = ""
    if action == "ouvrir":
        coord.store.set_override(cible, MODE_OPEN, minutes)
        retour = "{} a ouvert l'accès{}.".format(qui, " pour {} min".format(minutes) if minutes else "")
    elif action == "fermer":
        coord.store.set_override(cible, MODE_LOCKED, minutes)
        retour = "{} a fermé l'accès{}.".format(qui, " pour {} min".format(minutes) if minutes else "")
    elif action == "annuler":
        coord.store.clear_override(cible)
        retour = "Retour au planning."
    elif action == "acces":
        d = demandes.retirer(cible, str(corps.get("demande") or ""))
        if d is None:
            return ""
        decision = str(corps.get("decision") or "non")
        joli = d.get("libelle") or d.get("cle")
        if decision == "toujours":
            if coord.store.est_banni(d["cle"]):
                retour = "Impossible : {} est interdit pour toute la maison.".format(joli)
            else:
                coord.store.basculer(cible, d["cle"], False)
                retour = "{} a autorisé {}.".format(qui, joli)
        elif decision == "temporaire":
            minutes = minutes or 60
            if d.get("genre") == "apps":
                coord.store.laisser_passer_app(cible, d["cle"], minutes)
            else:
                coord.store.laisser_passer(cible, d["cle"], minutes)
            retour = "{} a ouvert {} pour {} min.".format(qui, joli, minutes)
        else:
            retour = "{} n'a pas autorisé {}.".format(qui, joli)
        persistent_notification.async_dismiss(
            hass, "{}_acces_{}_{}".format(DOMAIN, cible["id"], d["id"])
        )
        try:
            coord.store.add_message(cible["id"], retour, titre="Réponse")
        except ValueError:
            pass
    elif action == "autoriser":
        genre = "apps" if str(corps.get("genre") or "") == "apps" else "sites"
        nom = str(corps.get("nom") or "").strip()
        cle = demandes.cle_de(genre, nom)
        if not cle:
            raise _Refus(400, "nom")
        decision = str(corps.get("decision") or "temporaire")
        if decision == "toujours":
            if coord.store.est_banni(cle):
                raise _Refus(409, "banni", "Interdit pour toute la maison : à lever dans Vision.")
            coord.store.basculer(cible, cle, False)
            retour = "{} a autorisé {}.".format(qui, nom)
        elif decision == "bloquer":
            coord.store.basculer(cible, cle, True)
            retour = "{} a bloqué {}.".format(qui, nom)
        else:
            minutes = minutes or 60
            if genre == "apps":
                coord.store.laisser_passer_app(cible, cle, minutes)
            else:
                coord.store.laisser_passer(cible, cle, minutes)
            retour = "{} a ouvert {} pour {} min.".format(qui, nom, minutes)
        if cible["id"] != moi_id:
            try:
                coord.store.add_message(cible["id"], retour, titre="Vision")
            except ValueError:
                pass
    elif action == "etiquette":
        nom = str(corps.get("etiquette") or "").strip()
        etat = str(corps.get("etat") or "neutre")
        if not nom or not coord.store._est_etiquette(nom):
            raise _Refus(400, "etiquette")
        if coord.store.est_banni(nom):
            raise _Refus(409, "banni", "Interdit pour toute la maison : à lever dans Vision.")
        if etat == "bloquer":
            coord.store.basculer(cible, nom, True)
            retour = "{} : {} coupé.".format(qui, nom)
        elif etat == "autoriser":
            coord.store.basculer(cible, nom, False)
            retour = "{} : {} autorisé.".format(qui, nom)
        else:
            for champ in ("bloques", "autorises"):
                cible[champ] = [v for v in (cible.get(champ) or []) if str(v).strip().lower() != nom.lower()]
            retour = "{} : {} laissé aux règles de la maison.".format(qui, nom)
    elif action == "message":
        texte = str(corps.get("texte") or "").strip()[:200]
        if not texte:
            raise _Refus(400, "texte")
        try:
            coord.store.add_message(cible["id"], texte, titre=qui)
        except ValueError:
            pass
        retour = "Message envoyé."
    else:
        raise _Refus(400, "action")
    if action in ("ouvrir", "fermer", "annuler") and cible["id"] != moi_id:
        try:
            coord.store.add_message(cible["id"], retour, titre="Vision")
        except ValueError:
            pass
    await coord.store.async_save()
    coord.async_set_updated_data(
        {p: coord.store.evaluate(x) for p, x in coord.store.pcs.items()}
    )
    hass.bus.async_fire(
        "{}_parent_action".format(DOMAIN),
        {"action": action, "pc": cible["id"], "minutes": minutes, "par": qui},
    )
    return retour


def _coordinateur(hass: HomeAssistant) -> PcParentalCoordinator | None:
    entrees = list(hass.data.get(DOMAIN, {}).values())
    return entrees[0] if entrees else None


class PcParentalParentView(HomeAssistantView):
    """L'application d'un parent : secret de l'appareil et étiquette « Parents »."""

    url = URL_PARENT
    name = "api:pc_parental:parent"
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
        parents = labels.pcs_avec(self.hass, coord.store.pcs, "Parents")
        if moi["id"] not in parents:
            return self.json({"ok": False, "error": "parent"}, status_code=403)

        retour = ""
        if str(corps.get("action") or ""):
            cible = coord.store.pcs.get(str(corps.get("pc") or ""))
            if cible is None:
                return self.json({"ok": False, "error": "pc"}, status_code=404)
            qui = _prenom(self.hass, moi) or str(moi.get("name") or "Un parent")
            try:
                retour = await agir(self.hass, coord, cible, corps, qui, moi["id"])
            except _Refus as refus:
                reponse: dict[str, Any] = {"ok": False, "error": refus.erreur}
                if refus.retour:
                    reponse["retour"] = refus.retour
                return self.json(reponse, status_code=refus.status)
            if corps.get("action") == "acces" and not retour:
                return self.json({"ok": True, "deja": True, "appareils": []})
        etat = etat_maison(self.hass, coord, moi["id"])
        etat.update({"moi": moi["id"], "retour": retour})
        return self.json(etat)


class PcParentalMaisonView(HomeAssistantView):
    """Le tableau de bord : un administrateur Home Assistant, rien d'autre."""

    url = URL_MAISON
    name = "api:pc_parental:maison"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def _admin(self, request: web.Request) -> web.Response | None:
        utilisateur = request.get("hass_user")
        if utilisateur is None or not utilisateur.is_admin:
            return self.json({"ok": False, "error": "admin"}, status_code=403)
        return None

    async def get(self, request: web.Request) -> web.Response:
        if refus := self._admin(request):
            return refus
        coord = _coordinateur(self.hass)
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        return self.json(etat_maison(self.hass, coord))

    async def post(self, request: web.Request) -> web.Response:
        if refus := self._admin(request):
            return refus
        try:
            corps: dict[str, Any] = await request.json()
        except ValueError:
            return self.json({"ok": False, "error": "json"}, status_code=400)
        coord = _coordinateur(self.hass)
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        cible = coord.store.pcs.get(str(corps.get("pc") or ""))
        if cible is None:
            return self.json({"ok": False, "error": "pc"}, status_code=404)
        qui = str(getattr(request.get("hass_user"), "name", "") or "Un parent")
        try:
            retour = await agir(self.hass, coord, cible, corps, qui)
        except _Refus as refus:
            reponse: dict[str, Any] = {"ok": False, "error": refus.erreur}
            if refus.retour:
                reponse["retour"] = refus.retour
            return self.json(reponse, status_code=refus.status)
        etat = etat_maison(self.hass, coord)
        etat["retour"] = retour
        return self.json(etat)
