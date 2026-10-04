"""Étiquette « Toujours autorisé » : les applis qui la portent restent ouvertes
même quand l'appareil est fermé (musique pour s'endormir, par exemple). Le
relevé transmet leur liste à l'appli (`toujours`), qui les propose sur l'écran
de fermeture. L'étiquette est déclarée d'office pour apparaître dans le tableau.
Usage sur HA : python3 patch_toujours.py
"""
import py_compile
import shutil

p = "/homeassistant/custom_components/pc_parental/http.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".baktjs")
a = "            \"parent\": pc_id in labels.pcs_avec(self.hass, coord.store.pcs, \"Parents\"),\n        }\n"
assert a in t
t = t.replace(a, a +
    "        # Les applis « Toujours autorisé » : ouvertes même appareil fermé.\n"
    "        try:\n"
    "            if \"Toujours autorisé\" not in coord.store.toutes_etiquettes():\n"
    "                coord.store.declarer_etiquette(\"Toujours autorisé\")\n"
    "            reponse[\"toujours\"] = coord.store.noms_par_etiquette(\"apps\", \"Toujours autorisé\")\n"
    "        except Exception:  # noqa: BLE001\n"
    "            reponse[\"toujours\"] = []\n", 1)
open(p, "w", encoding="utf-8").write(t)
py_compile.compile(p, doraise=True)
print("ok toujours")
