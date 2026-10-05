"""Installe « les vraies cartes Home Assistant sur l'écran de veille » (panneau /vision-veille).
À lancer sur Home Assistant depuis ce dossier : python3 installer_page.py   (rejouable)
"""
import os
import py_compile
import shutil

ICI = os.path.dirname(os.path.abspath(__file__))
BASE = "/homeassistant/custom_components/pc_parental/"

shutil.copy2(os.path.join(ICI, "veille_page.py"), BASE + "veille_page.py")
py_compile.compile(BASE + "veille_page.py", doraise=True)
os.makedirs("/homeassistant/www", exist_ok=True)
shutil.copy2(os.path.join(ICI, "vision-veille-panel.js"), "/homeassistant/www/vision-veille-panel.js")
shutil.copy2(os.path.join(ICI, "vision-veille-coeur.js"), "/homeassistant/www/vision-veille-coeur.js")

p = BASE + "http.py"
t = open(p, encoding="utf-8").read()
if "veille_page.installer(hass)" not in t:
    shutil.copy2(p, p + ".bakpage")
    a = "    hass.http.register_view(PcParentalVeilleDashView(hass))\n"
    assert a in t
    t = t.replace(a, a + "    from . import veille_page\n    veille_page.installer(hass)\n", 1)
    open(p, "w", encoding="utf-8").write(t)
    py_compile.compile(p, doraise=True)
print("ok page")
