"""Agent Vision 1.60.0 : la liste des tableaux et des cartes des Réglages vient de la même source
que la page de veille (toutes les cartes, par nom), relevée toutes les vingt secondes ; bouton Actualiser.
Part de la 1.59.0. Usage sur HA : python3 patch_agent_160.py /chemin/tray_wpf.ps1
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
assert "'@" not in tray
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak159")


def remplacer(ancien, nouveau):
    global t
    assert ancien in t, ancien[:80]
    t = t.replace(ancien, nouveau, 1)


remplacer("$script:Version           = '1.59.0'", "$script:Version           = '1.60.0'")
debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]
remplacer("    if (((Get-Date) - $script:DerniereVeille).TotalSeconds -lt 60) { return }", "    if (((Get-Date) - $script:DerniereVeille).TotalSeconds -lt 20) { return }")
remplacer("            $acces = $null\n", "            $acces = $null; $pageLegere = $null\n")
remplacer("-Corps @{ id = $Config.id; secret = $Config.secret } -Config $Config\n                if ($null -ne $a -and (Get-PropOrDefault $a 'ok' $false)) {\n",
          "-Corps @{ id = $Config.id; secret = $Config.secret; ecran = 'tele' } -Config $Config\n                if ($null -ne $a -and (Get-PropOrDefault $a 'ok' $false)) {\n                    $pageLegere = Get-PropOrDefault $a 'tableaux' $null\n")
remplacer("tableaux = (Get-PropOrDefault $r 'tableaux' $null); acces = $acces } |", "tableaux = (Get-PropOrDefault $r 'tableaux' $null); acces = $acces; page = $pageLegere } |")
open(AGENT, "w", encoding="utf-8").write(t)
p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.59.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.59.0"', 'CLIENT_VERSION = "1.60.0"', 1))
py_compile.compile(p, doraise=True)
print("ok agent 1.60.0", len(tray))
