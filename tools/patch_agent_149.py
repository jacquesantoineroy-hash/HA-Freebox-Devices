"""Agent ComVision 1.49.0 : plus de notification pour les sites fermés ; la liste
« Ce qui est fermé » (avec les motifs) dans l'icône Vision, d'où l'enfant
demande l'accès. À exécuter sur HA : python3 patch_agent_149.py
"""
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak148")
assert "$script:Version           = '1.48.0'" in t
t = t.replace("$script:Version           = '1.48.0'", "$script:Version           = '1.49.0'", 1)
t = t.replace("$script:EtatSondePath     = Join-Path $script:SondeDir 'etat.json'\n",
              "$script:EtatSondePath     = Join-Path $script:SondeDir 'etat.json'\n"
              "$script:FermesPath        = Join-Path $script:SondeDir 'fermes.json'\n", 1)

# --- Plus de toast pour les sites proposés -----------------------------------------
debut = t.index("            # Home Assistant désigne les sites fermés par une règle que")
fin = t.index("            if ($decision.action -eq 'uninstall') {")
t = t[:debut] + t[fin:]

# --- Écrire la liste de ce qui est fermé, avec les motifs ---------------------------
old = """function Send-Demandes {"""
new = """function Write-Fermes {
    <#
        Ce qui est fermé sur ce PC, avec le motif, pour la fenêtre de l'icône.
        Les blocages de sécurité (sites dangereux, traçage) n'y figurent pas :
        on ne les montre pas, on ne les discute pas.
    #>
    param($Decision)
    try {
        $apps = @(); $sites = @()
        $vus = @{}
        foreach ($n in @($script:DernierVu)) { if ($n) { $vus[[string]$n] = $true } }
        foreach ($a in @(Get-PropOrDefault $Decision 'apps' @())) {
            $a = [string]$a
            if (-not $a -or $a -like '*.*') { continue }   # paquets Android : pas pour ce PC
            $r = Get-Raison -Nom $a
            if ($r -like 'Bloqué pour ta sécurité*') { continue }
            $apps += @{ nom = $a; raison = $r }
        }
        foreach ($s in @(Get-PropOrDefault $Decision 'sites' @())) {
            $s = [string]$s
            if (-not $s) { continue }
            # Un domaine par site : les sous-domaines et CDN n'apportent rien.
            if (($s.Split('.')).Count -gt 2) { continue }
            $r = Get-Raison -Nom $s
            if (-not $r -or $r -like 'Bloqué pour ta sécurité*') { continue }
            $sites += @{ nom = $s; raison = $r; recent = [bool]$vus.ContainsKey($s) }
        }
        @{ apps = $apps; sites = $sites; quand = (Get-Date -Format 'HH:mm') } |
            ConvertTo-Json -Compress -Depth 4 | Set-Content -Path $script:FermesPath -Encoding UTF8
    } catch { }
}

function Send-Demandes {"""
assert old in t
t = t.replace(old, new, 1)

old = """            Read-Raisons -Decision $decision"""
new = """            Read-Raisons -Decision $decision
            Write-Fermes -Decision $decision"""
assert old in t
t = t.replace(old, new, 1)

# Toast de logiciel refusé : sans son.
old = """        [void](Send-Message -Texte "$phrase Tu peux demander l'accès aux parents." `
            -Titre 'Vision' -Secondes 8 -Demande @{ genre = 'apps'; nom = $court; libelle = $joli })"""
new = """        [void](Send-Message -Texte "$phrase Tu peux demander l'accès aux parents." `
            -Titre 'Vision' -Secondes 8 -Son '' -Demande @{ genre = 'apps'; nom = $court; libelle = $joli })"""
assert old in t
t = t.replace(old, new, 1)

