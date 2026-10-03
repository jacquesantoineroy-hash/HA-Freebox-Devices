"""Agent ComVision 1.47.0 : icône Vision dans la zone de notification (demande
d'accès à un site avec lien et motif, demande de temps), état écrit pour elle,
lien et motif transmis à Home Assistant. À exécuter sur HA :
python3 patch_agent_147.py
"""
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"

t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak146")
assert "$script:Version           = '1.46.0'" in t
t = t.replace("$script:Version           = '1.46.0'", "$script:Version           = '1.47.0'", 1)

t = t.replace(
    "$script:LogoPath          = Join-Path $script:SondeDir 'vision.png'\n",
    "$script:LogoPath          = Join-Path $script:SondeDir 'vision.png'\n"
    "$script:TrayPath          = Join-Path $script:SondeDir 'tray.ps1'\n"
    "$script:EtatSondePath     = Join-Path $script:SondeDir 'etat.json'\n"
    "$script:DemandeTemps      = 0\n", 1)

# --- Script de l'icône ------------------------------------------------------------
TRAY = r"""
# L'icône de Vision en bas à droite, dans la session de l'utilisateur : un
# clic droit pour demander l'accès à un site (avec le lien et un mot
# d'explication) ou un peu de temps. Les demandes sont déposées dans le
# dossier de la sonde ; l'agent les envoie. Rien ne se décide ici.
$script:TraySource = @'
param([string]$Dossier)

$verrou = New-Object Threading.Mutex($false, 'Local\VisionTray')
try { $tenu = $verrou.WaitOne(0) } catch [Threading.AbandonedMutexException] { $tenu = $true }
if (-not $tenu) { exit 0 }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$fond   = [System.Drawing.Color]::FromArgb(18, 6, 9)
$carte  = [System.Drawing.Color]::FromArgb(39, 17, 26)
$or     = [System.Drawing.Color]::FromArgb(242, 193, 78)
$texte  = [System.Drawing.Color]::FromArgb(251, 243, 238)
$texte2 = [System.Drawing.Color]::FromArgb(205, 168, 166)
$police = New-Object System.Drawing.Font('Segoe UI', 10)
$grasse = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)

$logo = Join-Path $Dossier 'vision.png'
$icone = [System.Drawing.SystemIcons]::Shield
if (Test-Path $logo) {
    try { $icone = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]::new($logo)).GetHicon()) } catch { }
}

function Deposer($objet) {
    $nom = Join-Path $Dossier ('demande-{0}.json' -f [DateTime]::UtcNow.Ticks)
    ($objet | ConvertTo-Json -Compress) | Set-Content -Path $nom -Encoding UTF8
}

function Lire-Etat {
    $f = Join-Path $Dossier 'etat.json'
    if (-not (Test-Path $f)) { return $null }
    try { return (Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}

function Hote($lien) {
    $l = ([string]$lien).Trim()
    if (-not $l) { return '' }
    if ($l -notmatch '^[a-z][a-z0-9+.-]*://') { $l = 'https://' + $l }
    try { return ([Uri]$l).Host.ToLowerInvariant().TrimStart('www.') } catch { return '' }
}

function Bouton($txt, $principal) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $txt; $b.Font = $police; $b.FlatStyle = 'Flat'; $b.Height = 36; $b.Width = 130
    $b.FlatAppearance.BorderSize = 0
    if ($principal) { $b.BackColor = $or; $b.ForeColor = $fond } else { $b.BackColor = $carte; $b.ForeColor = $texte }
    return $b
}

function Formulaire {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = 'Vision'; $f.Icon = $icone; $f.BackColor = $fond; $f.ForeColor = $texte
    $f.FormBorderStyle = 'FixedDialog'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
    $f.StartPosition = 'CenterScreen'; $f.ClientSize = New-Object System.Drawing.Size(440, 300); $f.TopMost = $true

    $t1 = New-Object System.Windows.Forms.Label
    $t1.Text = "Demander l'accès à un site"; $t1.Font = $grasse; $t1.ForeColor = $or
    $t1.AutoSize = $true; $t1.Location = New-Object System.Drawing.Point(20, 18)
    $f.Controls.Add($t1)

    $l1 = New-Object System.Windows.Forms.Label
    $l1.Text = 'Lien ou nom du site'; $l1.Font = $police; $l1.ForeColor = $texte2
    $l1.AutoSize = $true; $l1.Location = New-Object System.Drawing.Point(20, 64)
    $f.Controls.Add($l1)
    $lien = New-Object System.Windows.Forms.TextBox
    $lien.Font = $police; $lien.BackColor = $carte; $lien.ForeColor = $texte; $lien.BorderStyle = 'FixedSingle'
    $lien.Location = New-Object System.Drawing.Point(20, 86); $lien.Width = 400
    try {
        $presse = [System.Windows.Forms.Clipboard]::GetText()
        if ($presse -match '^https?://\S+$') { $lien.Text = $presse.Trim() }
    } catch { }
    $f.Controls.Add($lien)

    $l2 = New-Object System.Windows.Forms.Label
    $l2.Text = 'Pourquoi ? (facultatif, les parents le verront)'; $l2.Font = $police; $l2.ForeColor = $texte2
    $l2.AutoSize = $true; $l2.Location = New-Object System.Drawing.Point(20, 128)
    $f.Controls.Add($l2)
    $motif = New-Object System.Windows.Forms.TextBox
    $motif.Font = $police; $motif.BackColor = $carte; $motif.ForeColor = $texte; $motif.BorderStyle = 'FixedSingle'
    $motif.Location = New-Object System.Drawing.Point(20, 150); $motif.Width = 400; $motif.MaxLength = 120
    $f.Controls.Add($motif)

    $info = New-Object System.Windows.Forms.Label
    $info.Text = "La demande arrive sur le téléphone d'un parent. Tu seras prévenu de la réponse."
    $info.Font = $police; $info.ForeColor = $texte2; $info.AutoSize = $false
    $info.Location = New-Object System.Drawing.Point(20, 190); $info.Size = New-Object System.Drawing.Size(400, 40)
    $f.Controls.Add($info)

    $ok = Bouton 'Envoyer' $true
    $ok.Location = New-Object System.Drawing.Point(290, 244)
    $non = Bouton 'Annuler' $false
    $non.Location = New-Object System.Drawing.Point(150, 244)
    $f.Controls.Add($ok); $f.Controls.Add($non)
    $f.AcceptButton = $ok; $f.CancelButton = $non
    $non.Add_Click({ $f.Close() })
    $ok.Add_Click({
        $h = Hote $lien.Text
        if (-not $h -or $h -notlike '*.*') {
            [System.Windows.Forms.MessageBox]::Show('Indique un lien ou un nom de site, par exemple youtube.com', 'Vision') | Out-Null
            return
        }
        Deposer @{ genre = 'sites'; nom = $h; libelle = $h; lien = $lien.Text.Trim(); motif = $motif.Text.Trim() }
        $f.Close()
    })
    [void]$f.ShowDialog()
    $f.Dispose()
}

$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = $icone; $tray.Text = 'Vision'; $tray.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$menu.Font = $police
$etatItem = $menu.Items.Add('Vision')
$etatItem.Enabled = $false
$menu.Items.Add('-') | Out-Null
$site = $menu.Items.Add("Demander l'accès à un site…")
$site.Add_Click({ Formulaire })
$temps = New-Object System.Windows.Forms.ToolStripMenuItem("Demander un peu de temps")
foreach ($m in 15, 30, 60) {
    $sous = $temps.DropDownItems.Add(('{0} min' -f $m))
    $sous.Tag = $m
    $sous.Add_Click({ param($s, $e) Deposer @{ genre = 'temps'; minutes = [int]$s.Tag } })
}
$menu.Items.Add($temps) | Out-Null
$menu.Add_Opening({
    $etat = Lire-Etat
    if ($null -eq $etat) { $etatItem.Text = 'Vision'; return }
    $etatItem.Text = [string]$etat.texte
    $temps.Enabled = [bool]$etat.ferme
})
$tray.ContextMenuStrip = $menu
$tray.Add_DoubleClick({ Formulaire })

[System.Windows.Forms.Application]::Run()
'@
"""
old = "function Write-ToastScript {"
assert old in t
t = t.replace(old, TRAY.lstrip("\n") + "\n" + old, 1)

