"""Résultats eSport pour l'écran de veille : Valorant (VCT) et Rocket League (RLCS).

Les sources sont publiques et sans clé : la page de résultats de vlr.gg pour
Valorant (les logos viennent de la page de chaque match, lue une seule fois),
l'API ouverte d'octane.gg pour Rocket League. Home Assistant rafraîchit au
plus toutes les dix minutes, et seulement quand un écran de veille le demande ;
la télé ne parle qu'à Home Assistant, qui lui relaie aussi les logos.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
import time
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AGENT = "Vision-HomeAssistant/1.0 (ecran de veille familial ; https://github.com/jacquesantoineroy-hash)"
RAFRAICHISSEMENT = 600
PAR_JEU = 8
LOGOS_HOTES = ("owcdn.net", "griffon.octane.gg")
VLR_RESULTATS = "https://www.vlr.gg/matches/results"
VLR_FILTRE = ("champions tour", "valorant champions", "masters")
OCTANE = "https://zsr.octane.gg/matches"

_BLOC = re.compile(r'<a href="/(\d+)/[^"]*" class="wf-module-item match-item[^"]*">(.*?)</a>', re.S)
_EQUIPE = re.compile(
    r'<div class="match-item-vs-team\s*(mod-winner)?\s*">.*?<div class="text-of">\s*(?:<span class="flag mod-(\w+)"></span>)?\s*(.*?)\s*</div>.*?'
    r'<div class="match-item-vs-team-score[^"]*">\s*(\S*)\s*</div>',
    re.S,
)
_SERIE = re.compile(r'<div class="match-item-event-series text-of">\s*(.*?)\s*</div>', re.S)
_EVENEMENT = re.compile(r'<div class="match-item-event text-of">.*?</div>\s*(.*?)\s*</div>', re.S)
_ETA = re.compile(r'<div class="ml-eta[^"]*">\s*(.*?)\s*</div>', re.S)
_STATUT = re.compile(r'<div class="ml-status">\s*(.*?)\s*</div>', re.S)
_LOGO = re.compile(r'<img src="(//owcdn\.net/img/[^"]+)" alt="([^"]*) team logo">')
_UTC = re.compile(r'data-utc-ts="(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"')


def _propre(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _eta_en_secondes(texte: str) -> int:
    """« 10h 16m », « 3d 2h », « 45m » → secondes écoulées depuis la fin."""
    total = 0
    for nombre, unite in re.findall(r"(\d+)\s*([wdhm])", texte):
        total += int(nombre) * {"w": 604800, "d": 86400, "h": 3600, "m": 60}[unite]
    return total


class Esports:
    """Le cache des résultats, un par installation."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.store = Store[dict[str, Any]](hass, 1, f"{DOMAIN}_esports")
        self.matchs_vlr: dict[str, dict[str, Any]] = {}  # id → {l1, l2, ts}
        self.resultats: list[dict[str, Any]] = []
        self.quand = 0.0
        self.en_cours: asyncio.Task | None = None
        self.charge = False
        self.dossier = hass.config.path(".storage", f"{DOMAIN}_logos")

    async def _charger(self) -> None:
        if self.charge:
            return
        self.charge = True
        data = await self.store.async_load() or {}
        self.matchs_vlr = dict(data.get("vlr") or {})
        self.resultats = list(data.get("resultats") or [])

    async def _sauver(self) -> None:
        # On ne garde que les matchs récents : la page de résultats ne remonte pas loin.
        if len(self.matchs_vlr) > 400:
            garde = sorted(self.matchs_vlr.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True)[:300]
            self.matchs_vlr = dict(garde)
        await self.store.async_save({"vlr": self.matchs_vlr, "resultats": self.resultats})

    def demander(self) -> list[dict[str, Any]]:
        """Les résultats connus, tout de suite ; un rafraîchissement part en fond s'il est temps."""
        if time.time() - self.quand > RAFRAICHISSEMENT and (self.en_cours is None or self.en_cours.done()):
            self.en_cours = self.hass.async_create_background_task(self._rafraichir(), f"{DOMAIN}_esports")
        return self.resultats

    async def _rafraichir(self) -> None:
        await self._charger()
        self.quand = time.time()
        sorties: list[dict[str, Any]] = []
        for nom, fonction in (("Valorant", self._valorant), ("Rocket League", self._rocket_league)):
            try:
                resultats = await fonction()
            except Exception as err:  # noqa: BLE001 - une source en panne ne vide pas l'écran
                _LOGGER.debug("eSport %s : %s", nom, err)
                resultats = next((j["resultats"] for j in self.resultats if j["jeu"] == nom), [])
            if resultats:
                sorties.append({"jeu": nom, "resultats": resultats[:PAR_JEU]})
        self.resultats = sorties
        await self._sauver()

    async def _texte(self, url: str, delai: int = 20) -> str:
        async with asyncio.timeout(delai):
            async with self.session.get(url, headers={"User-Agent": AGENT}) as rep:
                rep.raise_for_status()
                return await rep.text()

    async def _json(self, url: str, delai: int = 20) -> Any:
        async with asyncio.timeout(delai):
            async with self.session.get(url, headers={"User-Agent": AGENT}) as rep:
                rep.raise_for_status()
                return await rep.json(content_type=None)

    # --- Valorant --------------------------------------------------------------

    async def _valorant(self) -> list[dict[str, Any]]:
        page = await self._texte(VLR_RESULTATS)
        maintenant = time.time()
        sortie: list[dict[str, Any]] = []
        nouveaux = 0
        for ident, bloc in _BLOC.findall(page):
            if len(sortie) >= PAR_JEU:
                break
            statut = _STATUT.search(bloc)
            if not statut or _propre(statut.group(1)).lower() != "completed":
                continue
            evenement = _EVENEMENT.search(bloc)
            nom_evenement = _propre(evenement.group(1)) if evenement else ""
            if not any(mot in nom_evenement.lower() for mot in VLR_FILTRE):
                continue
            equipes = _EQUIPE.findall(bloc)
            if len(equipes) != 2:
                continue
            serie = _SERIE.search(bloc)
            eta = _ETA.search(bloc)
            ts = int(maintenant - _eta_en_secondes(eta.group(1))) if eta else int(maintenant)
            detail = self.matchs_vlr.get(ident)
            if detail is None and nouveaux < 4:
                nouveaux += 1
                detail = await self._detail_vlr(ident, [_propre(e[2]) for e in equipes])
                self.matchs_vlr[ident] = detail
                await asyncio.sleep(1.5)  # un visiteur poli
            detail = detail or {}

            def score(s: str) -> int | None:
                return int(s) if s.isdigit() else None

            sortie.append(
                {
                    "id": f"vlr{ident}",
                    "e1": _propre(equipes[0][2]),
                    "e2": _propre(equipes[1][2]),
                    "p1": equipes[0][1],
                    "p2": equipes[1][1],
                    "s1": score(equipes[0][3]),
                    "s2": score(equipes[1][3]),
                    "v": 1 if equipes[0][0] else 2 if equipes[1][0] else 0,
                    "l1": detail.get("l1", ""),
                    "l2": detail.get("l2", ""),
                    "evenement": nom_evenement,
                    "serie": _propre(serie.group(1)) if serie else "",
                    "ts": int(detail.get("ts") or ts),
                }
            )
        return sortie

    async def _detail_vlr(self, ident: str, noms: list[str]) -> dict[str, Any]:
        """Les logos et l'heure exacte, sur la page du match."""
        try:
            page = await self._texte(f"https://www.vlr.gg/{ident}/")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("vlr %s : %s", ident, err)
            return {"l1": "", "l2": "", "ts": 0}
        logos: dict[str, str] = {}
        for url, nom in _LOGO.findall(page):
            logos.setdefault(_propre(nom), "https:" + url)
        utc = _UTC.search(page)
        ts = 0
        if utc:
            try:
                ts = int(dt_util.as_timestamp(dt_util.parse_datetime(utc.group(1).replace(" ", "T") + "+00:00")))
            except Exception:  # noqa: BLE001
                ts = 0
        trouves = list(logos.values())
        return {
            "l1": logos.get(noms[0], trouves[0] if len(trouves) > 0 else ""),
            "l2": logos.get(noms[1], trouves[1] if len(trouves) > 1 else ""),
            "ts": ts,
        }

    # --- Rocket League -----------------------------------------------------------

    async def _rocket_league(self) -> list[dict[str, Any]]:
        avant = dt_util.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        data = await self._json(f"{OCTANE}?tier=S&before={avant}&sort=date:desc&perPage=20")
        sortie: list[dict[str, Any]] = []
        for m in data.get("matches") or []:
            bleu = m.get("blue") or {}
            orange = m.get("orange") or {}
            if "score" not in bleu and "score" not in orange:
                continue  # pas encore joué
            eb = (bleu.get("team") or {}).get("team") or {}
            eo = (orange.get("team") or {}).get("team") or {}
            if not eb.get("name") or not eo.get("name"):
                continue
            try:
                ts = int(dt_util.as_timestamp(dt_util.parse_datetime(m.get("date"))))
            except Exception:  # noqa: BLE001
                ts = int(time.time())
            sortie.append(
                {
                    "id": f"rl{m.get('_id')}",
                    "e1": eb.get("name"),
                    "e2": eo.get("name"),
                    "p1": "",
                    "p2": "",
                    "s1": bleu.get("score", 0),
                    "s2": orange.get("score", 0),
                    "v": 1 if bleu.get("winner") else 2 if orange.get("winner") else 0,
                    "l1": eb.get("image") or "",
                    "l2": eo.get("image") or "",
                    "evenement": (m.get("event") or {}).get("name", ""),
                    "serie": (m.get("stage") or {}).get("name", ""),
                    "ts": ts,
                }
            )
            if len(sortie) >= PAR_JEU:
                break
        return sortie

    # --- Logos -------------------------------------------------------------------

    async def logo(self, url: str) -> tuple[bytes, str] | None:
        """Le logo d'une équipe, mis en cache sur disque ; seuls les hôtes connus passent."""
        if not url.startswith("https://") or url.split("/")[2] not in LOGOS_HOTES:
            return None
        cle = hashlib.sha1(url.encode()).hexdigest()
        chemin = os.path.join(self.dossier, cle)

        def _lire() -> tuple[bytes, str] | None:
            if not os.path.exists(chemin):
                return None
            with open(chemin, "rb") as f:
                return f.read(), open(chemin + ".type", encoding="utf-8").read() if os.path.exists(chemin + ".type") else "image/png"

        connu = await self.hass.async_add_executor_job(_lire)
        if connu:
            return connu
        try:
            async with asyncio.timeout(15):
                async with self.session.get(url, headers={"User-Agent": AGENT}) as rep:
                    rep.raise_for_status()
                    octets = await rep.read()
                    genre = rep.headers.get("Content-Type", "image/png").split(";")[0]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("logo %s : %s", url, err)
            return None
        if len(octets) > 2_000_000:
            return None

        def _ecrire() -> None:
            os.makedirs(self.dossier, exist_ok=True)
            with open(chemin, "wb") as f:
                f.write(octets)
            with open(chemin + ".type", "w", encoding="utf-8") as f:
                f.write(genre)

        await self.hass.async_add_executor_job(_ecrire)
        return octets, genre


