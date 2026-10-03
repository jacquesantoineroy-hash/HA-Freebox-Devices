"""Agent ComVision 1.46.0 : notifications Vision (logo, bouton « Demander l'accès »)
et envoi des demandes d'accès à Home Assistant. À exécuter sur HA :
python3 patch_agent_146.py
"""
import re
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
AGENT = BASE + "client/ha-parental-agent.ps1"
LOGO_B64 = open(sys.argv[1]).read().strip() if len(sys.argv) > 1 else ""

t = open(AGENT, encoding="utf-8").read()
shutil.copy2(AGENT, AGENT + ".bak145")
assert "$script:Version           = '1.45.1'" in t
t = t.replace("$script:Version           = '1.45.1'", "$script:Version           = '1.46.0'", 1)

# --- Chemins et logo ----------------------------------------------------------
t = t.replace(
    "$script:ToastPath         = Join-Path $script:SondeDir 'toast.ps1'\n",
    "$script:ToastPath         = Join-Path $script:SondeDir 'toast.ps1'\n"
    "$script:DemandePath       = Join-Path $script:SondeDir 'demande.ps1'\n"
    "$script:LogoPath          = Join-Path $script:SondeDir 'vision.png'\n"
    "# Le logo de Vision (PNG 96 px), posé à côté de la sonde pour les notifications.\n"
    "$script:LogoBase64        = '" + LOGO_B64 + "'\n", 1)

# --- Titres : Vision ----------------------------------------------------------
t = t.replace("'ComVision'", "'Vision'")

# --- Script de notification -----------------------------------------------------
debut = t.index("$script:ToastSource = @'")
fin = t.index("'@", debut) + 2
TOAST = r"""$script:ToastSource = @'
param([string]$Payload)

$json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Payload)) |
    ConvertFrom-Json
$aumid = $json.aumid
$dossier = Split-Path -Parent $PSCommandPath

# Sans identité déclarée, Windows refuse d'afficher la notification ou
# l'attribue à « PowerShell ». On s'enregistre une fois, chez l'utilisateur,
# avec le nom et le logo de Vision.
$cle = "HKCU:\Software\Classes\AppUserModelId\$aumid"
if (-not (Test-Path $cle)) { New-Item -Path $cle -Force | Out-Null }
New-ItemProperty -Path $cle -Name 'DisplayName' -Value $json.appname `
    -PropertyType String -Force | Out-Null
New-ItemProperty -Path $cle -Name 'ShowInSettings' -Value 1 `
    -PropertyType DWord -Force | Out-Null
$logo = [string]$json.logo
if ($logo -and (Test-Path $logo)) {
    New-ItemProperty -Path $cle -Name 'IconUri' -Value $logo -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $cle -Name 'IconBackgroundColor' -Value 'FF120609' -PropertyType String -Force | Out-Null
}

# Le bouton « Demander l'accès » passe par un protocole enregistré chez
# l'utilisateur : un clic lance demande.ps1, qui dépose la demande pour
# l'agent. Cela marche aussi depuis le centre de notifications.
$proto = 'HKCU:\Software\Classes\vision-demande'
$commande = 'powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" "%1"' -f (Join-Path $dossier 'demande.ps1')
if (-not (Test-Path "$proto\shell\open\command")) {
    New-Item -Path "$proto\shell\open\command" -Force | Out-Null
}
Set-ItemProperty -Path $proto -Name '(Default)' -Value 'URL:Vision demande' -Force
New-ItemProperty -Path $proto -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
Set-ItemProperty -Path "$proto\shell\open\command" -Name '(Default)' -Value $commande -Force

[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]

$titre = [Security.SecurityElement]::Escape([string]$json.title)
$texte = [Security.SecurityElement]::Escape([string]$json.text)

# Un son répété exige une notification de durée longue, sinon Windows le
# coupe au bout de quelques secondes.
$repete = [bool]$json.loop
$son = [string]$json.sound
$duree = if ($repete -or $json.long) { 'long' } else { 'short' }
if ([string]::IsNullOrEmpty($son)) {
    $audio = '<audio silent="true"/>'
} elseif ($repete) {
    $audio = '<audio src="ms-winsoundevent:' + $son + '" loop="true"/>'
} else {
    $audio = '<audio src="ms-winsoundevent:' + $son + '"/>'
}

$image = ''
if ($logo -and (Test-Path $logo)) {
    $image = '<image placement="appLogoOverride" hint-crop="circle" src="file:///' + ($logo -replace '\\', '/') + '"/>'
}

$actions = ''
if ($json.PSObject.Properties['demande'] -and $json.demande) {
    $brut = [Text.Encoding]::UTF8.GetBytes(($json.demande | ConvertTo-Json -Compress))
    $arg = [Convert]::ToBase64String($brut).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $actions = @"
  <actions>
    <action content="Demander l&apos;accès" activationType="protocol" arguments="vision-demande:$arg"/>
    <action content="Fermer" activationType="system" arguments="dismiss"/>
  </actions>
"@
    if ($duree -eq 'short') { $duree = 'long' }
}

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@"
<toast duration="$duree">
  <visual>
    <binding template="ToastGeneric">
      $image
      <text>$titre</text>
      <text>$texte</text>
      <text placement="attribution">Vision · la maison</text>
    </binding>
  </visual>
  $audio
$actions
</toast>
"@)

$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($aumid).Show($toast)
'@

# Déposé à côté : ce que le clic sur « Demander l'accès » exécute, dans la
# session de l'utilisateur. Il écrit la demande ; l'agent l'envoie.
$script:DemandeSource = @'
param([string]$Uri)
$dossier = Split-Path -Parent $PSCommandPath
$brut = ([string]$Uri) -replace '^vision-demande:', '' -replace '/+$', ''
$b64 = $brut.Replace('-', '+').Replace('_', '/')
switch ($b64.Length % 4) { 2 { $b64 += '==' } 3 { $b64 += '=' } }
try {
    $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
    [void]($json | ConvertFrom-Json)
    $nom = Join-Path $dossier ('demande-{0}.json' -f [DateTime]::UtcNow.Ticks)
    Set-Content -Path $nom -Value $json -Encoding UTF8
} catch { }
'@"""
t = t[:debut] + TOAST + t[fin:]