old = """        if ($script:LogoBase64 -and -not (Test-Path $script:LogoPath)) {
            [IO.File]::WriteAllBytes($script:LogoPath, [Convert]::FromBase64String($script:LogoBase64))
        }
        return $true"""
new = """        if ($script:LogoBase64 -and -not (Test-Path $script:LogoPath)) {
            [IO.File]::WriteAllBytes($script:LogoPath, [Convert]::FromBase64String($script:LogoBase64))
        }
        if ((-not (Test-Path $script:TrayPath)) -or
            ((Get-Content $script:TrayPath -Raw -ErrorAction SilentlyContinue) -ne $script:TraySource)) {
            Set-Content -Path $script:TrayPath -Value $script:TraySource -Encoding UTF8
            $script:TrayRenouvelee = $true
        }
        return $true"""
assert old in t, "Write-ToastScript"
t = t.replace(old, new, 1)

# --- Lancement de l'icône, à chaque tour (une seule instance grâce au verrou) ---
old = "function Send-Demandes {"
new = """function Start-Tray {
    <#
        Lance l'icône de zone de notification dans la session de l'utilisateur.
        Le verrou du script garantit une seule instance ; quand le script a
        changé, on arrête l'ancienne pour que la nouvelle prenne la place.
    #>
    $session = Get-SessionConsole
    if ($null -eq $session -or $session.Etat -ne $script:WTS_ACTIVE) { return }
    if (-not (Grant-DossierSonde)) { return }
    if (-not (Write-ToastScript)) { return }
    if ($script:TrayRenouvelee) {
        $script:TrayRenouvelee = $false
        Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -like '*tray.ps1*' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    $ligne = ('powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden ' +
              '-ExecutionPolicy Bypass -File "{0}" -Dossier "{1}"') -f $script:TrayPath, $script:SondeDir
    try { [void][Wts]::RunAsUser($session.Id, $ligne) } catch { }
}

function Write-EtatSonde {
    # Ce que l'icône affiche dans son menu : ouvert ou fermé, et jusqu'à quand.
    param($Decision)
    try {
        $ferme = ($null -ne $Decision -and $Decision.action -eq 'lock')
        $texte = 'Vision : accès ouvert'
        if ($ferme) {
            $texte = [string](Get-PropOrDefault $Decision 'message' 'Accès fermé')
        } elseif ($null -ne $Decision -and (Get-PropOrDefault $Decision 'warn' 0) -gt 0) {
            $texte = [string](Get-PropOrDefault $Decision 'message' 'Vision : accès ouvert')
        }
        @{ ferme = $ferme; texte = $texte } | ConvertTo-Json -Compress |
            Set-Content -Path $script:EtatSondePath -Encoding UTF8
    } catch { }
}

function Send-Demandes {"""
assert old in t
t = t.replace(old, new, 1)

