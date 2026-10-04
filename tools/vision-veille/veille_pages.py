"""Pages de l'écran de veille composées avec des cartes Home Assistant.

Un tableau de bord ordinaire, « Écran de veille » (adresse `vision-veille`),
s'édite avec l'éditeur de Home Assistant : on y glisse des cartes, on les
déplace, on ajoute des vues. Chaque **vue** devient une page de l'écran de
veille ; chaque **carte** devient une case (valeur, jauge, courbe, état ou
texte), dans l'ordre de la vue. Huit cases par page : au-delà, la vue se
poursuit sur une page suivante.

Cartes comprises : tuile, entité, capteur (avec ou sans courbe), jauge,
entités, aperçu (glance), graphique d'historique ou de statistiques,
thermostat, lumière, bouton, météo, markdown (texte), et les piles / grilles
qui les contiennent. Toute autre carte qui porte `entity` ou `entities` est
lue de la même façon ; le reste est ignoré.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

ADRESSE = "vision-veille"
CASES_PAR_PAGE = 8
DUREE = 22
MAX_PAGES = 24

_cache: dict[str, Any] = {"t": 0.0, "v": []}


async def _config(hass: HomeAssistant) -> dict[str, Any] | None:
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None
    tableaux = getattr(lovelace, "dashboards", None)
    if tableaux is None and isinstance(lovelace, dict):
        tableaux = lovelace.get("dashboards")
    tableau = (tableaux or {}).get(ADRESSE)
    if tableau is None:
        return None
    try:
        return await tableau.async_load(False)
    except Exception:  # noqa: BLE001  (tableau encore vide, ou illisible)
        return None


def _entites_de(liste: Any) -> list[dict[str, Any]]:
    sortie = []
    for e in liste or []:
        if isinstance(e, str):
            sortie.append({"entite": e})
        elif isinstance(e, dict) and e.get("entity"):
            sortie.append({"entite": str(e["entity"]), "libelle": str(e.get("name") or "")})
    return sortie


def _cases_de(carte: Any) -> list[dict[str, Any]]:
    """Les cases qu'une carte Home Assistant donne à l'écran de veille."""
    if not isinstance(carte, dict):
        return []
    genre = str(carte.get("type") or "")
    # Les contenants : on descend.
    if isinstance(carte.get("cards"), list):
        return [c for sous in carte["cards"] for c in _cases_de(sous)]
    if isinstance(carte.get("card"), dict):
        return _cases_de(carte["card"])
    if genre == "heading":
        return []
    if genre == "markdown":
        texte = str(carte.get("content") or "").strip()
        return [{"texte": texte, "libelle": str(carte.get("title") or "Note")}] if texte else []
    if genre in ("history-graph", "statistics-graph"):
        return [dict(c, rendu="courbe") for c in _entites_de(carte.get("entities"))]
    if isinstance(carte.get("entities"), list):
        return _entites_de(carte["entities"])
    entite = carte.get("entity")
    if not entite or not isinstance(entite, str):
        return []
    nom = carte.get("name")
    case: dict[str, Any] = {"entite": entite, "libelle": str(nom) if isinstance(nom, str) else ""}
    if genre == "gauge":
        case["rendu"] = "jauge"
        for cle in ("min", "max"):
            if isinstance(carte.get(cle), (int, float)):
                case[cle] = float(carte[cle])
    elif genre == "sensor":
        case["rendu"] = "courbe" if carte.get("graph") == "line" else "valeur"
    return [case]


async def pages(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Les pages décrites par le tableau de bord, prêtes à être résolues."""
    if time.time() - float(_cache["t"]) < 20:
        return list(_cache["v"])
    sortie: list[dict[str, Any]] = []
    try:
        config = await _config(hass)
        for n, vue in enumerate((config or {}).get("views") or []):
            if not isinstance(vue, dict):
                continue
            cartes = list(vue.get("cards") or [])
            for section in vue.get("sections") or []:
                if isinstance(section, dict):
                    cartes.extend(section.get("cards") or [])
            cases = [c for carte in cartes for c in _cases_de(carte)]
            titre = str(vue.get("title") or "Page {}".format(n + 1))
            for k in range(0, len(cases), CASES_PAR_PAGE):
                if len(sortie) >= MAX_PAGES:
                    break
                sortie.append({
                    "id": "page{}_{}".format(n, k // CASES_PAR_PAGE),
                    "titre": titre,
                    "duree": DUREE,
                    "cases": cases[k:k + CASES_PAR_PAGE],
                })
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Lecture des pages de l'écran de veille")
        sortie = []
    _cache["t"] = time.time()
    _cache["v"] = sortie
    return list(sortie)


async def rendre_texte(hass: HomeAssistant, texte: str) -> str:
    """Un markdown peut contenir un gabarit : on le rend, puis on l'allège pour un écran de télé."""
    try:
        if "{{" in texte or "{%" in texte:
            from homeassistant.helpers.template import Template
            texte = str(Template(texte, hass).async_render(parse_result=False))
    except Exception:  # noqa: BLE001
        pass
    for marque in ("**", "__", "`", "#"):
        texte = texte.replace(marque, "")
    return " ".join(texte.split())[:160]
