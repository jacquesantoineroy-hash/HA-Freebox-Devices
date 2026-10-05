"""L'écran de veille montre les vraies cartes de Home Assistant.

On crée son tableau de bord dans Home Assistant, on le rend disponible dans
Vision, et chaque appareil l'affiche tel quel, dans son propre thème : la page
`/vision-veille` (un panneau de Vision) dessine les cartes avec le moteur de
Home Assistant lui-même. L'appareil n'a rien à redessiner.

- `POST /api/pc_parental/veille/acces` (identifiant et secret de l'appareil) :
  le jeton d'un utilisateur réservé à l'affichage, sans droits d'administration
  et limité au réseau de la maison.
- `GET /api/pc_parental/veille/entree` : la porte d'entrée. Le jeton arrive dans
  le fragment de l'adresse (jamais envoyé au serveur), elle le range dans le
  navigateur puis ouvre le panneau.
- `GET /api/pc_parental/veille/page` : les tableaux rendus disponibles pour cet
  appareil, avec la configuration d'origine de chaque carte.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from . import veille_dash

_LOGGER = logging.getLogger(__name__)

NOM_UTILISATEUR = "Vision affichage"
PANNEAU = "vision-veille"
MODULE = "/local/vision-veille-panel.js?v=1"
MAX_TABLEAUX = 16

ENTREE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Vision</title>
<style>html,body{margin:0;height:100%;background:#000}</style></head><body><script>
(function(){
  var p=new URLSearchParams(location.hash.slice(1)),t=p.get('t'),q=p.get('q')||'';
  try{
    if(t){localStorage.setItem('hassTokens',JSON.stringify({access_token:t,token_type:'Bearer',expires_in:283824000,
      hassUrl:location.origin,clientId:location.origin+'/',expires:Date.now()+283824000000,refresh_token:''}));}
    localStorage.setItem('dockedSidebar','"always_hidden"');
    localStorage.setItem('selectedLanguage','"fr"');
  }catch(e){}
  var c=new URLSearchParams(q).get('fond');if(c){document.body.style.background='#'+c;}
  location.replace('/vision-veille?'+q);
})();
</script></body></html>"""


def _coord(hass: HomeAssistant):
    from .const import DOMAIN

    entrees = list(hass.data.get(DOMAIN, {}).values())
    return entrees[0] if entrees else None


async def _jeton(hass: HomeAssistant) -> str:
    """Le jeton de l'utilisateur d'affichage, créé à la première demande et gardé."""
    garde = hass.data.get("pc_parental_veille_jeton")
    if garde:
        return garde
    magasin = Store(hass, 1, "pc_parental.veille_acces")
    lu = await magasin.async_load() or {}
    utilisateur = None
    if lu.get("user_id"):
        utilisateur = await hass.auth.async_get_user(lu["user_id"])
    if utilisateur is not None and lu.get("jeton") and hass.auth.async_validate_access_token(lu["jeton"]) is not None:
        hass.data["pc_parental_veille_jeton"] = lu["jeton"]
        return lu["jeton"]
    if utilisateur is None:
        utilisateur = await hass.auth.async_create_user(NOM_UTILISATEUR, group_ids=["system-users"], local_only=True)
    from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN

    rafraichi = await hass.auth.async_create_refresh_token(
        utilisateur,
        client_name="Vision écran de veille {}".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S")),
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=datetime.timedelta(days=3650),
    )
    jeton = hass.auth.async_create_access_token(rafraichi)
    await magasin.async_save({"user_id": utilisateur.id, "jeton": jeton})
    hass.data["pc_parental_veille_jeton"] = jeton
    return jeton