# --- Send-Demandes : temps, lien, motif ----------------------------------------
old = """        $libelle = [string](Get-PropOrDefault $contenu 'libelle' $contenu.nom)
        try {
            $r = Invoke-Ha -Chemin '/api/pc_parental/demande' -Corps @{
                id      = $Config.id
                secret  = $Config.secret
                genre   = [string](Get-PropOrDefault $contenu 'genre' 'apps')
                nom     = [string]$contenu.nom
                libelle = $libelle
            } -Config $Config"""
new = """        $genre = [string](Get-PropOrDefault $contenu 'genre' 'apps')
        if ($genre -eq 'temps') {
            # Une demande de temps part avec le prochain relevé, comme sur Android.
            $script:DemandeTemps = [int](Get-PropOrDefault $contenu 'minutes' 30)
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            Write-Journal "Demande de temps : $($script:DemandeTemps) min."
            [void](Send-Message -Texte "Demande de $($script:DemandeTemps) min envoyée aux parents." -Titre 'Vision' -Secondes 8 -Son '')
            continue
        }
        $libelle = [string](Get-PropOrDefault $contenu 'libelle' $contenu.nom)
        try {
            $r = Invoke-Ha -Chemin '/api/pc_parental/demande' -Corps @{
                id      = $Config.id
                secret  = $Config.secret
                genre   = $genre
                nom     = [string]$contenu.nom
                libelle = $libelle
                lien    = [string](Get-PropOrDefault $contenu 'lien' '')
                motif   = [string](Get-PropOrDefault $contenu 'motif' '')
            } -Config $Config"""
assert old in t, "Send-Demandes"
t = t.replace(old, new, 1)
# Un fichier de demande de temps n'a pas de « nom » : ne pas le jeter.
old = """        if ($null -eq $contenu -or -not $contenu.nom) {
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }"""
new = """        if ($null -eq $contenu -or (-not (Get-PropOrDefault $contenu 'nom' '') -and (Get-PropOrDefault $contenu 'genre' '') -ne 'temps')) {
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }"""
assert old in t, "nom"
t = t.replace(old, new, 1)

