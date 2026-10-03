"""Agent ComVision 1.51.0 : l'espace parents dans la fenêtre Vision du PC d'un
parent (enfants, état, ce qui est coupé par motif avec réactivation, planning,
temps, mot). L'agent (SYSTEM) sert d'intermédiaire : il écrit maison.json pour
la fenêtre et envoie ses actions à Home Assistant.
À exécuter sur HA : python3 patch_agent_151.py
"""
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak1501")
assert "$script:Version           = '1.50.1'" in t
t = t.replace("$script:Version           = '1.50.1'", "$script:Version           = '1.51.0'", 1)
t = t.replace("$script:FermesPath        = Join-Path $script:SondeDir 'fermes.json'\n",
              "$script:FermesPath        = Join-Path $script:SondeDir 'fermes.json'\n"
              "$script:MaisonPath        = Join-Path $script:SondeDir 'maison.json'\n"
              "$script:EstParent         = $false\n"
              "$script:DerniereMaison    = [datetime]::MinValue\n", 1)

# --- Agent : synchronisation de l'espace parents et envoi des actions -------------
old = "function Send-Demandes {"
new = """function Sync-Maison {
    <#
        Sur le PC d'un parent (étiquette « Parents » dans Vision), l'agent va
        chercher l'état des appareils de la maison et le dépose pour la
        fenêtre. Le secret ne quitte jamais le dossier de configuration : la
        fenêtre, qui tourne chez l'utilisateur, ne lit que le résultat.
    #>
    param($Config, [bool]$Force = $false)
    if (-not $script:EstParent) {
        if (Test-Path $script:MaisonPath) { Remove-Item $script:MaisonPath -Force -ErrorAction SilentlyContinue }
        return
    }
    if (-not $Force -and ((Get-Date) - $script:DerniereMaison).TotalSeconds -lt 60) { return }
    try {
        $r = Invoke-Ha -Chemin '/api/pc_parental/parent' -Corps @{ id = $Config.id; secret = $Config.secret } -Config $Config
        if ($null -ne $r -and (Get-PropOrDefault $r 'ok' $false)) {
            $r | ConvertTo-Json -Depth 12 -Compress | Set-Content -Path $script:MaisonPath -Encoding UTF8
            $script:DerniereMaison = Get-Date
        }
    } catch {
        Write-Journal "Espace parents non rafraîchi : $_" 'WARN'
    }
}

function Send-Actions {
    # Les actions du parent déposées par la fenêtre (action-*.json) partent à
    # Home Assistant avec le secret de ce PC ; puis l'espace est rafraîchi.
    param($Config)
    if ($null -eq $Config -or -not $script:EstParent -or -not (Test-Path $script:SondeDir)) { return }
    $fichiers = @(Get-ChildItem -Path $script:SondeDir -Filter 'action-*.json' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -First 5)
    $fait = $false
    foreach ($f in $fichiers) {
        $a = $null
        try { $a = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json } catch { }
        Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
        if ($null -eq $a -or -not (Get-PropOrDefault $a 'action' '')) { continue }
        $corps = @{ id = $Config.id; secret = $Config.secret }
        foreach ($p in $a.PSObject.Properties) { $corps[$p.Name] = $p.Value }
        try {
            $r = Invoke-Ha -Chemin '/api/pc_parental/parent' -Corps $corps -Config $Config
            $retour = [string](Get-PropOrDefault $r 'retour' '')
            if ($retour) { [void](Send-Message -Texte $retour -Titre 'Vision' -Secondes 6 -Son '') }
            $fait = $true
        } catch {
            Write-Journal "Action parent refusée : $_" 'WARN'
            [void](Send-Message -Texte "Action refusée par Home Assistant." -Titre 'Vision' -Secondes 6 -Son '')
        }
    }
    if ($fait) { Sync-Maison -Config $Config -Force $true }
}

function Send-Demandes {"""
assert old in t
t = t.replace(old, new, 1)

old = """            Read-Raisons -Decision $decision
            Write-Fermes -Decision $decision"""
new = """            Read-Raisons -Decision $decision
            Write-Fermes -Decision $decision
            $script:EstParent = [bool](Get-PropOrDefault $decision 'parent' $false)
            try { Sync-Maison -Config $config } catch { }"""
