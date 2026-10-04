"""Agent Vision 1.53.0 : la demande d'accès se fait dans la fenêtre (motif,
durée : 1 h / en permanence / toute la catégorie), les blocages récents sont
listés (fermes.json : recents), et la durée voyage jusqu'aux parents.
Usage sur HA : python3 patch_agent_153.py /chemin/tray_wpf.ps1
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
tray = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
assert "'@" not in tray, "le script tray contient '@"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak1522")


def remplacer(ancien, nouveau, n=1):
    global t
    assert t.count(ancien) >= 1, ancien[:80]
    t = t.replace(ancien, nouveau, n)


remplacer("$script:Version           = '1.52.2'", "$script:Version           = '1.53.0'")

# Le compagnon (fenêtre WPF).
debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
t = t[:debut] + "$script:TraySource = @'\n" + tray + "\n'@" + t[fin:]

# Les refus récents, pour la fenêtre.
remplacer(
    "$script:DernierVu         = @()",
    "$script:DernierVu         = @()\n$script:Recents           = @()   # derniers refus (apps et sites), pour « Bloqué récemment »",
)

fonctions = r'''
function Add-Recent {
    <#
        Un refus vient d'avoir lieu (logiciel refermé, site vu bloqué) : on le
        note pour la fenêtre, où l'enfant demande l'accès d'un geste. Un même
        nom n'est noté qu'une fois par dix minutes ; on garde 24 heures, 30 au plus.
    #>
    param([string]$Genre, [string]$Nom, [string]$Raison = '')
    if (-not $Nom) { return }
    $maintenant = Get-Date
    $cle = ($Genre + ':' + $Nom).ToLowerInvariant()
    $garde = @()
    foreach ($r in @($script:Recents)) {
        if ($null -eq $r) { continue }
        if (($maintenant - [datetime]$r.ts).TotalHours -gt 24) { continue }
        if ($r.cle -eq $cle -and ($maintenant - [datetime]$r.ts).TotalSeconds -lt 600) { return }
        if ($r.cle -eq $cle) { continue }
        $garde += $r
    }
    $garde += @{ cle = $cle; genre = $Genre; nom = $Nom; raison = $Raison; ts = $maintenant }
    if ($garde.Count -gt 30) { $garde = @($garde | Select-Object -Last 30) }
    $script:Recents = $garde
}

function Get-Recents {
    $sortie = @()
    foreach ($r in @($script:Recents | Sort-Object { $_.ts } -Descending)) {
        if ($null -eq $r) { continue }
        $sortie += @{ genre = $r.genre; nom = $r.nom; raison = $r.raison; quand = ([datetime]$r.ts).ToString('HH\hmm') }
    }
    return $sortie
}

function Write-Fermes {'''
remplacer("\nfunction Write-Fermes {", fonctions)

# Deny-Lancement : noter le refus.
remplacer(
    "        $pourquoi = Get-Raison -Nom $court\n        $phrase = \"$joli n'est pas accessible en ce moment.\"",
    "        $pourquoi = Get-Raison -Nom $court\n        Add-Recent -Genre 'apps' -Nom $joli -Raison $pourquoi\n        $phrase = \"$joli n'est pas accessible en ce moment.\"",
)

# Write-Fermes : récents des sites, « recent » des applis, et la liste.
remplacer(
    "            $apps += @{ nom = $a; raison = $r }",
    "            $recA = $false\n            try { $k = $a.ToLowerInvariant(); if ($script:AlerteApp.ContainsKey($k)) { $recA = (((Get-Date) - $script:AlerteApp[$k]).TotalMinutes -lt 10) } } catch { }\n            $apps += @{ nom = $a; raison = $r; recent = [bool]$recA }",
)
remplacer(
    "            $sites += @{ nom = $s; raison = $r; recent = [bool]$vus.ContainsKey($s) }",
    "            if ($vus.ContainsKey($s)) { Add-Recent -Genre 'sites' -Nom $s -Raison $r }\n            $sites += @{ nom = $s; raison = $r; recent = [bool]$vus.ContainsKey($s) }",
)
remplacer(
    "        @{ apps = $apps; sites = $sites; quand = (Get-Date -Format 'HH:mm') } |",
    "        @{ apps = $apps; sites = $sites; recents = @(Get-Recents); quand = (Get-Date -Format 'HH:mm') } |",
)

# Send-Demandes : la durée souhaitée part avec la demande.
remplacer(
    "                motif   = [string](Get-PropOrDefault $contenu 'motif' '')\n            } -Config $Config",
    "                motif   = [string](Get-PropOrDefault $contenu 'motif' '')\n                duree   = [string](Get-PropOrDefault $contenu 'duree' '')\n            } -Config $Config",
)

open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.52.2"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.52.2"', 'CLIENT_VERSION = "1.53.0"', 1))
py_compile.compile(p, doraise=True)
print("ok agent 1.53.0", len(tray))