# --- Écriture des scripts et du logo ------------------------------------------
old = """function Write-ToastScript {
    # Dépose (ou rafraîchit) le script d'affichage à côté de la configuration.
    try {
        if ((-not (Test-Path $script:ToastPath)) -or
            ((Get-Content $script:ToastPath -Raw -ErrorAction SilentlyContinue) -ne $script:ToastSource)) {
            Set-Content -Path $script:ToastPath -Value $script:ToastSource -Encoding UTF8
        }
        return $true"""
new = """function Write-ToastScript {
    # Dépose (ou rafraîchit) les scripts d'affichage et le logo à côté de la sonde.
    try {
        if ((-not (Test-Path $script:ToastPath)) -or
            ((Get-Content $script:ToastPath -Raw -ErrorAction SilentlyContinue) -ne $script:ToastSource)) {
            Set-Content -Path $script:ToastPath -Value $script:ToastSource -Encoding UTF8
        }
        if ((-not (Test-Path $script:DemandePath)) -or
            ((Get-Content $script:DemandePath -Raw -ErrorAction SilentlyContinue) -ne $script:DemandeSource)) {
            Set-Content -Path $script:DemandePath -Value $script:DemandeSource -Encoding UTF8
        }
        if ($script:LogoBase64 -and -not (Test-Path $script:LogoPath)) {
            [IO.File]::WriteAllBytes($script:LogoPath, [Convert]::FromBase64String($script:LogoBase64))
        }
        return $true"""
assert old in t
t = t.replace(old, new, 1)

# --- Show-Toast / Send-Message : logo et demande ------------------------------
old = """        [string]$Son = 'Notification.Default',
        [bool]$Repete = $false
    )

    $session = Get-SessionConsole
    if ($null -eq $session -or $session.Etat -ne $script:WTS_ACTIVE) { return $false }
    if (-not (Grant-DossierSonde)) { return $false }
    if (-not (Write-ToastScript)) { return $false }

    $charge = @{
        aumid   = $script:Aumid
        appname = 'Vision'
        title   = $Titre
        text    = $Texte
        long    = $Long
        sound   = $Son
        loop    = $Repete
    } | ConvertTo-Json -Compress"""
new = """        [string]$Son = 'Notification.Default',
        [bool]$Repete = $false,
        $Demande = $null
    )

    $session = Get-SessionConsole
    if ($null -eq $session -or $session.Etat -ne $script:WTS_ACTIVE) { return $false }
    if (-not (Grant-DossierSonde)) { return $false }
    if (-not (Write-ToastScript)) { return $false }

    $charge = @{
        aumid   = $script:Aumid
        appname = 'Vision'
        title   = $Titre
        text    = $Texte
        long    = $Long
        sound   = $Son
        loop    = $Repete
        logo    = $script:LogoPath
    }
    if ($Demande) { $charge.demande = $Demande }
    $charge = $charge | ConvertTo-Json -Compress -Depth 4"""
