"""Fabrique le banc d'essai de la fenêtre PC : le script de la fenêtre, sorti de l'agent,
qui se photographie vue par vue hors de l'écran puis sort. À lancer sur un PC Windows :
powershell -STA -File tray_banc.ps1 -Dossier <dossier avec maison.json, etat.json, vision.png>"""
import sys
s = open('pc_parental/client/ha-parental-agent.ps1', encoding='utf-8-sig').read()
a = s.index("$script:TraySource = @'\n") + len("$script:TraySource = @'\n")
t = s[a:s.index("\n'@\n", a)].replace("'Local\\VisionTray'", "'Local\\VisionTrayEssai'")
fin = "if ($Depart) { $script:Page = $Depart; Montrer }\n\n[System.Windows.Forms.Application]::Run()"
assert t.count(fin) == 1
banc = r'''
# ---- Banc d'essai : la fenêtre hors de l'écran, chaque vue photographiée, puis on sort.
$tray.Visible = $false; $script:Deverrouille = $true
$script:W.WindowStartupLocation = 'Manual'; $script:W.Left = -4000; $script:W.Top = 0; $script:W.ShowActivated = $false
$script:Page = 'maison'; Rafraichir; $script:W.Show()
function Photo([string]$nom) {
    $script:W.Dispatcher.Invoke([action]{}, [System.Windows.Threading.DispatcherPriority]::ContextIdle)
    $rtb = New-Object System.Windows.Media.Imaging.RenderTargetBitmap([int]$script:W.ActualWidth, [int]$script:W.ActualHeight, 96, 96, [System.Windows.Media.PixelFormats]::Pbgra32)
    $rtb.Render($script:W.Content)
    $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($rtb))
    $fs = [System.IO.File]::Create((Join-Path $script:Dossier ("photo-$nom.png"))); $enc.Save($fs); $fs.Close()
}
$journal = Join-Path $script:Dossier 'essai.log'
'debut' | Set-Content $journal
try {
    Photo '1-actifs'
    $script:Oeil.rx = 0.7; $script:Oeil.ry = -0.4; OeilDessiner 0.55; Photo '1b-clin'
    $maison = Lire 'maison.json'
    $gr = @(GroupesMaison $maison)
    ('groupes: ' + (($gr | ForEach-Object { $_.prenom + '=' + $_.appareils.Count }) -join ', ')) | Add-Content $journal
    $enfant = $gr | Where-Object { $_.appareils.Count -gt 1 -and $_.personne -and -not [bool](Prop $_.personne 'parent' $false) } | Select-Object -First 1
    $script:Vue = @{ type = 'personne'; personne = [string]$enfant.entite }; Rafraichir; Photo '2-fiche'
    ChoisirDuree 30 $false; Photo '3-materiel'
    ChoisirDuree 0 $true; Photo '4-autre'
    ('choix: ' + (($script:Vue.temps.choix.Keys) -join ',')) | Add-Content $journal
    $par = $gr | Where-Object { $_.personne -and [bool](Prop $_.personne 'parent' $false) } | Select-Object -First 1
    $script:Vue = @{ type = 'personne'; personne = [string]$par.entite }; Rafraichir; Photo '5-parent'
    $tv = @($par.appareils | Where-Object { [bool](Prop $_ 'partage_tous' $false) })[0]
    $script:Vue = @{ type = 'partage'; appareil = $tv; retour = @{ type = 'personne'; personne = [string]$par.entite } }; Rafraichir; Photo '6-partage'
    $script:Vue = $script:Vue.retour; Rafraichir; Photo '7-retour'
    # Un refus en cours sur la première ligne fermée : le bouton doit se fermer et dire jusqu'à quand.
    $f = Lire 'fermes.json'
    $lignes = @(Prop $f 'apps' @()) + @(Prop $f 'sites' @())
    if ($lignes.Count -gt 0) {
        $genre = if (@(Prop $f 'apps' @()).Count -gt 0) { 'apps' } else { 'sites' }
        $f | Add-Member -NotePropertyName refus -NotePropertyValue @(@{ genre = $genre; nom = [string](Prop $lignes[0] 'nom'); jusqua = ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() + 1800) }) -Force
        ($f | ConvertTo-Json -Depth 5 -Compress) | Set-Content (Join-Path $script:Dossier 'fermes.json') -Encoding UTF8
        ('refus posé sur ' + [string](Prop $lignes[0] 'nom') + ' : ' + (RefusJusqua (Lire 'fermes.json') $genre ([string](Prop $lignes[0] 'nom')))) | Add-Content $journal
    }
    $script:Vue = $null; $script:Page = 'moi'; Rafraichir; Photo '8-moi'
    # L'œil tourne-t-il ? On laisse passer deux secondes de boucle et on compte les redessins.
    $n = 0; $fin = (Get-Date).AddSeconds(2)
    while ((Get-Date) -lt $fin) { $script:W.Dispatcher.Invoke([action]{}, [System.Windows.Threading.DispatcherPriority]::Background); Start-Sleep -Milliseconds 20; $n++ }
    ('oeil: minuteur actif=' + $script:OeilTic.IsEnabled + ' regard=' + [Math]::Round($script:Oeil.rx, 2)) | Add-Content $journal
    ('icone: ' + $tray.Icon.Width + 'x' + $tray.Icon.Height) | Add-Content $journal
    'fin sans erreur' | Add-Content $journal
} catch { ('ERREUR: ' + $_ + ' @ ' + $_.ScriptStackTrace) | Add-Content $journal }
$script:W.Hide(); $tray.Dispose()
exit 0
'''
open(sys.argv[1], 'w', encoding='utf-8-sig', newline='\r\n').write(t.replace(fin, banc))
