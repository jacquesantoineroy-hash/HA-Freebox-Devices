"""Vision : le tableau de bord parle de personnes, plus de machines.

- onglet « Maison » : une ligne par personne, ce que font ses appareils ;
- une sous-vue par personne : accès par appareil, catégories en accordéon ;
- l'onglet « PC » disparaît, avec tout ce qu'on n'y lisait jamais ;
- http.py enregistre la vue /api/pc_parental/maison (administrateurs).

Usage sur HA : python3 patch_dashboard_maison.py /chemin/parent.py
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"


def lire(nom):
    return open(BASE + nom, encoding="utf-8").read()


def ecrire(nom, texte, sauvegarde):
    shutil.copy2(BASE + nom, BASE + nom + sauvegarde)
    open(BASE + nom, "w", encoding="utf-8").write(texte)
    py_compile.compile(BASE + nom, doraise=True)


# --- parent.py : remplacé en bloc ------------------------------------------
nouveau_parent = open(sys.argv[1], encoding="utf-8").read()
assert "class PcParentalMaisonView" in nouveau_parent
ecrire("parent.py", nouveau_parent, ".bak4")

# --- http.py : enregistrer la vue -------------------------------------------
h = lire("http.py")
if "PcParentalMaisonView" not in h:
    assert "from .parent import PcParentalParentView" in h
    h = h.replace(
        "from .parent import PcParentalParentView",
        "from .parent import PcParentalMaisonView, PcParentalParentView",
        1,
    )
    assert "    hass.http.register_view(PcParentalParentView(hass))" in h
    h = h.replace(
        "    hass.http.register_view(PcParentalParentView(hass))",
        "    hass.http.register_view(PcParentalParentView(hass))\n"
        "    hass.http.register_view(PcParentalMaisonView(hass))",
        1,
    )
    ecrire("http.py", h, ".bakmaison")

# --- dashboard.py -------------------------------------------------------------
d = lire("dashboard.py")
assert "vue_maison" not in d, "déjà appliqué"

ancien_chemins = 'CHEMINS = ("pc", "listes", "processus", "plages", "statistiques", "message", "ajouter")'
assert ancien_chemins in d
d = d.replace(
    ancien_chemins,
    'CHEMINS = ("maison", "pc", "listes", "processus", "plages", "statistiques", "message", "ajouter")\n'
    "# Les sous-vues d'une personne portent son nom : on les reconnaît au préfixe.\n"
    'PREFIXE_PERSONNE = "personne-"',
    1,
)

ancien_filtre = '        if isinstance(vue, dict) and vue.get("path") not in CHEMINS\n'
assert ancien_filtre in d
d = d.replace(
    ancien_filtre,
    '        if isinstance(vue, dict)\n'
    '        and vue.get("path") not in CHEMINS\n'
    '        and not str(vue.get("path") or "").startswith(PREFIXE_PERSONNE)\n',
    1,
)

ancienne_signature = '        morceaux.append(f"{pc_id}:{pc.get(\'name\')}:{regles}")'
assert ancienne_signature in d
d = d.replace(
    ancienne_signature,
    '        morceaux.append(f"{pc_id}:{pc.get(\'name\')}:{pc.get(\'person\')}:{regles}")',
    1,
)

debut = d.index("    machines = []\n    for pc_id in sorted(coord.pcs")
fin = d.index("    vue_ajout = {")
d = d[:debut] + '''    vue_maison = {
        "type": "sections",
        "title": "Maison",
        "path": "maison",
        "icon": "mdi:home-heart",
        "max_columns": 1,
        "sections": [
            {
                "type": "grid",
                "cards": [
                    {
                        "type": "custom:vision-maison-card",
                        "mode": "maison",
                        "chemin": f"/{URL_PATH}",
                    },
                    _mot(
                        "_Carte vide ? La ressource `/local/vision-maison-card.js` "
                        "n'est pas déclarée dans Paramètres → Tableaux de bord → "
                        "Ressources._"
                    ),
                ],
            }
        ],
    }
    vues_personnes = [
        _vue_personne(hass, coord, personne)
        for personne in _personnes_du_tableau(hass, coord)
    ]

''' + d[fin:]

ancien_vues = "    vues = [\n        vue_pc,\n"
assert ancien_vues in d
d = d.replace(ancien_vues, "    vues = [\n        vue_maison,\n        *vues_personnes,\n", 1)

fonctions = '''
def _personnes_du_tableau(
    hass: HomeAssistant, coord: PcParentalCoordinator
) -> list[dict[str, Any]]:
    """Une page par personne qu'un appareil désigne, et une pour les
    appareils que personne ne revendique encore."""
    personnes: dict[str, dict[str, Any]] = {}
    orphelins = False
    for pc in coord.store.pcs.values():
        entite = str(pc.get("person") or "")
        if not entite:
            orphelins = True
            continue
        if entite in personnes:
            continue
        etat = hass.states.get(entite)
        cle = entite.split(".")[-1]
        personnes[entite] = {
            "entite": entite,
            "cle": cle,
            "prenom": str(etat.name) if etat is not None and etat.name else cle,
        }
    sortie = sorted(personnes.values(), key=lambda p: p["prenom"].lower())
    if orphelins:
        sortie.append({"entite": "", "cle": "autres", "prenom": "Sans personne"})
    return sortie


def _section_moyenne_personne(
    hass: HomeAssistant, personne: dict[str, Any]
) -> dict[str, Any] | None:
    """Les réglages de la règle de moyenne de cette personne, s'il y en a."""
    cle = personne["cle"]
    regle = _eid(hass, "switch", f"{DOMAIN}_moyenne_active_{cle}")
    if not regle:
        return None
    lignes = [{"entity": regle, "name": "Règle active"}]
    if eid := _eid(hass, "number", f"{DOMAIN}_moyenne_seuil_{cle}"):
        lignes.append({"entity": eid, "name": "Seuil de moyenne"})
    if eid := _eid(hass, "switch", f"{DOMAIN}_moyenne_ignore_{cle}"):
        lignes.append({"entity": eid, "name": "Ignorer la règle"})
    return {
        "type": "grid",
        "cards": [
            _titre("Règle de moyenne", "mdi:school-outline", "subtitle"),
            {"type": "entities", "state_color": True, "entities": lignes},
            _mot(
                "Sous le seuil de moyenne Pronote, les catégories de "
                "divertissement se ferment sur tous ses appareils, au-dessus "
                "du planning. « Ignorer » suspend la règle sans la défaire."
            ),
        ],
    }


def _vue_personne(
    hass: HomeAssistant, coord: PcParentalCoordinator, personne: dict[str, Any]
) -> dict[str, Any]:
    """La page d'une personne : on y arrive depuis la ligne de la maison."""
    sections: list[dict[str, Any]] = [
        {
            "type": "grid",
            "cards": [
                {
                    "type": "custom:vision-maison-card",
                    "mode": "personne",
                    "personne": personne["entite"] or personne["cle"],
                    "chemin": f"/{URL_PATH}",
                }
            ],
        }
    ]
    if personne["entite"]:
        if regle := _section_moyenne_personne(hass, personne):
            sections.append(regle)
    return {
        "type": "sections",
        "title": personne["prenom"],
        "path": f"{PREFIXE_PERSONNE}{personne['cle']}",
        "icon": "mdi:account",
        "subview": True,
        "back_path": f"/{URL_PATH}/maison",
        "max_columns": 2,
        "sections": sections,
    }


def build('''
assert "\ndef build(" in d
d = d.replace("\ndef build(", fonctions, 1)

ecrire("dashboard.py", d, ".bakmaison")
print("ok")
