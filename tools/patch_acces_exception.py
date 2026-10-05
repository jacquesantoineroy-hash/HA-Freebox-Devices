"""Vocabulaire arrêté le 05-10-2026 :
- « Toujours autorisé » : ouvert en dehors des plages de coupure ;
- « Exception » : disponible même pendant les plages de coupure (une appli).

Répondre « exception » à une demande d'accès autorise le nom et, pour une appli, la garde disponible pendant
les coupures. La décision « disponible » de l'action « autoriser » autorise aussi le nom.

Usage sur HA : python3 patch_acces_exception.py
"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/parent.py"
s = open(P, encoding="utf-8").read()
shutil.copy2(P, P + ".bakexc3")
for a, b in (
    ('''        elif decision == "categorie":
            # Toute la catégorie''',
     '''        elif decision == "exception":
            # Exception : autorisé, et disponible même pendant les plages de coupure (une appli seulement).
            if coord.store.est_banni(d["cle"]):
                retour = "Impossible : {} est interdit pour toute la maison.".format(joli)
            else:
                coord.store.basculer(cible, d["cle"], False)
                if d.get("genre") == "apps":
                    nom_tj = str(d.get("nom") or d["cle"])
                    if nom_tj.lower() not in {n.lower() for n in _toujours_personne(coord.store, cible)}:
                        cible.setdefault("toujours", []).append(nom_tj)
                    retour = "{} a autorisé {}, même pendant les coupures.".format(qui, joli)
                else:
                    retour = "{} a autorisé {} (un site reste fermé pendant les coupures).".format(qui, joli)
        elif decision == "categorie":
            # Toute la catégorie'''),
    ('''            if nom.lower() not in {n.lower() for n in _toujours_personne(coord.store, cible)}:
                cible.setdefault("toujours", []).append(nom)
''',
     '''            if coord.store.est_banni(cle):
                raise _Refus(409, "banni", "Interdit pour toute la maison : à lever dans Vision.")
            coord.store.basculer(cible, cle, False)
            if nom.lower() not in {n.lower() for n in _toujours_personne(coord.store, cible)}:
                cible.setdefault("toujours", []).append(nom)
'''),
):
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok acces exception")
