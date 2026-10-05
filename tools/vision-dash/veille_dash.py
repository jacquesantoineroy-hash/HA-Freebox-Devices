"""Les tableaux de bord de Home Assistant sur l'écran de veille de Vision.

On ne compose plus rien à part : on reprend les tableaux de bord existants.
Dans Vision (onglet Écran de veille), on choisit lesquels sont montrés, quelles
vues et quelles cartes. Chaque vue retenue devient un tableau de veille : ses
sections, ses colonnes et la taille de ses cartes sont reprises, puis l'appli
les redessine dans son thème et les répartit selon l'écran (télé, téléphone).
Quand tout ne tient pas, l'appli enchaîne plusieurs écrans en fondu.

Cartes comprises : tuile, entité, capteur, jauge, bouton, lumière, thermostat,
météo, entités, aperçu, graphiques d'historique et de statistiques, markdown,
et les piles, grilles et cartes conditionnelles qui les contiennent. Toute
autre carte portant `entity` ou `entities` est lue de la même façon.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

ECRANS = ("tele", "telephone")
PUBLICS = ("affichage", "parent", "enfant")
MAX_TABLEAUX = 16
MAX_CASES = 60

_cache: dict[str, Any] = {}


# --- Lecture des tableaux de bord -------------------------------------------------------


def _lovelace(hass: HomeAssistant) -> dict[Any, Any]:
    lovelace = hass.data.get("lovelace")
    tableaux = getattr(lovelace, "dashboards", None)
    if tableaux is None and isinstance(lovelace, dict):
        tableaux = lovelace.get("dashboards")
    return tableaux or {}


def _titre_tableau(adresse: Any, tableau: Any) -> str:
    fiche = getattr(tableau, "config", None)
    if isinstance(fiche, dict) and fiche.get("title"):
        return str(fiche["title"])
    return "Aperçu" if adresse in (None, "lovelace") else str(adresse)


async def _config(hass: HomeAssistant, adresse: str) -> dict[str, Any] | None:
    """La configuration d'un tableau de bord (gardée 20 s)."""
    connu = _cache.get(adresse)
    if connu and time.time() - connu[0] < 20:
        return connu[1]
    tableaux = _lovelace(hass)
    tableau = tableaux.get(None if adresse == "lovelace" else adresse)
    config = None
    if tableau is not None:
        try:
            config = await tableau.async_load(False)
        except Exception:  # noqa: BLE001  (vide, ou illisible)
            config = None
    _cache[adresse] = (time.time(), config)
    return config


# --- D'une carte Home Assistant à des cases ---------------------------------------------


def _options(carte: dict[str, Any]) -> dict[str, Any]:
    return carte.get("grid_options") or carte.get("layout_options") or {}


def _largeur(carte: dict[str, Any], defaut: int) -> int:
    o = _options(carte)
    v = o.get("columns", o.get("grid_columns"))
    if v == "full":
        return 12
    if isinstance(v, (int, float)):
        return max(1, min(12, int(v)))
    return defaut


def _hauteur(carte: dict[str, Any]) -> int | None:
    o = _options(carte)
    v = o.get("rows", o.get("grid_rows"))
    if isinstance(v, (int, float)):
        return max(1, min(3, int(v)))
    return None


def _entites_de(liste: Any) -> list[dict[str, Any]]:
    sortie = []
    for e in liste or []:
        if isinstance(e, str):
            sortie.append({"entite": e})
        elif isinstance(e, dict) and e.get("entity"):
            nom = e.get("name")
            sortie.append({"entite": str(e["entity"]), "libelle": str(nom) if isinstance(nom, str) else ""})
    return sortie


