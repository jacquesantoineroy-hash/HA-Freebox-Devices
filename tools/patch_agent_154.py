"""Agent Vision 1.54.0 : écran de veille sur PC (l'horloge, puis les tableaux de
bord rendus disponibles dans Vision), réglé par PC dans le menu de l'icône ;
vue Catégories réparée ; saisie au clavier dans la fenêtre (un mot, une demande).
L'agent dépose veille.json (météo et tableaux seulement) pour la fenêtre.
Usage sur HA : python3 patch_agent_154.py /chemin/tray_wpf.ps1
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
assert "'@" not in tray, "le script tray contient '@"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak153")


def remplacer(ancien, nouveau, n=1):
    global t
    assert t.count(ancien) >= 1, ancien[:80]
    t = t.replace(ancien, nouveau, n)


remplacer("$script:Version           = '1.53.0'", "$script:Version           = '1.54.0'")

debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]

remplacer(
    "$script:DerniereMaison    = [datetime]::MinValue\n",
    "$script:DerniereMaison    = [datetime]::MinValue\n"
    "$script:VeillePath        = Join-Path $script:SondeDir 'veille.json'\n"
    "$script:DerniereVeille    = [datetime]::MinValue\n",
)

remplacer("\nfunction Send-Actions {", r'''
function Sync-Veille {
    <#
        L'écran de veille du PC : l'agent va chercher ce que Home Assistant
        rend disponible (l'horloge et les tableaux de bord choisis dans Vision)
        et ne dépose pour la fenêtre que la météo et les tableaux.
    #>
    param($Config)
    if (((Get-Date) - $script:DerniereVeille).TotalSeconds -lt 60) { return }
    $script:DerniereVeille = Get-Date
    try {
        $r = Invoke-Ha -Chemin '/api/pc_parental/veille' -Corps @{ id = $Config.id; secret = $Config.secret; ecran = 'tele' } -Config $Config
        if ($null -ne $r) {
            @{ meteo = (Get-PropOrDefault $r 'meteo' $null); tableaux = (Get-PropOrDefault $r 'tableaux' $null) } |
                ConvertTo-Json -Depth 14 -Compress | Set-Content -Path $script:VeillePath -Encoding UTF8
        }
    } catch {
        Write-Journal "Écran de veille non rafraîchi : $_" 'WARN'
    }
}

function Send-Actions {''')

remplacer(
    "            try { Sync-Maison -Config $config } catch { }\n",
    "            try { Sync-Maison -Config $config } catch { }\n"
    "            try { Sync-Veille -Config $config } catch { }\n",
)

open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.53.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.53.0"', 'CLIENT_VERSION = "1.54.0"', 1))
py_compile.compile(p, doraise=True)
print("ok agent 1.54.0", len(tray))