def esports(hass: HomeAssistant) -> Esports:
    cle = f"{DOMAIN}_esports"
    if cle not in hass.data:
        hass.data[cle] = Esports(hass)
    return hass.data[cle]


class PcParentalVeilleLogoView(HomeAssistantView):
    """Un logo d'équipe pour l'écran de veille, relayé et mis en cache par Home Assistant."""

    url = "/api/pc_parental/veille/logo"
    name = "api:pc_parental:veille_logo"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        try:
            corps: dict[str, Any] = await request.json()
        except ValueError:
            return self.json({"ok": False, "error": "json"}, status_code=400)
        entrees = list(self.hass.data.get(DOMAIN, {}).values())
        coord = entrees[0] if entrees else None
        if coord is None:
            return self.json({"ok": False, "error": "loading"}, status_code=503)
        if coord.store.by_secret(str(corps.get("id") or ""), str(corps.get("secret") or "")) is None:
            return self.json({"ok": False, "error": "auth"}, status_code=401)
        trouve = await esports(self.hass).logo(str(corps.get("url") or ""))
        if trouve is None:
            return self.json({"ok": False, "error": "logo"}, status_code=404)
        octets, genre = trouve
        return web.Response(body=octets, content_type=genre, headers={"Cache-Control": "max-age=86400"})
