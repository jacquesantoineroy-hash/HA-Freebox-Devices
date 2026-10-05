"""Tableau de bord Vision : un onglet « Messages » à part, et « nouveaux appareils » au lieu de « nouveaux PC ».

Le mot à envoyer quitte l'onglet Maison (où il était sous la carte de la maison) et prend son onglet,
entre Activité et Protection. Le chemin « messages » rejoint ceux que Vision écrit lui-même.

Usage sur HA : python3 patch_dashboard_messages.py   (puis redémarrer et « Régénérer le tableau de bord »)
"""
import py_compile
import re
import shutil

P = "/homeassistant/custom_components/pc_parental/dashboard.py"
s = open(P, encoding="utf-8").read()
origine = s


def rep(avant: str, apres: str) -> None:
    global s
    assert s.count(avant) == 1, (avant[:60], s.count(avant))
    s = s.replace(avant, apres)


# 1. Le chemin de l'onglet, pour que la régénération le réécrive au lieu de le doubler.
m = re.search(r"^CHEMINS = \((.*)\)$", s, flags=re.M)
assert m, "CHEMINS introuvable"
if '"messages"' not in m.group(1):
    s = s[: m.end() - 1] + ', "messages")' + s[m.end():]

# 2. La maison ne porte plus le mot à envoyer.
rep(
    """                ],
            },
            _section_message(hass, coord),
        ],
    }
    vues_personnes = [""",
    """                ],
            },
        ],
    }
    vues_personnes = [""",
)

# 3. L'onglet Messages.
rep(
    "    # Protection : les sites dangereux ou inconnus, puis ce qui démarre tout seul sur les machines.\n",
    """    # Messages : le mot à envoyer sur un appareil, une étiquette ou toute la maison.
    vue_messages = {
        "type": "sections",
        "title": "Messages",
        "path": "messages",
        "icon": "mdi:message-alert-outline",
        "max_columns": 2,
        "sections": [_section_message(hass, coord)],
    }
    # Protection : les sites dangereux ou inconnus, puis ce qui démarre tout seul sur les machines.
""",
)
rep("        vue_protection,\n", "        vue_messages,\n        vue_protection,\n")

# 4. On inscrit des téléphones et des télés autant que des PC.
s = s.replace('"Inscription de nouveaux PC"', '"Inscription de nouveaux appareils"')

assert s != origine
shutil.copy2(P, P + ".bakmsg")
open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok messages")
