"""Réorganise les onglets du tableau de bord Vision (dashboard.py), sans toucher au contenu des cartes.

Avant : Maison, Trancher, Planning, Activité, Écran de veille, Processus, Réglages (un fourre-tout).
Après : Maison (avec le mot à envoyer), Autorisations, Planning, Activité, Protection (sites dangereux
et logiciels au démarrage), Écran de veille, Appareils (installer, ajouter, retirer).

Usage sur HA : python3 patch_dashboard_organisation.py
"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/dashboard.py"
s = open(P, encoding="utf-8").read()
shutil.copy2(P, P + ".bakorga")


def rep(avant: str, apres: str) -> None:
    global s
    assert s.count(avant) == 1, (avant[:60], s.count(avant))
    s = s.replace(avant, apres)


# Les chemins que Vision écrit lui-même (les autres onglets sont ceux faits à la main et restent devant).
rep(
    'CHEMINS = ("maison", "veille", "pc", "listes", "processus", "plages", "statistiques", "message", "ajouter", "reglages")',
    'CHEMINS = ("maison", "veille", "pc", "listes", "processus", "plages", "statistiques", "message", "ajouter", "reglages", "protection", "appareils")',
)

# « Trancher » disait mal ce qu'on y fait : on y décide de ce qui est permis.
rep('        "title": "Trancher",\n        "path": "listes",\n        "icon": "mdi:gavel",', '        "title": "Autorisations",\n        "path": "listes",\n        "icon": "mdi:check-decagram-outline",')

# La maison : la carte de la maison, puis le mot à envoyer (il était rangé dans les réglages).
rep(
    """                        "chemin": f"/{URL_PATH}",
                    },
                ],
            }
        ],
    }
    vues_personnes = [""",
    """                        "chemin": f"/{URL_PATH}",
                    },
                ],
            },
            _section_message(hass, coord),
        ],
    }
    vues_personnes = [""",
)

# Les réglages étaient un fourre-tout : la protection d'un côté, les appareils de l'autre.
rep(
    """    vue_reglages = {
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
    }
""",
    """    # Protection : les sites dangereux ou inconnus, puis ce qui démarre tout seul sur les machines.
    sections_processus = list(_vue_processus(hass).get("sections") or [])
    for section in sections_processus:
        if isinstance(section, dict):
            section.setdefault("column_span", 3)
    vue_protection = {
        "type": "sections",
        "title": "Protection",
        "path": "protection",
        "icon": "mdi:shield-lock-outline",
        "max_columns": 3,
        "sections": [_section_securite(hass, coord), *sections_processus],
    }
    # Appareils : installer un PC, ajouter un téléphone ou une télé, retirer un appareil.
    vue_appareils = {
        "type": "sections",
        "title": "Appareils",
        "path": "appareils",
        "icon": "mdi:devices",
        "max_columns": 3,
        "sections": [
            _section_installation(hass, coord),
            _section_retrait(hass, coord),
        ],
    }
""",
)

rep(
    """        _vue_listes(hass, coord),
        _vue_plages(hass, coord),
        _vue_statistiques(hass, coord),
        _vue_veille(hass, coord),
        _vue_processus(hass),
        vue_reglages,
    ]""",
    """        _vue_listes(hass, coord),
        _vue_plages(hass, coord),
        _vue_statistiques(hass, coord),
        vue_protection,
        _vue_veille(hass, coord),
        vue_appareils,
    ]""",
)

open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok organisation")
