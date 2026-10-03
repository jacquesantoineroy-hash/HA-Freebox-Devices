param([string]$Dossier)

# Vision, la fenêtre du PC : WPF, fenêtre sans bordure système, coins arrondis,
# charte Vision. Tourne dans la session de l'utilisateur, sous Windows
# PowerShell 5.1. Elle lit ce que l'agent dépose (etat.json, fermes.json,
# maison.json) et dépose ses demandes et actions ; l'agent fait le reste.

$verrou = New-Object Threading.Mutex($false, 'Local\VisionTray')
try { $tenu = $verrou.WaitOne(0) } catch [Threading.AbandonedMutexException] { $tenu = $true }
if (-not $tenu) { exit 0 }

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms, System.Drawing

# ------------------------------------------------------------------ Données
$script:Dossier = $Dossier
function Lire([string]$fichier) {
    $f = Join-Path $script:Dossier $fichier
    if (-not (Test-Path $f)) { return $null }
    try { return (Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}
function Deposer($objet) {
    $nom = Join-Path $script:Dossier ('demande-{0}.json' -f [DateTime]::UtcNow.Ticks)
    ($objet | ConvertTo-Json -Compress) | Set-Content -Path $nom -Encoding UTF8
}
function Agir($objet) {
    $nom = Join-Path $script:Dossier ('action-{0}.json' -f [DateTime]::UtcNow.Ticks)
    ($objet | ConvertTo-Json -Compress -Depth 4) | Set-Content -Path $nom -Encoding UTF8
}
function Prop($o, [string]$n, $defaut = $null) {
    if ($null -eq $o) { return $defaut }
    $p = $o.PSObject.Properties[$n]
    if ($null -eq $p -or $null -eq $p.Value) { return $defaut }
    return $p.Value
}
function Hote($lien) {
    $l = ([string]$lien).Trim()
    if (-not $l) { return '' }
    if ($l -notmatch '^[a-z][a-z0-9+.-]*://') { $l = 'https://' + $l }
    try { return ([Uri]$l).Host.ToLowerInvariant() -replace '^www\.', '' } catch { return '' }
}
function Heure([string]$iso) {
    if (-not $iso) { return '' }
    try { return ([datetime]$iso).ToString('HH\hmm') } catch { return '' }
}
$script:Demandees = @{}

# ------------------------------------------------------------------ XAML
[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Vision" Width="620" Height="760" WindowStartupLocation="CenterScreen"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent" ResizeMode="NoResize"
        Topmost="True" ShowInTaskbar="True" FontFamily="Segoe UI">
  <Window.Resources>
    <SolidColorBrush x:Key="Fond" Color="#FF120609"/>
    <SolidColorBrush x:Key="Carte" Color="#FF27111A"/>
    <SolidColorBrush x:Key="Haute" Color="#FF361724"/>
    <SolidColorBrush x:Key="Ligne" Color="#FF4C2231"/>
    <SolidColorBrush x:Key="Or" Color="#FFF2C14E"/>
    <SolidColorBrush x:Key="OrSombre" Color="#FF1E1605"/>
    <SolidColorBrush x:Key="Vert" Color="#FF4CC38A"/>
    <SolidColorBrush x:Key="Rouge" Color="#FFFF6B6B"/>
    <SolidColorBrush x:Key="Texte" Color="#FFFBF3EE"/>
    <SolidColorBrush x:Key="Texte2" Color="#FFCDA8A6"/>
    <SolidColorBrush x:Key="Texte3" Color="#FF8C666C"/>

    <Style x:Key="Primaire" TargetType="Button">
      <Setter Property="Background" Value="{StaticResource Or}"/>
      <Setter Property="Foreground" Value="{StaticResource OrSombre}"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="FontSize" Value="13"/>
      <Setter Property="Padding" Value="16,8"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="{TemplateBinding Background}" CornerRadius="12" Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="#FFF5CC5A"/></Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter TargetName="b" Property="Opacity" Value="0.5"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="Secondaire" TargetType="Button" BasedOn="{StaticResource Primaire}">
      <Setter Property="Background" Value="{StaticResource Haute}"/>
      <Setter Property="Foreground" Value="{StaticResource Texte}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" Background="{TemplateBinding Background}" BorderBrush="{StaticResource Ligne}" BorderThickness="1" CornerRadius="12" Padding="{TemplateBinding Padding}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="{StaticResource Ligne}"/></Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter TargetName="b" Property="Opacity" Value="0.5"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="Danger" TargetType="Button" BasedOn="{StaticResource Secondaire}">
      <Setter Property="Foreground" Value="{StaticResource Rouge}"/>
    </Style>
    <Style x:Key="Onglet" TargetType="ToggleButton">
      <Setter Property="Foreground" Value="{StaticResource Texte2}"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="FontSize" Value="13"/>
      <Setter Property="Padding" Value="16,8"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ToggleButton">
            <Border x:Name="b" Background="Transparent" CornerRadius="10" Padding="{TemplateBinding Padding}" Margin="0,0,6,0">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="b" Property="Background" Value="{StaticResource Or}"/>
                <Setter Property="Foreground" Value="{StaticResource OrSombre}"/>
              </Trigger>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Opacity" Value="0.85"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="Interrupteur" TargetType="ToggleButton">
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ToggleButton">
            <Grid Width="46" Height="26">
              <Border x:Name="piste" CornerRadius="13" Background="{StaticResource Ligne}"/>
              <Border x:Name="pouce" Width="20" Height="20" CornerRadius="10" Background="{StaticResource Texte2}" HorizontalAlignment="Left" Margin="3,0,0,0"/>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="piste" Property="Background" Value="#FF8A2B2B"/>
                <Setter TargetName="pouce" Property="Background" Value="{StaticResource Rouge}"/>
                <Setter TargetName="pouce" Property="HorizontalAlignment" Value="Right"/>
                <Setter TargetName="pouce" Property="Margin" Value="0,0,3,0"/>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter Property="Opacity" Value="0.4"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style x:Key="Champ" TargetType="TextBox">
      <Setter Property="Background" Value="{StaticResource Haute}"/>
      <Setter Property="Foreground" Value="{StaticResource Texte}"/>
      <Setter Property="CaretBrush" Value="{StaticResource Or}"/>
      <Setter Property="BorderBrush" Value="{StaticResource Ligne}"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="12,9"/>
      <Setter Property="FontSize" Value="13"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="TextBox">
            <Border Background="{TemplateBinding Background}" BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}" CornerRadius="12">
              <ScrollViewer x:Name="PART_ContentHost" Margin="{TemplateBinding Padding}" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsKeyboardFocused" Value="True"><Setter Property="BorderBrush" Value="{StaticResource Or}"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
    <Style TargetType="ScrollBar">
      <Setter Property="Width" Value="6"/>
      <Setter Property="Background" Value="Transparent"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="ScrollBar">
            <Track x:Name="PART_Track" IsDirectionReversed="True">
              <Track.Thumb><Thumb><Thumb.Template><ControlTemplate><Border Background="{StaticResource Ligne}" CornerRadius="3" Width="6"/></ControlTemplate></Thumb.Template></Thumb></Track.Thumb>
            </Track>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>

  <Border CornerRadius="22" Background="{StaticResource Fond}" BorderBrush="{StaticResource Ligne}" BorderThickness="1" Margin="12">
    <Border.Effect><DropShadowEffect BlurRadius="24" ShadowDepth="0" Opacity="0.55"/></Border.Effect>
    <DockPanel>
      <!-- En-tête : la poignée pour déplacer la fenêtre -->
      <Grid x:Name="Entete" DockPanel.Dock="Top" Margin="24,20,20,8" Background="Transparent">
        <StackPanel Orientation="Horizontal">
          <Image x:Name="Logo" Width="44" Height="44" Margin="0,0,14,0"/>
          <StackPanel VerticalAlignment="Center">
            <TextBlock Text="Vision" FontSize="24" FontWeight="SemiBold" Foreground="{StaticResource Texte}"/>
            <TextBlock Text="Le contrôle parental de la maison" FontSize="12" Foreground="{StaticResource Texte2}"/>
          </StackPanel>
        </StackPanel>
        <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" VerticalAlignment="Top">
          <Border x:Name="ChipEtat" CornerRadius="10" Background="{StaticResource Haute}" Padding="12,5" Margin="0,4,10,0">
            <TextBlock x:Name="ChipEtatTexte" Text="OUVERT" FontSize="11" FontWeight="Bold" Foreground="{StaticResource Vert}"/>
          </Border>
          <Button x:Name="Fermer" Style="{StaticResource Secondaire}" Padding="10,4" Content="✕" FontSize="12"/>
        </StackPanel>
      </Grid>
      <StackPanel x:Name="Onglets" DockPanel.Dock="Top" Orientation="Horizontal" Margin="24,8,24,10"/>
      <ScrollViewer VerticalScrollBarVisibility="Auto" Margin="12,0,6,16" Padding="12,0,10,0">
        <StackPanel x:Name="Contenu"/>
      </ScrollViewer>
    </DockPanel>
  </Border>
</Window>
"@

$lecteur = New-Object System.Xml.XmlNodeReader $xaml
$script:W = [Windows.Markup.XamlReader]::Load($lecteur)
$W.Add_MouseLeftButtonDown({ param($s, $e) if ($e.ButtonState -eq 'Pressed') { try { $script:W.DragMove() } catch { } } })
$W.FindName('Fermer').Add_Click({ $script:W.Hide() })
$script:Contenu = $W.FindName('Contenu')
$script:Onglets = $W.FindName('Onglets')
$logoPath = Join-Path $Dossier 'vision.png'
if (Test-Path $logoPath) {
    try {
        $bmp = New-Object System.Windows.Media.Imaging.BitmapImage
        $bmp.BeginInit(); $bmp.UriSource = New-Object Uri($logoPath); $bmp.CacheOption = 'OnLoad'; $bmp.EndInit()
        $W.FindName('Logo').Source = $bmp
        $W.Icon = $bmp
    } catch { }
}
$W.Add_Closing({ param($s, $e) $e.Cancel = $true; $script:W.Hide() })

function Pinceau([string]$cle) { return $script:W.Resources[$cle] }
function Txt([string]$t, [double]$taille = 13, [string]$couleur = 'Texte', [bool]$gras = $false, [string]$marge = '0') {
    $tb = New-Object System.Windows.Controls.TextBlock
    $tb.Text = $t; $tb.FontSize = $taille; $tb.Foreground = (Pinceau $couleur); $tb.TextWrapping = 'Wrap'
    if ($gras) { $tb.FontWeight = 'SemiBold' }
    $m = @([string]$marge -split ',' | ForEach-Object { [double]$_ })
    if ($m.Count -ge 4) { $tb.Margin = [System.Windows.Thickness]::new($m[0], $m[1], $m[2], $m[3]) } else { $tb.Margin = [System.Windows.Thickness]::new($m[0]) }
    return $tb
}
function Section([string]$t) {
    $tb = Txt $t.ToUpper() 11 'Or' $true '4,14,0,8'
    $tb.FontWeight = 'Bold'
    return $tb
}
function Carte([string]$fond = 'Carte') {
    $b = New-Object System.Windows.Controls.Border
    $b.Background = (Pinceau $fond); $b.CornerRadius = [System.Windows.CornerRadius]::new(18)
    $b.Padding = [System.Windows.Thickness]::new(18, 16, 18, 16); $b.Margin = [System.Windows.Thickness]::new(0, 0, 0, 12)
    $sp = New-Object System.Windows.Controls.StackPanel
    $b.Child = $sp
    return $b
}
function Bouton([string]$t, [string]$style = 'Secondaire', $action = $null, $tag = $null) {
    $b = New-Object System.Windows.Controls.Button
    $b.Content = $t; $b.Style = $script:W.Resources[$style]; $b.Margin = [System.Windows.Thickness]::new(0, 0, 8, 0); $b.Tag = $tag
    if ($action) { $b.Add_Click($action) }
    return $b
}
function Chip([string]$t, [string]$couleur) {
    $b = New-Object System.Windows.Controls.Border
    $b.Background = (Pinceau 'Haute'); $b.CornerRadius = [System.Windows.CornerRadius]::new(10); $b.Padding = [System.Windows.Thickness]::new(10, 4, 10, 4)
    $b.VerticalAlignment = 'Top'
    $tb = Txt $t 11 $couleur $true; $tb.FontWeight = 'Bold'; $b.Child = $tb
    return $b
}
function Rangee() { $sp = New-Object System.Windows.Controls.StackPanel; $sp.Orientation = 'Horizontal'; return $sp }
function Champ([string]$indice) {
    $tb = New-Object System.Windows.Controls.TextBox
    $tb.Style = $script:W.Resources['Champ']; $tb.Tag = $indice; $tb.Text = $indice; $tb.Foreground = (Pinceau 'Texte3')
    $tb.Margin = [System.Windows.Thickness]::new(0, 0, 0, 10)
    $tb.Add_GotFocus({ param($s, $e) if ($s.Text -eq $s.Tag) { $s.Text = ''; $s.Foreground = (Pinceau 'Texte') } })
    $tb.Add_LostFocus({ param($s, $e) if (-not $s.Text) { $s.Text = $s.Tag; $s.Foreground = (Pinceau 'Texte3') } })
    return $tb
}
function Valeur($tb) { if ($tb.Text -eq $tb.Tag) { return '' } else { return $tb.Text.Trim() } }
function Separateur() {
    $b = New-Object System.Windows.Controls.Border; $b.Height = 1; $b.Background = (Pinceau 'Ligne'); $b.Margin = [System.Windows.Thickness]::new(0, 8, 0, 8); return $b
}
function Deux($gauche, $droite) {
    # Une ligne : contenu à gauche, quelque chose à droite.
    $g = New-Object System.Windows.Controls.Grid
    $c1 = New-Object System.Windows.Controls.ColumnDefinition; $c1.Width = [System.Windows.GridLength]::new(1, 'Star')
    $c2 = New-Object System.Windows.Controls.ColumnDefinition; $c2.Width = [System.Windows.GridLength]::Auto
    $g.ColumnDefinitions.Add($c1); $g.ColumnDefinitions.Add($c2)
    [System.Windows.Controls.Grid]::SetColumn($droite, 1)
    $droite.VerticalAlignment = 'Center'; $droite.Margin = [System.Windows.Thickness]::new(12, 0, 0, 0)
    $g.Children.Add($gauche) | Out-Null; $g.Children.Add($droite) | Out-Null
    return $g
}

# ------------------------------------------------------------------ Pages
$script:Page = 'maison'
$script:Vue = $null          # une sous-vue ouverte (fermés, planning, catégories) : @{ type; appareil }

function Rafraichir() {
    $etat = Lire 'etat.json'
    $ferme = ($null -ne $etat -and [bool](Prop $etat 'ferme' $false))
    $W.FindName('ChipEtatTexte').Text = $(if ($ferme) { 'FERMÉ' } else { 'OUVERT' })
    $W.FindName('ChipEtatTexte').Foreground = (Pinceau $(if ($ferme) { 'Rouge' } else { 'Vert' }))
    $parent = Test-Path (Join-Path $script:Dossier 'maison.json')
    if (-not $parent -and $script:Page -eq 'maison') { $script:Page = 'moi' }
    $Onglets.Children.Clear()
    if ($parent) {
        foreach ($def in @(@('maison', 'La maison'), @('moi', 'Cet ordinateur'))) {
            $t = New-Object System.Windows.Controls.Primitives.ToggleButton
            $t.Content = $def[1]; $t.Style = $W.Resources['Onglet']; $t.Tag = $def[0]; $t.IsChecked = ($script:Page -eq $def[0])
            $t.Add_Click({ param($s, $e) $script:Page = [string]$s.Tag; $script:Vue = $null; Rafraichir })
            $Onglets.Children.Add($t) | Out-Null
        }
    }
    $Contenu.Children.Clear()
    if ($script:Vue) { PageSousVue; return }
    if ($script:Page -eq 'maison') { PageMaison } else { PageMoi $etat $ferme }
}

function Retour([string]$titre) {
    $r = Rangee
    $r.Margin = [System.Windows.Thickness]::new(0, 0, 0, 10)
    $r.Children.Add((Bouton '←' 'Secondaire' { $script:Vue = $null; Rafraichir })) | Out-Null
    $t = Txt $titre 18 'Texte' $true; $t.VerticalAlignment = 'Center'
    $r.Children.Add($t) | Out-Null
    $Contenu.Children.Add($r) | Out-Null
}

# ---- La maison -------------------------------------------------------------
function ResumeAppareil($a) {
    $d = Prop $a 'derogation'
    if ($d) {
        $fin = [double](Prop $d 'fin' 0)
        $quand = if ($fin -gt 0) { ' jusqu''à ' + ([DateTimeOffset]::FromUnixTimeSeconds([long]$fin).ToLocalTime().ToString('HH\hmm')) } else { ' jusqu''au prochain créneau' }
        if ([string](Prop $d 'mode') -eq 'locked') { return 'Fermé par un parent' + $quand } else { return 'Ouvert par un parent' + $quand }
    }
    if ([bool](Prop $a 'verrouille' $false)) { $h = Heure ([string](Prop $a 'prochain')); if ($h) { return "Réouverture à $h" } else { return 'Fermé par le planning' } }
    $h = Heure ([string](Prop $a 'prochain_verrou'))
    if ($h) { return "Fermeture prévue à $h" } else { return 'Aucune fermeture prévue' }
}

function PageMaison() {
    $maison = Lire 'maison.json'
    if ($null -eq $maison) { $Contenu.Children.Add((Txt "L'espace parents se charge…" 13 'Texte2')) | Out-Null; return }
    $demandes = @(Prop $maison 'demandes' @())
    if ($demandes.Count -gt 0) {
        $Contenu.Children.Add((Section "Demandes d'accès")) | Out-Null
        foreach ($d in $demandes) {
            $c = Carte 'Haute'; $sp = $c.Child
            $sp.Children.Add((Txt ('{0} demande {1}' -f [string](Prop $d 'prenom'), [string](Prop $d 'libelle')) 15 'Texte' $true)) | Out-Null
            $det = @()
            if (Prop $d 'lien') { $det += [string](Prop $d 'lien') }
            if (Prop $d 'motif') { $det += ('« {0} »' -f [string](Prop $d 'motif')) }
            if (Prop $d 'raison') { $det += ('Fermé car : {0}' -f [string](Prop $d 'raison')) }
            if ($det.Count) { $sp.Children.Add((Txt ($det -join '   ') 12 'Texte2' $false '0,4,0,0')) | Out-Null }
            $r = Rangee; $r.Margin = [System.Windows.Thickness]::new(0, 12, 0, 0)
            foreach ($def in @(@('1 h', 'temporaire', 60, 'Secondaire'), @('Toujours', 'toujours', 0, 'Primaire'), @('Non', 'non', 0, 'Danger'))) {
                $r.Children.Add((Bouton $def[0] $def[3] {
                    param($s, $e); $t = $s.Tag
                    Agir @{ action = 'acces'; pc = [string]$t.pc; demande = [string]$t.id; decision = [string]$t.decision; minutes = [int]$t.minutes }
                    $s.Parent.IsEnabled = $false
                } @{ pc = (Prop $d 'pc'); id = (Prop $d 'id'); decision = $def[1]; minutes = $def[2] })) | Out-Null
            }
            $sp.Children.Add($r) | Out-Null
            $Contenu.Children.Add($c) | Out-Null
        }
    }
    $Contenu.Children.Add((Section 'Les enfants')) | Out-Null
    foreach ($a in @(Prop $maison 'appareils' @())) {
        if ([bool](Prop $a 'parent' $false)) { continue }
        $c = Carte; $sp = $c.Child
        $prenom = [string](Prop $a 'prenom'); if (-not $prenom) { $prenom = [string](Prop $a 'nom') }
        $enLigne = [bool](Prop $a 'en_ligne' $false); $verrou = [bool](Prop $a 'verrouille' $false)
        $etatTxt = 'OUVERT'; $coul = 'Vert'
        if (-not $enLigne) { $etatTxt = 'HORS LIGNE'; $coul = 'Texte3' } elseif ($verrou) { $etatTxt = 'FERMÉ'; $coul = 'Rouge' }
        $gauche = New-Object System.Windows.Controls.StackPanel
        $gauche.Children.Add((Txt $prenom 17 'Texte' $true)) | Out-Null
        $icone = if ([bool](Prop $a 'android' $false)) { '📱 ' } else { '💻 ' }
        $gauche.Children.Add((Txt ($icone + [string](Prop $a 'nom')) 12 'Texte2')) | Out-Null
        $sp.Children.Add((Deux $gauche (Chip $etatTxt $coul))) | Out-Null
        $l2 = ResumeAppareil $a
        $u = Prop $a 'usage'
        if ($u) { $l2 = $l2 + ('  ·  Écran {0} min aujourd''hui' -f [int](Prop $u 'actif' 0)) }
        $foc = [string](Prop $a 'focus_libelle'); if (-not $foc) { $foc = [string](Prop $a 'focus') }
        if ($enLigne -and $foc) { $l2 = $l2 + ('  ·  En ce moment : {0}' -f $foc) }
        $sp.Children.Add((Txt $l2 12 'Texte2' $false '0,10,0,0')) | Out-Null
        $r = Rangee; $r.Margin = [System.Windows.Thickness]::new(0, 14, 0, 0)
        $defs = @(@('+30 min', 'ouvrir', 30, 'Secondaire'), @('+1 h', 'ouvrir', 60, 'Secondaire'), @('Fermer', 'fermer', 0, 'Danger'))
        if (Prop $a 'derogation') { $defs += ,@('Planning', 'annuler', 0, 'Secondaire') }
        foreach ($def in $defs) {
            $r.Children.Add((Bouton $def[0] $def[3] {
                param($s, $e); $t = $s.Tag
                Agir @{ action = [string]$t.action; pc = [string]$t.pc; minutes = [int]$t.minutes }
                $s.Content = '✓'; $s.IsEnabled = $false
            } @{ action = $def[1]; pc = (Prop $a 'id'); minutes = $def[2] })) | Out-Null
        }
        $sp.Children.Add($r) | Out-Null
        $r2 = Rangee; $r2.Margin = [System.Windows.Thickness]::new(0, 8, 0, 0)
        foreach ($def in @(@('Catégories', 'categories'), @('Ce qui est fermé', 'fermes'), @('Planning', 'planning'), @('Un mot…', 'mot'))) {
            $r2.Children.Add((Bouton $def[0] 'Secondaire' {
                param($s, $e); $t = $s.Tag
                if ($t.type -eq 'mot') { EnvoyerMot $t.appareil; return }
                $script:Vue = @{ type = $t.type; appareil = $t.appareil }; Rafraichir
            } @{ type = $def[1]; appareil = $a })) | Out-Null
        }
        $sp.Children.Add($r2) | Out-Null
        $Contenu.Children.Add($c) | Out-Null
    }
    $Contenu.Children.Add((Txt ('Actualisé à {0}' -f (Get-Date -Format 'HH:mm')) 11 'Texte3' $false '4,4,0,0')) | Out-Null
}

function EnvoyerMot($a) {
    $prenom = [string](Prop $a 'prenom'); if (-not $prenom) { $prenom = [string](Prop $a 'nom') }
    $texte = [Microsoft.VisualBasic.Interaction]::InputBox("Un mot pour $prenom (il s'affiche sur son appareil)", 'Vision', '')
    if ($texte) { Agir @{ action = 'message'; pc = [string](Prop $a 'id'); texte = [string]$texte } }
}

function PageSousVue() {
    $a = $script:Vue.appareil
    $prenom = [string](Prop $a 'prenom'); if (-not $prenom) { $prenom = [string](Prop $a 'nom') }
    switch ($script:Vue.type) {
        'fermes' { Retour "Ce qui est fermé chez $prenom"; VueFermes $a }
        'planning' { Retour "Planning de $prenom"; VuePlanning $a }
        'categories' { Retour "Catégories de $prenom"; VueCategories $a }
    }
}

function MotifDe($a, [string]$nom) {
    $motifs = @(Prop $a 'motifs' @()); $raisons = Prop $a 'raisons'
    $n = $nom.ToLowerInvariant()
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

function VueFermes($a) {
    $titres = [ordered]@{ plage = 'Planning'; moyenne = 'Moyenne'; regle = 'Décision des parents'; age = 'Âge (PEGI)'; maison = 'Toute la maison'; securite = 'Sécurité' }
    $filtre = Champ 'Chercher'
    $Contenu.Children.Add($filtre) | Out-Null
    $zone = New-Object System.Windows.Controls.StackPanel
    $Contenu.Children.Add($zone) | Out-Null
    $script:ListeFermes = @()
    foreach ($x in @(Prop $a 'apps' @())) { $script:ListeFermes += @{ genre = 'apps'; nom = [string](Prop $x 'nom'); lib = [string](Prop $x 'libelle'); type = 'Appli' } }
    foreach ($x in @(Prop $a 'sites' @())) {
        $n = [string](Prop $x 'nom'); if (($n.Split('.')).Count -ne 2) { continue }
        $script:ListeFermes += @{ genre = 'sites'; nom = $n; lib = $n; type = 'Site' }
    }
    foreach ($e in $script:ListeFermes) {
        $m = MotifDe $a $e.nom
        $e.code = 'regle'; $e.texte = 'Coupé par les parents.'
        if ($m) { $e.code = $m.Substring(0, $m.IndexOf('|')); $e.texte = $m.Substring($m.IndexOf('|') + 1) }
    }
    $script:VF = @{ zone = $zone; filtre = $filtre; titres = $titres; a = $a }
    $script:RemplirFermes = {
        $zone = $script:VF.zone; $filtre = $script:VF.filtre; $titres = $script:VF.titres; $a = $script:VF.a
        $zone.Children.Clear()
        $q = (Valeur $filtre).ToLowerInvariant()
        foreach ($code in $titres.Keys) {
            $groupe = @($script:ListeFermes | Where-Object { $_.code -eq $code -and (-not $q -or $_.lib.ToLowerInvariant() -like "*$q*" -or $_.nom -like "*$q*") })
            if ($groupe.Count -eq 0) { continue }
            $zone.Children.Add((Section ('{0} ({1})' -f $titres[$code], $groupe.Count))) | Out-Null
            $c = Carte; $sp = $c.Child
            $textes = @($groupe | ForEach-Object { $_.texte } | Select-Object -Unique)
            if ($textes.Count -eq 1) { $sp.Children.Add((Txt $textes[0] 12 'Texte2' $false '0,0,0,6')) | Out-Null }
            if ($code -eq 'securite') {
                $sp.Children.Add((Txt ('{0} éléments, coupés partout pour tout le monde. Se lèvent dans Vision.' -f $groupe.Count) 12 'Texte3')) | Out-Null
                $zone.Children.Add($c) | Out-Null; continue
            }
            $k = 0
            foreach ($e in ($groupe | Sort-Object { $_.type }, { $_.lib.ToLowerInvariant() })) {
                if ($k++ -gt 0) { $sp.Children.Add((Separateur)) | Out-Null }
                $g = New-Object System.Windows.Controls.StackPanel
                $g.Children.Add((Txt $e.lib 14 'Texte' $true)) | Out-Null
                $sous = $e.type; if ($textes.Count -gt 1) { $sous = $sous + ' · ' + $e.texte }
                $g.Children.Add((Txt $sous 11 'Texte2')) | Out-Null
                $r = Rangee
                foreach ($def in @(@('1 h', 'temporaire', 60), @('Toujours', 'toujours', 0))) {
                    $r.Children.Add((Bouton $def[0] $(if ($def[1] -eq 'toujours') { 'Primaire' } else { 'Secondaire' }) {
                        param($s, $e2); $t = $s.Tag
                        Agir @{ action = 'autoriser'; pc = [string]$t.pc; genre = $t.genre; nom = $t.nom; decision = $t.decision; minutes = [int]$t.minutes }
                        $s.Content = '✓'; $s.IsEnabled = $false
                    } @{ pc = (Prop $a 'id'); genre = $e.genre; nom = $e.nom; decision = $def[1]; minutes = $def[2] })) | Out-Null
                }
                $sp.Children.Add((Deux $g $r)) | Out-Null
            }
            $zone.Children.Add($c) | Out-Null
        }
    }
    & $script:RemplirFermes
    $filtre.Add_TextChanged({ & $script:RemplirFermes })
}

function VuePlanning($a) {
    $Contenu.Children.Add((Txt 'Les plages se modifient dans le tableau Vision de Home Assistant.' 12 'Texte2' $false '0,0,0,10')) | Out-Null
    $c = Carte; $sp = $c.Child
    $jours = @('L', 'M', 'M', 'J', 'V', 'S', 'D')
    $k = 0
    foreach ($p in @(Prop $a 'plages' @())) {
        if ($k++ -gt 0) { $sp.Children.Add((Separateur)) | Out-Null }
        $g = New-Object System.Windows.Controls.StackPanel
        $actif = [bool](Prop $p 'actif' $false); $active = [bool](Prop $p 'active' $true)
        $g.Children.Add((Txt ('{0}   {1} → {2}' -f [string](Prop $p 'nom'), [string](Prop $p 'debut'), [string](Prop $p 'fin')) 14 $(if (-not $active) { 'Texte3' } elseif ($actif) { 'Or' } else { 'Texte' }) $true)) | Out-Null
        $js = @(Prop $p 'jours' @()); $lettres = @()
        for ($i = 0; $i -lt 7; $i++) { if ($i -lt $js.Count -and [bool]$js[$i]) { $lettres += $jours[$i] } else { $lettres += '·' } }
        $quoi = switch ([string](Prop $p 'portee')) { 'etiquettes' { 'Coupe : ' + ((@(Prop $p 'etiquettes' @())) -join ', ') } 'elements' { 'Des applis ou sites précis' } default { "Tout l'appareil" } }
        $g.Children.Add((Txt ($quoi + '     ' + ($lettres -join ' ')) 11 'Texte2')) | Out-Null
        $droite = if ($actif) { Chip 'EN COURS' 'Or' } elseif (-not $active) { Chip 'DÉSACTIVÉE' 'Texte3' } else { New-Object System.Windows.Controls.TextBlock }
        $sp.Children.Add((Deux $g $droite)) | Out-Null
    }
    if ($k -eq 0) { $sp.Children.Add((Txt 'Aucune plage.' 13 'Texte2')) | Out-Null }
    $Contenu.Children.Add($c) | Out-Null
}

function VueCategories($a) {
    $maison = Lire 'maison.json'
    $cats = @(Prop $maison 'categories' @())
    $etats = Prop $a 'etiquettes_etat'
    $Contenu.Children.Add((Txt 'Interrupteur rouge : coupé pour cette personne, sur tous ses appareils. Touche une catégorie pour voir ce qu''elle contient. Le planning et la règle de moyenne s''ajoutent par-dessus.' 12 'Texte2' $false '0,0,0,6')) | Out-Null
    $groupes = [ordered]@{ 'Âge' = @(); 'Catégories' = @(); 'Toute la maison (verrouillé)' = @() }
    foreach ($c in $cats) {
        if ([bool](Prop $c 'maison' $false) -or [bool](Prop $c 'securite' $false)) { $groupes['Toute la maison (verrouillé)'] += $c }
        elseif ([bool](Prop $c 'age' $false)) { $groupes['Âge'] += $c } else { $groupes['Catégories'] += $c }
    }
    foreach ($titre in $groupes.Keys) {
        $liste = $groupes[$titre]; if ($liste.Count -eq 0) { continue }
        $Contenu.Children.Add((Section $titre)) | Out-Null
        $card = Carte; $sp = $card.Child; $k = 0
        $verrou = $titre -like 'Toute la maison*'
        foreach ($c in $liste) {
            if ($k++ -gt 0) { $sp.Children.Add((Separateur)) | Out-Null }
            $nom = [string](Prop $c 'nom')
            $nA = @(Prop $c 'apps' @()).Count; $nS = @(Prop $c 'sites' @()).Count
            $e = Prop $etats $nom
            $choix = 'neutre'; $coupe = $false; $parRegle = $false; $raison = ''
            if ($e -is [string]) { $choix = $e; $coupe = ($e -eq 'bloquer') }
            elseif ($null -ne $e) {
                $choix = [string](Prop $e 'choix' 'neutre'); $coupe = [bool](Prop $e 'coupe' $false)
                $parRegle = ([bool](Prop $e 'verrou' $false)) -and -not $verrou
                $raison = [string](Prop $e 'raison' '')
            }
            $g = New-Object System.Windows.Controls.StackPanel; $g.Cursor = 'Hand'; $g.Tag = $c; $g.Background = [System.Windows.Media.Brushes]::Transparent
            $g.Children.Add((Txt $nom 14 $(if ($verrou) { 'Texte2' } else { 'Texte' }) $true)) | Out-Null
            $det = @(); if ($nA) { $det += "$nA applis" }; if ($nS) { $det += "$nS sites" }
            $d = if ($det.Count) { $det -join ', ' } else { 'vide' }
            if ($choix -eq 'autoriser') { $d += ' · autorisé explicitement' }
            $g.Children.Add((Txt $d 11 'Texte2')) | Out-Null
            if ($raison -and ($parRegle -or $verrou)) { $g.Children.Add((Txt $raison 11 $(if ($parRegle) { 'Or' } else { 'Texte3' }))) | Out-Null }
            $contenu = New-Object System.Windows.Controls.StackPanel; $contenu.Visibility = 'Collapsed'; $contenu.Margin = [System.Windows.Thickness]::new(0, 6, 0, 0)
            foreach ($x in @(Prop $c 'apps' @())) { $contenu.Children.Add((Txt ('•  ' + [string](Prop $x 'libelle')) 12 'Texte')) | Out-Null }
            foreach ($x in @(Prop $c 'sites' @())) { $contenu.Children.Add((Txt ('◦  ' + [string]$x) 12 'Texte2')) | Out-Null }
            if ($contenu.Children.Count -eq 0) { $contenu.Children.Add((Txt 'Rien de classé ici pour l''instant.' 12 'Texte3')) | Out-Null }
            $g.Children.Add($contenu) | Out-Null
            $g.Add_MouseLeftButtonUp({ param($s, $e) $cc = $s.Children[$s.Children.Count - 1]; $cc.Visibility = $(if ($cc.Visibility -eq 'Visible') { 'Collapsed' } else { 'Visible' }); $e.Handled = $true })
            if ($verrou) { $droite = Chip 'MAISON' 'Texte3' }
            else {
                $droite = New-Object System.Windows.Controls.Primitives.ToggleButton
                $droite.Style = $W.Resources['Interrupteur']; $droite.IsChecked = $coupe
                if ($parRegle) { $droite.IsEnabled = $false; $droite.ToolTip = $raison }
                $droite.Tag = @{ pc = (Prop $a 'id'); etiquette = $nom }
                $droite.Add_Click({ param($s, $e); $t = $s.Tag
                    Agir @{ action = 'etiquette'; pc = [string]$t.pc; etiquette = [string]$t.etiquette; etat = $(if ($s.IsChecked) { 'bloquer' } else { 'neutre' }) }
                })
            }
            $sp.Children.Add((Deux $g $droite)) | Out-Null
        }
        $Contenu.Children.Add($card) | Out-Null
    }
}

# ---- Cet ordinateur --------------------------------------------------------
function PageMoi($etat, [bool]$ferme) {
    $c = Carte 'Haute'; $sp = $c.Child
    $g = New-Object System.Windows.Controls.StackPanel
    $g.Children.Add((Txt $env:USERNAME 17 'Texte' $true)) | Out-Null
    $texte = 'Vision : accès ouvert'; if ($etat -and (Prop $etat 'texte')) { $texte = [string](Prop $etat 'texte') }
    $g.Children.Add((Txt $texte 12 'Texte2')) | Out-Null
    $sp.Children.Add((Deux $g (Chip $(if ($ferme) { 'FERMÉ' } else { 'OUVERT' }) $(if ($ferme) { 'Rouge' } else { 'Vert' })))) | Out-Null
    if ($ferme) {
        $r = Rangee; $r.Margin = [System.Windows.Thickness]::new(0, 12, 0, 0)
        $r.Children.Add((Txt 'Demander un peu de temps :' 12 'Texte2' $false '0,0,10,0')) | Out-Null
        foreach ($m in 15, 30, 60) {
            $r.Children.Add((Bouton ('+{0} min' -f $m) 'Secondaire' { param($s, $e) Deposer @{ genre = 'temps'; minutes = [int]$s.Tag }; $s.Content = 'Envoyé'; $s.IsEnabled = $false } $m)) | Out-Null
        }
        $sp.Children.Add($r) | Out-Null
    }
    $Contenu.Children.Add($c) | Out-Null

    $Contenu.Children.Add((Section 'Ce qui est fermé ici')) | Out-Null
    $Contenu.Children.Add((Txt "Choisis une ligne et demande l'accès : un parent répond sur son téléphone. Tu peux aussi coller le lien d'un autre site." 12 'Texte2' $false '0,0,0,8')) | Out-Null
    $filtre = Champ 'Chercher une appli ou un site'
    $Contenu.Children.Add($filtre) | Out-Null
    $data = Lire 'fermes.json'
    $card = Carte; $sp2 = $card.Child
    $script:VM = @{ sp2 = $sp2; filtre = $filtre; data = $data }
    $script:RemplirMoi = {
        $sp2 = $script:VM.sp2; $filtre = $script:VM.filtre; $data = $script:VM.data
        $sp2.Children.Clear()
        $q = (Valeur $filtre).ToLowerInvariant()
        $lignes = @()
        foreach ($x in @(Prop $data 'apps' @())) { $lignes += @{ genre = 'apps'; nom = [string](Prop $x 'nom'); raison = [string](Prop $x 'raison'); type = 'Appli'; recent = $false } }
        foreach ($x in @(Prop $data 'sites' @())) { $lignes += @{ genre = 'sites'; nom = [string](Prop $x 'nom'); raison = [string](Prop $x 'raison'); type = 'Site'; recent = [bool](Prop $x 'recent' $false) } }
        $lignes = @($lignes | Where-Object { -not $q -or $_.nom.ToLowerInvariant() -like "*$q*" } | Sort-Object { -not $_.recent }, { $_.type }, { $_.nom })
        if ($lignes.Count -eq 0) { $sp2.Children.Add((Txt 'Rien de fermé ici.' 13 'Texte2')) | Out-Null }
        $k = 0
        foreach ($l in ($lignes | Select-Object -First 120)) {
            if ($k++ -gt 0) { $sp2.Children.Add((Separateur)) | Out-Null }
            $g = New-Object System.Windows.Controls.StackPanel
            $g.Children.Add((Txt $l.nom 14 $(if ($l.recent) { 'Or' } else { 'Texte' }) $true)) | Out-Null
            $g.Children.Add((Txt ($l.type + ' · ' + $l.raison) 11 'Texte2')) | Out-Null
            $deja = $script:Demandees.ContainsKey($l.genre + ':' + $l.nom)
            $b = Bouton $(if ($deja) { 'Demandé ✓' } else { 'Demander' }) 'Secondaire' {
                param($s, $e); $t = $s.Tag
                $motif = [Microsoft.VisualBasic.Interaction]::InputBox('Pourquoi en as-tu besoin ? (facultatif, les parents le verront)', 'Vision', '')
                Deposer @{ genre = $t.genre; nom = $t.nom; libelle = $t.nom; lien = ''; motif = [string]$motif }
                $script:Demandees[$t.genre + ':' + $t.nom] = $true
                $s.Content = 'Demandé ✓'; $s.IsEnabled = $false
            } @{ genre = $l.genre; nom = $l.nom }
            if ($deja) { $b.IsEnabled = $false }
            $sp2.Children.Add((Deux $g $b)) | Out-Null
        }
    }
    & $script:RemplirMoi
    $filtre.Add_TextChanged({ & $script:RemplirMoi })
    $Contenu.Children.Add($card) | Out-Null

    $Contenu.Children.Add((Section 'Un autre site')) | Out-Null
    $c3 = Carte; $sp3 = $c3.Child
    $lien = Champ 'Colle le lien ou le nom du site'
    try { $presse = [System.Windows.Clipboard]::GetText(); if ($presse -match '^https?://\S+$') { $lien.Text = $presse.Trim(); $lien.Foreground = (Pinceau 'Texte') } } catch { }
    $motif = Champ 'Pourquoi ? (facultatif, les parents le verront)'
    $sp3.Children.Add($lien) | Out-Null; $sp3.Children.Add($motif) | Out-Null
    $ok = Bouton "Demander l'accès" 'Primaire' {
        param($s, $e); $t = $s.Tag
        $l = Valeur $t.lien; $h = Hote $l
        if (-not $h -or $h -notlike '*.*') { [System.Windows.MessageBox]::Show('Ce lien ne ressemble pas à un site. Exemple : youtube.com', 'Vision') | Out-Null; return }
        Deposer @{ genre = 'sites'; nom = $h; libelle = $h; lien = $l; motif = (Valeur $t.motif) }
        $s.Content = 'Envoyé ✓'; $s.IsEnabled = $false
    } @{ lien = $lien; motif = $motif }
    $ok.HorizontalAlignment = 'Right'
    $sp3.Children.Add($ok) | Out-Null
    $Contenu.Children.Add($c3) | Out-Null
}

# ------------------------------------------------------------------ L'icône
Add-Type -AssemblyName Microsoft.VisualBasic
$iconeTray = [System.Drawing.SystemIcons]::Shield
if (Test-Path $logoPath) { try { $iconeTray = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]::new($logoPath)).GetHicon()) } catch { } }
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = $iconeTray; $tray.Text = 'Vision'; $tray.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$ouvrir = $menu.Items.Add('Ouvrir Vision'); $ouvrir.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$ouvrir.Add_Click({ Montrer })
$menu.Items.Add('-') | Out-Null
$etatItem = $menu.Items.Add('Vision'); $etatItem.Enabled = $false
$menu.Add_Opening({ $e = Lire 'etat.json'; $etatItem.Text = $(if ($e -and (Prop $e 'texte')) { [string](Prop $e 'texte') } else { 'Vision : accès ouvert' }) })
$tray.ContextMenuStrip = $menu
$tray.Add_MouseClick({ param($s, $e) if ($e.Button -eq 'Left') { Montrer } })

function Montrer() {
    Rafraichir
    $script:W.Show(); $script:W.Activate()
}

$horloge = New-Object System.Windows.Forms.Timer; $horloge.Interval = 30000
$horloge.Add_Tick({
    $e = Lire 'etat.json'; $txt = 'Vision'
    if ($e -and (Prop $e 'texte')) { $txt = [string](Prop $e 'texte') }
    if ($txt.Length -gt 63) { $txt = $txt.Substring(0, 63) }
    $tray.Text = $txt
    if ($script:W.IsVisible -and $script:Page -eq 'maison' -and -not $script:Vue) { Rafraichir }
})
$horloge.Start()

[System.Windows.Forms.Application]::Run()
