"""Exceptions par personne, suite : une appli Android est reconnue comme une appli (pas comme un site) et
porte son vrai nom (« Snapchat » au lieu de « snapchat.android »). Usage sur HA : python3 patch_parent_exceptions2.py"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/parent.py"
s = open(P, encoding="utf-8").read()
shutil.copy2(P, P + ".bakexc2")
for a, b in (
    ('''    applis = {str(n).lower() for n in (store.etiquettes.get("apps") or {})}
    applis.update(str(n).lower() for n in (pc.get("apps_vues") or {}))
    sites = {str(n).lower() for n in (store.etiquettes.get("sites") or {})}''',
     '''    # Une appli se reconnaît sous son nom brut ou raccourci (« com.snapchat.android », « snapchat.android ») ;
    # son libellé (« Snapchat ») vient de n'importe quel appareil qui l'a déjà vue.
    applis: dict[str, str] = {}
    for n in (store.etiquettes.get("apps") or {}):
        for cle_app in (str(n).lower(), str(demandes._nom_app(str(n)) or "").lower()):
            if cle_app:
                applis.setdefault(cle_app, "")
    for autre in [pc, *store.pcs.values()]:
        for n, f in (autre.get("apps_vues") or {}).items():
            lib_app = str(f.get("libelle") or "") if isinstance(f, dict) else ""
            for cle_app in (str(n).lower(), str(demandes._nom_app(str(n)) or "").lower()):
                if cle_app and not applis.get(cle_app):
                    applis[cle_app] = lib_app
    sites = {str(n).lower() for n in (store.etiquettes.get("sites") or {})}'''),
    ('''            vus = pc.get("apps_vues" if genre == "apps" else "sites_vus") or {}
            fiche = vus.get(valeur) if isinstance(vus, dict) else None
            libelle = str(fiche.get("libelle") or "") if isinstance(fiche, dict) else ""''',
     '''            libelle = applis.get(bas, "") if genre == "apps" else ""'''),
):
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok exceptions 2")