assert old in t
t = t.replace(old, new, 1)
old = """            try { Send-Demandes -Config $script:ConfigCourante } catch { }"""
new = """            try { Send-Demandes -Config $script:ConfigCourante } catch { }
            try { Send-Actions -Config $script:ConfigCourante } catch { }"""
assert old in t
t = t.replace(old, new, 1)
old = """        try { Send-Demandes -Config $config } catch { Write-Journal "Demandes : $_" 'WARN' }"""
new = """        try { Send-Demandes -Config $config } catch { Write-Journal "Demandes : $_" 'WARN' }
        try { Send-Actions -Config $config } catch { Write-Journal "Actions : $_" 'WARN' }"""
assert old in t
t = t.replace(old, new, 1)

# --- Fenêtre : onglet « La maison » ------------------------------------------------
# On insère les fonctions de l'espace parents avant « function Fenetre {", et on
# transforme la fenêtre en deux onglets quand maison.json existe.
old = "# ------------------------------------------------------------ La fenêtre\n$script:Fenetre = $null\n"
new = r"""# ------------------------------------------------------------ Espace parents
function Agir($objet) {
    $nom = Join-Path $Dossier ('action-{0}.json' -f [DateTime]::UtcNow.Ticks)
    ($objet | ConvertTo-Json -Compress) | Set-Content -Path $nom -Encoding UTF8
}

function Heure([string]$iso) {
    if (-not $iso) { return '' }
    try { return ([datetime]$iso).ToString('HH\hmm') } catch { return '' }
}

function ResumeAppareil($a) {
    $d = $a.derogation
    if ($null -ne $d -and $d) {
        $fin = [double](Get-PropOrDefault $d 'fin' 0)
        $quand = if ($fin -gt 0) { ' jusqu''à ' + ([DateTimeOffset]::FromUnixTimeSeconds([long]$fin).ToLocalTime().ToString('HH\hmm')) } else { ' jusqu''au prochain créneau' }
        if ([string]$d.mode -eq 'locked') { return 'Fermé par un parent' + $quand } else { return 'Ouvert par un parent' + $quand }
    }
    if ($a.verrouille) {
        $h = Heure ([string]$a.prochain)
        if ($h) { return "Réouverture à $h" } else { return 'Fermé par le planning' }
    }
    $h = Heure ([string]$a.prochain_verrou)
    if ($h) { return "Fermeture prévue à $h" } else { return 'Aucune fermeture prévue' }
}

function FenetreFermesEnfant($a) {
    $f = New-Object System.Windows.Forms.Form
    $prenom = [string]$a.prenom; if (-not $prenom) { $prenom = [string]$a.nom }
    $f.Text = "Vision : ce qui est fermé chez $prenom"; $f.Icon = $icone; $f.BackColor = $C.fond; $f.ForeColor = $C.texte
    $f.StartPosition = 'CenterParent'; $f.ClientSize = New-Object System.Drawing.Size(640, 560); $f.TopMost = $true; $f.MinimizeBox = $false
    $f.Controls.Add((Etiquette "Ce qui est fermé chez $prenom" $F.titre $C.texte 24 14))
    $f.Controls.Add((Etiquette ([string]$a.nom) $F.petit $C.texte2 26 50))
    $filtre = Champ 'Chercher' 24 76 592
    $f.Controls.Add($filtre)
    $cL = Carte 24 112 592 380
    $liste = New-Object System.Windows.Forms.ListView
    $liste.View = 'Details'; $liste.FullRowSelect = $true; $liste.MultiSelect = $false; $liste.HideSelection = $false
    $liste.HeaderStyle = 'None'; $liste.BackColor = $C.carte; $liste.ForeColor = $C.texte; $liste.Font = $F.corps; $liste.BorderStyle = 'None'
    $liste.Location = New-Object System.Drawing.Point(12, 12); $liste.Size = New-Object System.Drawing.Size(568, 356)
    [void]$liste.Columns.Add('Quoi', 220); [void]$liste.Columns.Add('Type', 70); [void]$liste.Columns.Add('Motif', 260)
    $cL.Controls.Add($liste); $f.Controls.Add($cL)

    $motifs = @(Get-PropOrDefault $a 'motifs' @())
    $raisons = Get-PropOrDefault $a 'raisons' $null
    $titres = @{ plage = 'Planning'; moyenne = 'Moyenne'; regle = 'Décision des parents'; age = 'Âge (PEGI)'; maison = 'Toute la maison'; securite = 'Sécurité' }
    $ordre = @('plage', 'moyenne', 'regle', 'age', 'maison', 'securite')
    $motifDe = {
        param($nom)
        $n = ([string]$nom).ToLowerInvariant()
        while ($true) {
            if ($null -ne $raisons -and $raisons.PSObject.Properties[$n]) {
                $i = [int]$raisons.$n
                if ($i -ge 0 -and $i -lt $motifs.Count) { return [string]$motifs[$i] }
                return ''
            }
            if ($n -notlike '*.*') { return '' }
            $n = $n.Substring($n.IndexOf('.') + 1)
        }
    }
    $remplir = {
        $liste.BeginUpdate(); $liste.Items.Clear(); $liste.Groups.Clear()
        $q = (Valeur $filtre).ToLowerInvariant()
        $groupes = @{}
        foreach ($code in $ordre) { $groupes[$code] = $liste.Groups.Add($code, $titres[$code]) }
        $elements = @()
        foreach ($x in @($a.apps)) { $elements += @{ genre = 'Appli'; g = 'apps'; nom = [string]$x.nom; lib = [string]$x.libelle } }
        foreach ($x in @($a.sites)) {
            $n = [string]$x.nom
            if (($n.Split('.')).Count -ne 2) { continue }
            $elements += @{ genre = 'Site'; g = 'sites'; nom = $n; lib = $n }
        }
        foreach ($e in $elements) {
            if ($q -and $e.lib.ToLowerInvariant() -notlike "*$q*" -and $e.nom -notlike "*$q*") { continue }
            $m = & $motifDe $e.nom
            $code = 'regle'; $texte = 'Coupé par les parents.'
            if ($m) { $code = $m.Substring(0, $m.IndexOf('|')); $texte = $m.Substring($m.IndexOf('|') + 1) }
            if (-not $groupes.ContainsKey($code)) { $code = 'regle' }
            $it = New-Object System.Windows.Forms.ListViewItem($e.lib)
            [void]$it.SubItems.Add($e.genre); [void]$it.SubItems.Add($texte)
            $it.Group = $groupes[$code]; $it.Tag = @{ genre = $e.g; nom = $e.nom; code = $code; lib = $e.lib }
            if ($code -eq 'securite') { $it.ForeColor = $C.texte3 }
            [void]$liste.Items.Add($it)
        }
        $liste.EndUpdate()
    }
    & $remplir
    $filtre.Add_TextChanged({ & $remplir })

    $x = 24
    foreach ($def in @(@('30 min', 'temporaire', 30), @('1 h', 'temporaire', 60), @('2 h', 'temporaire', 120), @('Toujours', 'toujours', 0))) {
        $b = Bouton ([string]$def[0]) $(if ($def[1] -eq 'toujours') { 'primaire' } else { 'secondaire' }) 118
        $b.Location = New-Object System.Drawing.Point($x, 506); $b.Tag = $def
        $b.Add_Click({
            param($s, $e)
            if ($liste.SelectedItems.Count -eq 0) { [System.Windows.Forms.MessageBox]::Show('Choisis une ligne.', 'Vision') | Out-Null; return }
            $sel = $liste.SelectedItems[0].Tag
            if ($sel.code -eq 'securite') { [System.Windows.Forms.MessageBox]::Show('Les blocages de sécurité se lèvent dans Vision, pas ici.', 'Vision') | Out-Null; return }
            $d = $s.Tag
            Agir @{ action = 'autoriser'; pc = [string]$a.id; genre = $sel.genre; nom = $sel.nom; decision = [string]$d[1]; minutes = [int]$d[2] }
            $liste.SelectedItems[0].ForeColor = $C.vert
        })
        $f.Controls.Add($b); $x += 126
    }
    $f.Controls.Add((Etiquette 'Ouvrir la ligne choisie :' $F.petit $C.texte2 26 490))
    [void]$f.ShowDialog(); $f.Dispose()
}

function FenetrePlanning($a) {
    $f = New-Object System.Windows.Forms.Form
    $prenom = [string]$a.prenom; if (-not $prenom) { $prenom = [string]$a.nom }
    $f.Text = "Vision : planning de $prenom"; $f.Icon = $icone; $f.BackColor = $C.fond; $f.ForeColor = $C.texte
    $f.StartPosition = 'CenterParent'; $f.ClientSize = New-Object System.Drawing.Size(640, 420); $f.TopMost = $true; $f.MinimizeBox = $false
    $f.Controls.Add((Etiquette "Planning de $prenom" $F.titre $C.texte 24 14))
    $f.Controls.Add((Etiquette 'Les plages se modifient dans le tableau Vision de Home Assistant.' $F.petit $C.texte2 26 50))
    $cL = Carte 24 80 592 316
    $liste = New-Object System.Windows.Forms.ListView
    $liste.View = 'Details'; $liste.FullRowSelect = $true; $liste.BackColor = $C.carte; $liste.ForeColor = $C.texte; $liste.Font = $F.corps; $liste.BorderStyle = 'None'
    $liste.Location = New-Object System.Drawing.Point(12, 12); $liste.Size = New-Object System.Drawing.Size(568, 292)
    [void]$liste.Columns.Add('Plage', 130); [void]$liste.Columns.Add('Horaires', 110); [void]$liste.Columns.Add('Jours', 130); [void]$liste.Columns.Add('Ferme', 190)
    $jours = @('L', 'M', 'M', 'J', 'V', 'S', 'D')
    foreach ($p in @($a.plages)) {
        $it = New-Object System.Windows.Forms.ListViewItem(([string]$p.nom))
        [void]$it.SubItems.Add(('{0} → {1}' -f [string]$p.debut, [string]$p.fin))
        $js = @($p.jours); $lettres = @()
        for ($i = 0; $i -lt 7; $i++) { if ($i -lt $js.Count -and [bool]$js[$i]) { $lettres += $jours[$i] } else { $lettres += '·' } }
        [void]$it.SubItems.Add(($lettres -join ' '))
        $quoi = switch ([string]$p.portee) {
            'etiquettes' { 'Coupe : ' + ((@($p.etiquettes)) -join ', ') }
            'elements' { 'Des applis ou sites précis' }
            default { "Tout l'appareil" }
        }
        [void]$it.SubItems.Add($quoi)
        if ([bool]$p.actif) { $it.ForeColor = $C.or }
        if (-not [bool]$p.active) { $it.ForeColor = $C.texte3 }
        [void]$liste.Items.Add($it)
    }
    $cL.Controls.Add($liste); $f.Controls.Add($cL)
    [void]$f.ShowDialog(); $f.Dispose()
}

function OngletMaison($page) {
    # Le contenu de l'onglet « La maison » : un appareil d'enfant par carte.
    $page.Controls.Clear()
    $maison = Lire 'maison.json'
    $y = 12
    if ($null -eq $maison) {
        $page.Controls.Add((Etiquette "L'espace parents se charge…" $F.corps $C.texte2 16 16))
        return
    }
    $demandes = @(Get-PropOrDefault $maison 'demandes' @())
    if ($demandes.Count -gt 0) {
        $page.Controls.Add((Etiquette "DEMANDES D'ACCÈS" $F.section $C.or 16 $y)); $y += 20
        foreach ($d in $demandes) {
            $c = Carte 12 $y 500 92 $C.haute
            $titre = ('{0} demande {1}' -f [string]$d.prenom, [string]$d.libelle)
            $c.Controls.Add((Etiquette $titre $F.gras $C.texte 16 10))
            $detail = @()
            if ($d.lien) { $detail += [string]$d.lien }
            if ($d.motif) { $detail += ('« {0} »' -f [string]$d.motif) }
            if ($d.raison) { $detail += ('Fermé car : {0}' -f [string]$d.raison) }
            $c.Controls.Add((Etiquette ($detail -join '   ') $F.petit $C.texte2 16 32 470))
            $x = 16
            foreach ($def in @(@('1 h', 'temporaire', 60), @('Toujours', 'toujours', 0), @('Non', 'non', 0))) {
                $b = Bouton ([string]$def[0]) $(if ($def[1] -eq 'non') { 'danger' } elseif ($def[1] -eq 'toujours') { 'primaire' } else { 'secondaire' }) 100
                $b.Location = New-Object System.Drawing.Point($x, 56); $b.Height = 28; $b.Tag = @{ d = $d; def = $def }
                $b.Add_Click({ param($s, $e)
                    $t = $s.Tag
                    Agir @{ action = 'acces'; pc = [string]$t.d.pc; demande = [string]$t.d.id; decision = [string]$t.def[1]; minutes = [int]$t.def[2] }
                    $s.Parent.Enabled = $false
                })
                $c.Controls.Add($b); $x += 108
            }
            $page.Controls.Add($c); $y += 100
        }
    }
    $page.Controls.Add((Etiquette 'LES ENFANTS' $F.section $C.or 16 $y)); $y += 20
    foreach ($a in @($maison.appareils)) {
        if ([bool]$a.parent) { continue }
        $c = Carte 12 $y 500 150
        $prenom = [string]$a.prenom; if (-not $prenom) { $prenom = [string]$a.nom }
        $c.Controls.Add((Etiquette $prenom $F.gras $C.texte 16 12))
        $c.Controls.Add((Etiquette ([string]$a.nom) $F.petit $C.texte2 16 32))
        $etatTxt = 'OUVERT'; $etatCoul = $C.vert
        if (-not [bool]$a.en_ligne) { $etatTxt = 'HORS LIGNE'; $etatCoul = $C.texte2 }
        elseif ([bool]$a.verrouille) { $etatTxt = 'FERMÉ'; $etatCoul = $C.rouge }
        $c.Controls.Add((Chip $etatTxt $etatCoul 396 14))
        $u = $a.usage
        $ligne2 = ResumeAppareil $a
        if ($null -ne $u) { $ligne2 = $ligne2 + ('   ·   Écran : {0} min aujourd''hui' -f [int]$u.actif) }
        $foc = [string](Get-PropOrDefault $a 'focus_libelle' '')
        if (-not $foc) { $foc = [string](Get-PropOrDefault $a 'focus' '') }
        if ([bool]$a.en_ligne -and $foc) { $ligne2 = $ligne2 + ('   ·   En ce moment : {0}' -f $foc) }
        $c.Controls.Add((Etiquette $ligne2 $F.petit $C.texte2 16 54 470))
        $x = 16
        $defs = @(@('+30 min', 'ouvrir', 30), @('+1 h', 'ouvrir', 60), @('Fermer', 'fermer', 0))
        if ($null -ne $a.derogation -and $a.derogation) { $defs += ,@('Planning', 'annuler', 0) }
        foreach ($def in $defs) {
            $style = switch ([string]$def[1]) { 'fermer' { 'danger' } default { 'secondaire' } }
            $b = Bouton ([string]$def[0]) $style 86
            $b.Location = New-Object System.Drawing.Point($x, 102); $b.Height = 30; $b.Tag = @{ a = $a; def = $def }
            $b.Add_Click({ param($s, $e)
                $t = $s.Tag
                Agir @{ action = [string]$t.def[1]; pc = [string]$t.a.id; minutes = [int]$t.def[2] }
                $s.Text = '✓'; $s.Enabled = $false
            })
            $c.Controls.Add($b); $x += 92
        }
        $bF = Bouton 'Fermé…' 'secondaire' 86
        $bF.Location = New-Object System.Drawing.Point(316, 102); $bF.Height = 30; $bF.Tag = $a
        $bF.Add_Click({ param($s, $e) FenetreFermesEnfant $s.Tag })
        $c.Controls.Add($bF)
        $bP = Bouton 'Planning…' 'secondaire' 86
        $bP.Location = New-Object System.Drawing.Point(408, 102); $bP.Height = 30; $bP.Tag = $a
        $bP.Add_Click({ param($s, $e) FenetrePlanning $s.Tag })
        $c.Controls.Add($bP)
        $page.Controls.Add($c); $y += 158
    }
    $y += 8
    $page.Controls.Add((Etiquette ('Actualisé {0}' -f (Get-Date -Format 'HH:mm')) $F.petit $C.texte3 16 $y))
}

# ------------------------------------------------------------ La fenêtre
$script:Fenetre = $null
"""
assert old in t
t = t.replace(old, new, 1)

