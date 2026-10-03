"""Vision, tableau par personne, retouches : largeur des cartes, note retirée,
libellé du logiciel au premier plan. Usage : python3 patch_maison_2.py /chemin/parent.py
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"

nouveau_parent = open(sys.argv[1], encoding="utf-8").read()
assert "removesuffix" in nouveau_parent
shutil.copy2(BASE + "parent.py", BASE + "parent.py.bak5")
open(BASE + "parent.py", "w", encoding="utf-8").write(nouveau_parent)
py_compile.compile(BASE + "parent.py", doraise=True)

p = BASE + "dashboard.py"
d = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakmaison2")

ancien = '''        "max_columns": 1,
        "sections": [
            {
                "type": "grid",
                "cards": [
                    {
                        "type": "custom:vision-maison-card",
                        "mode": "maison",
                        "chemin": f"/{URL_PATH}",
                    },
                    _mot(
                        "_Carte vide ? La ressource `/local/vision-maison-card.js` "
                        "n'est pas déclarée dans Paramètres → Tableaux de bord → "
                        "Ressources._"
                    ),
                ],
            }
        ],'''
assert ancien in d
d = d.replace(ancien, '''        "max_columns": 2,
        "sections": [
            {
                "type": "grid",
                "column_span": 2,
                "cards": [
                    {
                        "type": "custom:vision-maison-card",
                        "mode": "maison",
                        "chemin": f"/{URL_PATH}",
                    },
                ],
            }
        ],''', 1)

ancien = '''    sections: list[dict[str, Any]] = [
        {
            "type": "grid",
            "cards": [
                {
                    "type": "custom:vision-maison-card",
                    "mode": "personne",'''
assert ancien in d
d = d.replace(ancien, '''    sections: list[dict[str, Any]] = [
        {
            "type": "grid",
            "column_span": 2,
            "cards": [
                {
                    "type": "custom:vision-maison-card",
                    "mode": "personne",''', 1)

ancien = '''        "back_path": f"/{URL_PATH}/maison",
        "max_columns": 2,'''
assert ancien in d
d = d.replace(ancien, '''        "back_path": f"/{URL_PATH}/maison",
        "max_columns": 3,''', 1)

open(p, "w", encoding="utf-8").write(d)
py_compile.compile(p, doraise=True)
print("ok")