assert old in t, "Show-Toast"
t = t.replace(old, new, 1)

old = """        [string]$Son = 'Notification.Default',
        [bool]$Repete = $false
    )

    $session = Get-SessionConsole
    if ($null -eq $session -or $session.Etat -ne $script:WTS_ACTIVE) {
        Write-Journal "Message non affiché (aucune session active) : $Texte" 'WARN'
        return $false
    }

    # Par défaut une notification Windows, discrète et conservée dans le
    # centre de notifications. Un message urgent passe par-dessus tout.
    if (-not $Urgent) {
        if (Show-Toast -Texte $Texte -Titre $Titre -Son $Son -Repete $Repete) {"""
new = """        [string]$Son = 'Notification.Default',
        [bool]$Repete = $false,
        $Demande = $null
    )

    $session = Get-SessionConsole
    if ($null -eq $session -or $session.Etat -ne $script:WTS_ACTIVE) {
        Write-Journal "Message non affiché (aucune session active) : $Texte" 'WARN'
        return $false
    }

    # Par défaut une notification Windows, discrète et conservée dans le
    # centre de notifications. Un message urgent passe par-dessus tout.
    if (-not $Urgent) {
        if (Show-Toast -Texte $Texte -Titre $Titre -Son $Son -Repete $Repete -Demande $Demande) {"""
assert old in t, "Send-Message"
t = t.replace(old, new, 1)

# --- Lancement refusé : proposer de demander l'accès --------------------------
old = """        [void](Send-Message -Texte "$joli n'est pas accessible en ce moment." `
            -Titre 'Vision' -Secondes 8)"""
new = """        [void](Send-Message -Texte "$joli n'est pas accessible en ce moment. Tu peux demander l'accès aux parents." `
            -Titre 'Vision' -Secondes 8 -Demande @{ genre = 'apps'; nom = $court; libelle = $joli })"""
assert old in t, "Deny-Lancement"
t = t.replace(old, new, 1)

# --- Envoi des demandes déposées par le clic ----------------------------------
old = "function Wait-Tour {"
new = """function Send-Demandes {
    <#
        Le clic sur « Demander l'accès » a déposé un fichier dans le dossier
        de la sonde. On l'envoie à Home Assistant, qui prévient les parents,
        et on le dit : la demande ne part pas dans le vide.
    #>
    param($Config)
    if ($null -eq $Config -or -not (Test-Path $script:SondeDir)) { return }
    $fichiers = @(Get-ChildItem -Path $script:SondeDir -Filter 'demande-*.json' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -First 5)
    foreach ($f in $fichiers) {
        $contenu = $null
        try { $contenu = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json } catch { }
        if ($null -eq $contenu -or -not $contenu.nom) {
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        $libelle = [string](Get-PropOrDefault $contenu 'libelle' $contenu.nom)
        try {
            $r = Invoke-Ha -Chemin '/api/pc_parental/demande' -Corps @{
                id      = $Config.id
                secret  = $Config.secret
                genre   = [string](Get-PropOrDefault $contenu 'genre' 'apps')
                nom     = [string]$contenu.nom
                libelle = $libelle
            } -Config $Config
            Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
            Write-Journal "Demande d'accès envoyée : $libelle."
            [void](Send-Message -Texte "Demande envoyée aux parents pour $libelle. Tu seras prévenu de la réponse." `
                -Titre 'Vision' -Secondes 8 -Son '')
        } catch {
            # Home Assistant injoignable : le fichier reste, on réessaiera.
            if ((Get-CodeHttp $_) -ge 400) { Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue }
            Write-Journal "Demande d'accès non envoyée : $_" 'WARN'
            break
        }
    }
}

function Wait-Tour {"""
assert old in t
t = t.replace(old, new, 1)

old = """        if (((Get-Date) - $dernierBalayage).TotalSeconds -ge $filet) {
            $dernierBalayage = Get-Date
            Stop-LogicielsInterdits -Noms $script:AppsInterdites
        }"""
