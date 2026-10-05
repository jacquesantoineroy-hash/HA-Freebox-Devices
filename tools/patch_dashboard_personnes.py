"""Tableau de bord Vision : une page par personne de la maison, et le planning rangé dans ces pages.

- Toute personne de Home Assistant (person.*) a sa page, même sans appareil : en créer une suffit.
- L'onglet « Planning » disparaît : chaque page de personne porte les plannings de ses appareils,
  leur prochain changement, et le formulaire « Ajouter une plage ».
- La règle de moyenne ne parle plus de Pronote : elle suit le capteur choisi, quel qu'il soit.

Usage sur HA : python3 patch_dashboard_personnes.py
"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/dashboard.py"
s = open(P, encoding="utf-8").read()
shutil.copy2(P, P + ".bakpers")


def rep(avant: str, apres: str) -> None:
    global s
    assert s.count(avant) == 1, (avant[:70], s.count(avant))
    s = s.replace(avant, apres)


# --- Une page par personne de la maison, appareil ou non.
rep(
    """    sortie = sorted(personnes.values(), key=lambda p: p["prenom"].lower())
    if orphelins:""",
    """    # Toute personne de Home Assistant a sa page, même avant son premier appareil :
    # en créer une dans Home Assistant suffit pour la voir arriver ici.
    for etat in hass.states.async_all("person"):
        if etat.entity_id in personnes:
            continue
        cle = etat.entity_id.split(".")[-1]
        personnes[etat.entity_id] = {
            "entite": etat.entity_id,
            "cle": cle,
            "prenom": str(etat.name) if etat.name else cle,
        }
    sortie = sorted(personnes.values(), key=lambda p: p["prenom"].lower())
    if orphelins:""",
)
rep(
    """    morceaux.append(",".join(coord.store.personnes_suivies()))
    return "|".join(morceaux)""",
    """    morceaux.append(",".join(coord.store.personnes_suivies()))
    # Une personne ajoutée ou retirée dans Home Assistant refait le tableau.
    try:
        morceaux.append(",".join(sorted(e.entity_id for e in coord.hass.states.async_all("person"))))
    except Exception:  # noqa: BLE001 - l'empreinte ne doit jamais casser
        pass
    return "|".join(morceaux)""",
)

# --- Le planning dans la page de la personne : prochain changement, puis le formulaire d'ajout.
rep(
    """                        {
                            "type": "custom:comvision-planning-card",
                            "entity": eid,
                            "title": "Planning",
                        },
                    ],
                }
            )
    return {
        "type": "sections",
        "title": personne["prenom"],""",
    """                        {
                            "type": "custom:comvision-planning-card",
                            "entity": eid,
                            "title": "Planning",
                        },
                        *(
                            [{"type": "tile", "entity": suivant, "name": "Prochain changement", "icon": "mdi:calendar-arrow-right"}]
                            if (suivant := _eid(hass, "sensor", f"{DOMAIN}_suivant_{pc_id}"))
                            else []
                        ),
                    ],
                }
            )
            appareils_planifies += 1
    # Ajouter une plage : c'était un onglet à part, c'est ici qu'on en a besoin.
    if appareils_planifies:
        try:
            sections.append(_section_gestion(hass, coord))
        except Exception:  # noqa: BLE001 - la page s'affiche même sans le formulaire
            _LOGGER.exception("Formulaire des plages")
    return {
        "type": "sections",
        "title": personne["prenom"],""",
)
rep(
    """    if personne["entite"]:
        if regle := _section_moyenne_personne(hass, personne):
            sections.append(regle)
""",
    """    if personne["entite"]:
        if regle := _section_moyenne_personne(hass, personne):
            sections.append(regle)
    appareils_planifies = 0
""",
)

# --- Plus d'onglet Planning.
rep(
    """        _vue_listes(hass, coord),
        _vue_plages(hass, coord),
        _vue_statistiques(hass, coord),""",
    """        _vue_listes(hass, coord),
        _vue_statistiques(hass, coord),""",
)

# --- La règle de moyenne suit un capteur, pas une intégration en particulier.
rep(
    """                "Sous le seuil de moyenne Pronote, les catégories de "
                "divertissement se ferment sur tous ses appareils, au-dessus "
                "du planning. « Ignorer » suspend la règle sans la défaire.\"""",
    """                "Sous le seuil, les catégories de divertissement se ferment "
                "sur tous ses appareils, au-dessus du planning. La moyenne "
                "vient du capteur suivi (celui de l'école s'il y en a un). "
                "« Ignorer » suspend la règle sans la défaire.\"""",
)

open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok personnes")
