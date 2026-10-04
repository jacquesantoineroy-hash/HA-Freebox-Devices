"""Écran de veille : tableaux composés sur l'appareil, catalogue d'entités.
Usage : python3 patch_veille_10.py /dossier (contenant veille.py, veille_plus.py, veille_tableaux.py)
"""
import os
import py_compile
import shutil
import sys

BASE = "/config/custom_components/pc_parental/" if os.path.isdir("/config/custom_components/pc_parental/") else "/homeassistant/custom_components/pc_parental/"
src = sys.argv[1].rstrip("/") + "/"
SUF = ".bakveille10b"
for nom in ("veille.py", "veille_plus.py", "veille_tableaux.py"):
    if os.path.exists(BASE + nom):
        shutil.copy2(BASE + nom, BASE + nom + SUF)
    shutil.copy(src + nom, BASE + nom)
    py_compile.compile(BASE + nom, doraise=True)
h = open(BASE + "http.py", encoding="utf-8").read()
if "PcParentalVeilleEntitesView" not in h:
    h = h.replace("from .veille import PcParentalVeilleFluxView, PcParentalVeilleImageView, PcParentalVeilleView",
                  "from .veille import PcParentalVeilleEntitesView, PcParentalVeilleFluxView, PcParentalVeilleImageView, PcParentalVeilleView", 1)
    h = h.replace("    hass.http.register_view(PcParentalVeilleImageView(hass))\n",
                  "    hass.http.register_view(PcParentalVeilleImageView(hass))\n    hass.http.register_view(PcParentalVeilleEntitesView(hass))\n", 1)
    assert "PcParentalVeilleEntitesView(hass)" in h
    shutil.copy2(BASE + "http.py", BASE + "http.py" + SUF)
    open(BASE + "http.py", "w", encoding="utf-8").write(h)
    py_compile.compile(BASE + "http.py", doraise=True)
print("patch 10 appliqué, redémarrer Home Assistant")