# --- Fenêtre « Ce qui est fermé » dans l'icône -------------------------------------
old = """function Lire-Etat {"""
new = """function Lire-Fermes {
    $f = Join-Path $Dossier 'fermes.json'
    if (-not (Test-Path $f)) { return $null }
    try { return (Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}

function FenetreFermes {
    $data = Lire-Fermes
    $f = New-Object System.Windows.Forms.Form
    $f.Text = 'Vision : ce qui est fermé'; $f.Icon = $icone; $f.BackColor = $fond; $f.ForeColor = $texte
    $f.StartPosition = 'CenterScreen'; $f.ClientSize = New-Object System.Drawing.Size(640, 460); $f.TopMost = $true
    $f.MinimizeBox = $false

    $t1 = New-Object System.Windows.Forms.Label
    $t1.Text = 'Ce qui est fermé sur ce PC'; $t1.Font = $grasse; $t1.ForeColor = $or
    $t1.AutoSize = $true; $t1.Location = New-Object System.Drawing.Point(20, 16)
    $f.Controls.Add($t1)
    $l0 = New-Object System.Windows.Forms.Label
    $l0.Text = 'Choisis une ligne puis « Demander l''accès » : un parent répond sur son téléphone.'
    $l0.Font = $police; $l0.ForeColor = $texte2; $l0.AutoSize = $true; $l0.Location = New-Object System.Drawing.Point(20, 48)
    $f.Controls.Add($l0)

    $filtre = New-Object System.Windows.Forms.TextBox
    $filtre.Font = $police; $filtre.BackColor = $carte; $filtre.ForeColor = $texte; $filtre.BorderStyle = 'FixedSingle'
    $filtre.Location = New-Object System.Drawing.Point(20, 76); $filtre.Width = 600
    $f.Controls.Add($filtre)

    $liste = New-Object System.Windows.Forms.ListView
    $liste.View = 'Details'; $liste.FullRowSelect = $true; $liste.MultiSelect = $false; $liste.HideSelection = $false
    $liste.BackColor = $carte; $liste.ForeColor = $texte; $liste.Font = $police; $liste.BorderStyle = 'None'
    $liste.Location = New-Object System.Drawing.Point(20, 110); $liste.Size = New-Object System.Drawing.Size(600, 290)
    [void]$liste.Columns.Add('Quoi', 200)
    [void]$liste.Columns.Add('Pourquoi', 396)
    $f.Controls.Add($liste)

    $remplir = {
        $liste.BeginUpdate(); $liste.Items.Clear()
        $q = $filtre.Text.Trim().ToLowerInvariant()
        if ($null -ne $data) {
            $gA = $liste.Groups.Add('apps', 'Logiciels')
            $gS = $liste.Groups.Add('sites', 'Sites')
            foreach ($a in @($data.apps)) {
                if ($q -and ([string]$a.nom).ToLowerInvariant() -notlike "*$q*") { continue }
                $it = New-Object System.Windows.Forms.ListViewItem(([string]$a.nom))
                [void]$it.SubItems.Add([string]$a.raison); $it.Group = $gA; $it.Tag = @{ genre = 'apps'; nom = [string]$a.nom }
                [void]$liste.Items.Add($it)
            }
            $tries = @($data.sites | Sort-Object -Property @{ Expression = { -not $_.recent } }, nom)
            foreach ($s in $tries) {
                if ($q -and ([string]$s.nom).ToLowerInvariant() -notlike "*$q*") { continue }
                $it = New-Object System.Windows.Forms.ListViewItem(([string]$s.nom))
                [void]$it.SubItems.Add([string]$s.raison); $it.Group = $gS; $it.Tag = @{ genre = 'sites'; nom = [string]$s.nom }
                if ($s.recent) { $it.ForeColor = $or }
                [void]$liste.Items.Add($it)
            }
        }
        $liste.EndUpdate()
    }
    & $remplir
    $filtre.Add_TextChanged({ & $remplir })

    $ok = Bouton "Demander l'accès" $true
    $ok.Width = 170; $ok.Location = New-Object System.Drawing.Point(450, 412)
    $autre = Bouton 'Un autre site…' $false
    $autre.Width = 150; $autre.Location = New-Object System.Drawing.Point(290, 412)
    $f.Controls.Add($ok); $f.Controls.Add($autre)
    $autre.Add_Click({ $f.Close(); Formulaire })
    $ok.Add_Click({
        if ($liste.SelectedItems.Count -eq 0) { return }
        $sel = $liste.SelectedItems[0].Tag
        $motif = [Microsoft.VisualBasic.Interaction]::InputBox("Pourquoi en as-tu besoin ? (facultatif, les parents le verront)", 'Vision', '')
        Deposer @{ genre = $sel.genre; nom = $sel.nom; libelle = $sel.nom; lien = ''; motif = [string]$motif }
        $f.Close()
    })
    $liste.Add_DoubleClick({ $ok.PerformClick() })
    [void]$f.ShowDialog()
    $f.Dispose()
}

function Lire-Etat {"""
assert old in t, "tray"
t = t.replace(old, new, 1)
t = t.replace("""Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()""",
"""Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic
[System.Windows.Forms.Application]::EnableVisualStyles()""", 1)
old = """$site = $menu.Items.Add("Demander l'accès à un site…")
$site.Add_Click({ Formulaire })"""
new = """$fermes = $menu.Items.Add("Ce qui est fermé, et demander l'accès…")
$fermes.Add_Click({ FenetreFermes })
$site = $menu.Items.Add("Demander l'accès à un site…")
$site.Add_Click({ Formulaire })"""
assert old in t, "menu"
t = t.replace(old, new, 1)
t = t.replace("$tray.Add_DoubleClick({ Formulaire })", "$tray.Add_DoubleClick({ FenetreFermes })", 1)
open(AGENT, "w", encoding="utf-8").write(t)

# --- HA : plus de proposer_acces dans le poll ----------------------------------------
p = BASE + "http.py"
h = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakand12")
old = """        if _proposer:
            reponse["proposer_acces"] = _proposer
"""
if old in h:
    h = h.replace(old, "", 1)
    open(p, "w", encoding="utf-8").write(h)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.48.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.48.0"', 'CLIENT_VERSION = "1.49.0"', 1))
import py_compile
for f in ("const.py", "http.py"):
    py_compile.compile(BASE + f, doraise=True)
print("ok", t.count("FenetreFermes"), t.count("proposer_acces"))
