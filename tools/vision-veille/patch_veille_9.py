"""Écran de veille : tableaux composés depuis Home Assistant, par écran et par public.
Usage : python3 patch_veille_9.py /dossier (contenant veille.py, veille_plus.py, veille_tableaux.py, vision-veille-card.js)
"""
import json
import os
import py_compile
import shutil
import sys

BASE = "/config/custom_components/pc_parental/"
if not os.path.isdir(BASE):
    BASE = "/homeassistant/custom_components/pc_parental/"
WWW = os.path.dirname(os.path.dirname(BASE.rstrip("/"))) + "/www/"
STORAGE = os.path.dirname(os.path.dirname(BASE.rstrip("/"))) + "/.storage/"
src = sys.argv[1].rstrip("/") + "/"
SUF = ".bakveille9b"


def lire(nom):
    return open(BASE + nom, encoding="utf-8").read()


def ecrire(nom, texte):
    shutil.copy2(BASE + nom, BASE + nom + SUF)
    open(BASE + nom, "w", encoding="utf-8").write(texte)
    py_compile.compile(BASE + nom, doraise=True)


def remplacer(texte, ancien, nouveau):
    assert ancien in texte, ancien[:70]
    return texte.replace(ancien, nouveau, 1)


# 1. Les modules de l'écran de veille.
for nom in ("veille.py", "veille_plus.py"):
    shutil.copy2(BASE + nom, BASE + nom + SUF)
    shutil.copy(src + nom, BASE + nom)
shutil.copy(src + "veille_tableaux.py", BASE + "veille_tableaux.py")
for nom in ("veille.py", "veille_plus.py", "veille_tableaux.py"):
    py_compile.compile(BASE + nom, doraise=True)

# 2. Le magasin : la liste des tableaux.
s = lire("store.py")
if "veille_tableaux" not in s:
    s = remplacer(
        s,
        '        self.veille_nuit: str = "23:00-07:00"\n',
        '        self.veille_nuit: str = "23:00-07:00"\n'
        "        # Les tableaux de l'écran de veille : ordre, durée, public, et les tableaux composés d'entités.\n"
        "        self.veille_tableaux: list[dict] = []\n",
    )
    s = remplacer(
        s,
        '        self.veille_nuit = str(data.get("veille_nuit") if data.get("veille_nuit") is not None else "23:00-07:00")\n',
        '        self.veille_nuit = str(data.get("veille_nuit") if data.get("veille_nuit") is not None else "23:00-07:00")\n'
        '        self.veille_tableaux = [t for t in (data.get("veille_tableaux") or []) if isinstance(t, dict)]\n',
    )
    s = remplacer(
        s,
        '                "veille_nuit": self.veille_nuit,\n',
        '                "veille_nuit": self.veille_nuit,\n'
        '                "veille_tableaux": self.veille_tableaux,\n',
    )
    ecrire("store.py", s)

# 3. La vue d'administration.
h = lire("http.py")
if "PcParentalVeilleTableauxView" not in h:
    h = remplacer(
        h,
        "from .veille_plus import PcParentalVeillePhotoView, PcParentalVeilleReglagesView\n",
        "from .veille_plus import PcParentalVeillePhotoView, PcParentalVeilleReglagesView\n"
        "from .veille_tableaux import PcParentalVeilleTableauxView\n",
    )
    h = remplacer(
        h,
        "    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n",
        "    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n"
        "    hass.http.register_view(PcParentalVeilleTableauxView(hass))\n",
    )
    ecrire("http.py", h)

# 4. L'onglet « Écran de veille » du tableau de bord Vision.
d = lire("dashboard.py")
if "_vue_veille" not in d:
    d = remplacer(
        d,
        "def _vue_statistiques(",
        '''def _vue_veille(hass: HomeAssistant, coord: PcParentalCoordinator) -> dict[str, Any]:
    """L'écran de veille des télés : les tableaux à composer, et les réglages d'ambiance."""
    reglages = []
    for plateforme, uid in (("select", "veille_theme"), ("select", "veille_radio"), ("text", "veille_nuit"), ("text", "veille_musique"),
                            ("text", "veille_entites"), ("text", "veille_courbe"), ("text", "veille_flux_suffixe")):
        if eid := _eid(hass, plateforme, f"{DOMAIN}_{uid}"):
            reglages.append(eid)
    return {
        "type": "sections",
        "title": "Écran de veille",
        "path": "veille",
        "icon": "mdi:television-ambient-light",
        "max_columns": 3,
        "sections": [
            {
                "type": "grid",
                "column_span": 2,
                "cards": [
                    {"type": "custom:vision-veille-card", "grid_options": {"columns": "full"}},
                    {
                        "type": "markdown",
                        "content": (
                            "_Carte vide ? La ressource `/local/vision-veille-card.js` "
                            "n'est pas chargée : Paramètres → Tableaux de bord → Ressources._"
                        ),
                    },
                ],
            },
            {
                "type": "grid",
                "cards": [
                    _titre("Ambiance", "mdi:palette-outline"),
                    {"type": "entities", "entities": reglages, "state_color": True} if reglages else None,
                    {
                        "type": "markdown",
                        "content": (
                            "Le thème, la radio et le mode nuit se changent aussi depuis la télé "
                            "(Vision → Réglages). Les photos viennent de `/media/vision_photos`."
                        ),
                    },
                ],
            },
        ],
    }


def _vue_statistiques(''',
    )
    d = remplacer(
        d,
        "        _vue_statistiques(hass, coord),\n        _vue_processus(hass),\n",
        "        _vue_statistiques(hass, coord),\n        _vue_veille(hass, coord),\n        _vue_processus(hass),\n",
    )
    # Les cartes None d'une section sont retirées.
    if '"cards": [c for c in' not in d:
        d = remplacer(
            d,
            "    for v in vues:\n        _replier_longs(v)\n",
            "    for v in vues:\n        for section in v.get(\"sections\", []):\n            section[\"cards\"] = [c for c in section.get(\"cards\", []) if c]\n        _replier_longs(v)\n",
        )
    ecrire("dashboard.py", d)

# 5. La carte, et sa ressource Lovelace.
shutil.copy(src + "vision-veille-card.js", WWW + "vision-veille-card.js")
chemin = STORAGE + "lovelace_resources"
try:
    res = json.load(open(chemin, encoding="utf-8"))
    items = res["data"]["items"]
    if not any("vision-veille-card" in (i.get("url") or "") for i in items):
        import uuid
        items.append({"id": uuid.uuid4().hex, "url": "/local/vision-veille-card.js?v=1", "type": "module"})
        shutil.copy2(chemin, chemin + SUF)
        json.dump(res, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("ressource ajoutée")
    else:
        print("ressource déjà là")
except FileNotFoundError:
    print("pas de lovelace_resources : ajouter /local/vision-veille-card.js à la main")

print("patch 9 appliqué, redémarrer Home Assistant")
