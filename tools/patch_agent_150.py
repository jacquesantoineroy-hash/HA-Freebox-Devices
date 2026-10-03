"""Agent ComVision 1.50.0 : fenêtre Vision (état, ce qui est fermé, demandes)
à la charte Vision, remplaçant les deux petites boîtes. À exécuter sur HA :
python3 patch_agent_150.py
"""
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak149")
assert "$script:Version           = '1.49.0'" in t
t = t.replace("$script:Version           = '1.49.0'", "$script:Version           = '1.50.0'", 1)

debut = t.index("$script:TraySource = @'")
fin = t.index("'@", debut) + 2
TRAY = r"""$script:TraySource = @'
param([string]$Dossier)

$verrou = New-Object Threading.Mutex($false, 'Local\VisionTray')
try { $tenu = $verrou.WaitOne(0) } catch [Threading.AbandonedMutexException] { $tenu = $true }
if (-not $tenu) { exit 0 }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# ------------------------------------------------------------ Charte Vision
$C = @{
    fond   = [System.Drawing.Color]::FromArgb(18, 6, 9)
    carte  = [System.Drawing.Color]::FromArgb(39, 17, 26)
    haute  = [System.Drawing.Color]::FromArgb(54, 23, 36)
    ligne  = [System.Drawing.Color]::FromArgb(76, 34, 49)
    or     = [System.Drawing.Color]::FromArgb(242, 193, 78)
    orS    = [System.Drawing.Color]::FromArgb(30, 22, 5)
    vert   = [System.Drawing.Color]::FromArgb(76, 195, 138)
    rouge  = [System.Drawing.Color]::FromArgb(255, 107, 107)
    texte  = [System.Drawing.Color]::FromArgb(251, 243, 238)
    texte2 = [System.Drawing.Color]::FromArgb(205, 168, 166)
    texte3 = [System.Drawing.Color]::FromArgb(140, 102, 108)
}
$F = @{
    corps  = New-Object System.Drawing.Font('Segoe UI', 10)
    petit  = New-Object System.Drawing.Font('Segoe UI', 9)
    gras   = New-Object System.Drawing.Font('Segoe UI Semibold', 10.5)
    titre  = New-Object System.Drawing.Font('Segoe UI Semibold', 20)
    section = New-Object System.Drawing.Font('Segoe UI Semibold', 8.5)
}

$logoPath = Join-Path $Dossier 'vision.png'
$icone = [System.Drawing.SystemIcons]::Shield
$logoImg = $null
if (Test-Path $logoPath) {
    try { $logoImg = [System.Drawing.Image]::FromFile($logoPath); $icone = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]$logoImg).GetHicon()) } catch { }
}

function Arrondir($ctrl, [int]$r) {
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $w = $ctrl.Width; $h = $ctrl.Height; $d = $r * 2
    $p.AddArc(0, 0, $d, $d, 180, 90); $p.AddArc($w - $d, 0, $d, $d, 270, 90)
    $p.AddArc($w - $d, $h - $d, $d, $d, 0, 90); $p.AddArc(0, $h - $d, $d, $d, 90, 90)
    $p.CloseFigure(); $ctrl.Region = New-Object System.Drawing.Region($p)
}

function Etiquette([string]$txt, $font, $couleur, [int]$x, [int]$y, [int]$w = 0) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $txt; $l.Font = $font; $l.ForeColor = $couleur; $l.BackColor = [System.Drawing.Color]::Transparent
    $l.Location = New-Object System.Drawing.Point($x, $y)
    if ($w -gt 0) { $l.AutoSize = $false; $l.Width = $w; $l.Height = 40 } else { $l.AutoSize = $true }
    return $l
}

function Carte([int]$x, [int]$y, [int]$w, [int]$h, $couleur = $null) {
    $p = New-Object System.Windows.Forms.Panel
    $p.Location = New-Object System.Drawing.Point($x, $y); $p.Size = New-Object System.Drawing.Size($w, $h)
    $p.BackColor = $(if ($couleur) { $couleur } else { $C.carte })
    Arrondir $p 16
    return $p
}

function Bouton([string]$txt, [string]$style, [int]$w = 140) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $txt; $b.Font = $F.gras; $b.FlatStyle = 'Flat'; $b.Height = 38; $b.Width = $w; $b.Cursor = 'Hand'
    $b.FlatAppearance.BorderSize = 0
    switch ($style) {
        'primaire' { $b.BackColor = $C.or; $b.ForeColor = $C.orS; $b.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(245, 204, 90) }
        'danger'   { $b.BackColor = $C.haute; $b.ForeColor = $C.rouge; $b.FlatAppearance.MouseOverBackColor = $C.ligne }
        default    { $b.BackColor = $C.haute; $b.ForeColor = $C.texte; $b.FlatAppearance.MouseOverBackColor = $C.ligne }
    }
    Arrondir $b 12
    return $b
}

function Champ([string]$indice, [int]$x, [int]$y, [int]$w) {
    $tb = New-Object System.Windows.Forms.TextBox
    $tb.Font = $F.corps; $tb.BackColor = $C.haute; $tb.ForeColor = $C.texte; $tb.BorderStyle = 'FixedSingle'
    $tb.Location = New-Object System.Drawing.Point($x, $y); $tb.Width = $w
    $tb.Tag = $indice; $tb.Text = $indice; $tb.ForeColor = $C.texte3
    $tb.Add_Enter({ param($s, $e) if ($s.Text -eq $s.Tag) { $s.Text = ''; $s.ForeColor = $C.texte } })
    $tb.Add_Leave({ param($s, $e) if (-not $s.Text) { $s.Text = $s.Tag; $s.ForeColor = $C.texte3 } })
    return $tb
}
function Valeur($tb) { if ($tb.Text -eq $tb.Tag) { return '' } else { return $tb.Text.Trim() } }

function Chip([string]$txt, $couleur, [int]$x, [int]$y) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $txt; $l.Font = $F.section; $l.ForeColor = $couleur; $l.BackColor = $C.haute
    $l.AutoSize = $false; $l.Size = New-Object System.Drawing.Size(88, 24); $l.TextAlign = 'MiddleCenter'
    $l.Location = New-Object System.Drawing.Point($x, $y)
    Arrondir $l 12
    return $l
}

# ------------------------------------------------------------ Données
function Deposer($objet) {
    $nom = Join-Path $Dossier ('demande-{0}.json' -f [DateTime]::UtcNow.Ticks)
    ($objet | ConvertTo-Json -Compress) | Set-Content -Path $nom -Encoding UTF8
}
function Lire([string]$fichier) {
    $f = Join-Path $Dossier $fichier
    if (-not (Test-Path $f)) { return $null }
    try { return (Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}
function Hote($lien) {
    $l = ([string]$lien).Trim()
    if (-not $l) { return '' }
    if ($l -notmatch '^[a-z][a-z0-9+.-]*://') { $l = 'https://' + $l }
    try { return ([Uri]$l).Host.ToLowerInvariant() -replace '^www\.', '' } catch { return '' }
}
$script:Demandees = @{}

# ------------------------------------------------------------ La fenêtre
$script:Fenetre = $null

function Fenetre {
    if ($script:Fenetre -and -not $script:Fenetre.IsDisposed) { $script:Fenetre.Activate(); return }
    $etat = Lire 'etat.json'
    $data = Lire 'fermes.json'
    $ferme = ($null -ne $etat -and [bool]$etat.ferme)

    $f = New-Object System.Windows.Forms.Form
    $script:Fenetre = $f
    $f.Text = 'Vision'; $f.Icon = $icone; $f.BackColor = $C.fond; $f.ForeColor = $C.texte
    $f.FormBorderStyle = 'FixedSingle'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
    $f.StartPosition = 'CenterScreen'; $f.ClientSize = New-Object System.Drawing.Size(560, 640); $f.TopMost = $true
    $f.Font = $F.corps

    # En-tête
    if ($logoImg) {
        $pb = New-Object System.Windows.Forms.PictureBox
        $pb.Image = $logoImg; $pb.SizeMode = 'Zoom'; $pb.Size = New-Object System.Drawing.Size(44, 44)
        $pb.Location = New-Object System.Drawing.Point(24, 20); $pb.BackColor = [System.Drawing.Color]::Transparent
        $f.Controls.Add($pb)
    }
    $f.Controls.Add((Etiquette 'Vision' $F.titre $C.texte 78 14))
    $f.Controls.Add((Etiquette 'Le contrôle parental de la maison' $F.petit $C.texte2 80 46))

    # Carte état
    $cE = Carte 24 80 512 96 $C.haute
    $texteEtat = 'Vision : accès ouvert'
    if ($null -ne $etat -and $etat.texte) { $texteEtat = [string]$etat.texte }
    $cE.Controls.Add((Etiquette $env:USERNAME $F.gras $C.texte 20 16))
    $cE.Controls.Add((Etiquette $texteEtat $F.petit $C.texte2 20 40 380))
    $cE.Controls.Add((Chip $(if ($ferme) { 'FERMÉ' } else { 'OUVERT' }) $(if ($ferme) { $C.rouge } else { $C.vert }) 404 18))
    if ($ferme) {
        $x = 20
        foreach ($m in 15, 30, 60) {
            $b = Bouton ('+{0} min' -f $m) 'secondaire' 88
            $b.Location = New-Object System.Drawing.Point($x, 56); $b.Height = 30; $b.Tag = $m
            $b.Add_Click({ param($s, $e) Deposer @{ genre = 'temps'; minutes = [int]$s.Tag }; $s.Text = 'Envoyé'; $s.Enabled = $false })
            $cE.Controls.Add($b); $x += 96
        }
    }
    $f.Controls.Add($cE)

    # Section « ce qui est fermé »
    $f.Controls.Add((Etiquette 'CE QUI EST FERMÉ ICI' $F.section $C.or 28 190))
    $f.Controls.Add((Etiquette "Touche une ligne, puis « Demander » : un parent répond sur son téléphone." $F.petit $C.texte2 28 208))
    $filtre = Champ 'Chercher une appli ou un site' 24 232 512
    $f.Controls.Add($filtre)

    $cL = Carte 24 268 512 270
    $liste = New-Object System.Windows.Forms.ListView
    $liste.View = 'Details'; $liste.FullRowSelect = $true; $liste.MultiSelect = $false; $liste.HideSelection = $false
    $liste.HeaderStyle = 'None'; $liste.BackColor = $C.carte; $liste.ForeColor = $C.texte; $liste.Font = $F.corps; $liste.BorderStyle = 'None'
    $liste.Location = New-Object System.Drawing.Point(12, 12); $liste.Size = New-Object System.Drawing.Size(488, 246)
    [void]$liste.Columns.Add('Quoi', 170)
    [void]$liste.Columns.Add('Pourquoi', 296)
    $cL.Controls.Add($liste)
    $f.Controls.Add($cL)

    $remplir = {
        $liste.BeginUpdate(); $liste.Items.Clear(); $liste.Groups.Clear()
        $q = (Valeur $filtre).ToLowerInvariant()
        if ($null -ne $data) {
            $gA = $liste.Groups.Add('apps', 'Logiciels')
            $gS = $liste.Groups.Add('sites', 'Sites')
            foreach ($a in @($data.apps)) {
                if ($q -and ([string]$a.nom).ToLowerInvariant() -notlike "*$q*") { continue }
                $it = New-Object System.Windows.Forms.ListViewItem(([string]$a.nom))
                [void]$it.SubItems.Add([string]$a.raison); $it.Group = $gA; $it.Tag = @{ genre = 'apps'; nom = [string]$a.nom }
                if ($script:Demandees.ContainsKey('apps:' + $a.nom)) { $it.ForeColor = $C.texte3 }
                [void]$liste.Items.Add($it)
            }
            $tries = @($data.sites | Sort-Object -Property @{ Expression = { -not $_.recent } }, nom)
            foreach ($s in $tries) {
                if ($q -and ([string]$s.nom).ToLowerInvariant() -notlike "*$q*") { continue }
                $it = New-Object System.Windows.Forms.ListViewItem(([string]$s.nom))
                [void]$it.SubItems.Add([string]$s.raison); $it.Group = $gS; $it.Tag = @{ genre = 'sites'; nom = [string]$s.nom }
                if ($s.recent) { $it.ForeColor = $C.or }
                if ($script:Demandees.ContainsKey('sites:' + $s.nom)) { $it.ForeColor = $C.texte3 }
                [void]$liste.Items.Add($it)
            }
        }
        $liste.EndUpdate()
    }
    & $remplir
    $filtre.Add_TextChanged({ & $remplir })

    # Pied : motif, lien pour un autre site, envoyer
    $motif = Champ 'Pourquoi ? (facultatif, les parents le verront)' 24 552 512
    $f.Controls.Add($motif)
    $lien = Champ 'Ou un autre site : colle le lien ici' 24 588 328
    try {
        $presse = [System.Windows.Forms.Clipboard]::GetText()
        if ($presse -match '^https?://\S+$') { $lien.Text = $presse.Trim(); $lien.ForeColor = $C.texte }
    } catch { }
    $f.Controls.Add($lien)
    $ok = Bouton "Demander l'accès" 'primaire' 172
    $ok.Location = New-Object System.Drawing.Point(364, 586)
    $f.Controls.Add($ok)
    $ok.Add_Click({
        $l = Valeur $lien
        $m = Valeur $motif
        if ($l) {
            $h = Hote $l
            if (-not $h -or $h -notlike '*.*') {
                [System.Windows.Forms.MessageBox]::Show('Ce lien ne ressemble pas à un site. Exemple : youtube.com', 'Vision') | Out-Null
                return
            }
            Deposer @{ genre = 'sites'; nom = $h; libelle = $h; lien = $l; motif = $m }
            $script:Demandees['sites:' + $h] = $true
        } elseif ($liste.SelectedItems.Count -gt 0) {
            $sel = $liste.SelectedItems[0].Tag
            Deposer @{ genre = $sel.genre; nom = $sel.nom; libelle = $sel.nom; lien = ''; motif = $m }
            $script:Demandees[$sel.genre + ':' + $sel.nom] = $true
        } else {
            [System.Windows.Forms.MessageBox]::Show("Choisis une ligne dans la liste, ou colle le lien d'un site.", 'Vision') | Out-Null
            return
        }
        $ok.Text = 'Envoyé ✓'; $ok.Enabled = $false
        $lien.Text = $lien.Tag; $lien.ForeColor = $C.texte3
        & $remplir
        $timer = New-Object System.Windows.Forms.Timer; $timer.Interval = 2500
        $timer.Add_Tick({ param($s, $e) $ok.Text = "Demander l'accès"; $ok.Enabled = $true; $s.Stop(); $s.Dispose() })
        $timer.Start()
    })
    $liste.Add_DoubleClick({ $ok.PerformClick() })
    $f.Add_FormClosed({ $script:Fenetre = $null })
    # Modale : la fonction reste vivante, et les boutons gardent leurs variables.
    [void]$f.ShowDialog()
    $f.Dispose()
}

# ------------------------------------------------------------ L'icône
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = $icone; $tray.Text = 'Vision'; $tray.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$menu.Font = $F.corps
$ouvrir = $menu.Items.Add('Ouvrir Vision')
$ouvrir.Font = $F.gras
$ouvrir.Add_Click({ Fenetre })
$menu.Items.Add('-') | Out-Null
$etatItem = $menu.Items.Add('Vision')
$etatItem.Enabled = $false
$menu.Add_Opening({
    $e = Lire 'etat.json'
    if ($null -ne $e -and $e.texte) { $etatItem.Text = [string]$e.texte } else { $etatItem.Text = 'Vision : accès ouvert' }
})
$tray.ContextMenuStrip = $menu
$tray.Add_MouseClick({ param($s, $e) if ($e.Button -eq 'Left') { Fenetre } })

# Info-bulle vivante : ouvert ou fermé.
$horloge = New-Object System.Windows.Forms.Timer; $horloge.Interval = 30000
$horloge.Add_Tick({
    $e = Lire 'etat.json'
    $txt = 'Vision'
    if ($null -ne $e -and $e.texte) { $txt = [string]$e.texte }
    if ($txt.Length -gt 63) { $txt = $txt.Substring(0, 63) }
    $tray.Text = $txt
})
$horloge.Start()

[System.Windows.Forms.Application]::Run()
'@"""
t = t[:debut] + TRAY + t[fin:]
open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.49.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.49.0"', 'CLIENT_VERSION = "1.50.0"', 1))
import py_compile
py_compile.compile(p, doraise=True)
print("ok")
