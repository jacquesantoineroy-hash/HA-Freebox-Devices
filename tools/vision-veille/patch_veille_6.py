"""Écran de veille : résultats eSport. Usage : python3 patch_veille_6.py /dossier (contenant veille.py et esports.py)"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
src = sys.argv[1].rstrip("/") + "/"
shutil.copy2(BASE + "veille.py", BASE + "veille.py.bakveille6")
shutil.copy(src + "veille.py", BASE + "veille.py")
shutil.copy(src + "esports.py", BASE + "esports.py")
py_compile.compile(BASE + "veille.py", doraise=True)
py_compile.compile(BASE + "esports.py", doraise=True)
h = open(BASE + "http.py", encoding="utf-8").read()
if "PcParentalVeilleLogoView" not in h:
    shutil.copy2(BASE + "http.py", BASE + "http.py.bakveille6")
    ancre = "from .veille import PcParentalVeilleFluxView, PcParentalVeilleImageView, PcParentalVeilleView\n"
    assert ancre in h
    h = h.replace(ancre, ancre + "from .esports import PcParentalVeilleLogoView\n", 1)
    ancre2 = "    hass.http.register_view(PcParentalVeilleFluxView(hass))\n"
    assert ancre2 in h
    h = h.replace(ancre2, ancre2 + "    hass.http.register_view(PcParentalVeilleLogoView(hass))\n", 1)
    open(BASE + "http.py", "w", encoding="utf-8").write(h)
    py_compile.compile(BASE + "http.py", doraise=True)
print("ok")
