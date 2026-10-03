"""Écran de veille : flux HLS des caméras. Usage : python3 patch_veille_4.py /chemin/veille.py"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
shutil.copy(sys.argv[1], BASE + "veille.py")
py_compile.compile(BASE + "veille.py", doraise=True)
h = open(BASE + "http.py", encoding="utf-8").read()
if "PcParentalVeilleFluxView" not in h:
    shutil.copy2(BASE + "http.py", BASE + "http.py.bakveille4")
    assert "from .veille import PcParentalVeilleImageView, PcParentalVeilleView\n" in h
    h = h.replace("from .veille import PcParentalVeilleImageView, PcParentalVeilleView\n", "from .veille import PcParentalVeilleFluxView, PcParentalVeilleImageView, PcParentalVeilleView\n", 1)
    assert "    hass.http.register_view(PcParentalVeilleImageView(hass))\n" in h
    h = h.replace("    hass.http.register_view(PcParentalVeilleImageView(hass))\n",
                  "    hass.http.register_view(PcParentalVeilleImageView(hass))\n    hass.http.register_view(PcParentalVeilleFluxView(hass))\n", 1)
    open(BASE + "http.py", "w", encoding="utf-8").write(h)
    py_compile.compile(BASE + "http.py", doraise=True)
print("ok")