def _feuille(carte: dict[str, Any], largeur: int | None) -> dict[str, Any] | None:
    """Une carte affichable : ses cases, son libellé pour le choix, sa clé stable."""
    genre = str(carte.get("type") or "")
    titre = carte.get("title") or carte.get("name") or carte.get("heading")
    titre = str(titre) if isinstance(titre, str) else ""
    cases: list[dict[str, Any]] = []
    if genre == "markdown":
        texte = str(carte.get("content") or "").strip()
        if texte:
            cases = [{"texte": texte, "libelle": titre or "Note", "largeur": largeur or _largeur(carte, 12), "hauteur": _hauteur(carte) or 2}]
    elif genre in ("history-graph", "statistics-graph"):
        ents = _entites_de(carte.get("entities"))
        for c in ents:
            c.update(rendu="courbe", largeur=largeur or (12 if len(ents) == 1 else 6), hauteur=2)
        cases = ents
    elif isinstance(carte.get("entities"), list):
        ents = _entites_de(carte["entities"])
        for c in ents:
            c.update(largeur=largeur or 6, hauteur=1)
        cases = ents
    elif isinstance(carte.get("entity"), str) and carte["entity"]:
        case: dict[str, Any] = {
            "entite": carte["entity"],
            "libelle": str(carte["name"]) if isinstance(carte.get("name"), str) else "",
            "largeur": largeur or _largeur(carte, 12 if genre in ("thermostat", "weather-forecast", "humidifier", "media-control") else 6),
            "hauteur": _hauteur(carte),
        }
        if genre == "gauge":
            case["rendu"] = "jauge"
            for cle in ("min", "max"):
                if isinstance(carte.get(cle), (int, float)):
                    case[cle] = float(carte[cle])
        elif genre == "sensor":
            case["rendu"] = "courbe" if carte.get("graph") == "line" else "valeur"
        cases = [case]
    identite = "|".join([
        genre,
        str(carte.get("entity") or ""),
        ",".join(c.get("entite", "") for c in cases)[:200],
        titre,
        str(carte.get("content") or "")[:40],
    ])
    return {
        "cle": hashlib.sha1(identite.encode("utf-8")).hexdigest()[:10],
        "type": genre or "carte",
        "titre": titre,
        "cases": cases,
    }