def _cartes_de(vue: dict[str, Any]) -> list[dict[str, Any]]:
    """Les sections d'une vue et leurs cartes d'origine ; chaque carte garde les clés de ses
    éléments (celles que l'on coche dans Vision et sur l'appareil)."""
    sections: list[dict[str, Any]] = []

    vues_cles: dict[str, int] = {}

    def _carte(carte: Any) -> dict[str, Any] | None:
        if not isinstance(carte, dict) or not carte.get("type"):
            return None
        cles = [f["cle"] for f in veille_dash._feuilles(carte) if f.get("cases")]
        # Une clé par carte, pour la cocher sur l'appareil : stable tant que la carte ne change pas.
        import hashlib
        import json

        cle = hashlib.sha1(json.dumps(carte, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
        n = vues_cles.get(cle, 0) + 1
        vues_cles[cle] = n
        if n > 1:
            cle = "{}-{}".format(cle, n)
        return {"cle": cle, "cles": cles, "config": carte}

    for section in vue.get("sections") or []:
        if not isinstance(section, dict):
            continue
        cartes = [c for c in (_carte(x) for x in section.get("cards") or []) if c]
        if cartes:
            sections.append({"titre": str(section.get("title") or ""), "cartes": cartes})
    libres = [c for c in (_carte(x) for x in vue.get("cards") or []) if c]
    if libres:
        sections.extend({"titre": "", "cartes": [c]} for c in libres)
    return sections


async def page(hass: HomeAssistant, coord, pc: dict[str, Any] | None, ecran: str) -> dict[str, Any]:
    from . import veille_tableaux as vt

    ecran = ecran if ecran in veille_dash.ECRANS else "tele"
    qui = vt.profil(hass, coord, pc)
    tableaux: list[dict[str, Any]] = []
    for adresse in list((getattr(coord.store, "veille_dash", None) or {}).keys()):
        choix = veille_dash._choix(coord, adresse)
        if not choix["actif"] or not vt._vise(choix, ecran, qui):
            continue
        config = await veille_dash._config(hass, adresse)
        vues = [v for v in (config or {}).get("views") or [] if isinstance(v, dict)]
        tableau = veille_dash._lovelace(hass).get(None if adresse == "lovelace" else adresse)
        nom = veille_dash._titre_tableau(None if adresse == "lovelace" else adresse, tableau)
        for rang, vue in enumerate(vues):
            cv = veille_dash._cle_vue(vue, rang)
            if not choix["vues"].get(cv, True) or len(tableaux) >= MAX_TABLEAUX:
                continue
            sections = []
            for s in _cartes_de(vue):
                gardees = []
                for c in s["cartes"]:
                    # Masquée dans Vision seulement si tous ses éléments le sont.
                    if c["cles"] and all(not choix["cartes"].get("{}/{}".format(cv, k), True) for k in c["cles"]):
                        continue
                    gardees.append(c)
                if gardees:
                    sections.append({"titre": s["titre"], "cartes": gardees})
            if not sections:
                continue
            titre_vue = str(vue.get("title") or "")
            tableaux.append({
                "id": "dash_{}_{}".format(adresse, cv),
                "titre": titre_vue if titre_vue and len(vues) > 1 else nom,
                "duree": choix["duree"],
                "colonnes": vue.get("max_columns") if isinstance(vue.get("max_columns"), int) else 3,
                "sections": sections,
            })
    horloge = next((t for t in vt.configuration(coord) if t["code"] == "horloge"), None)
    meteo = next((e.entity_id for e in hass.states.async_all("weather")), "")
    return {
        "ok": True,
        "horloge": {"actif": bool(horloge and horloge["actif"]), "duree": int((horloge or {}).get("duree") or 15)},
        "meteo": meteo,
        "tableaux": tableaux,
    }


def _nom_carte(hass: HomeAssistant, carte: dict[str, Any]) -> str:
    for champ in ("title", "name", "primary", "heading"):
        v = carte.get(champ)
        if isinstance(v, str) and v.strip() and "{{" not in v:
            return v.strip()[:60]
    eid = carte.get("entity")
    if not isinstance(eid, str):
        ents = carte.get("entities") or carte.get("include") or []
        premier = ents[0] if isinstance(ents, list) and ents else None
        eid = premier if isinstance(premier, str) else (premier or {}).get("entity") if isinstance(premier, dict) else None
    if isinstance(eid, str) and eid:
        etat = hass.states.get(eid)
        if etat is not None:
            return str(etat.attributes.get("friendly_name") or eid)[:60]
    genre = str(carte.get("type") or "carte").replace("custom:", "").replace("-card", "").replace("-", " ")
    return genre.capitalize()[:60]


def legere(hass: HomeAssistant, complet: dict[str, Any]) -> list[dict[str, Any]]:
    """Pour les réglages de l'appareil : les tableaux disponibles et leurs cartes, par nom (sans configuration)."""
    sortie = []
    for t in complet.get("tableaux") or []:
        cartes = []
        for s in t["sections"]:
            section = s["titre"]
            for c in s["cartes"]:
                config = c["config"]
                if config.get("type") == "heading":
                    section = str(config.get("heading") or section)
                    continue
                cartes.append({"cle": c["cle"], "nom": _nom_carte(hass, config), "section": section})
        sortie.append({"id": t["id"], "titre": t["titre"], "cartes": cartes})
    return sortie


class PcParentalVeilleAccesView(HomeAssistantView):
    url = "/api/pc_parental/veille/acces"
    name = "api:pc_parental:veille_acces"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        try:
            corps: dict[str, Any] = await request.json()
        except ValueError:
            return self.json({"ok": False, "error": "json"}, status_code=400)
        coord = _coord(self.hass)
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        pc = coord.store.by_secret(str(corps.get("id") or ""), str(corps.get("secret") or ""))
        if pc is None:
            return self.json({"ok": False, "error": "auth"}, status_code=401)
        try:
            tableaux = legere(self.hass, await page(self.hass, coord, pc, str(corps.get("ecran") or "tele")))
            return self.json({"ok": True, "jeton": await _jeton(self.hass), "tableaux": tableaux})
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Accès d'affichage de l'écran de veille")
            return self.json({"ok": False, "error": str(err)}, status_code=500)


class PcParentalVeilleEntreeView(HomeAssistantView):
    url = "/api/pc_parental/veille/entree"
    name = "api:pc_parental:veille_entree"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        return web.Response(text=ENTREE, content_type="text/html", headers={"Cache-Control": "no-store"})


class PcParentalVeillePageView(HomeAssistantView):
    url = "/api/pc_parental/veille/page"
    name = "api:pc_parental:veille_page"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        coord = _coord(self.hass)
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        pc = coord.store.get(str(request.query.get("id") or ""))
        return self.json(await page(self.hass, coord, pc, str(request.query.get("ecran") or "tele")))


def _module(hass: HomeAssistant) -> str:
    """L'adresse du panneau change à chaque nouvelle version du fichier : les navigateurs ne gardent pas l'ancienne."""
    import os

    try:
        return "/local/vision-veille-panel.js?v={}".format(int(os.path.getmtime(hass.config.path("www", "vision-veille-panel.js"))))
    except OSError:
        return MODULE


def installer(hass: HomeAssistant) -> None:
    hass.http.register_view(PcParentalVeilleAccesView(hass))
    hass.http.register_view(PcParentalVeilleEntreeView())
    hass.http.register_view(PcParentalVeillePageView(hass))
    try:
        from homeassistant.components import frontend

        if PANNEAU not in hass.data.get(frontend.DATA_PANELS, {}):
            frontend.async_register_built_in_panel(
                hass,
                component_name="custom",
                frontend_url_path=PANNEAU,
                config={"_panel_custom": {"name": "vision-veille-panel", "module_url": _module(hass), "embed_iframe": False, "trust_external": False}},
                require_admin=False,
            )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Panneau de l'écran de veille")
