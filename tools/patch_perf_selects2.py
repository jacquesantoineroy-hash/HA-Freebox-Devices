"""Les attributs des listes « constaté » (tableaux markdown de plusieurs pages)
ne vont plus dans la base du recorder : `_unrecorded_attributes = MATCH_ALL`
(l'état reste enregistré, les attributs non). Fin des avertissements
« exceed maximum size of 16384 bytes » et de l'écriture de 50 Ko toutes les
quelques secondes. Usage sur HA : python3 patch_perf_selects2.py
"""
import py_compile
import shutil

p = "/homeassistant/custom_components/pc_parental/select.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakperf2")
a = "_PAR_ETAT: dict = {}\n\n\nclass _ConstateSelect(HubEntity, SelectEntity):"
assert a in t
t = t.replace(a, "_PAR_ETAT: dict = {}\n\n\nclass _ConstateSelect(HubEntity, SelectEntity):\n"
    "    # Les tableaux markdown de ces listes pèsent des dizaines de Ko et changent à chaque relevé :\n"
    "    # le recorder ne garde que l'état, pas les attributs.\n"
    "    _unrecorded_attributes = frozenset({MATCH_ALL})\n", 1)
if "MATCH_ALL" not in t.split("class ")[0]:
    t = t.replace("from homeassistant.", "from homeassistant.const import MATCH_ALL\nfrom homeassistant.", 1)
open(p, "w", encoding="utf-8").write(t)
py_compile.compile(p, doraise=True)
print("ok perf2")
