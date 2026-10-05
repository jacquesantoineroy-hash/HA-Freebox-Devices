"""Agent Vision 1.56.0 : l'écran de veille du PC montre les vraies cartes de Home
Assistant (page plein écran dans Edge, aux couleurs du PC) ; l'agent dépose avec
veille.json l'accès d'affichage. Thème changé sans fermer la fenêtre, bouton
plein écran, icône Vision dans la barre des tâches. Part de la 1.55.0.
Usage sur HA : python3 patch_agent_156.py /chemin/tray_wpf.ps1
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
assert "'@" not in tray, "le script tray contient '@"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak155")


def remplacer(ancien, nouveau):
    global t
    assert ancien in t, ancien[:80]
    t = t.replace(ancien, nouveau, 1)


remplacer("$script:Version           = '1.55.0'", "$script:Version           = '1.56.0'")
debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]
remplacer(
    "            @{ meteo = (Get-PropOrDefault $r 'meteo' $null); tableaux = (Get-PropOrDefault $r 'tableaux' $null) } |",
    "            $acces = $null\n"
    "            try {\n"
    "                $a = Invoke-Ha -Chemin '/api/pc_parental/veille/acces' -Corps @{ id = $Config.id; secret = $Config.secret } -Config $Config\n"
    "                if ($null -ne $a -and (Get-PropOrDefault $a 'ok' $false)) {\n"
    "                    $acces = @{ url = [string]$Config.url; id = [string]$Config.id; jeton = [string]$a.jeton; insecure = [bool](Get-PropOrDefault $Config 'insecure' $false) }\n"
    "                }\n"
    "            } catch { }\n"
    "            @{ meteo = (Get-PropOrDefault $r 'meteo' $null); tableaux = (Get-PropOrDefault $r 'tableaux' $null); acces = $acces } |",
)
open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.55.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.55.0"', 'CLIENT_VERSION = "1.56.0"', 1))
py_compile.compile(p, doraise=True)
print("ok agent 1.56.0", len(tray))
