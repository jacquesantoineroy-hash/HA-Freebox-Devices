"""Installe « les tableaux de bord sur l'écran de veille » dans l'intégration pc_parental.
À lancer sur Home Assistant, depuis le dossier qui contient veille_dash.py et
vision-dashboards-card.js :  python3 installer_dash.py
Rejouable : chaque fichier modifié repart de sa sauvegarde `.bakdash`.
"""
import os
import py_compile
import shutil

ICI = os.path.dirname(os.path.abspath(__file__))
BASE = "/homeassistant/custom_components/pc_parental/"


def patch(nom, remplacements, bak=".bakdash", depuis=None):
    p = BASE + nom
    source = p + depuis if depuis and os.path.exists(p + depuis) else (p + bak if os.path.exists(p + bak) else p)
    t = open(source, encoding="utf-8").read()
    if not os.path.exists(p + bak):
        shutil.copy2(p, p + bak)
    for a, b in remplacements:
        if b in t:
            continue  # déjà fait
        assert a in t, (nom, a[:70])
        t = t.replace(a, b, 1)
    open(p, "w", encoding="utf-8").write(t)
    py_compile.compile(p, doraise=True)


shutil.copy2(os.path.join(ICI, "veille_dash.py"), BASE + "veille_dash.py")
py_compile.compile(BASE + "veille_dash.py", doraise=True)
os.makedirs("/homeassistant/www", exist_ok=True)
shutil.copy2(os.path.join(ICI, "vision-dashboards-card.js"), "/homeassistant/www/vision-dashboards-card.js")

# Le choix se range avec le reste des réglages de l'intégration.
patch("store.py", [
    ("        self.veille_tableaux: list[dict] = []\n",
     "        self.veille_tableaux: list[dict] = []\n        self.veille_dash: dict = {}\n"),
    ("        self.veille_tableaux = [t for t in (data.get(\"veille_tableaux\") or []) if isinstance(t, dict)]\n",
     "        self.veille_tableaux = [t for t in (data.get(\"veille_tableaux\") or []) if isinstance(t, dict)]\n"
     "        self.veille_dash = dict(data.get(\"veille_dash\") or {})\n"),
    ("                \"veille_tableaux\": self.veille_tableaux,\n",
     "                \"veille_tableaux\": self.veille_tableaux,\n                \"veille_dash\": self.veille_dash,\n"),
])

# Des anciens tableaux de Vision il ne reste que l'horloge ; le reste vient des tableaux de bord.
patch("veille_tableaux.py", [
    ("        if not t[\"actif\"] or not _vise(t, ecran, qui):\n            continue\n"
     "        if t[\"code\"] != \"entites\":\n",
     "        if t[\"code\"] != \"horloge\" or not t[\"actif\"] or not _vise(t, ecran, qui):\n            continue\n"
     "        if t[\"code\"] != \"entites\":\n"),
    ("        liste.append({\"code\": \"entites\", \"id\": t[\"id\"], \"titre\": t[\"titre\"], \"duree\": t[\"duree\"], \"cases\": cases})\n"
     "    return {\"profil\": qui[\"public\"], \"ecran\": ecran, \"liste\": liste}\n",
     "        liste.append({\"code\": \"entites\", \"id\": t[\"id\"], \"titre\": t[\"titre\"], \"duree\": t[\"duree\"], \"cases\": cases})\n"
     "    # Les tableaux de bord de Home Assistant retenus dans Vision.\n"
     "    try:\n"
     "        from . import veille_dash\n"
     "        liste.extend(await veille_dash.tableaux(hass, coord, ecran, qui))\n"
     "    except Exception:  # noqa: BLE001\n"
     "        import logging\n"
     "        logging.getLogger(__name__).exception(\"Tableaux de bord sur l'écran de veille\")\n"
     "    return {\"profil\": qui[\"public\"], \"ecran\": ecran, \"liste\": liste}\n"),
    ("            sortie.append(_nettoyer({\"code\": code, \"duree\": duree}))\n    return sortie\n",
     "            sortie.append(_nettoyer({\"code\": code, \"duree\": duree}))\n"
     "    # Des anciens tableaux il ne reste que l'horloge.\n"
     "    return [t for t in sortie if t and t[\"code\"] == \"horloge\"]\n"),
    ("async def resoudre_locaux(hass: HomeAssistant, locaux: Any) -> list[dict[str, Any]]:\n",
     "async def resoudre_locaux(hass: HomeAssistant, locaux: Any) -> list[dict[str, Any]]:\n"
     "    return []  # les tableaux composés sur l'appareil n'existent plus\n"),
], depuis=".bakpages")

patch("http.py", [
    ("    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n",
     "    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n"
     "    from .veille_dash import PcParentalVeilleDashView\n"
     "    hass.http.register_view(PcParentalVeilleDashView(hass))\n"),
])

# Les réglages de l'appareil listent aussi les tableaux de bord rendus disponibles, avec leurs cartes.
patch("veille_plus.py", [
    ("            \"actif\": t[\"actif\"], \"duree\": t[\"duree\"],\n        })\n    return sortie\n",
     "            \"actif\": t[\"actif\"], \"duree\": t[\"duree\"],\n        })\n"
     "    try:\n"
     "        from . import veille_dash\n"
     "        sortie.extend(veille_dash.legers(coord.hass, coord))\n"
     "    except Exception:  # noqa: BLE001\n"
     "        pass\n"
     "    return sortie\n"),
])

# Dans Vision > Écran de veille, la carte des tableaux de bord remplace l'ancien compositeur.
patch("dashboard.py", [
    # L'onglet « Écran de veille » est écrit par Vision : sans cela chaque régénération en gardait un double.
    ("CHEMINS = (\"maison\", \"pc\",", "CHEMINS = (\"maison\", \"veille\", \"pc\","),
    ("                    {\"type\": \"custom:vision-veille-card\", \"grid_options\": {\"columns\": \"full\"}},\n",
     "                    {\"type\": \"custom:vision-dashboards-card\", \"grid_options\": {\"columns\": \"full\"}},\n"),
    ("`/local/vision-veille-card.js` ", "`/local/vision-dashboards-card.js` "),
    # Thème, musique, radio, nuit : propres à chaque appareil, plus rien à régler ici.
    ("                    _titre(\"Ambiance\", \"mdi:palette-outline\"),\n", "                    _titre(\"Sur chaque appareil\", \"mdi:palette-outline\"),\n"),
    ("                    {\"type\": \"entities\", \"entities\": reglages, \"state_color\": True} if reglages else None,\n", "                    None,\n"),
    ("\"Le thème, la radio et le mode nuit se changent aussi depuis la télé \"", "\"Le thème, la musique ou la radio et le mode nuit se règlent sur chaque appareil \""),
    ("\"(Vision → Réglages). Les photos viennent de `/media/vision_photos`.\"", "\"(Vision → Réglages) : chaque télé, chaque téléphone a les siens. Ici, on choisit seulement les tableaux de bord et les cartes rendus disponibles.\""),
])
print("ok dash")
