"""Publie une nouvelle fenêtre du PC (tray_wpf.ps1) dans l'agent, sans autre changement.
Usage sur HA : python3 patch_agent_tray.py /chemin/tray_wpf.ps1 <version actuelle> <nouvelle version>
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
avant, apres = sys.argv[2], sys.argv[3]
assert "'@" not in tray, "le script tray contient '@"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak" + avant.replace(".", ""))
ligne = "$script:Version           = '{}'"
assert ligne.format(avant) in t, "l'agent n'est pas en " + avant
t = t.replace(ligne.format(avant), ligne.format(apres), 1)
debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]
open(AGENT, "w", encoding="utf-8").write(t)
p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
v = 'CLIENT_VERSION = "{}"'
assert v.format(avant) in c
open(p, "w", encoding="utf-8").write(c.replace(v.format(avant), v.format(apres), 1))
py_compile.compile(p, doraise=True)
print("ok agent", apres, len(tray))