# --- Get-Decision : demande de temps dans le relevé ------------------------------
old = """        signatures   = (Get-Signatures -Noms @($releve.ouverts + @($releve.premier)))
    }"""
new = """        signatures   = (Get-Signatures -Noms @($releve.ouverts + @($releve.premier)))
    }
    if ($script:DemandeTemps -gt 0) {
        $corps.demande_temps = $script:DemandeTemps
        $script:DemandeTemps = 0
    }"""
assert old in t, "Get-Decision"
t = t.replace(old, new, 1)

# --- Boucle : icône et état ------------------------------------------------------
old = """        try { Start-Sonde } catch { Write-Journal "Sonde : $_" 'WARN' }
        $script:ConfigCourante = $config"""
new = """        try { Start-Sonde } catch { Write-Journal "Sonde : $_" 'WARN' }
        try { Start-Tray } catch { Write-Journal "Icône : $_" 'WARN' }
        $script:ConfigCourante = $config"""
assert old in t, "boucle"
t = t.replace(old, new, 1)
old = """            if ($decision.PSObject.Properties['poll']) { $attente = [int]$decision.poll }
            Save-Etat -Decision $decision"""
new = """            if ($decision.PSObject.Properties['poll']) { $attente = [int]$decision.poll }
            Save-Etat -Decision $decision
            Write-EtatSonde -Decision $decision"""
assert old in t, "Save-Etat"
t = t.replace(old, new, 1)
t = t.replace("$script:DemandeTemps      = 0\n", "$script:DemandeTemps      = 0\n$script:TrayRenouvelee    = $false\n", 1)

open(AGENT, "w", encoding="utf-8").write(t)

# --- const.py --------------------------------------------------------------------
p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.46.0"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.46.0"', 'CLIENT_VERSION = "1.47.0"', 1))

# --- demandes.py : lien et motif -------------------------------------------------
p = BASE + "demandes.py"
d = open(p, encoding="utf-8").read()
if '"lien"' not in d:
    d = d.replace(
        "    genre: str, nom: str, libelle: str,\n) -> dict[str, Any] | None:",
        "    genre: str, nom: str, libelle: str, lien: str = \"\", motif: str = \"\",\n) -> dict[str, Any] | None:", 1)
    d = d.replace(
        """        "libelle": joli, "ts": time.time(), "pc": pc["id"], "prenom": qui,
    }
    liste.append(d)
    texte = "{} demande l'accès à {}.".format(qui or pc.get("name"), joli)""",
        """        "libelle": joli, "ts": time.time(), "pc": pc["id"], "prenom": qui,
        "lien": lien[:300], "motif": motif[:120],
    }
    liste.append(d)
    texte = "{} demande l'accès à {}.".format(qui or pc.get("name"), joli)
    if lien and lien.strip().lower() != cle:
        texte = "{} {}".format(texte, lien[:120])
    if motif:
        texte = "{} ({})".format(texte, motif[:120])""", 1)
    d = d.replace(
        """        msg["acces"] = {
            "id": d["id"], "pc": pc["id"], "prenom": qui, "genre": genre,
            "nom": nom, "libelle": joli,
        }""",
        """        msg["acces"] = {
            "id": d["id"], "pc": pc["id"], "prenom": qui, "genre": genre,
            "nom": nom, "libelle": joli, "lien": lien[:300], "motif": motif[:120],
        }""", 1)
    d = d.replace(
        """        libelle = str(corps.get("libelle") or "").strip()[:60]
        if not nom:
            return self.json({"ok": False, "error": "nom"}, status_code=400)
        d = deposer(self.hass, coord, pc, genre, nom, libelle)""",
        """        libelle = str(corps.get("libelle") or "").strip()[:60]
        lien = str(corps.get("lien") or "").strip()[:300]
        motif = str(corps.get("motif") or "").strip()[:120]
        if not nom:
            return self.json({"ok": False, "error": "nom"}, status_code=400)
        d = deposer(self.hass, coord, pc, genre, nom, libelle, lien, motif)""", 1)
    assert d.count("lien") >= 6, d.count("lien")
    open(p, "w", encoding="utf-8").write(d)

import py_compile
for f in ("const.py", "demandes.py"):
    py_compile.compile(BASE + f, doraise=True)
print("ok", t.count("Start-Tray"), t.count("DemandeTemps"))
