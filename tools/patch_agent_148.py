"""Agent ComVision 1.48.0 : dire pourquoi c'est fermé (motifs envoyés par HA).
À exécuter sur HA : python3 patch_agent_148.py
"""
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak147")
assert "$script:Version           = '1.47.0'" in t
t = t.replace("$script:Version           = '1.47.0'", "$script:Version           = '1.48.0'", 1)
t = t.replace("$script:DemandeTemps      = 0\n", "$script:DemandeTemps      = 0\n$script:Raisons           = @{}\n", 1)

# Lire les motifs de la décision.
old = """            if ($decision.PSObject.Properties['poll']) { $attente = [int]$decision.poll }
            Save-Etat -Decision $decision"""
new = """            if ($decision.PSObject.Properties['poll']) { $attente = [int]$decision.poll }
            Save-Etat -Decision $decision
            Read-Raisons -Decision $decision"""
assert old in t
t = t.replace(old, new, 1)

old = "function Send-Demandes {"
new = """function Read-Raisons {
    # Home Assistant dit pourquoi chaque nom est fermé : `motifs` (textes) et
    # `raisons` (nom → index). On garde une table nom → texte.
    param($Decision)
    $table = @{}
    try {
        if ($null -ne $Decision -and $Decision.PSObject.Properties['raisons'] -and $Decision.raisons) {
            $motifs = @(Get-PropOrDefault $Decision 'motifs' @())
            foreach ($p in $Decision.raisons.PSObject.Properties) {
                $i = [int]$p.Value
                if ($i -ge 0 -and $i -lt $motifs.Count) {
                    $texte = [string]$motifs[$i]
                    $table[$p.Name.ToLowerInvariant()] = $texte.Substring($texte.IndexOf('|') + 1)
                }
            }
        }
    } catch { }
    $script:Raisons = $table
}

function Get-Raison {
    # Le motif pour un programme ou un domaine (en remontant les sous-domaines).
    param([string]$Nom)
    $n = ([string]$Nom).ToLowerInvariant().Trim()
    $n = $n -replace '\\.exe$', ''
    while ($true) {
        if ($script:Raisons.ContainsKey($n)) { return [string]$script:Raisons[$n] }
        if ($n -notlike '*.*') { return '' }
        $n = $n.Substring($n.IndexOf('.') + 1)
    }
}

function Send-Demandes {"""
assert old in t
t = t.replace(old, new, 1)

old = """        [void](Send-Message -Texte "$joli n'est pas accessible en ce moment. Tu peux demander l'accès aux parents." `
            -Titre 'Vision' -Secondes 8 -Demande @{ genre = 'apps'; nom = $court; libelle = $joli })"""
new = """        $pourquoi = Get-Raison -Nom $court
        $phrase = "$joli n'est pas accessible en ce moment."
        if ($pourquoi) { $phrase = "$joli : $pourquoi" }
        [void](Send-Message -Texte "$phrase Tu peux demander l'accès aux parents." `
            -Titre 'Vision' -Secondes 8 -Demande @{ genre = 'apps'; nom = $court; libelle = $joli })"""
assert old in t, "Deny"
t = t.replace(old, new, 1)

old = """                    [void](Send-Message -Texte "$site n'est pas accessible en ce moment. Tu peux demander l'accès aux parents." `
                        -Titre 'Vision' -Secondes 8 -Son '' -Demande @{ genre = 'sites'; nom = $site; libelle = $site })"""
new = """                    $pourquoi = Get-Raison -Nom $site
                    $phrase = "$site n'est pas accessible en ce moment."
                    if ($pourquoi) { $phrase = "$site : $pourquoi" }
                    [void](Send-Message -Texte "$phrase Tu peux demander l'accès aux parents." `
                        -Titre 'Vision' -Secondes 8 -Son '' -Demande @{ genre = 'sites'; nom = $site; libelle = $site })"""
assert old in t, "proposer"
t = t.replace(old, new, 1)
open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.47.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.47.0"', 'CLIENT_VERSION = "1.48.0"', 1))
import py_compile
py_compile.compile(p, doraise=True)
print("ok")