new = """        if (((Get-Date) - $dernierBalayage).TotalSeconds -ge $filet) {
            $dernierBalayage = Get-Date
            Stop-LogicielsInterdits -Noms $script:AppsInterdites
            try { Send-Demandes -Config $script:ConfigCourante } catch { }
        }"""
assert old in t, "Wait-Tour"
t = t.replace(old, new, 1)

# --- Boucle principale : config courante, demandes, propositions de sites ------
old = """    while ($true) {
        # La sonde est un confort : une erreur chez elle ne doit jamais
        # arreter l'agent, donc le controle parental.
        try { Start-Sonde } catch { Write-Journal "Sonde : $_" 'WARN' }
"""
new = """    while ($true) {
        # La sonde est un confort : une erreur chez elle ne doit jamais
        # arreter l'agent, donc le controle parental.
        try { Start-Sonde } catch { Write-Journal "Sonde : $_" 'WARN' }
        $script:ConfigCourante = $config
        try { Send-Demandes -Config $config } catch { Write-Journal "Demandes : $_" 'WARN' }
"""
assert old in t, "boucle"
t = t.replace(old, new, 1)

old = """            if ($decision.action -eq 'uninstall') {
                Invoke-AutoDesinstallation -Config $config
                return
            }"""
new = """            # Home Assistant désigne les sites fermés par une règle que
            # l'enfant vient d'essayer d'ouvrir : on le lui dit, avec le bouton.
            if ($decision.PSObject.Properties['proposer_acces'] -and $decision.proposer_acces) {
                foreach ($site in @($decision.proposer_acces)) {
                    $site = [string]$site
                    if (-not $site) { continue }
                    [void](Send-Message -Texte "$site n'est pas accessible en ce moment. Tu peux demander l'accès aux parents." `
                        -Titre 'Vision' -Secondes 8 -Son '' -Demande @{ genre = 'sites'; nom = $site; libelle = $site })
                }
            }
            if ($decision.action -eq 'uninstall') {
                Invoke-AutoDesinstallation -Config $config
                return
            }"""
assert old in t, "uninstall"
t = t.replace(old, new, 1)

open(AGENT, "w", encoding="utf-8").write(t)

# --- const.py : version du client ----------------------------------------------
p = BASE + "const.py"
c = open(p, encoding="utf-8").read()
assert 'CLIENT_VERSION = "1.45.1"' in c
open(p, "w", encoding="utf-8").write(c.replace('CLIENT_VERSION = "1.45.1"', 'CLIENT_VERSION = "1.46.0"', 1))

# --- http.py : proposer_acces dans la réponse du poll --------------------------
p = BASE + "http.py"
h = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakand11")
old = """        for brut in list(corps.get("alertes") or [])[:20]:
            if isinstance(brut, dict):
                domaine = str(brut.get("domaine") or "")
                origine = str(brut.get("source") or "")[:32]
            else:
                domaine, origine = str(brut), ""
"""
new = """        _proposer: list[str] = []
        for brut in list(corps.get("alertes") or [])[:20]:
            if isinstance(brut, dict):
                domaine = str(brut.get("domaine") or "")
                origine = str(brut.get("source") or "")[:32]
            else:
                domaine, origine = str(brut), ""
            # Un site fermé par une règle de la maison (pas la liste noire,
            # pas la pub) : on propose à l'enfant de demander l'accès.
            if origine == "regle" and len(_proposer) < 2:
                try:
                    _ets = {e.lower() for e in coord.store.etiquettes_de("sites", domaine)}
                except Exception:  # noqa: BLE001
                    _ets = set()
                _muets = {"pub & traçage", "dangereux", "système", "systeme", "contournement", "adulte"}
                if _ets and not (_ets & _muets) and "." in domaine:
                    _proposer.append(domaine)
"""
assert old in h, "alertes"
h = h.replace(old, new, 1)
old = """        # Messages à afficher sur ce PC (poubelle, rappel, avertissement…).
        if attente := coord.store.take_messages(pc):
            reponse["notify"] = attente
"""
new = """        # Messages à afficher sur ce PC (poubelle, rappel, avertissement…).
        if attente := coord.store.take_messages(pc):
            reponse["notify"] = attente
        if _proposer:
            reponse["proposer_acces"] = _proposer
"""
assert old in h, "notify"
h = h.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(h)

import py_compile
for f in ("const.py", "http.py"):
    py_compile.compile(BASE + f, doraise=True)
print("ok", t.count("Send-Demandes"), t.count("proposer_acces"), len(LOGO_B64))
