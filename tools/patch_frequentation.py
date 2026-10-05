"""Fréquentation des sites : « Tranco : archive illisible ».

`reponse.content.read(TAILLE_MAX)` ne rend que ce qui est déjà arrivé (au plus TAILLE_MAX octets),
pas le fichier entier : le zip était tronqué et `zipfile` le refusait à chaque fois. On lit jusqu'au
bout, par morceaux, en gardant le plafond de taille.

Usage sur HA : python3 patch_frequentation.py   (puis redémarrer Home Assistant)
"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/notoriete.py"
s = open(P, encoding="utf-8").read()

AVANT = "                donnees = await reponse.content.read(TAILLE_MAX)\n"
APRES = (
    "                morceaux = []\n"
    "                taille = 0\n"
    "                async for morceau in reponse.content.iter_chunked(65536):\n"
    "                    taille += len(morceau)\n"
    "                    if taille > TAILLE_MAX:\n"
    "                        raise ValueError(\"Fichier plus gros que prévu.\")\n"
    "                    morceaux.append(morceau)\n"
    "                donnees = b\"\".join(morceaux)\n"
)
assert s.count(AVANT) == 1, s.count(AVANT)
shutil.copy2(P, P + ".bakfreq")
s = s.replace(AVANT, APRES)
open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok frequentation")