def _feuilles(carte: Any, largeur: int | None = None) -> list[dict[str, Any]]:
    """Toutes les cartes affichables sous une carte (on descend dans les contenants)."""
    if not isinstance(carte, dict):
        return []
    genre = str(carte.get("type") or "")
    if genre == "heading":
        return []
    if isinstance(carte.get("cards"), list):
        enfants = carte["cards"]
        part = largeur
        if genre == "horizontal-stack" and enfants:
            part = max(3, (largeur or 12) // len(enfants))
        elif genre == "grid" and enfants:
            n = carte.get("columns") if isinstance(carte.get("columns"), int) else 3
            part = max(3, (largeur or 12) // max(1, n))
        return [f for sous in enfants for f in _feuilles(sous, part)]
    if isinstance(carte.get("card"), dict):
        return _feuilles(carte["card"], largeur)
    f = _feuille(carte, largeur)
    return [f] if f else []


def _sections(vue: dict[str, Any]) -> list[dict[str, Any]]:
    """Les sections d'une vue : un titre et des cartes affichables, dans l'ordre de la vue."""
    sortie: list[dict[str, Any]] = []
    for section in vue.get("sections") or []:
        if not isinstance(section, dict):
            continue
        courante = {"titre": str(section.get("title") or ""), "cartes": []}
        for carte in section.get("cards") or []:
            if isinstance(carte, dict) and carte.get("type") == "heading":
                if courante["cartes"]:
                    sortie.append(courante)
                courante = {"titre": str(carte.get("heading") or ""), "cartes": []}
                continue
            courante["cartes"].extend(_feuilles(carte))
        if courante["cartes"]:
            sortie.append(courante)
    # Vues sans sections (mosaïque, panneau) : chaque carte titrée ou chaque pile fait une section.
    libre = {"titre": "", "cartes": []}
    for carte in vue.get("cards") or []:
        if not isinstance(carte, dict):
            continue
        feuilles = _feuilles(carte)
        if not feuilles:
            continue
        titre = carte.get("title")
        if isinstance(titre, str) and titre or isinstance(carte.get("cards"), list):
            if libre["cartes"]:
                sortie.append(libre)
                libre = {"titre": "", "cartes": []}
            sortie.append({"titre": str(titre) if isinstance(titre, str) else "", "cartes": feuilles})
        else:
            libre["cartes"].extend(feuilles)
    if libre["cartes"]:
        sortie.append(libre)
    # Deux cartes identiques dans la même vue : la seconde reçoit une clé distincte.
    vues: dict[str, int] = {}
    for s in sortie:
        for f in s["cartes"]:
            n = vues.get(f["cle"], 0) + 1
            vues[f["cle"]] = n
            if n > 1:
                f["cle"] = "{}-{}".format(f["cle"], n)
    return sortie


def _cle_vue(vue: dict[str, Any], rang: int) -> str:
    return str(vue.get("path") or "v{}".format(rang))


# --- Le choix fait dans Vision ----------------------------------------------------------


def _choix(coord, adresse: str) -> dict[str, Any]:
    brut = (getattr(coord.store, "veille_dash", None) or {}).get(adresse) or {}
    try:
        duree = max(5, min(120, int(brut.get("duree") or 25)))
    except (TypeError, ValueError):
        duree = 25
    ecrans = [e for e in (brut.get("ecrans") or ECRANS) if e in ECRANS] or list(ECRANS)
    publics = [p for p in (brut.get("publics") or PUBLICS) if p in PUBLICS] or list(PUBLICS)
    return {
        "actif": bool(brut.get("actif")),
        "duree": duree,
        "ecrans": ecrans,
        "publics": publics,
        "personnes": [],
        "vues": {str(k): bool(v) for k, v in (brut.get("vues") or {}).items()},
        "cartes": {str(k): bool(v) for k, v in (brut.get("cartes") or {}).items()},
    }


def enregistrer(coord, choix: Any) -> None:
    """Enregistre le choix (on ne garde que ce qui s'écarte du défaut : masqué)."""
    propre: dict[str, Any] = {}
    if isinstance(choix, dict):
        for adresse, c in list(choix.items())[:40]:
            if not isinstance(c, dict):
                continue
            propre[str(adresse)[:80]] = {
                "actif": bool(c.get("actif")),
                "duree": c.get("duree"),
                "ecrans": [e for e in (c.get("ecrans") or []) if e in ECRANS],
                "publics": [p for p in (c.get("publics") or []) if p in PUBLICS],
                "vues": {str(k)[:80]: False for k, v in (c.get("vues") or {}).items() if v is False},
                "cartes": {str(k)[:120]: False for k, v in (c.get("cartes") or {}).items() if v is False},
            }
    coord.store.veille_dash = propre
    _cache.clear()


async def inventaire(hass: HomeAssistant, coord) -> list[dict[str, Any]]:
    """Tous les tableaux de bord, leurs vues et leurs cartes, avec le choix en cours (pour l'écran de réglage)."""
    sortie = []
    for adresse, tableau in _lovelace(hass).items():
        cle = "lovelace" if adresse is None else str(adresse)
        choix = _choix(coord, cle)
        config = await _config(hass, cle)
        vues = []
        for rang, vue in enumerate((config or {}).get("views") or []):
            if not isinstance(vue, dict):
                continue
            cv = _cle_vue(vue, rang)
            cartes = []
            for s in _sections(vue):
                for f in s["cartes"]:
                    premier = (f["cases"][0].get("entite") if f["cases"] else "") or ""
                    etat = hass.states.get(premier) if premier else None
                    libelle = f["titre"] or (str(etat.attributes.get("friendly_name") or premier) if etat else premier) or f["type"]
                    cartes.append({
                        "cle": f["cle"], "type": f["type"], "libelle": libelle, "section": s["titre"],
                        "comprise": bool(f["cases"]), "cases": len(f["cases"]),
                        "actif": choix["cartes"].get("{}/{}".format(cv, f["cle"]), True),
                    })
            vues.append({
                "cle": cv, "titre": str(vue.get("title") or "Vue {}".format(rang + 1)),
                "actif": choix["vues"].get(cv, True), "cartes": cartes,
            })
        sortie.append({
            "adresse": cle, "titre": _titre_tableau(adresse, tableau),
            "lisible": bool(vues), "genere": bool(config and config.get("strategy")),
            "actif": choix["actif"], "duree": choix["duree"], "ecrans": choix["ecrans"], "publics": choix["publics"],
            "vues": vues,
        })
    sortie.sort(key=lambda t: t["titre"].lower())
    return sortie


async def tableaux(hass: HomeAssistant, coord, ecran: str, qui: dict[str, str]) -> list[dict[str, Any]]:
    """Les tableaux de veille tirés des tableaux de bord retenus, résolus pour cet appareil."""
    from . import veille_tableaux as vt

    sortie: list[dict[str, Any]] = []
    for adresse in list((getattr(coord.store, "veille_dash", None) or {}).keys()):
        choix = _choix(coord, adresse)
        if not choix["actif"] or not vt._vise(choix, ecran, qui):
            continue
        config = await _config(hass, adresse)
        vues = [v for v in (config or {}).get("views") or [] if isinstance(v, dict)]
        tableau = _lovelace(hass).get(None if adresse == "lovelace" else adresse)
        nom = _titre_tableau(None if adresse == "lovelace" else adresse, tableau)
        for rang, vue in enumerate(vues):
            cv = _cle_vue(vue, rang)
            if not choix["vues"].get(cv, True) or len(sortie) >= MAX_TABLEAUX:
                continue
            sections = []
            total = 0
            for s in _sections(vue):
                cases = []
                for f in s["cartes"]:
                    if not choix["cartes"].get("{}/{}".format(cv, f["cle"]), True):
                        continue
                    for c in f["cases"]:
                        if total >= MAX_CASES:
                            break
                        if not c.get("entite"):
                            r = {"entite": "", "nom": c.get("libelle") or "Note", "rendu": "texte", "texte": await _texte(hass, str(c.get("texte") or ""))}
                        else:
                            r = await vt._case(hass, c)
                            if r.get("absent"):
                                continue
                            if r.get("rendu") == "jauge":
                                for borne in ("min", "max"):
                                    if borne in c:
                                        r[borne] = c[borne]
                        r["largeur"] = int(c.get("largeur") or 6)
                        r["hauteur"] = int(c.get("hauteur") or (2 if r.get("rendu") in ("jauge", "courbe") else 1))
                        cases.append(r)
                        total += 1
                if cases:
                    sections.append({"titre": s["titre"], "cases": cases})
            if not sections:
                continue
            titre_vue = str(vue.get("title") or "")
            sortie.append({
                "code": "dash",
                "id": "dash_{}_{}".format(adresse, cv),
                "titre": titre_vue if titre_vue and len(vues) > 1 else nom,
                "duree": choix["duree"],
                "colonnes": int(vue.get("max_columns") or 3) if isinstance(vue.get("max_columns"), int) else 3,
                "sections": sections,
            })
    return sortie


async def _texte(hass: HomeAssistant, texte: str) -> str:
    try:
        if "{{" in texte or "{%" in texte:
            from homeassistant.helpers.template import Template
            texte = str(Template(texte, hass).async_render(parse_result=False))
    except Exception:  # noqa: BLE001
        pass
    for marque in ("**", "__", "`", "#"):
        texte = texte.replace(marque, "")
    return " ".join(texte.split())[:200]


# --- L'écran de réglage (administrateurs) -----------------------------------------------


class PcParentalVeilleDashView(HomeAssistantView):
    """Choisir les tableaux de bord, les vues et les cartes montrés sur l'écran de veille."""

    url = "/api/pc_parental/veille/dashboards"
    name = "api:pc_parental:veille_dashboards"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    def _coord(self):
        from .const import DOMAIN
        entrees = list(self.hass.data.get(DOMAIN, {}).values())
        return entrees[0] if entrees else None

    def _refus(self, request: web.Request) -> web.Response | None:
        utilisateur = request.get("hass_user")
        if utilisateur is None or not utilisateur.is_admin:
            return self.json({"ok": False, "error": "admin"}, status_code=403)
        return None

    async def get(self, request: web.Request) -> web.Response:
        if refus := self._refus(request):
            return refus
        coord = self._coord()
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        return self.json({"ok": True, "tableaux": await inventaire(self.hass, coord)})

    async def post(self, request: web.Request) -> web.Response:
        if refus := self._refus(request):
            return refus
        try:
            corps: dict[str, Any] = await request.json()
        except ValueError:
            return self.json({"ok": False, "error": "json"}, status_code=400)
        coord = self._coord()
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        from .entity import appliquer

        try:
            await appliquer(coord, lambda: enregistrer(coord, corps.get("choix")))
        except Exception as err:  # noqa: BLE001
            return self.json({"ok": False, "error": str(err)}, status_code=400)
        return self.json({"ok": True, "tableaux": await inventaire(self.hass, coord)})
