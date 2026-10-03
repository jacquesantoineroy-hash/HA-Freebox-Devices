import shutil
p = "/homeassistant/custom_components/pc_parental/parent.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bak2")
assert '"etiquette"' not in t

old = '''class PcParentalParentView(HomeAssistantView):'''
new = '''ROLES = ("parents", "enfants", "affichage")


def _categories(hass: HomeAssistant, coord: PcParentalCoordinator) -> list[dict[str, Any]]:
    """Les étiquettes qui classent des applis et des sites, avec leur contenu."""
    store = coord.store
    contenu: dict[str, dict[str, list]] = {}
    libelles: dict[str, str] = {}
    for pc in store.pcs.values():
        for nom, fiche in (pc.get("apps_vues") or {}).items():
            if isinstance(fiche, dict) and fiche.get("libelle"):
                libelles.setdefault(nom, str(fiche["libelle"]))
    for genre in ("apps", "sites"):
        for nom, ets in (store.etiquettes.get(genre) or {}).items():
            for e in ets or []:
                bloc = contenu.setdefault(str(e), {"apps": [], "sites": []})
                bloc[genre].append(nom)
    noms = set(contenu)
    noms.update(e for e in labels.vocabulaire(hass) if e)
    noms.update(e for e in store.bannis if store._est_etiquette(e))
    divert = {e.lower() for e in (store.divertissement or [])}
    sortie = []
    for nom in sorted(noms, key=lambda s: s.lower()):
        if nom.lower() in ROLES:
            continue
        bloc = contenu.get(nom, {"apps": [], "sites": []})
        apps = sorted(({"nom": a, "libelle": libelles.get(a, a)} for a in bloc["apps"]), key=lambda x: x["libelle"].lower())
        sites = sorted(s for s in bloc["sites"] if s.count(".") == 1) or sorted(bloc["sites"])
        sortie.append({
            "nom": nom,
            "maison": store.est_banni(nom),
            "securite": nom.lower() in ("dangereux", "contournement", "pub & traçage", "pub & tracage"),
            "age": nom.lower() in ("pegi 12", "pegi 16", "pegi 18", "adulte"),
            "divertissement": nom.lower() in divert,
            "apps": apps,
            "sites": sites,
        })
    return sortie


def _etats_etiquettes(pc: dict[str, Any], categories: list[dict[str, Any]]) -> dict[str, str]:
    bloques = {str(b).lower() for b in (pc.get("bloques") or [])}
    autorises = {str(b).lower() for b in (pc.get("autorises") or [])}
    etats = {}
    for c in categories:
        bas = c["nom"].lower()
        etats[c["nom"]] = "bloquer" if bas in bloques else ("autoriser" if bas in autorises else "neutre")
    return etats


class PcParentalParentView(HomeAssistantView):'''
assert old in t
t = t.replace(old, new, 1)

old = '''            elif action == "message":'''
new = '''            elif action == "etiquette":
                nom = str(corps.get("etiquette") or "").strip()
                etat = str(corps.get("etat") or "neutre")
                if not nom or not coord.store._est_etiquette(nom):
                    return self.json({"ok": False, "error": "etiquette"}, status_code=400)
                if coord.store.est_banni(nom):
                    return self.json({"ok": False, "error": "banni", "retour": "Interdit pour toute la maison : à lever dans Vision."}, status_code=409)
                if etat == "bloquer":
                    coord.store.basculer(cible, nom, True)
                    retour = "{} : {} coupé.".format(qui, nom)
                elif etat == "autoriser":
                    coord.store.basculer(cible, nom, False)
                    retour = "{} : {} autorisé.".format(qui, nom)
                else:
                    for champ in ("bloques", "autorises"):
                        cible[champ] = [v for v in (cible.get(champ) or []) if str(v).strip().lower() != nom.lower()]
                    retour = "{} : {} laissé aux règles de la maison.".format(qui, nom)
            elif action == "message":'''
assert old in t
t = t.replace(old, new, 1)

old = '''        appareils = []
        for pc in coord.store.pcs.values():'''
new = '''        categories = _categories(self.hass, coord)
        appareils = []
        for pc in coord.store.pcs.values():'''
assert old in t
t = t.replace(old, new, 1)
old = '''                appareils.append(self._fiche(coord, pc, parents))'''
new = '''                fiche = self._fiche(coord, pc, parents)
                fiche["etiquettes_etat"] = _etats_etiquettes(pc, categories)
                appareils.append(fiche)'''
assert old in t
t = t.replace(old, new, 1)
old = '''        return self.json({"ok": True, "moi": moi["id"], "retour": retour, "appareils": appareils, "demandes": attente})'''
new = '''        return self.json({"ok": True, "moi": moi["id"], "retour": retour, "appareils": appareils, "demandes": attente, "categories": categories})'''
assert old in t
t = t.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(t)
import py_compile
py_compile.compile(p, doraise=True)
print("ok")
