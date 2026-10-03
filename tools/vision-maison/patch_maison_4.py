"""Vision : des onglets cohérents, et moins de texte.

- Maison, une page par personne (avec le planning de chaque appareil),
  Trancher, Planning, Activité, Processus, Réglages ;
- l'onglet Message disparaît (un mot s'envoie depuis la page de la personne) ;
- la sécurité (liste noire, DNS, VirusTotal) rejoint les Réglages ;
- les longs modes d'emploi se replient derrière « Comment ça marche ».
"""
import py_compile
import shutil

p = "/homeassistant/custom_components/pc_parental/dashboard.py"
d = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakmaison4")
assert "def _replier_longs" not in d, "déjà appliqué"


def remplacer(ancien, nouveau):
    global d
    assert ancien in d, ancien[:80]
    d = d.replace(ancien, nouveau, 1)


# Chemins : Réglages remplace Ajouter ; les anciens restent pour être purgés.
remplacer(
    'CHEMINS = ("maison", "pc", "listes", "processus", "plages", "statistiques", "message", "ajouter")',
    'CHEMINS = ("maison", "pc", "listes", "processus", "plages", "statistiques", "message", "ajouter", "reglages")',
)

# Page d'une personne : le planning de chacun de ses appareils, sous la carte.
remplacer(
    '''    if personne["entite"]:
        if regle := _section_moyenne_personne(hass, personne):
            sections.append(regle)
    return {
        "type": "sections",
        "title": personne["prenom"],''',
    '''    if personne["entite"]:
        if regle := _section_moyenne_personne(hass, personne):
            sections.append(regle)
    for pc_id in sorted(coord.pcs, key=lambda p: coord.pc_name(p).lower()):
        pc = coord.store.pcs.get(pc_id) or {}
        if str(pc.get("person") or "") != personne["entite"]:
            continue
        if eid := _eid(hass, "sensor", f"{DOMAIN}_plages_{pc_id}"):
            sections.append(
                {
                    "type": "grid",
                    "cards": [
                        _entete_appareil(pc, coord.pc_name(pc_id), "subtitle"),
                        {
                            "type": "custom:comvision-planning-card",
                            "entity": eid,
                            "title": "Planning",
                        },
                    ],
                }
            )
    return {
        "type": "sections",
        "title": personne["prenom"],''',
)

# Trancher : la carte, puis l'aide et les outils ; la sécurité part aux Réglages.
remplacer(
    '''        "title": "Sites & logiciels",
        "path": "listes",
        "icon": "mdi:format-list-checks",''',
    '''        "title": "Trancher",
        "path": "listes",
        "icon": "mdi:gavel",''',
)
remplacer(
    '''            {
                "type": "grid",
                "cards": [_section_portes(hass)],
            },
            _section_securite(hass, coord),
        ],
    }''',
    '''            {
                "type": "grid",
                "cards": [_section_portes(hass)],
            },
        ],
    }''',
)

# Planning et Activité : des noms qui disent ce qu'on vient y faire.
remplacer(
    '''        "title": "Plages horaires",
        "path": "plages",
        "icon": "mdi:calendar-clock",''',
    '''        "title": "Planning",
        "path": "plages",
        "icon": "mdi:calendar-clock",''',
)
remplacer(
    '''        "title": "Statistiques",
        "path": "statistiques",
        "icon": "mdi:chart-line",''',
    '''        "title": "Activité",
        "path": "statistiques",
        "icon": "mdi:chart-timeline-variant",''',
)

# Réglages : installer, retirer, sécurité, message à tous.
remplacer(
    '''    vue_ajout = {
        "type": "sections",
        "title": "Ajouter / supprimer",
        "path": "ajouter",
        "icon": "mdi:desktop-tower",
        "max_columns": 2,
        "sections": [
            _section_installation(hass, coord),
            _section_retrait(hass, coord),
        ],
    }''',
    '''    vue_reglages = {
        "type": "sections",
        "title": "Réglages",
        "path": "reglages",
        "icon": "mdi:cog-outline",
        "max_columns": 3,
        "sections": [
            _section_securite(hass, coord),
            _section_installation(hass, coord),
            _section_retrait(hass, coord),
            _section_message(hass, coord),
        ],
    }''',
)
remplacer(
    '''        _vue_listes(hass, coord),
        _vue_processus(hass),
        _vue_plages(hass, coord),
        _vue_statistiques(hass, coord),
        _vue_message(hass, coord),
        vue_ajout,
    ]''',
    '''        _vue_listes(hass, coord),
        _vue_plages(hass, coord),
        _vue_statistiques(hass, coord),
        _vue_processus(hass),
        vue_reglages,
    ]
    for v in vues:
        _replier_longs(v)''',
)

# Les modes d'emploi se replient : le tableau montre, l'aide attend qu'on l'ouvre.
remplacer(
    "\ndef _personnes_du_tableau(",
    '''
def _replier_longs(noeud: Any, seuil: int = 420) -> None:
    """Replie les cartes markdown bavardes derrière « Comment ça marche ».

    Un tableau de bord se lit d'un coup d'œil ; le mode d'emploi reste à
    portée de clic, sans occuper la page. Les cartes qui affichent des
    données (gabarits Jinja) ne sont pas touchées.
    """
    if isinstance(noeud, list):
        for n in noeud:
            _replier_longs(n, seuil)
        return
    if not isinstance(noeud, dict):
        return
    if noeud.get("type") == "markdown":
        texte = str(noeud.get("content") or "")
        if len(texte) > seuil and "{%" not in texte and "<details" not in texte:
            noeud["content"] = (
                "<details><summary>Comment ça marche</summary>\\n\\n"
                + texte
                + "\\n\\n</details>"
            )
        return
    for cle in ("cards", "sections", "views"):
        if cle in noeud:
            _replier_longs(noeud[cle], seuil)


def _personnes_du_tableau(''',
)

open(p, "w", encoding="utf-8").write(d)
py_compile.compile(p, doraise=True)
print("ok")
