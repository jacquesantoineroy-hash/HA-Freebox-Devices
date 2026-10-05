"""Applis « toujours disponibles » par personne : elles restent ouvertes même quand le planning ferme l'appareil.

Jusqu'ici la liste était la même pour toute la maison (étiquette « Toujours autorisé »). Chaque personne a
maintenant la sienne en plus, rangée dans la fiche de ses appareils (« toujours ») et lue pour la personne
entière : posée sur un appareil, elle vaut sur tous.

- relevé (http.py) : « toujours » = liste de la maison + liste de la personne ;
- espace parents (parent.py) : « exceptions.toujours », et les décisions « disponible » / « indisponible »
  de l'action « autoriser ».

Usage sur HA : python3 patch_toujours_personne.py
"""
import py_compile
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"


def patch(fichier: str, suffixe: str, remplacements: list[tuple[str, str]]) -> None:
    p = BASE + fichier
    s = open(p, encoding="utf-8").read()
    shutil.copy2(p, p + suffixe)
    for avant, apres in remplacements:
        assert s.count(avant) == 1, (fichier, avant[:70], s.count(avant))
        s = s.replace(avant, apres)
    open(p, "w", encoding="utf-8").write(s)
    py_compile.compile(p, doraise=True)


patch("http.py", ".baktjp", [(
    '''            reponse["toujours"] = coord.store.noms_par_etiquette("apps", "Toujours autorisé")
''',
    '''            reponse["toujours"] = list(coord.store.noms_par_etiquette("apps", "Toujours autorisé"))
            # Plus celles de la personne : posées sur un de ses appareils, elles valent sur tous.
            moi_pc = coord.store.pcs.get(pc_id) or {}
            ma_personne = str(moi_pc.get("person") or "")
            for autre in coord.store.pcs.values():
                if autre is moi_pc or (ma_personne and str(autre.get("person") or "") == ma_personne):
                    for nom_tj in autre.get("toujours") or []:
                        if nom_tj not in reponse["toujours"]:
                            reponse["toujours"].append(nom_tj)
''',
)])

patch("parent.py", ".baktjp", [
    (
        '''    sortie: dict[str, list[dict[str, Any]]] = {"autorises": [], "bloques": []}
    for champ in ("autorises", "bloques"):''',
        '''    sortie: dict[str, list[dict[str, Any]]] = {"autorises": [], "bloques": [], "toujours": []}
    # Toujours disponibles, même appareil fermé : celles de toute la maison (non modifiables ici), puis celles de la personne.
    deja: set[str] = set()
    try:
        maison_tj = list(store.noms_par_etiquette("apps", "Toujours autorisé"))
    except Exception:  # noqa: BLE001
        maison_tj = []
    for nom_tj in maison_tj:
        if str(nom_tj).lower() not in deja:
            deja.add(str(nom_tj).lower())
            sortie["toujours"].append({"nom": str(nom_tj), "libelle": applis.get(str(nom_tj).lower()) or str(nom_tj), "genre": "apps", "maison": True})
    for nom_tj in _toujours_personne(store, pc):
        if nom_tj.lower() not in deja:
            deja.add(nom_tj.lower())
            sortie["toujours"].append({"nom": nom_tj, "libelle": applis.get(nom_tj.lower()) or nom_tj, "genre": "apps", "maison": False})
    sortie["toujours"].sort(key=lambda x: x["libelle"].lower())
    for champ in ("autorises", "bloques"):''',
    ),
    (
        '''def _exceptions(store, pc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:''',
        '''def _appareils_personne(store, pc: dict[str, Any]) -> list[dict[str, Any]]:
    """Cet appareil et ceux de la même personne."""
    personne = str(pc.get("person") or "")
    return [a for a in store.pcs.values() if a is pc or (personne and str(a.get("person") or "") == personne)]


def _toujours_personne(store, pc: dict[str, Any]) -> list[str]:
    """Les applis que cette personne garde ouvertes même appareil fermé (tous ses appareils confondus)."""
    vus: dict[str, str] = {}
    for a in _appareils_personne(store, pc):
        for nom in a.get("toujours") or []:
            nom = str(nom).strip()
            if nom:
                vus.setdefault(nom.lower(), nom)
    return list(vus.values())


def _exceptions(store, pc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:''',
    ),
    (
        '''        elif decision == "oublier":''',
        '''        elif decision == "disponible":
            # Reste ouverte même quand le planning ferme l'appareil. Une appli seulement : un site n'a pas d'icône à proposer.
            if genre != "apps":
                raise _Refus(400, "genre", "Seule une appli peut rester disponible appareil fermé.")
            if nom.lower() not in {n.lower() for n in _toujours_personne(coord.store, cible)}:
                cible.setdefault("toujours", []).append(nom)
            retour = "{} : {} reste disponible, même appareil fermé.".format(qui, nom)
        elif decision == "indisponible":
            retire = False
            for a in _appareils_personne(coord.store, cible):
                avant_tj = list(a.get("toujours") or [])
                apres_tj = [n for n in avant_tj if str(n).strip().lower() != nom.lower()]
                if len(apres_tj) != len(avant_tj):
                    a["toujours"] = apres_tj
                    retire = True
            if not retire:
                raise _Refus(404, "inconnu", "Cette appli n'est plus dans la liste.")
            retour = "{} : {} suit de nouveau le planning.".format(qui, nom)
        elif decision == "oublier":''',
    ),
])
print("ok toujours par personne")
