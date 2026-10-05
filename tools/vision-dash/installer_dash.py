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
    source = depuis if depuis and os.path.exists(p + depuis) else (p + bak if os.path.exists(p + bak) else p)
    t = open(source, encoding="utf-8").read()
    if not os.path.exists(p + bak):
        shutil.copy2(p, p + bak)
    for a, b in remplacements:
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

# Les tableaux tirés des tableaux de bord s'ajoutent à ceux de Vision (l'ancien essai « pages » est retiré).
patch("veille_tableaux.py", [
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
], depuis=".bakpages")

patch("http.py", [
    ("    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n",
     "    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n"
     "    from .veille_dash import PcParentalVeilleDashView\n"
     "    hass.http.register_view(PcParentalVeilleDashView(hass))\n"),
])

patch("dashboard.py", [
    ("                    {\"type\": \"custom:vision-veille-card\", \"grid_options\": {\"columns\": \"full\"}},\n",
     "                    {\"type\": \"custom:vision-veille-card\", \"grid_options\": {\"columns\": \"full\"}},\n"
     "                    {\"type\": \"custom:vision-dashboards-card\", \"grid_options\": {\"columns\": \"full\"}},\n"),
])
print("ok dash")
