import shutil
p = "/homeassistant/custom_components/pc_parental/parent.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bak3")
assert "def _etat_categorie" not in t
old = '''def _etats_etiquettes(pc: dict[str, Any], categories: list[dict[str, Any]]) -> dict[str, str]:
    bloques = {str(b).lower() for b in (pc.get("bloques") or [])}
    autorises = {str(b).lower() for b in (pc.get("autorises") or [])}
    etats = {}
    for c in categories:
        bas = c["nom"].lower()
        etats[c["nom"]] = "bloquer" if bas in bloques else ("autoriser" if bas in autorises else "neutre")
    return etats
'''
new = '''def _etat_categorie(store, pc: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
    """Ce que vaut une catégorie pour cet appareil : le choix du parent, et
    ce qui est réellement appliqué (la maison, la moyenne ou le planning
    peuvent la couper par-dessus)."""
    nom = c["nom"]
    bas = nom.lower()
    bloques = {str(b).lower() for b in (pc.get("bloques") or [])}
    autorises = {str(b).lower() for b in (pc.get("autorises") or [])}
    choix = "bloquer" if bas in bloques else ("autoriser" if bas in autorises else "neutre")
    code, texte = "", ""
    if c.get("maison"):
        code = "securite" if c.get("securite") else "maison"
        texte = "Interdit pour toute la maison."
    else:
        try:
            if store.moyenne_ferme(pc, [nom]):
                personne = str(pc.get("person") or "")
                cfg = store.moyennes.get(personne) or {}
                valeur = store.moyenne_de(personne) or 0.0
                code, texte = "moyenne", "Coupé par la règle de moyenne ({:g} sous {:g}).".format(valeur, float(cfg.get("seuil") or 12))
            else:
                regle = store.plage_ferme(pc, nom)
                if regle:
                    code, texte = "plage", "Coupé en ce moment par le planning « {} ».".format(regle.get("name") or "plage")
        except Exception:  # noqa: BLE001
            pass
    if not code and choix == "bloquer":
        code = "age" if c.get("age") else "regle"
        texte = "Coupé par les parents."
    return {"choix": choix, "coupe": bool(code), "code": code, "raison": texte, "verrou": code in ("securite", "maison", "moyenne", "plage")}


def _etats_etiquettes(pc: dict[str, Any], categories: list[dict[str, Any]], store=None) -> dict[str, Any]:
    etats = {}
    for c in categories:
        if store is None:
            bloques = {str(b).lower() for b in (pc.get("bloques") or [])}
            etats[c["nom"]] = "bloquer" if c["nom"].lower() in bloques else "neutre"
        else:
            etats[c["nom"]] = _etat_categorie(store, pc, c)
    return etats
'''
assert old in t
t = t.replace(old, new, 1)
old = '''                fiche["etiquettes_etat"] = _etats_etiquettes(pc, categories)'''
new = '''                fiche["etiquettes_etat"] = _etats_etiquettes(pc, categories, coord.store)'''
assert old in t
t = t.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(t)
import py_compile
py_compile.compile(p, doraise=True)
print("ok")
