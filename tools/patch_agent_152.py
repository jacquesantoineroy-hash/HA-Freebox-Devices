"""Agent ComVision 1.52.0 : la fenêtre Vision en WPF (tray_wpf.ps1), sans
bordure Windows, coins arrondis, charte Vision. Usage sur HA :
python3 patch_agent_152.py /chemin/tray_wpf.ps1
"""
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
assert "'@" not in tray, "le script tray contient '@"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak152")
assert "$script:Version           = '1.52.0'" in t
t = t.replace("$script:Version           = '1.52.0'", "$script:Version           = '1.52.1'", 1)
debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]
open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.52.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.52.0"', 'CLIENT_VERSION = "1.52.1"', 1))
import py_compile
py_compile.compile(p, doraise=True)
print("ok", len(tray))
