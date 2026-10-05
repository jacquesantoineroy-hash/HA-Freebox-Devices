"""Exceptions par personne : ce qui est décidé nom par nom (toujours ouvert, toujours fermé) devient visible
et modifiable depuis l'application et la fenêtre du PC.

- Chaque fiche d'appareil porte « exceptions » : {autorises: [...], bloques: [...]}, un élément = nom, libellé, genre.
  Grâce aux règles par personne, c'est la même liste sur tous les appareils d'une personne.
- L'action « autoriser » accepte la décision « oublier » : l'exception est retirée, retour aux catégories.

Usage sur HA : python3 patch_parent_exceptions.py
"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/parent.py"
s = open(P, encoding="utf-8").read()
shutil.copy2(P, P + ".bakexc")


def rep(avant: str, apres: str) -> None:
    global s
    assert s.count(avant) == 1, (avant[:70], s.count(avant))
    s = s.replace(avant, apres)


rep(
    '''def _fiche(hass: HomeAssistant, coord: PcParentalCoordinator, pc: dict[str, Any], parents: list[str]) -> dict[str, Any]:''',
    '''def _exceptions(store, pc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Ce qui est décidé nom par nom pour cette personne : toujours ouvert, toujours fermé.

    Les étiquettes (catégories) ont leur propre écran ; ici ne restent que les applis et les sites.
    """
    applis = {str(n).lower() for n in (store.etiquettes.get("apps") or {})}
    applis.update(str(n).lower() for n in (pc.get("apps_vues") or {}))
    sites = {str(n).lower() for n in (store.etiquettes.get("sites") or {})}
    sortie: dict[str, list[dict[str, Any]]] = {"autorises": [], "bloques": []}
    for champ in ("autorises", "bloques"):
        for valeur in pc.get(champ) or []:
            valeur = str(valeur).strip()
            if not valeur or store._est_etiquette(valeur):
                continue
            bas = valeur.lower()
            if bas in applis:
                genre = "apps"
            elif bas in sites:
                genre = "sites"
            else:
                genre = "sites" if "." in bas and " " not in bas and not bas.endswith(".exe") and bas.count(".") <= 2 else "apps"
            vus = pc.get("apps_vues" if genre == "apps" else "sites_vus") or {}
            fiche = vus.get(valeur) if isinstance(vus, dict) else None
            libelle = str(fiche.get("libelle") or "") if isinstance(fiche, dict) else ""
            sortie[champ].append({"nom": valeur, "libelle": libelle or valeur, "genre": genre, "maison": bool(store.est_banni(valeur))})
        sortie[champ].sort(key=lambda x: x["libelle"].lower())
    return sortie


def _fiche(hass: HomeAssistant, coord: PcParentalCoordinator, pc: dict[str, Any], parents: list[str]) -> dict[str, Any]:''',
)
rep(
    '''            fiche["etiquettes_etat"] = _etats_etiquettes(pc, categories, coord.store)
''',
    '''            fiche["etiquettes_etat"] = _etats_etiquettes(pc, categories, coord.store)
            try:
                fiche["exceptions"] = _exceptions(coord.store, pc)
            except Exception:  # noqa: BLE001 - la fiche s'affiche même sans ses exceptions
                fiche["exceptions"] = {"autorises": [], "bloques": []}
''',
)
rep(
    '''        elif decision == "bloquer":
            coord.store.basculer(cible, cle, True)
            retour = "{} a bloqué {}.".format(qui, nom)
''',
    '''        elif decision == "bloquer":
            coord.store.basculer(cible, cle, True)
            retour = "{} a bloqué {}.".format(qui, nom)
        elif decision == "oublier":
            # L'exception est retirée : ce nom suit de nouveau ses catégories, l'âge et le planning.
            retire = coord.store.oublier_regle(cible, cle)
            retire = coord.store.oublier_regle(cible, nom) or retire
            if not retire:
                raise _Refus(404, "inconnu", "Cette exception n'existe plus.")
            retour = "{} a retiré l'exception sur {}.".format(qui, nom)
''',
)
open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok exceptions")
