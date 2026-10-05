"""Agent Vision 1.55.0 : onglet Réglages dans la fenêtre du PC (thème de couleur
comme dans l'appli, écran de veille, tableaux et cartes montrés). Plus rien dans
le menu du clic droit. Seule la fenêtre change ; part de la 1.54.1.
Usage sur HA : python3 patch_agent_155.py /chemin/tray_wpf.ps1
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
assert "'@" not in tray, "le script tray contient '@"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak1541")
ancien = "$script:Version           = '1.54.1'"
assert ancien in t
t = t.replace(ancien, "$script:Version           = '1.55.0'", 1)
debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]
open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.54.1"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.54.1"', 'CLIENT_VERSION = "1.55.0"', 1))
py_compile.compile(p, doraise=True)
print("ok agent 1.55.0", len(tray))