# La fenêtre : si maison.json existe, deux onglets.
old = """    $f.Text = 'Vision'; $f.Icon = $icone; $f.BackColor = $C.fond; $f.ForeColor = $C.texte
    $f.FormBorderStyle = 'FixedSingle'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
    $f.StartPosition = 'CenterScreen'; $f.ClientSize = New-Object System.Drawing.Size(560, 640); $f.TopMost = $true
    $f.Font = $F.corps
"""
new = """    $f.Text = 'Vision'; $f.Icon = $icone; $f.BackColor = $C.fond; $f.ForeColor = $C.texte
    $f.FormBorderStyle = 'FixedSingle'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
    $f.StartPosition = 'CenterScreen'; $f.ClientSize = New-Object System.Drawing.Size(560, 640); $f.TopMost = $true
    $f.Font = $F.corps
    $parent = Test-Path (Join-Path $Dossier 'maison.json')
    if ($parent) {
        # Deux onglets : cet ordinateur, et la maison. Le contenu « cet
        # ordinateur » ci-dessous est posé sur le premier onglet.
        $f.ClientSize = New-Object System.Drawing.Size(560, 700)
        $onglets = New-Object System.Windows.Forms.TabControl
        $onglets.Location = New-Object System.Drawing.Point(0, 72); $onglets.Size = New-Object System.Drawing.Size(560, 628)
        $onglets.Font = $F.gras
        $pMoi = New-Object System.Windows.Forms.TabPage; $pMoi.Text = 'Cet ordinateur'; $pMoi.BackColor = $C.fond
        $pMaison = New-Object System.Windows.Forms.TabPage; $pMaison.Text = 'La maison'; $pMaison.BackColor = $C.fond; $pMaison.AutoScroll = $true
        $onglets.TabPages.Add($pMaison); $onglets.TabPages.Add($pMoi)
        $f.Controls.Add($onglets)
        OngletMaison $pMaison
        $rafraichisseur = New-Object System.Windows.Forms.Timer; $rafraichisseur.Interval = 45000
        $rafraichisseur.Add_Tick({ if ($onglets.SelectedTab -eq $pMaison) { OngletMaison $pMaison } })
        $rafraichisseur.Start()
        $f.Add_FormClosed({ $rafraichisseur.Stop(); $rafraichisseur.Dispose() })
        # Les contrôles « cet ordinateur » iront dans $pMoi, décalés vers le haut.
        $cible = $pMoi; $dy = -72
    } else { $cible = $f; $dy = 0 }
"""
assert old in t, "fenetre"
t = t.replace(old, new, 1)
# Les ajouts « cet ordinateur » passent par $cible avec le décalage $dy.
bloc_debut = t.index("    # Carte état\n    $cE = Carte 24 80 512 96 $C.haute")
bloc_fin = t.index("    $liste.Add_DoubleClick({ $ok.PerformClick() })", bloc_debut)
bloc = t[bloc_debut:bloc_fin]
bloc = bloc.replace("$f.Controls.Add(", "$cible.Controls.Add(")
# Décaler les Y absolus des contrôles posés directement dans la page.
import re
def decale(m):
    return "{} {} {} ({} + $dy)".format(m.group(1), m.group(2), m.group(3), m.group(4))
bloc = re.sub(r"(Carte) (\d+) (\d+) (\d+)", lambda m: "Carte {} ({} + $dy) {}".format(m.group(2), m.group(3), m.group(4)), bloc)
bloc = re.sub(r"(Champ '[^']*') (\d+) (\d+) (\d+)", lambda m: "{} {} ({} + $dy) {}".format(m.group(1), m.group(2), m.group(3), m.group(4)), bloc)
bloc = re.sub(r"(\$cible\.Controls\.Add\(\(Etiquette [^\n]*?) (\d+) (\d+)\)\)$", lambda m: "{} {} ({} + $dy)))".format(m.group(1), m.group(2), m.group(3)), bloc, flags=re.M)
bloc = bloc.replace("$ok.Location = New-Object System.Drawing.Point(364, 586)", "$ok.Location = New-Object System.Drawing.Point(364, (586 + $dy))")
t = t[:bloc_debut] + bloc + t[bloc_fin:]
open(AGENT, "w", encoding="utf-8").write(t)

p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.50.1"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.50.1"', 'CLIENT_VERSION = "1.51.0"', 1))
import py_compile
py_compile.compile(p, doraise=True)
print("ok", t.count("OngletMaison"), t.count("$cible.Controls.Add("))
