param([string]$Dossier, [string]$Depart = '')

# Vision, la fenêtre du PC : WPF, fenêtre sans bordure système, coins arrondis,
# charte Vision. Tourne dans la session de l'utilisateur, sous Windows
# PowerShell 5.1. Elle lit ce que l'agent dépose (etat.json, fermes.json,
# maison.json) et dépose ses demandes et actions ; l'agent fait le reste.

$verrou = New-Object Threading.Mutex($false, 'Local\VisionTray')
try { $tenu = $verrou.WaitOne(0) } catch [Threading.AbandonedMutexException] { $tenu = $true }
if (-not $tenu) { exit 0 }

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms, System.Drawing
# Sa propre identité dans la barre des tâches : l'icône de Vision, pas celle de PowerShell.
try { Add-Type -Namespace VisionShell -Name Identite -MemberDefinition '[DllImport("shell32.dll", CharSet = CharSet.Unicode)] public static extern int SetCurrentProcessExplicitAppUserModelID(string id);'; [void][VisionShell.Identite]::SetCurrentProcessExplicitAppUserModelID('FamilleRoy.Vision') } catch { }

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

# ------------------------------------------------------------------ Réglages de ce PC
# Propres à chaque PC et à chaque session : le thème de couleur, l'écran de veille,
# les tableaux et les cartes montrés. Home Assistant dit seulement ce qui est disponible.
$script:Themes = [ordered]@{
    'Vision'      = @{ Fond = '#FF120609'; Carte = '#FF27111A'; Haute = '#FF361724'; Ligne = '#FF4C2231'; Or = '#FFF2C14E'; OrSombre = '#FF1E1605'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFFBF3EE'; Texte2 = '#FFCDA8A6'; Texte3 = '#FF8C666C'; Horloge = 'defaut' }
    'Sombre'      = @{ Fond = '#FF17121C'; Carte = '#FF251C2D'; Haute = '#FF30253A'; Ligne = '#FF3A2D45'; Or = '#FFE2B24A'; OrSombre = '#FF1E1605'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF4EDE1'; Texte2 = '#FFBDB1C4'; Texte3 = '#FF8E8396'; Horloge = 'sombre' }
    'Bleu nuit'   = @{ Fond = '#FF0F1830'; Carte = '#FF1A2647'; Haute = '#FF223158'; Ligne = '#FF2B3A64'; Or = '#FFE2B24A'; OrSombre = '#FF1E1605'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFEAF0FA'; Texte2 = '#FFB6C1D4'; Texte3 = '#FF7F8CA3'; Horloge = 'bleu-nuit' }
    'Beige'       = @{ Fond = '#FFEFE6D6'; Carte = '#FFFBF6EC'; Haute = '#FFE6DBC6'; Ligne = '#FFD9CBB3'; Or = '#FF8F6110'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF2A2026'; Texte2 = '#FF6E5A5E'; Texte3 = '#FF8F7D80'; Horloge = 'beige' }
    'Sauge'       = @{ Fond = '#FFDDE5DA'; Carte = '#FFF2F6EF'; Haute = '#FFD0DACB'; Ligne = '#FFC2CEBD'; Or = '#FF7F5C0E'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF1F2A24'; Texte2 = '#FF5E6E64'; Texte3 = '#FF7F8F85'; Horloge = 'sauge' }
    'Salon'       = @{ Fond = '#FFD9D1C5'; Carte = '#FFF4F1EB'; Haute = '#FFCCC3B5'; Ligne = '#FFBDB3A4'; Or = '#FF8A6433'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF2A2724'; Texte2 = '#FF6B645C'; Texte3 = '#FF8E867D'; Horloge = 'salon' }
    'Rose poudré' = @{ Fond = '#FFF0DEDD'; Carte = '#FFFBF1F0'; Haute = '#FFE6D0CF'; Ligne = '#FFD9BFBE'; Or = '#FF875A12'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF2C1F24'; Texte2 = '#FF7A5A60'; Texte3 = '#FF998287'; Horloge = 'rose-poudre' }
    # Thèmes d'univers : jeux (Tactique, Briques, Corsaire, Royale), passions (Circuit, Cockpit, Bourse, Écrin), dehors (Prairie, Large, Sommet, Sous-bois).
    'Tactique' = @{ Fond = '#FF0F1923'; Carte = '#FF1B2733'; Haute = '#FF2E3843'; Ligne = '#FF2C3A47'; Or = '#FFFF4655'; OrSombre = '#FFFFFFFF'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFECE8E1'; Texte2 = '#FF9AA7B1'; Texte3 = '#FF69757F'; Horloge = 'tactique' }
    'Briques' = @{ Fond = '#FFF2F4F5'; Carte = '#FFFFFFFF'; Haute = '#FFE1E3E4'; Ligne = '#FFD5DADE'; Or = '#FF0A84D6'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF191B1D'; Texte2 = '#FF60666C'; Texte3 = '#FF93989C'; Horloge = 'briques' }
    'Corsaire' = @{ Fond = '#FF0B2A3A'; Carte = '#FF123C50'; Haute = '#FF264C5C'; Ligne = '#FF1F5166'; Or = '#FFF2A93B'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF4EBD0'; Texte2 = '#FFA9C3C9'; Texte3 = '#FF728D97'; Horloge = 'corsaire' }
    'Royale' = @{ Fond = '#FF1B1035'; Carte = '#FF2A1B55'; Haute = '#FF3C2E64'; Ligne = '#FF3D2A78'; Or = '#FFF8D21A'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF5F3FF'; Texte2 = '#FFB9AEE0'; Texte3 = '#FF8277A4'; Horloge = 'royale' }
    'Circuit' = @{ Fond = '#FF121212'; Carte = '#FF1E1E1E'; Haute = '#FF313131'; Ligne = '#FF363636'; Or = '#FFE5281B'; OrSombre = '#FFFFFFFF'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF2F2F2'; Texte2 = '#FFA0A0A0'; Texte3 = '#FF6E6E6E'; Horloge = 'circuit' }
    'Cockpit' = @{ Fond = '#FF0E1A24'; Carte = '#FF16283A'; Haute = '#FF293A4B'; Ligne = '#FF25405A'; Or = '#FFFFB000'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFE8F1F8'; Texte2 = '#FF9DB2C4'; Texte3 = '#FF6B7D8C'; Horloge = 'cockpit' }
    'Bourse' = @{ Fond = '#FF0B0F0E'; Carte = '#FF141B19'; Haute = '#FF272E2C'; Ligne = '#FF24302C'; Or = '#FF21C77A'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFE6F2EC'; Texte2 = '#FF8FA59B'; Texte3 = '#FF61706A'; Horloge = 'bourse' }
    'Écrin' = @{ Fond = '#FF0E0C0A'; Carte = '#FF1A1714'; Haute = '#FF2E2A26'; Ligne = '#FF322B22'; Or = '#FFC9A45C'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF3EBDD'; Texte2 = '#FFB4A68F'; Texte3 = '#FF7A7060'; Horloge = 'ecrin' }
    'Prairie' = @{ Fond = '#FFEEF3E6'; Carte = '#FFFAFCF5'; Haute = '#FFDEE3D6'; Ligne = '#FFCFDBC2'; Or = '#FF4F8A2B'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF22301F'; Texte2 = '#FF5F7058'; Texte3 = '#FF919E8A'; Horloge = 'prairie' }
    'Large' = @{ Fond = '#FFE6F1F5'; Carte = '#FFF7FBFD'; Haute = '#FFD5E2E6'; Ligne = '#FFC3D9E1'; Or = '#FF0F7EA3'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF12303D'; Texte2 = '#FF55737F'; Texte3 = '#FF889FA8'; Horloge = 'large' }
    'Sommet' = @{ Fond = '#FFE9EDF1'; Carte = '#FFF8FAFC'; Haute = '#FFD9DDE2'; Ligne = '#FFCBD3DB'; Or = '#FFC2553A'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF1F2933'; Texte2 = '#FF5C6B7A'; Texte3 = '#FF8D98A4'; Horloge = 'sommet' }
    'Sous-bois' = @{ Fond = '#FF1A2119'; Carte = '#FF252E23'; Haute = '#FF373F33'; Ligne = '#FF36422F'; Or = '#FFC58B3B'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFECE6D6'; Texte2 = '#FFA9B19C'; Texte3 = '#FF777F6E'; Horloge = 'sous-bois' }
    # Thèmes d'histoires : écran (Code, Plume, Galaxie, Rétro 85, Grimoire), contes (Féerie, Banquise, Lagon), créatures (Étincelle)
    'Code' = @{ Fond = '#FF030A05'; Carte = '#FF0A1A10'; Haute = '#FF1C2F23'; Ligne = '#FF13301F'; Or = '#FF2BEA6B'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFD7FFE0'; Texte2 = '#FF6FBF87'; Texte3 = '#FF49805A'; Horloge = 'code' }
    'Plume' = @{ Fond = '#FFE8F1F7'; Carte = '#FFF8FBFD'; Haute = '#FFE5E9EC'; Ligne = '#FFC9D8E2'; Or = '#FFA8552F'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF23313D'; Texte2 = '#FF5F7482'; Texte3 = '#FF8FA0AB'; Horloge = 'plume' }
    'Galaxie' = @{ Fond = '#FF05060A'; Carte = '#FF10131C'; Haute = '#FF25272E'; Ligne = '#FF23283A'; Or = '#FFFFD426'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF4F1E4'; Texte2 = '#FF9AA0B4'; Texte3 = '#FF666A78'; Horloge = 'galaxie' }
    'Rétro 85' = @{ Fond = '#FF14100E'; Carte = '#FF221B17'; Haute = '#FF352E29'; Ligne = '#FF3A2E27'; Or = '#FFFF7A1A'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF6EDE2'; Texte2 = '#FFB8A698'; Texte3 = '#FF7F7268'; Horloge = 'retro-85' }
    'Grimoire' = @{ Fond = '#FF1C1210'; Carte = '#FF2A1C18'; Haute = '#FF3C2E28'; Ligne = '#FF44302A'; Or = '#FFD4A843'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF1E6CF'; Texte2 = '#FFB9A583'; Texte3 = '#FF82725B'; Horloge = 'grimoire' }
    'Féerie' = @{ Fond = '#FF141A3C'; Carte = '#FF1F2757'; Haute = '#FF323966'; Ligne = '#FF303A78'; Or = '#FFFFD36E'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF6F3FF'; Texte2 = '#FFB4B8E0'; Texte3 = '#FF7C81A7'; Horloge = 'feerie' }
    'Banquise' = @{ Fond = '#FFE9F4FB'; Carte = '#FFF8FCFF'; Haute = '#FFE4EAEE'; Ligne = '#FFC5DDEC'; Or = '#FF2F8FCB'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF173247'; Texte2 = '#FF5C7C92'; Texte3 = '#FF8DA6B7'; Horloge = 'banquise' }
    'Lagon' = @{ Fond = '#FF06343B'; Carte = '#FF0C4750'; Haute = '#FF21565D'; Ligne = '#FF1A5F69'; Or = '#FFFF8A5B'; OrSombre = '#FF1A1408'; Vert = '#FF4CC38A'; Rouge = '#FFFF6B6B'; Texte = '#FFF3F0DC'; Texte2 = '#FF9CC7C2'; Texte3 = '#FF689493'; Horloge = 'lagon' }
    'Étincelle' = @{ Fond = '#FFFFF4CC'; Carte = '#FFFFFBEA'; Haute = '#FFECE8D7'; Ligne = '#FFEBD98F'; Or = '#FFD93A2B'; OrSombre = '#FFFFFFFF'; Vert = '#FF2E7D57'; Rouge = '#FFB3261E'; Texte = '#FF2B2416'; Texte2 = '#FF75683F'; Texte3 = '#FFA59970'; Horloge = 'etincelle' }
}
$script:SvFichier = Join-Path $env:APPDATA 'Vision\veille.json'
function SvReglages() {
    $r = @{ actif = $true; delai = 10; theme = 'Vision'; style = 'doux'; fondCartes = $true; contourCartes = $false; animer = $true; masques = @(); cartes = @(); figees = @(); verrou = $false; codeSel = ''; codeHash = '' }
    try {
        if (Test-Path $script:SvFichier) {
            $lu = Get-Content $script:SvFichier -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($null -ne (Prop $lu 'actif')) { $r.actif = [bool](Prop $lu 'actif') }
            if (Prop $lu 'delai') { $r.delai = [int](Prop $lu 'delai') }
            if ($script:Themes.Contains([string](Prop $lu 'theme'))) { $r.theme = [string](Prop $lu 'theme') }
            if (@('doux', 'neoretro') -contains [string](Prop $lu 'style')) { $r.style = [string](Prop $lu 'style') }
            if ($null -ne (Prop $lu 'fondCartes')) { $r.fondCartes = [bool](Prop $lu 'fondCartes') }
            if ($null -ne (Prop $lu 'contourCartes')) { $r.contourCartes = [bool](Prop $lu 'contourCartes') }
            if ($null -ne (Prop $lu 'animer')) { $r.animer = [bool](Prop $lu 'animer') }
            if ($null -ne (Prop $lu 'verrou')) { $r.verrou = [bool](Prop $lu 'verrou') }
            $r.codeSel = [string](Prop $lu 'codeSel' ''); $r.codeHash = [string](Prop $lu 'codeHash' '')
            $r.masques = @(@(Prop $lu 'masques' @()) | ForEach-Object { [string]$_ })
            $r.cartes = @(@(Prop $lu 'cartes' @()) | ForEach-Object { [string]$_ })
            $r.figees = @(@(Prop $lu 'figees' @()) | ForEach-Object { [string]$_ })
        }
    } catch { }
    return $r
}
function SvEcrire($r) {
    try {
        $d = Split-Path $script:SvFichier -Parent
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
        (@{ actif = [bool]$r.actif; delai = [int]$r.delai; theme = [string]$r.theme; style = [string]$r.style; fondCartes = [bool]$r.fondCartes; contourCartes = [bool]$r.contourCartes; animer = [bool]$r.animer; masques = @($r.masques); cartes = @($r.cartes); figees = @($r.figees); verrou = [bool]$r.verrou; codeSel = [string]$r.codeSel; codeHash = [string]$r.codeHash } | ConvertTo-Json -Compress) | Set-Content -Path $script:SvFichier -Encoding UTF8
    } catch { }
}
$script:Pal = $script:Themes[(SvReglages).theme]
function SvPinceau([string]$cle) {
    $noms = @{ fond = 'Fond'; carte = 'Carte'; encre = 'Texte'; encre2 = 'Texte2'; accent = 'Or'; piste = 'Ligne' }
    return (New-Object System.Windows.Media.BrushConverter).ConvertFromString($script:Pal[$noms[$cle]])
}

# ------------------------------------------------------------------ XAML
function CreerFenetre() {
[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Vision" Width="620" Height="760" WindowStartupLocation="CenterScreen"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent" ResizeMode="NoResize"
        Topmost="True" ShowInTaskbar="True" FontFamily="Segoe UI">
  <Window.Resources>
    <SolidColorBrush x:Key="Fond" Color="$($script:Pal.Fond)"/>
    <SolidColorBrush x:Key="Carte" Color="$($script:Pal.Carte)"/>
    <SolidColorBrush x:Key="Haute" Color="$($script:Pal.Haute)"/>
    <SolidColorBrush x:Key="Ligne" Color="$($script:Pal.Ligne)"/>
    <SolidColorBrush x:Key="Or" Color="$($script:Pal.Or)"/>
    <SolidColorBrush x:Key="OrSombre" Color="$($script:Pal.OrSombre)"/>
    <SolidColorBrush x:Key="Vert" Color="$($script:Pal.Vert)"/>
    <SolidColorBrush x:Key="Rouge" Color="$($script:Pal.Rouge)"/>
    <SolidColorBrush x:Key="Texte" Color="$($script:Pal.Texte)"/>
    <SolidColorBrush x:Key="Texte2" Color="$($script:Pal.Texte2)"/>
    <SolidColorBrush x:Key="Texte3" Color="$($script:Pal.Texte3)"/>

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
    <Style x:Key="Coche" TargetType="CheckBox">
      <Setter Property="Foreground" Value="{StaticResource Texte}"/>
      <Setter Property="FontSize" Value="13"/>
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="CheckBox">
            <StackPanel Orientation="Horizontal" Background="Transparent">
              <Border x:Name="boite" Width="22" Height="22" CornerRadius="7" Background="{StaticResource Haute}" BorderBrush="{StaticResource Ligne}" BorderThickness="1.5" VerticalAlignment="Center">
                <Path x:Name="trait" Data="M4.5,10 L8.5,14 L15,5.5" Stroke="{StaticResource OrSombre}" StrokeThickness="2.4" StrokeStartLineCap="Round" StrokeEndLineCap="Round" StrokeLineJoin="Round" Visibility="Collapsed"/>
              </Border>
              <ContentPresenter Margin="11,0,0,0" VerticalAlignment="Center"/>
            </StackPanel>
            <ControlTemplate.Triggers>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="boite" Property="Background" Value="{StaticResource Or}"/>
                <Setter TargetName="boite" Property="BorderBrush" Value="{StaticResource Or}"/>
                <Setter TargetName="trait" Property="Visibility" Value="Visible"/>
              </Trigger>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="boite" Property="BorderBrush" Value="{StaticResource Or}"/></Trigger>
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
          <Button x:Name="Plein" Style="{StaticResource Secondaire}" Padding="10,4" Content="⛶" FontSize="12" Margin="0,0,6,0" ToolTip="Plein écran"/>
          <Button x:Name="Fermer" Style="{StaticResource Secondaire}" Padding="10,4" Content="✕" FontSize="12"/>
        </StackPanel>
      </Grid>
      <StackPanel x:Name="Onglets" DockPanel.Dock="Top" Orientation="Horizontal" Margin="24,8,24,10"/>
      <ScrollViewer VerticalScrollBarVisibility="Auto" Margin="12,0,6,16" Padding="12,0,10,0">
        <StackPanel x:Name="Contenu" MaxWidth="1100"/>
      </ScrollViewer>
    </DockPanel>
  </Border>
</Window>
"@

$lecteur = New-Object System.Xml.XmlNodeReader $xaml
$script:W = [Windows.Markup.XamlReader]::Load($lecteur)
$W.Add_MouseLeftButtonDown({ param($s, $e) if ($e.ButtonState -eq 'Pressed') { try { $script:W.DragMove() } catch { } } })
$W.FindName('Fermer').Add_Click({ $script:Deverrouille = $false; $script:W.Hide() })
$script:Contenu = $W.FindName('Contenu')
$script:Onglets = $W.FindName('Onglets')
$script:logoPath = Join-Path $script:Dossier 'vision.png'
if (Test-Path $script:logoPath) {
    try {
        $bmp = New-Object System.Windows.Media.Imaging.BitmapImage
        $bmp.BeginInit(); $bmp.UriSource = New-Object Uri($script:logoPath); $bmp.CacheOption = 'OnLoad'; $bmp.EndInit()
        $W.FindName('Logo').Source = $bmp
        $W.Icon = $bmp
    } catch { }
}
$W.Add_Closing({ param($s, $e) if ($s -ne $script:W) { return }; $e.Cancel = $true; $script:Deverrouille = $false; $script:W.Hide() })
# Sans cela, une fenêtre WPF ouverte depuis une boucle Windows Forms ne reçoit pas les frappes : impossible d'écrire un mot.
try { Add-Type -AssemblyName WindowsFormsIntegration; [System.Windows.Forms.Integration.ElementHost]::EnableModelessKeyboardInterop($W) } catch { }
$W.FindName('Plein').Add_Click({ $script:W.WindowState = $(if ($script:W.WindowState -eq 'Maximized') { 'Normal' } else { 'Maximized' }) })
}
CreerFenetre

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

# ------------------------------------------------------------------ Verrou de la fenêtre
# À l'ouverture, Vision peut demander Windows Hello (empreinte, visage, code Windows) ou son propre code.
# Le verrou se remet dès que la fenêtre est fermée. Le code n'est jamais gardé en clair : seule son empreinte l'est.
$script:Deverrouille = $false
$script:VerrouAffiche = $false
function CodeEmpreinte([string]$code, [string]$sel) {
    $d = New-Object System.Security.Cryptography.Rfc2898DeriveBytes($code, [Convert]::FromBase64String($sel), 20000)
    try { return [Convert]::ToBase64String($d.GetBytes(32)) } finally { $d.Dispose() }
}
function CodePoser([string]$code) {
    $sel = New-Object byte[] 16
    $g = [System.Security.Cryptography.RandomNumberGenerator]::Create(); $g.GetBytes($sel); $g.Dispose()
    $rr = SvReglages; $rr.codeSel = [Convert]::ToBase64String($sel); $rr.codeHash = (CodeEmpreinte $code $rr.codeSel); SvEcrire $rr
}
function CodeJuste([string]$code) {
    $rr = SvReglages
    if (-not $rr.codeHash -or -not $rr.codeSel -or -not $code) { return $false }
    try { return ((CodeEmpreinte $code $rr.codeSel) -ceq $rr.codeHash) } catch { return $false }
}
function HelloAttendre($operation, [Type]$type) {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $methode = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -like 'IAsyncOperation*' } | Select-Object -First 1
    $tache = $methode.MakeGenericMethod($type).Invoke($null, @($operation))
    # La fenêtre continue de vivre pendant que Windows pose sa question.
    $fin = (Get-Date).AddSeconds(90)
    while (-not $tache.IsCompleted -and (Get-Date) -lt $fin) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 40 }
    if (-not $tache.IsCompleted -or $tache.IsFaulted) { return $null }
    return $tache.Result
}
function HelloDisponible() {
    if ($null -ne $script:HelloVu) { return $script:HelloVu }
    $script:HelloVu = $false
    try {
        [void][Windows.Security.Credentials.UI.UserConsentVerifier, Windows.Security.Credentials.UI, ContentType = WindowsRuntime]
        $r = HelloAttendre ([Windows.Security.Credentials.UI.UserConsentVerifier]::CheckAvailabilityAsync()) ([Windows.Security.Credentials.UI.UserConsentVerifierAvailability])
        $script:HelloVu = ([string]$r -eq 'Available')
    } catch { }
    return $script:HelloVu
}
function HelloDemander() {
    if ($script:HelloEnCours) { return $false }
    $script:HelloEnCours = $true
    try {
        $r = HelloAttendre ([Windows.Security.Credentials.UI.UserConsentVerifier]::RequestVerificationAsync('Ouvrir Vision')) ([Windows.Security.Credentials.UI.UserConsentVerificationResult])
        return ([string]$r -eq 'Verified')
    } catch { return $false } finally { $script:HelloEnCours = $false }
}
function CodeEssayer() {
    $pb = $script:ChampCode; $erreur = $script:VerrouErreur
    if (-not $pb) { return }
    # Après cinq essais faux, une pause qui s'allonge : pas de devinette à la chaîne.
    if ($script:CodeBloqueJusqua -and (Get-Date) -lt $script:CodeBloqueJusqua) { $erreur.Text = ('Trop d''essais. Réessaie dans {0} s.' -f [int][Math]::Ceiling(($script:CodeBloqueJusqua - (Get-Date)).TotalSeconds)); $erreur.Visibility = 'Visible'; return }
    if (CodeJuste $pb.Password) { Deverrouiller; return }
    $script:EssaisCode = [int]$script:EssaisCode + 1
    if ($script:EssaisCode -ge 5) { $script:CodeBloqueJusqua = (Get-Date).AddSeconds([Math]::Min(300, 30 * ($script:EssaisCode - 4))) }
    $pb.Clear(); $erreur.Text = 'Ce n''est pas le bon code.'; $erreur.Visibility = 'Visible'
}
function CodeEnregistrer() {
    $nouveau = $script:CodeNouveau; $noteC = $script:CodeNote
    if (-not $nouveau) { return }
    if ($nouveau.Password.Length -lt 4) { $noteC.Text = 'Le code doit faire au moins 4 caractères.'; $noteC.Foreground = (Pinceau 'Rouge'); return }
    CodePoser $nouveau.Password; $nouveau.Clear(); Rafraichir
}
function Deverrouiller() { $script:Deverrouille = $true; $script:VerrouAffiche = $false; $script:EssaisCode = 0; $script:ChampCode = $null; Rafraichir }
function PageVerrou() {
    $script:VerrouAffiche = $true; $script:ChampCode = $null
    $carte = Carte; $carte.MaxWidth = 460; $carte.Margin = [System.Windows.Thickness]::new(0, 30, 0, 0); $carte.HorizontalAlignment = 'Center'
    $carte.Child.Children.Add((Txt 'Vision est verrouillée' 20 'Texte' $true '0,0,0,4')) | Out-Null
    $rr = SvReglages
    $hello = HelloDisponible
    $carte.Child.Children.Add((Txt $(if ($hello -and $rr.codeHash) { 'Windows Hello ou le code de Vision pour entrer.' } elseif ($hello) { 'Windows Hello pour entrer.' } else { 'Le code de Vision pour entrer.' }) 12 'Texte2' $false '0,0,0,14')) | Out-Null
    if ($hello) {
        $bh = Bouton 'Déverrouiller avec Windows Hello' 'Primaire' { if (HelloDemander) { Deverrouiller } else { try { $script:W.Activate() | Out-Null } catch { } } }
        $bh.HorizontalAlignment = 'Left'; $bh.Margin = [System.Windows.Thickness]::new(0, 0, 0, 12)
        $carte.Child.Children.Add($bh) | Out-Null
    }
    if ($rr.codeHash) {
        $ligne = Rangee
        $pb = New-Object System.Windows.Controls.PasswordBox
        $pb.Width = 180; $pb.FontSize = 16; $pb.Padding = [System.Windows.Thickness]::new(10, 7, 10, 7); $pb.MaxLength = 32; $pb.VerticalContentAlignment = 'Center'
        $pb.Background = (Pinceau 'Haute'); $pb.Foreground = (Pinceau 'Texte'); $pb.BorderBrush = (Pinceau 'Ligne'); $pb.Margin = [System.Windows.Thickness]::new(0, 0, 8, 0)
        $erreur = Txt '' 12 'Rouge' $false '0,8,0,0'; $erreur.Visibility = 'Collapsed'
        $script:ChampCode = $pb; $script:VerrouErreur = $erreur
        $pb.Add_KeyDown({ param($s, $e) if ($e.Key -eq 'Return') { CodeEssayer } })
        $ligne.Children.Add($pb) | Out-Null
        $ligne.Children.Add((Bouton 'Entrer' 'Secondaire' { CodeEssayer })) | Out-Null
        $carte.Child.Children.Add($ligne) | Out-Null
        $carte.Child.Children.Add($erreur) | Out-Null
    }
    $Contenu.Children.Add($carte) | Out-Null
}

# ------------------------------------------------------------------ Pages
$script:Page = 'maison'
$script:Vue = $null          # une sous-vue ouverte (fermés, planning, catégories) : @{ type; appareil }

function Rafraichir() {
    $etat = Lire 'etat.json'
    $ferme = ($null -ne $etat -and [bool](Prop $etat 'ferme' $false))
    $W.FindName('ChipEtatTexte').Text = $(if ($ferme) { 'FERMÉ' } else { 'OUVERT' })
    $W.FindName('ChipEtatTexte').Foreground = (Pinceau $(if ($ferme) { 'Rouge' } else { 'Vert' }))
    # Verrouillée : ni onglets ni contenu tant que Windows Hello ou le code n'a pas ouvert.
    $rv = SvReglages
    if ($rv.verrou -and -not $script:Deverrouille -and ($rv.codeHash -or (HelloDisponible))) {
        if ($script:VerrouAffiche) { return }
        $Onglets.Children.Clear(); $Contenu.Children.Clear(); PageVerrou; return
    }
    $script:VerrouAffiche = $false
    $parent = Test-Path (Join-Path $script:Dossier 'maison.json')
    if (-not $parent -and $script:Page -eq 'maison') { $script:Page = 'moi' }
    $Onglets.Children.Clear()
    $defsOnglets = @()
    if ($parent) { $defsOnglets += , @('maison', 'La maison') }
    $defsOnglets += , @('moi', 'Cet ordinateur'); $defsOnglets += , @('reglages', 'Réglages')
    if ($true) {
        foreach ($def in $defsOnglets) {
            $t = New-Object System.Windows.Controls.Primitives.ToggleButton
            $t.Content = $def[1]; $t.Style = $W.Resources['Onglet']; $t.Tag = $def[0]; $t.IsChecked = ($script:Page -eq $def[0])
            $t.Add_Click({ param($s, $e) $script:Page = [string]$s.Tag; $script:Vue = $null; Rafraichir })
            $Onglets.Children.Add($t) | Out-Null
        }
    }
    $Contenu.Children.Clear()
    if ($script:Vue) { PageSousVue; return }
    if ($script:Page -eq 'maison') { PageMaison } elseif ($script:Page -eq 'reglages') { PageReglages } else { PageMoi $etat $ferme }
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
            $duree = [string](Prop $d 'duree'); $cats = @(Prop $d 'etiquettes' @())
            switch ($duree) {
                '1h' { $det += 'Souhait : 1 heure' }
                'toujours' { $det += 'Souhait : en permanence (quand l''écran est ouvert)' }
                'categorie' { $det += ('Souhait : toute la catégorie' + $(if ($cats.Count) { ' (' + ($cats -join ', ') + ')' } else { '' })) }
            }
            if ($det.Count) { $sp.Children.Add((Txt ($det -join '   ') 12 'Texte2' $false '0,4,0,0')) | Out-Null }
            $r = Rangee; $r.Margin = [System.Windows.Thickness]::new(0, 12, 0, 0)
            $choix = @(@('1 h', 'temporaire', 60, $(if ($duree -eq '1h') { 'Primaire' } else { 'Secondaire' })), @('Toujours', 'toujours', 0, $(if ($duree -eq 'toujours' -or -not $duree) { 'Primaire' } else { 'Secondaire' })))
            if ($cats.Count) { $choix += ,@('Catégorie', 'categorie', 0, $(if ($duree -eq 'categorie') { 'Primaire' } else { 'Secondaire' })) }
            $choix += ,@('Non', 'non', 0, 'Danger')
            foreach ($def in $choix) {
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

function EnvoyerMot($a) { $script:Vue = @{ type = 'mot'; appareil = $a }; Rafraichir }

function ChampLong([string]$indice) {
    $tb = Champ $indice
    $tb.AcceptsReturn = $true; $tb.TextWrapping = 'Wrap'; $tb.Height = 72; $tb.VerticalContentAlignment = 'Top'
    return $tb
}

# Tout se passe dans la fenêtre : pas de boîte de dialogue à côté.
function VueMot($a) {
    $prenom = [string](Prop $a 'prenom'); if (-not $prenom) { $prenom = [string](Prop $a 'nom') }
    $c = Carte; $sp = $c.Child
    $sp.Children.Add((Txt "Le mot s'affiche sur l'appareil de $prenom." 12 'Texte2' $false '0,0,0,10')) | Out-Null
    $texte = ChampLong 'Ton message'
    $sp.Children.Add($texte) | Out-Null
    $ok = Bouton 'Envoyer' 'Primaire' {
        param($s, $e); $t = $s.Tag
        $m = Valeur $t.texte
        if (-not $m) { return }
        Agir @{ action = 'message'; pc = [string](Prop $t.appareil 'id'); texte = [string]$m }
        $s.Content = 'Envoyé ✓'; $s.IsEnabled = $false
    } @{ texte = $texte; appareil = $a }
    $ok.HorizontalAlignment = 'Right'
    $sp.Children.Add($ok) | Out-Null
    $Contenu.Children.Add($c) | Out-Null
}

# La demande d'accès de l'enfant : pour qui, pourquoi, et pour combien de temps.
function VueDemande($item) {
    $c = Carte 'Haute'; $sp = $c.Child
    $sp.Children.Add((Txt ([string]$item.nom) 17 'Texte' $true)) | Out-Null
    $sousTitre = [string]$item.type
    if ($item.raison) { $sousTitre += ' · fermé car : ' + [string]$item.raison }
    $sp.Children.Add((Txt $sousTitre 12 'Texte2' $false '0,2,0,0')) | Out-Null
    $Contenu.Children.Add($c) | Out-Null

    $c2 = Carte; $sp2 = $c2.Child
    $lien = $null
    if ($item.genre -eq 'sites' -and $item.saisie) {
        $sp2.Children.Add((Txt 'Le site' 12 'Texte2' $false '0,0,0,6')) | Out-Null
        $lien = Champ 'Colle le lien ou le nom du site'
        if ($item.lien) { $lien.Text = [string]$item.lien; $lien.Foreground = (Pinceau 'Texte') }
        $sp2.Children.Add($lien) | Out-Null
    }
    $sp2.Children.Add((Txt 'Pourquoi en as-tu besoin ? Les parents le liront.' 12 'Texte2' $false '0,0,0,6')) | Out-Null
    $motif = ChampLong 'Explique en quelques mots (facultatif)'
    $sp2.Children.Add($motif) | Out-Null
    $sp2.Children.Add((Txt 'Pour combien de temps ?' 12 'Texte2' $false '0,4,0,6')) | Out-Null
    $script:DureeChoisie = '1h'
    $rd = Rangee
    $boutons = @()
    foreach ($def in @(@('1h', 'Pour 1 heure'), @('toujours', 'En permanence'), @('categorie', 'Toute la catégorie'))) {
        $t = New-Object System.Windows.Controls.Primitives.ToggleButton
        $t.Content = $def[1]; $t.Style = $W.Resources['Onglet']; $t.Tag = $def[0]; $t.IsChecked = ($def[0] -eq '1h'); $t.Margin = [System.Windows.Thickness]::new(0, 0, 8, 0)
        $t.Add_Click({ param($s, $e) $script:DureeChoisie = [string]$s.Tag; foreach ($x in $s.Parent.Children) { $x.IsChecked = ($x.Tag -eq $s.Tag) } })
        $rd.Children.Add($t) | Out-Null
    }
    $sp2.Children.Add($rd) | Out-Null
    $sp2.Children.Add((Txt '« En permanence » : à chaque fois que ton écran est ouvert. « Toute la catégorie » : aussi ce qui est fermé pour la même raison (par exemple tous les jeux).' 11 'Texte3' $false '0,8,0,12')) | Out-Null
    $ok = Bouton "Demander l'accès" 'Primaire' {
        param($s, $e); $t = $s.Tag
        $nom = [string]$t.item.nom; $l = ''
        if ($t.lien) {
            $l = Valeur $t.lien; $h = Hote $l
            if (-not $h -or $h -notlike '*.*') { $t.erreur.Text = 'Ce lien ne ressemble pas à un site. Exemple : youtube.com'; $t.erreur.Visibility = 'Visible'; return }
            $nom = $h
        }
        Deposer @{ genre = [string]$t.item.genre; nom = $nom; libelle = $nom; lien = $l; motif = (Valeur $t.motif); duree = [string]$script:DureeChoisie }
        $script:Demandees[[string]$t.item.genre + ':' + $nom] = $true
        $s.Content = 'Envoyé aux parents ✓'; $s.IsEnabled = $false
        $t.erreur.Text = 'Tu seras prévenu de la réponse ici et par une notification.'; $t.erreur.Foreground = (Pinceau 'Vert'); $t.erreur.Visibility = 'Visible'
    } @{ item = $item; motif = $motif; lien = $lien; erreur = $null }
    $erreur = Txt '' 12 'Rouge' $false '0,8,0,0'; $erreur.Visibility = 'Collapsed'
    $ok.Tag.erreur = $erreur
    $ok.HorizontalAlignment = 'Right'
    $sp2.Children.Add($ok) | Out-Null
    $sp2.Children.Add($erreur) | Out-Null
    $Contenu.Children.Add($c2) | Out-Null
}

function PageSousVue() {
    $a = $script:Vue.appareil
    $prenom = ''
    if ($a) { $prenom = [string](Prop $a 'prenom'); if (-not $prenom) { $prenom = [string](Prop $a 'nom') } }
    switch ($script:Vue.type) {
        'fermes' { Retour "Ce qui est fermé chez $prenom"; VueFermes $a }
        'planning' { Retour "Planning de $prenom"; VuePlanning $a }
        'categories' { Retour "Catégories de $prenom"; VueCategories $a }
        'mot' { Retour "Un mot pour $prenom"; VueMot $a }
        'demande' { Retour "Demander l'accès"; VueDemande $script:Vue.item }
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
            $detailCat = New-Object System.Windows.Controls.StackPanel; $detailCat.Visibility = 'Collapsed'; $detailCat.Margin = [System.Windows.Thickness]::new(0, 6, 0, 0)
            foreach ($x in @(Prop $c 'apps' @())) { $detailCat.Children.Add((Txt ('•  ' + [string](Prop $x 'libelle')) 12 'Texte')) | Out-Null }
            foreach ($x in @(Prop $c 'sites' @())) { $detailCat.Children.Add((Txt ('◦  ' + [string]$x) 12 'Texte2')) | Out-Null }
            if ($detailCat.Children.Count -eq 0) { $detailCat.Children.Add((Txt 'Rien de classé ici pour l''instant.' 12 'Texte3')) | Out-Null }
            $g.Children.Add($detailCat) | Out-Null
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

    $data = Lire 'fermes.json'

    # Ce qui vient d'être bloqué : les derniers refus, pour demander tout de suite.
    $recents = @(Prop $data 'recents' @())
    if ($recents.Count -gt 0) {
        $Contenu.Children.Add((Section 'Bloqué récemment')) | Out-Null
        $cr = Carte 'Haute'; $spr = $cr.Child
        $k = 0
        foreach ($x in ($recents | Select-Object -First 8)) {
            if ($k++ -gt 0) { $spr.Children.Add((Separateur)) | Out-Null }
            $genre = [string](Prop $x 'genre' 'apps'); $nom = [string](Prop $x 'nom'); $raison = [string](Prop $x 'raison')
            $type = $(if ($genre -eq 'sites') { 'Site' } else { 'Appli' })
            $g = New-Object System.Windows.Controls.StackPanel
            $g.Children.Add((Txt $nom 14 'Or' $true)) | Out-Null
            $g.Children.Add((Txt (([string](Prop $x 'quand')) + ' · ' + $type + $(if ($raison) { ' · ' + $raison } else { '' })) 11 'Texte2')) | Out-Null
            $deja = $script:Demandees.ContainsKey($genre + ':' + $nom)
            $b = Bouton $(if ($deja) { 'Demandé ✓' } else { 'Demander' }) 'Primaire' {
                param($s, $e); $script:Vue = @{ type = 'demande'; item = $s.Tag }; Rafraichir
            } @{ genre = $genre; nom = $nom; raison = $raison; type = $type; saisie = $false }
            if ($deja) { $b.IsEnabled = $false }
            $spr.Children.Add((Deux $g $b)) | Out-Null
        }
        $Contenu.Children.Add($cr) | Out-Null
    }

    $Contenu.Children.Add((Section 'Ce qui est fermé ici')) | Out-Null
    $Contenu.Children.Add((Txt "Choisis une ligne et demande l'accès : tu diras pourquoi et pour combien de temps, un parent répond sur son téléphone." 12 'Texte2' $false '0,0,0,8')) | Out-Null
    $filtre = Champ 'Chercher une appli ou un site'
    $Contenu.Children.Add($filtre) | Out-Null
    $card = Carte; $sp2 = $card.Child
    $script:VM = @{ sp2 = $sp2; filtre = $filtre; data = $data }
    $script:RemplirMoi = {
        $sp2 = $script:VM.sp2; $filtre = $script:VM.filtre; $data = $script:VM.data
        $sp2.Children.Clear()
        $q = (Valeur $filtre).ToLowerInvariant()
        $lignes = @()
        foreach ($x in @(Prop $data 'apps' @())) { $lignes += @{ genre = 'apps'; nom = [string](Prop $x 'nom'); raison = [string](Prop $x 'raison'); type = 'Appli'; recent = [bool](Prop $x 'recent' $false) } }
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
                param($s, $e); $script:Vue = @{ type = 'demande'; item = $s.Tag }; Rafraichir
            } @{ genre = $l.genre; nom = $l.nom; raison = $l.raison; type = $l.type; saisie = $false }
            if ($deja) { $b.IsEnabled = $false }
            $sp2.Children.Add((Deux $g $b)) | Out-Null
        }
    }
    & $script:RemplirMoi
    $filtre.Add_TextChanged({ & $script:RemplirMoi })
    $Contenu.Children.Add($card) | Out-Null

    $Contenu.Children.Add((Section 'Un autre site')) | Out-Null
    $c3 = Carte; $sp3 = $c3.Child
    $presse = ''
    try { $pp = [System.Windows.Clipboard]::GetText(); if ($pp -match '^https?://\S+$') { $presse = $pp.Trim() } } catch { }
    $sp3.Children.Add((Txt $(if ($presse) { 'Un lien est dans le presse-papiers : ' + $presse } else { 'Un site qui n''est pas dans la liste.' }) 12 'Texte2' $false '0,0,0,10')) | Out-Null
    $ok = Bouton "Demander l'accès à un site…" 'Secondaire' {
        param($s, $e); $script:Vue = @{ type = 'demande'; item = @{ genre = 'sites'; nom = $(if ($s.Tag) { Hote $s.Tag } else { 'Un autre site' }); raison = ''; type = 'Site'; saisie = $true; lien = [string]$s.Tag } }; Rafraichir
    } $presse
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
    $script:VerrouAffiche = $false
    Rafraichir
    $script:W.Show(); $script:W.Activate()
    # Verrouillée : Windows Hello se propose de lui-même, le code reste possible à côté.
    if ($script:VerrouAffiche) {
        if ($script:ChampCode) { try { $script:ChampCode.Focus() | Out-Null } catch { } }
        if (HelloDisponible) { if (HelloDemander) { Deverrouiller }; try { $script:W.Activate() | Out-Null } catch { } }
    }
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

# ------------------------------------------------------------------ Écran de veille
# Le PC a le même écran de veille que les télés : l'horloge, puis les tableaux de
# bord que Home Assistant rend disponibles (l'agent dépose veille.json). Chaque
# PC garde ses propres réglages (activé, délai, thème) dans le profil de l'utilisateur.
$svNatif = 'using System; using System.Runtime.InteropServices; public static class VisionVeilleNatif { [StructLayout(LayoutKind.Sequential)] struct LII { public uint cb; public uint t; } [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p); [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow(); [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; } [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r); [DllImport("user32.dll")] static extern IntPtr GetDesktopWindow(); [DllImport("user32.dll")] static extern IntPtr GetShellWindow(); public static uint Inactif() { LII l = new LII(); l.cb = (uint)Marshal.SizeOf(l); if (!GetLastInputInfo(ref l)) return 0; return ((uint)Environment.TickCount - l.t) / 1000; } public static bool PleinEcran(int w, int h) { IntPtr f = GetForegroundWindow(); if (f == IntPtr.Zero || f == GetDesktopWindow() || f == GetShellWindow()) return false; RECT r; if (!GetWindowRect(f, out r)) return false; return (r.R - r.L) >= w && (r.B - r.T) >= h; } delegate bool Enum(IntPtr h, IntPtr l); [DllImport("user32.dll")] static extern bool EnumWindows(Enum f, IntPtr l); [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid); [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h); [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr apres, int x, int y, int cx, int cy, uint drapeaux); public static int Devant(int[] pids) { System.Collections.Generic.List<uint> s = new System.Collections.Generic.List<uint>(); foreach (int p in pids) s.Add((uint)p); int n = 0; EnumWindows(delegate(IntPtr h, IntPtr l) { uint pid; GetWindowThreadProcessId(h, out pid); if (s.Contains(pid) && IsWindowVisible(h)) { SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040); n++; } return true; }, IntPtr.Zero); return n; } }'
$script:SvPret = $false
try { Add-Type -TypeDefinition $svNatif -ErrorAction Stop; $script:SvPret = $true } catch { }

$script:SvFenetres = @()
$script:SvScenes = @()
$script:SvHeures = @()
$script:SvListe = @()
$script:SvIndice = 0
$script:SvDepuis = [datetime]::MinValue
$script:SvOuvertA = [datetime]::MinValue
$script:SvOrigine = $null
function SvTexte([string]$t, [double]$taille, [string]$couleur = 'encre', [bool]$gras = $false) {
    $b = New-Object System.Windows.Controls.TextBlock
    $b.Text = $t; $b.FontSize = $taille; $b.Foreground = (SvPinceau $couleur); $b.TextTrimming = 'CharacterEllipsis'
    if ($gras) { $b.FontWeight = 'SemiBold' }
    return $b
}
function SvMeteo([string]$etat) {
    $noms = @{ 'sunny' = 'Ensoleillé'; 'clear-night' = 'Nuit claire'; 'partlycloudy' = 'Éclaircies'; 'cloudy' = 'Nuageux'; 'rainy' = 'Pluie'; 'pouring' = 'Forte pluie'; 'fog' = 'Brouillard'; 'snowy' = 'Neige'; 'snowy-rainy' = 'Neige fondue'; 'lightning' = 'Orage'; 'lightning-rainy' = 'Orage'; 'windy' = 'Vent'; 'windy-variant' = 'Vent'; 'hail' = 'Grêle'; 'exceptional' = 'Exceptionnel' }
    if ($noms.ContainsKey($etat)) { return $noms[$etat] }
    return ''
}
function SvValeur($k) {
    $v = Prop $k 'valeur'
    if ($null -ne $v) {
        try {
            $n = [double]$v
            $fr = [Globalization.CultureInfo]::GetCultureInfo('fr-FR')
            $s = if ([Math]::Abs($n - [Math]::Round($n)) -lt 0.05) { [Math]::Round($n).ToString('0', $fr) } else { $n.ToString('0.#', $fr) }
            $u = [string](Prop $k 'unite' '')
            if ($u) { return "$s $u" } else { return $s }
        } catch { }
    }
    return [string](Prop $k 'texte' '')
}
function SvHauteur($k) { if (@('jauge', 'courbe') -contains [string](Prop $k 'rendu')) { return 2 } else { return 1 } }

# Une case d'un tableau de bord, redessinée dans le thème du PC.
function SvCase($k) {
    $bord = New-Object System.Windows.Controls.Border
    $bord.Background = (SvPinceau 'carte'); $bord.CornerRadius = [System.Windows.CornerRadius]::new(14)
    $bord.Padding = [System.Windows.Thickness]::new(18, 10, 18, 10); $bord.Margin = [System.Windows.Thickness]::new(0, 0, 0, 8)
    $rendu = [string](Prop $k 'rendu' 'valeur')
    $pile = New-Object System.Windows.Controls.StackPanel
    if ($rendu -eq 'texte' -and -not (Prop $k 'entite')) {
        $tx = SvTexte ([string](Prop $k 'texte' '')) 20 'encre2'; $tx.TextWrapping = 'Wrap'; $tx.MaxHeight = 56
        $pile.Children.Add($tx) | Out-Null; $bord.Child = $pile; $bord.Height = 60
        return $bord
    }
    $ligne = New-Object System.Windows.Controls.DockPanel; $ligne.LastChildFill = $true
    $val = SvTexte (SvValeur $k) 24 'encre' $true; $val.Margin = [System.Windows.Thickness]::new(14, 0, 0, 0)
    $allume = Prop $k 'on'
    if ($null -ne $allume -and [bool]$allume) { $val.Foreground = (SvPinceau 'accent') }
    [System.Windows.Controls.DockPanel]::SetDock($val, 'Right'); $ligne.Children.Add($val) | Out-Null
    $nomCase = SvTexte ([string](Prop $k 'nom' '')) 21 'encre2'; $nomCase.VerticalAlignment = 'Center'
    $ligne.Children.Add($nomCase) | Out-Null
    $pile.Children.Add($ligne) | Out-Null
    $bord.Height = 60
    if ($rendu -eq 'jauge') {
        $mini = [double](Prop $k 'min' 0); $maxi = [double](Prop $k 'max' 100); $part = 0.0
        try { if ($maxi -gt $mini) { $part = [Math]::Max(0.0, [Math]::Min(1.0, ([double](Prop $k 'valeur' $mini) - $mini) / ($maxi - $mini))) } } catch { }
        $piste = New-Object System.Windows.Controls.Border; $piste.Height = 12; $piste.CornerRadius = [System.Windows.CornerRadius]::new(6); $piste.Background = (SvPinceau 'piste')
        $piste.Margin = [System.Windows.Thickness]::new(0, 22, 0, 0); $piste.HorizontalAlignment = 'Left'; $piste.Width = 524
        $plein = New-Object System.Windows.Controls.Border; $plein.CornerRadius = [System.Windows.CornerRadius]::new(6); $plein.Background = (SvPinceau 'accent')
        $plein.HorizontalAlignment = 'Left'; $plein.Width = [Math]::Max(12.0, 524 * $part)
        $piste.Child = $plein
        $pile.Children.Add($piste) | Out-Null; $bord.Height = 128
    } elseif ($rendu -eq 'courbe') {
        $serie = @(Prop $k 'serie' @())
        $trace = New-Object System.Windows.Shapes.Polyline; $trace.Stroke = (SvPinceau 'accent'); $trace.StrokeThickness = 3; $trace.StrokeLineJoin = 'Round'
        $trace.Margin = [System.Windows.Thickness]::new(0, 12, 0, 0); $trace.Height = 56; $trace.Width = 524; $trace.HorizontalAlignment = 'Left'
        if ($serie.Count -ge 2) {
            try {
                $t0 = [double]$serie[0][0]; $t1 = [double]$serie[$serie.Count - 1][0]
                $bas = [double]::MaxValue; $haut = [double]::MinValue
                foreach ($pt in $serie) { $y = [double]$pt[1]; if ($y -lt $bas) { $bas = $y }; if ($y -gt $haut) { $haut = $y } }
                if ($haut - $bas -lt 0.001) { $haut = $bas + 1 }
                if ($t1 -le $t0) { $t1 = $t0 + 1 }
                foreach ($pt in $serie) {
                    $x = 524 * (([double]$pt[0] - $t0) / ($t1 - $t0)); $y = 52 - 48 * (([double]$pt[1] - $bas) / ($haut - $bas))
                    $trace.Points.Add([System.Windows.Point]::new($x, $y))
                }
            } catch { }
        }
        $pile.Children.Add($trace) | Out-Null; $bord.Height = 128
    }
    $bord.Child = $pile
    return $bord
}

# Les tableaux à montrer : l'horloge, puis chaque tableau de bord découpé en écrans de trois colonnes.
function SvTableaux() {
    $sortie = @()
    $data = Lire 'veille.json'
    $liste = @(Prop (Prop $data 'tableaux') 'liste' @())
    $regl = SvReglages
    foreach ($def in $liste) {
        $code = [string](Prop $def 'code')
        # Ce PC choisit ce qu'il montre parmi ce qui est disponible.
        $idTab = if ($code -eq 'horloge') { 'horloge' } else { [string](Prop $def 'id') }
        if ($regl.masques -contains $idTab) { continue }
        $duree = [int](Prop $def 'duree' 20); if ($duree -lt 5) { $duree = 5 }
        if ($code -eq 'horloge') { $sortie += @{ genre = 'horloge'; duree = $duree; data = $data }; continue }
        if ($code -ne 'dash') { continue }
        # Des blocs (un titre, des cases) d'au plus dix unités de hauteur.
        $blocs = @()
        foreach ($s in @(Prop $def 'sections' @())) {
            $courant = @(); $unites = 1; $premier = $true
            foreach ($k in @(Prop $s 'cases' @())) {
                if ($regl.cartes -contains ($idTab + '|' + [string](Prop $k 'carte' ''))) { continue }
                $hk = SvHauteur $k
                if ($unites + $hk -gt 10 -and $courant.Count -gt 0) {
                    $blocs += @{ titre = $(if ($premier) { [string](Prop $s 'titre' '') } else { '' }); cases = $courant; unites = $unites }
                    $courant = @(); $unites = 1; $premier = $false
                }
                $courant += $k; $unites += $hk
            }
            if ($courant.Count -gt 0) { $blocs += @{ titre = $(if ($premier) { [string](Prop $s 'titre' '') } else { '' }); cases = $courant; unites = $unites } }
        }
        # Trois colonnes de dix unités ; ce qui ne tient pas fait un écran de plus.
        $pages = @(); $colonnes = @(@(), @(), @()); $col = 0; $pris = 0
        foreach ($b in $blocs) {
            if ($pris + $b.unites -gt 10 -and $pris -gt 0) { $col++; $pris = 0 }
            if ($col -gt 2) { $pages += , $colonnes; $colonnes = @(@(), @(), @()); $col = 0; $pris = 0 }
            $colonnes[$col] += $b; $pris += $b.unites
        }
        if (@($colonnes[0]).Count -gt 0) { $pages += , $colonnes }
        $n = 0
        foreach ($pg in $pages) {
            $n++
            $sortie += @{ genre = 'dash'; duree = $duree; titre = [string](Prop $def 'titre' ''); colonnes = $pg; numero = $n; total = $pages.Count }
        }
    }
    if ($sortie.Count -eq 0) { $sortie += @{ genre = 'horloge'; duree = 30; data = $data } }
    return $sortie
}

function SvDessiner($scene, $tab) {
    $scene.Children.Clear()
    if ($tab.genre -eq 'horloge') {
        $pile = New-Object System.Windows.Controls.StackPanel; $pile.HorizontalAlignment = 'Center'; $pile.VerticalAlignment = 'Center'
        $h = SvTexte ((Get-Date).ToString('HH:mm')) 300 'encre'; $h.FontWeight = 'Light'; $h.HorizontalAlignment = 'Center'; $h.Tag = 'heure'
        $fr = [Globalization.CultureInfo]::GetCultureInfo('fr-FR')
        $jour = (Get-Date).ToString('dddd d MMMM', $fr); $jour = $jour.Substring(0, 1).ToUpper() + $jour.Substring(1)
        $d = SvTexte $jour 52 'encre2'; $d.HorizontalAlignment = 'Center'
        $pile.Children.Add($h) | Out-Null; $pile.Children.Add($d) | Out-Null
        $m = Prop $tab.data 'meteo'
        if ($m) {
            $morceaux = @()
            $temp = Prop $m 'temperature'; if ($null -ne $temp) { try { $morceaux += ('{0:0}°' -f [double]$temp) } catch { } }
            $ciel = SvMeteo ([string](Prop $m 'etat' '')); if ($ciel) { $morceaux += $ciel }
            if ($morceaux.Count) { $mt = SvTexte ($morceaux -join '  ·  ') 44 'accent'; $mt.HorizontalAlignment = 'Center'; $mt.Margin = [System.Windows.Thickness]::new(0, 26, 0, 0); $pile.Children.Add($mt) | Out-Null }
        }
        $script:SvHeures += $h
        $scene.Children.Add($pile) | Out-Null
        return
    }
    $dock = New-Object System.Windows.Controls.DockPanel; $dock.Margin = [System.Windows.Thickness]::new(70, 50, 70, 50)
    $tete = New-Object System.Windows.Controls.DockPanel; $tete.Margin = [System.Windows.Thickness]::new(0, 0, 0, 22)
    $petite = SvTexte ((Get-Date).ToString('HH:mm')) 40 'encre2'; [System.Windows.Controls.DockPanel]::SetDock($petite, 'Right'); $tete.Children.Add($petite) | Out-Null
    $script:SvHeures += $petite
    $titre = [string]$tab.titre; if ($tab.total -gt 1) { $titre = '{0}   {1}/{2}' -f $titre, $tab.numero, $tab.total }
    $tete.Children.Add((SvTexte $titre 44 'encre' $true)) | Out-Null
    [System.Windows.Controls.DockPanel]::SetDock($tete, 'Top'); $dock.Children.Add($tete) | Out-Null
    $grille = New-Object System.Windows.Controls.Grid
    for ($i = 0; $i -lt 3; $i++) { $cd = New-Object System.Windows.Controls.ColumnDefinition; $cd.Width = [System.Windows.GridLength]::new(1, 'Star'); $grille.ColumnDefinitions.Add($cd) }
    for ($i = 0; $i -lt 3; $i++) {
        $colonne = New-Object System.Windows.Controls.StackPanel; $colonne.Width = 560; $colonne.HorizontalAlignment = 'Center'
        foreach ($b in @($tab.colonnes[$i])) {
            if ($null -eq $b) { continue }
            $tb = SvTexte ([string]$b.titre).ToUpper() 18 'accent' $true; $tb.Margin = [System.Windows.Thickness]::new(4, 6, 0, 10); $tb.Height = 26
            $colonne.Children.Add($tb) | Out-Null
            foreach ($k in @($b.cases)) { $colonne.Children.Add((SvCase $k)) | Out-Null }
        }
        [System.Windows.Controls.Grid]::SetColumn($colonne, $i); $grille.Children.Add($colonne) | Out-Null
    }
    $dock.Children.Add($grille) | Out-Null
    $scene.Children.Add($dock) | Out-Null
}

# Plusieurs écrans : chacun montre un tableau différent (l'horloge sur l'un, un tableau de bord
# sur l'autre), et tout avance d'un cran à chaque passage, si bien que l'horloge change d'écran.
function SvToutDessiner() {
    $script:SvHeures = @()
    $nb = $script:SvListe.Count
    for ($j = 0; $j -lt $script:SvScenes.Count; $j++) {
        try { SvDessiner $script:SvScenes[$j] $script:SvListe[($script:SvIndice + $j) % $nb] } catch { }
    }
}

function SvFondu([double]$de, [double]$vers, $ensuite) {
    $premiere = $true
    foreach ($sc in @($script:SvScenes)) {
        $anim = New-Object System.Windows.Media.Animation.DoubleAnimation($de, $vers, [System.Windows.Duration]::new([TimeSpan]::FromMilliseconds(450)))
        if ($premiere -and $ensuite) { $anim.Add_Completed($ensuite) }
        $premiere = $false
        $sc.BeginAnimation([System.Windows.UIElement]::OpacityProperty, $anim)
    }
}

function SvSuivant([int]$pas = 1) {
    # Les valeurs sont relues à chaque changement de tableau.
    $script:SvListe = @(SvTableaux)
    $nb = $script:SvListe.Count
    $script:SvIndice = (($script:SvIndice + $pas) % $nb + $nb) % $nb
    $script:SvDepuis = Get-Date
    if ($nb -le 1) { SvToutDessiner; return }
    SvFondu 1 0 { SvToutDessiner; SvFondu 0 1 $null }
}

function SvFermer() {
    try { $script:SvTic.Stop() } catch { }
    foreach ($f in @($script:SvFenetres)) { try { $f.Close() } catch { } }
    $script:SvFenetres = @(); $script:SvScenes = @(); $script:SvHeures = @()
}

# Les vraies cartes de Home Assistant : une page plein écran par écran, dans Edge, aux couleurs de ce PC.
function SvEdge() {
    foreach ($c in @((Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'), (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'))) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}
function SvOuvrirWeb() {
    $acces = Prop (Lire 'veille.json') 'acces'
    $jeton = [string](Prop $acces 'jeton' ''); $base = ([string](Prop $acces 'url' '')).TrimEnd('/')
    $edge = SvEdge
    if (-not $jeton -or -not $base -or -not $edge) { return $false }
    $r = SvReglages; $pal = $script:Pal; $j = 0
    # Plusieurs écrans : ils partent de la même heure et avancent ensemble, décalés d'un cran, pour ne jamais
    # montrer la même chose. L'écran principal ouvre sur l'horloge, les autres sur les tableaux qui suivent.
    $tous = @([System.Windows.Forms.Screen]::AllScreens | Sort-Object { -not $_.Primary })
    $depart = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    foreach ($ecran in $tous) {
        $q = 'id={0}&ecran=tele&dec={1}&fond={2}&carte={3}&texte={4}&texte2={5}&accent={6}&ligne={7}&masques={8}&cartes={9}&style={10}&cfond={11}&ccontour={12}&ecrans={13}&t0={14}&horloge={15}&anim={16}&figees={17}' -f `
            [uri]::EscapeDataString([string](Prop $acces 'id' '')), $j, $pal.Fond.Substring(3), $pal.Carte.Substring(3), $pal.Texte.Substring(3), $pal.Texte2.Substring(3), $pal.Or.Substring(3), $pal.Ligne.Substring(3), `
            [uri]::EscapeDataString((@($r.masques) -join ',')), [uri]::EscapeDataString((@($r.cartes) -join ',')), [string]$r.style, $(if ($r.fondCartes) { 1 } else { 0 }), $(if ($r.contourCartes) { 1 } else { 0 }), $tous.Count, $depart, [string]$pal.Horloge, $(if ($r.animer) { 1 } else { 0 }), [uri]::EscapeDataString((@($r.figees) -join ','))
        $adresse = '{0}/api/pc_parental/veille/entree#t={1}&q={2}' -f $base, $jeton, [uri]::EscapeDataString($q)
        $profilEdge = Join-Path $env:LOCALAPPDATA ('Vision\veille-edge-{0}' -f $j)
        # Une fenêtre d'application en mode borne par écran, placée sur le sien ; en navigation privée, pour
        # qu'Edge n'y connecte pas le compte Windows ni n'affiche ses propres messages.
        $arguments = @('--kiosk', ('--app="{0}"' -f $adresse), '--edge-kiosk-type=fullscreen', '--inprivate', '--no-first-run', '--no-default-browser-check',
            ('--user-data-dir="{0}"' -f $profilEdge), ('--window-position={0},{1}' -f $ecran.Bounds.Left, $ecran.Bounds.Top),
            ('--window-size={0},{1}' -f $ecran.Bounds.Width, $ecran.Bounds.Height),
            '--disable-features=msEdgeSidebarV2,Translate', '--hide-crash-restore-bubble', '--autoplay-policy=no-user-gesture-required')
        if ([bool](Prop $acces 'insecure' $false)) { $arguments += @('--ignore-certificate-errors', '--test-type') }
        try { Start-Process -FilePath $edge -ArgumentList $arguments } catch { return $false }
        $j++
    }
    $script:SvWebOuvert = $true; $script:SvOuvertA = Get-Date
    $script:SvWebTic.Start()
    return $true
}
function SvFermerWeb() {
    try { $script:SvWebTic.Stop() } catch { }
    $script:SvWebOuvert = $false
    try {
        Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -like '*Vision\veille-edge-*' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
}
$script:SvWebOuvert = $false
$script:SvDevantA = [datetime]::MinValue
# Le moindre geste (souris, clavier) referme la page.
$script:SvWebTic = New-Object System.Windows.Threading.DispatcherTimer
$script:SvWebTic.Interval = [TimeSpan]::FromMilliseconds(300)
$script:SvWebTic.Add_Tick({
    try {
        if (-not $script:SvWebOuvert) { $script:SvWebTic.Stop(); return }
        # Les fenêtres de la veille passent devant tout le reste, même devant une fenêtre restée au premier plan.
        # Edge met quelques secondes à les ouvrir : on y revient pendant les vingt-cinq premières secondes.
        $depuis = ((Get-Date) - $script:SvOuvertA).TotalSeconds
        if ($depuis -lt 25 -and ((Get-Date) - $script:SvDevantA).TotalSeconds -ge 1.5) {
            $script:SvDevantA = Get-Date
            try {
                $pids = @(Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -like '*Vision\veille-edge-*' } | ForEach-Object { [int]$_.ProcessId })
                if ($pids.Count -gt 0) { [void][VisionVeilleNatif]::Devant([int[]]$pids) }
            } catch { }
        }
        if ($depuis -lt 3) { return }
        if ([VisionVeilleNatif]::Inactif() -lt 1) { SvFermerWeb }
    } catch { }
})

function SvOuvrir() {
    if ($script:SvFenetres.Count -gt 0 -or $script:SvWebOuvert) { return }
    if ($script:SvPret -and (SvOuvrirWeb)) { return }
    $script:SvOrigine = $null; $script:SvOuvertA = Get-Date; $script:SvScenes = @(); $script:SvHeures = @()
    $ecrans = [System.Windows.Forms.Screen]::AllScreens
    $echelle = 1.0
    try { $echelle = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width / [System.Windows.SystemParameters]::PrimaryScreenWidth } catch { }
    foreach ($ecran in $ecrans) {
        $f = New-Object System.Windows.Window
        $f.WindowStyle = 'None'; $f.ResizeMode = 'NoResize'; $f.ShowInTaskbar = $false; $f.Topmost = $true
        $f.Background = (SvPinceau 'fond'); $f.Cursor = [System.Windows.Input.Cursors]::None; $f.FontFamily = (New-Object System.Windows.Media.FontFamily('Segoe UI'))
        $f.WindowStartupLocation = 'Manual'
        $f.Left = $ecran.Bounds.Left / $echelle; $f.Top = $ecran.Bounds.Top / $echelle
        $f.Width = $ecran.Bounds.Width / $echelle; $f.Height = $ecran.Bounds.Height / $echelle
        # Une scène de 1920 × 1080 mise à l'échelle : la même mise en page sur tous les écrans.
        $boite = New-Object System.Windows.Controls.Viewbox; $boite.Stretch = 'Uniform'
        $scene = New-Object System.Windows.Controls.Grid; $scene.Width = 1920; $scene.Height = 1080
        $boite.Child = $scene; $f.Content = $boite
        $script:SvScenes += $scene
        $f.Add_PreviewKeyDown({ param($s, $e)
            if ($e.Key -eq 'Right') { SvSuivant 1 } elseif ($e.Key -eq 'Left') { SvSuivant -1 } else { SvFermer }
            $e.Handled = $true })
        $f.Add_PreviewMouseDown({ SvFermer })
        $f.Add_MouseMove({ param($s, $e)
            if (((Get-Date) - $script:SvOuvertA).TotalMilliseconds -lt 900) { return }
            $pos = $s.PointToScreen($e.GetPosition($s))
            if ($null -eq $script:SvOrigine) { $script:SvOrigine = $pos; return }
            if ([Math]::Abs($pos.X - $script:SvOrigine.X) + [Math]::Abs($pos.Y - $script:SvOrigine.Y) -gt 14) { SvFermer } })
        $f.Add_Closed({ param($s, $e) $script:SvFenetres = @($script:SvFenetres | Where-Object { $_ -ne $s }) })
        $script:SvFenetres += $f
        try { [System.Windows.Forms.Integration.ElementHost]::EnableModelessKeyboardInterop($f) } catch { }
        $f.Show()
        if ($ecran.Primary) { $f.Activate() | Out-Null }
    }
    $script:SvListe = @(SvTableaux); $script:SvIndice = 0; $script:SvDepuis = Get-Date
    SvToutDessiner
    SvFondu 0 1 $null
    $script:SvTic.Start()
}

# Une fois par seconde pendant la veille : l'heure, et le passage au tableau suivant.
$script:SvTic = New-Object System.Windows.Threading.DispatcherTimer
$script:SvTic.Interval = [TimeSpan]::FromSeconds(1)
$script:SvTic.Add_Tick({
    try {
        if ($script:SvFenetres.Count -eq 0) { $script:SvTic.Stop(); return }
        foreach ($hh in @($script:SvHeures)) { if ($hh) { $hh.Text = (Get-Date).ToString('HH:mm') } }
        $courant = $script:SvListe[$script:SvIndice]
        if (((Get-Date) - $script:SvDepuis).TotalSeconds -ge [int]$courant.duree) {
            if ($script:SvListe.Count -gt 1) { SvSuivant 1 } else { $script:SvDepuis = Get-Date; SvSuivant 0 }
        }
    } catch { }
})

# Le guet : personne au clavier ni à la souris depuis le délai choisi, et rien en plein écran (film, jeu).
$script:SvGuet = New-Object System.Windows.Threading.DispatcherTimer
$script:SvGuet.Interval = [TimeSpan]::FromSeconds(5)
$script:SvGuet.Add_Tick({
    try {
        if (-not $script:SvPret -or $script:SvFenetres.Count -gt 0 -or $script:SvWebOuvert) { return }
        $r = SvReglages
        if (-not $r.actif) { return }
        if ([VisionVeilleNatif]::Inactif() -lt ($r.delai * 60)) { return }
        $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        if ([VisionVeilleNatif]::PleinEcran($b.Width, $b.Height)) { return }
        SvOuvrir
    } catch { }
})
$script:SvGuet.Start()

# Les réglages de ce PC, dans la fenêtre (onglet Réglages) : thème, écran de veille, tableaux et cartes.
function Coche([string]$t, [bool]$etat, $action, $tag = $null) {
    $c = New-Object System.Windows.Controls.CheckBox
    $c.Content = $t; $c.IsChecked = $etat; $c.Style = $script:W.Resources['Coche']; $c.Tag = $tag
    $c.Margin = [System.Windows.Thickness]::new(0, 6, 0, 6)
    if ($action) { $c.Add_Click($action) }
    return $c
}

# Une carte dans la liste des tableaux : à gauche « affichée », à droite « animée » (quand les animations sont en service).
function LigneCarte([string]$nom, [string]$cle, $r) {
    $montre = Coche $nom (-not ($r.cartes -contains $cle)) { param($s, $e) $rr = SvReglages; $c = [string]$s.Tag; $rr.cartes = @($rr.cartes | Where-Object { $_ -ne $c }); if (-not $s.IsChecked) { $rr.cartes += $c }; SvEcrire $rr } $cle
    if (-not $r.animer) { return $montre }
    $rang = New-Object System.Windows.Controls.DockPanel
    $anime = Coche 'animée' (-not ($r.figees -contains $cle)) { param($s, $e) $rr = SvReglages; $c = [string]$s.Tag; $rr.figees = @($rr.figees | Where-Object { $_ -ne $c }); if (-not $s.IsChecked) { $rr.figees += $c }; SvEcrire $rr } $cle
    $anime.Opacity = 0.8; $anime.Margin = [System.Windows.Thickness]::new(14, 6, 0, 6)
    [System.Windows.Controls.DockPanel]::SetDock($anime, [System.Windows.Controls.Dock]::Right)
    $rang.Children.Add($anime) | Out-Null
    $rang.Children.Add($montre) | Out-Null
    return $rang
}

# Changer de thème : les couleurs sont posées à la création de la fenêtre, on la recrée donc
# au même endroit et dans le même état, sans que rien ne se ferme.
function ChangerTheme([string]$nom) {
    $rr = SvReglages; $rr.theme = $nom; SvEcrire $rr
    $script:Pal = $script:Themes[$nom]
    $ancienne = $script:W
    $gauche = $ancienne.Left; $haut = $ancienne.Top; $etatF = $ancienne.WindowState
    CreerFenetre
    $script:W.WindowStartupLocation = 'Manual'; $script:W.Left = $gauche; $script:W.Top = $haut
    Rafraichir
    $script:W.Show(); $script:W.WindowState = $etatF; $script:W.Activate() | Out-Null
    try { $ancienne.Close() } catch { }
}

function PageReglages() {
    $r = SvReglages
    $Contenu.Children.Add((Section 'Thème de couleur')) | Out-Null
    $carteT = Carte; $enveloppe = New-Object System.Windows.Controls.WrapPanel
    foreach ($nomTheme in $script:Themes.Keys) {
        $bt = New-Object System.Windows.Controls.Primitives.ToggleButton
        $bt.Content = $nomTheme; $bt.Style = $W.Resources['Onglet']; $bt.Tag = $nomTheme; $bt.IsChecked = ($r.theme -eq $nomTheme)
        $bt.Margin = [System.Windows.Thickness]::new(0, 0, 6, 6)
        $bt.Add_Click({ param($s, $e) if ((SvReglages).theme -eq [string]$s.Tag) { $s.IsChecked = $true; return }; ChangerTheme ([string]$s.Tag) })
        $enveloppe.Children.Add($bt) | Out-Null
    }
    $carteT.Child.Children.Add($enveloppe) | Out-Null
    $carteT.Child.Children.Add((Txt 'Pour la fenêtre Vision et l''écran de veille de cet ordinateur.' 11 'Texte2')) | Out-Null
    # Le style graphique (formes, bordures, lettres) se choisit à part des couleurs.
    $carteT.Child.Children.Add((Txt 'Style graphique de l''écran de veille' 12 'Texte2' $false '0,12,0,6')) | Out-Null
    $styles = New-Object System.Windows.Controls.WrapPanel
    foreach ($defStyle in @(@('doux', 'Doux'), @('neoretro', 'Néo-rétro'))) {
        $bs = New-Object System.Windows.Controls.Primitives.ToggleButton
        $bs.Content = $defStyle[1]; $bs.Style = $W.Resources['Onglet']; $bs.Tag = $defStyle[0]; $bs.IsChecked = ($r.style -eq $defStyle[0])
        $bs.Margin = [System.Windows.Thickness]::new(0, 0, 6, 6)
        $bs.Add_Click({ param($s, $e) $rr = SvReglages; $rr.style = [string]$s.Tag; SvEcrire $rr; Rafraichir })
        $styles.Children.Add($bs) | Out-Null
    }
    $carteT.Child.Children.Add($styles) | Out-Null
    $carteT.Child.Children.Add((Coche 'Un fond sous les cartes' ([bool]$r.fondCartes) { param($s, $e) $rr = SvReglages; $rr.fondCartes = [bool]$s.IsChecked; SvEcrire $rr })) | Out-Null
    $carteT.Child.Children.Add((Coche 'Un contour autour des cartes' ([bool]$r.contourCartes) { param($s, $e) $rr = SvReglages; $rr.contourCartes = [bool]$s.IsChecked; SvEcrire $rr })) | Out-Null
    $carteT.Child.Children.Add((Coche 'Animer les cartes (arrivée, jauges, courbes, nombres) ; le choix carte par carte est dans la liste plus bas' ([bool]$r.animer) { param($s, $e) $rr = SvReglages; $rr.animer = [bool]$s.IsChecked; SvEcrire $rr; Rafraichir })) | Out-Null
    $Contenu.Children.Add($carteT) | Out-Null

    $Contenu.Children.Add((Section 'Accès à Vision')) | Out-Null
    $carteA = Carte
    $hello = HelloDisponible
    $carteA.Child.Children.Add((Coche 'Demander Windows Hello ou un code pour ouvrir Vision' ([bool]$r.verrou) {
        param($s, $e)
        $rr = SvReglages
        if ($s.IsChecked -and -not $rr.codeHash -and -not (HelloDisponible)) { $s.IsChecked = $false; return }
        $rr.verrou = [bool]$s.IsChecked; SvEcrire $rr; Rafraichir
    })) | Out-Null
    $carteA.Child.Children.Add((Txt $(if ($hello) { 'Windows Hello est prêt sur cet ordinateur (empreinte, visage ou code Windows).' } else { 'Windows Hello n''est pas configuré sur cet ordinateur : choisis un code ci-dessous.' }) 11 'Texte2' $false '0,2,0,10')) | Out-Null
    $ligneC = Rangee
    $nouveau = New-Object System.Windows.Controls.PasswordBox
    $nouveau.Width = 180; $nouveau.FontSize = 14; $nouveau.Padding = [System.Windows.Thickness]::new(10, 6, 10, 6); $nouveau.MaxLength = 32; $nouveau.VerticalContentAlignment = 'Center'
    $nouveau.Background = (Pinceau 'Haute'); $nouveau.Foreground = (Pinceau 'Texte'); $nouveau.BorderBrush = (Pinceau 'Ligne'); $nouveau.Margin = [System.Windows.Thickness]::new(0, 0, 8, 0)
    $noteC = Txt $(if ($r.codeHash) { 'Un code est enregistré.' } else { 'Aucun code pour l''instant (4 caractères au moins).' }) 11 'Texte2' $false '0,6,0,0'
    $script:CodeNouveau = $nouveau; $script:CodeNote = $noteC
    $ligneC.Children.Add($nouveau) | Out-Null
    $ligneC.Children.Add((Bouton $(if ($r.codeHash) { 'Changer le code' } else { 'Enregistrer le code' }) 'Secondaire' { CodeEnregistrer })) | Out-Null
    if ($r.codeHash) {
        $ligneC.Children.Add((Bouton 'Retirer le code' 'Secondaire' { $rr = SvReglages; $rr.codeSel = ''; $rr.codeHash = ''; if (-not (HelloDisponible)) { $rr.verrou = $false }; SvEcrire $rr; Rafraichir })) | Out-Null
    }
    $carteA.Child.Children.Add($ligneC) | Out-Null
    $carteA.Child.Children.Add($noteC) | Out-Null
    $carteA.Child.Children.Add((Txt 'Le verrou se remet dès que la fenêtre est fermée. Il protège la fenêtre, pas l''écran de veille.' 11 'Texte2' $false '0,8,0,0')) | Out-Null
    $Contenu.Children.Add($carteA) | Out-Null

    $Contenu.Children.Add((Section 'Écran de veille')) | Out-Null
    $carteV = Carte
    $carteV.Child.Children.Add((Coche 'Activer l''écran de veille sur cet ordinateur' ([bool]$r.actif) { param($s, $e) $rr = SvReglages; $rr.actif = [bool]$s.IsChecked; SvEcrire $rr })) | Out-Null
    $carteV.Child.Children.Add((Txt 'Démarre quand personne ne touche au clavier ni à la souris depuis :' 12 'Texte2' $false '0,8,0,6')) | Out-Null
    $delais = New-Object System.Windows.Controls.WrapPanel
    foreach ($minutes in @(2, 5, 10, 20, 30)) {
        $bd = New-Object System.Windows.Controls.Primitives.ToggleButton
        $bd.Content = ('{0} min' -f $minutes); $bd.Style = $W.Resources['Onglet']; $bd.Tag = $minutes; $bd.IsChecked = ([int]$r.delai -eq $minutes)
        $bd.Margin = [System.Windows.Thickness]::new(0, 0, 6, 6)
        $bd.Add_Click({ param($s, $e) $rr = SvReglages; $rr.delai = [int]$s.Tag; SvEcrire $rr; Rafraichir })
        $delais.Children.Add($bd) | Out-Null
    }
    $carteV.Child.Children.Add($delais) | Out-Null
    $carteV.Child.Children.Add((Txt 'Il ne démarre pas pendant un film ou un jeu en plein écran. Avec plusieurs écrans, chacun montre un tableau différent.' 11 'Texte2' $false '0,2,0,8')) | Out-Null
    $voir = Bouton 'Voir maintenant' 'Secondaire' { $script:W.Hide(); SvOuvrir }; $voir.HorizontalAlignment = 'Left'
    $carteV.Child.Children.Add($voir) | Out-Null
    $Contenu.Children.Add($carteV) | Out-Null

    $Contenu.Children.Add((Section 'Tableaux affichés')) | Out-Null
    $carteL = Carte
    $data = Lire 'veille.json'
    # La liste vient de Home Assistant (l'agent la relève toutes les vingt secondes) ; « Actualiser » la relit.
    $teteL = New-Object System.Windows.Controls.DockPanel; $teteL.Margin = [System.Windows.Thickness]::new(0, 0, 0, 8)
    $actualiser = Bouton 'Actualiser' 'Secondaire' { Rafraichir }; $actualiser.Margin = [System.Windows.Thickness]::new(0)
    [System.Windows.Controls.DockPanel]::SetDock($actualiser, 'Right'); $teteL.Children.Add($actualiser) | Out-Null
    $releve = ''
    try { $releve = 'Liste relevée à ' + (Get-Item (Join-Path $script:Dossier 'veille.json')).LastWriteTime.ToString('HH:mm:ss') + '. Un tableau rendu disponible dans Home Assistant arrive ici en moins d''une minute.' } catch { }
    $noteL = Txt $releve 11 'Texte2'; $noteL.VerticalAlignment = 'Center'
    $teteL.Children.Add($noteL) | Out-Null
    $carteL.Child.Children.Add($teteL) | Out-Null
    $nbDash = 0
    $listePage = @(Prop $data 'page' @())
    if ($listePage.Count -gt 0) {
        $carteL.Child.Children.Add((Coche 'Horloge' (-not ($r.masques -contains 'horloge')) { param($s, $e) $rr = SvReglages; $rr.masques = @($rr.masques | Where-Object { $_ -ne 'horloge' }); if (-not $s.IsChecked) { $rr.masques += 'horloge' }; SvEcrire $rr })) | Out-Null
        foreach ($def in $listePage) {
            $nbDash++
            $idTab = [string](Prop $def 'id')
            $montre = -not ($r.masques -contains $idTab)
            $ct = Coche ([string](Prop $def 'titre' 'Tableau de bord')) $montre { param($s, $e) $rr = SvReglages; $cle = [string]$s.Tag; $rr.masques = @($rr.masques | Where-Object { $_ -ne $cle }); if (-not $s.IsChecked) { $rr.masques += $cle }; SvEcrire $rr; Rafraichir } $idTab
            $ct.FontWeight = 'SemiBold'
            $carteL.Child.Children.Add($ct) | Out-Null
            if (-not $montre) { continue }
            $lot = New-Object System.Windows.Controls.StackPanel; $lot.Margin = [System.Windows.Thickness]::new(26, 0, 0, 8)
            $sectionVue = $null
            foreach ($cc in @(Prop $def 'cartes' @())) {
                $sec = [string](Prop $cc 'section' '')
                if ($sec -ne $sectionVue) { $sectionVue = $sec; if ($sec) { $lot.Children.Add((Txt $sec.ToUpper() 10 'Texte3' $true '0,6,0,2')) | Out-Null } }
                $cleC = $idTab + '|' + [string](Prop $cc 'cle')
                $lot.Children.Add((LigneCarte ([string](Prop $cc 'nom' 'Carte')) $cleC $r)) | Out-Null
            }
            $carteL.Child.Children.Add($lot) | Out-Null
        }
    } else {
        foreach ($def in @(Prop (Prop $data 'tableaux') 'liste' @())) {
            $code = [string](Prop $def 'code')
            if ($code -eq 'horloge') {
                $carteL.Child.Children.Add((Coche 'Horloge' (-not ($r.masques -contains 'horloge')) { param($s, $e) $rr = SvReglages; $rr.masques = @($rr.masques | Where-Object { $_ -ne 'horloge' }); if (-not $s.IsChecked) { $rr.masques += 'horloge' }; SvEcrire $rr })) | Out-Null
                continue
            }
            if ($code -ne 'dash') { continue }
            $nbDash++
            $idTab = [string](Prop $def 'id')
            $montre = -not ($r.masques -contains $idTab)
            $ct = Coche ([string](Prop $def 'titre' 'Tableau de bord')) $montre { param($s, $e) $rr = SvReglages; $cle = [string]$s.Tag; $rr.masques = @($rr.masques | Where-Object { $_ -ne $cle }); if (-not $s.IsChecked) { $rr.masques += $cle }; SvEcrire $rr; Rafraichir } $idTab
            $ct.FontWeight = 'SemiBold'
            $carteL.Child.Children.Add($ct) | Out-Null
            if (-not $montre) { continue }
            # Ses cartes : une ligne par carte du tableau de bord.
            $lot = New-Object System.Windows.Controls.StackPanel; $lot.Margin = [System.Windows.Thickness]::new(26, 0, 0, 8)
            foreach ($sec in @(Prop $def 'sections' @())) {
                $vues = [ordered]@{}
                foreach ($k in @(Prop $sec 'cases' @())) {
                    $cc = [string](Prop $k 'carte' '')
                    if (-not $vues.Contains($cc)) { $vues[$cc] = @{ nom = [string](Prop $k 'nom' ''); n = 0 } }
                    $vues[$cc].n++
                }
                if ($vues.Count -eq 0) { continue }
                $titreSec = [string](Prop $sec 'titre' '')
                if ($titreSec) { $lot.Children.Add((Txt $titreSec.ToUpper() 10 'Texte3' $true '0,6,0,2')) | Out-Null }
                foreach ($cc in $vues.Keys) {
                    $nomC = $vues[$cc].nom; if ($vues[$cc].n -gt 1) { $nomC = '{0} (+{1})' -f $nomC, ($vues[$cc].n - 1) }
                    $cleC = $idTab + '|' + $cc
                    $lot.Children.Add((LigneCarte $nomC $cleC $r)) | Out-Null
                }
            }
            $carteL.Child.Children.Add($lot) | Out-Null
        }
    }
    if ($nbDash -eq 0) { $carteL.Child.Children.Add((Txt 'Aucun tableau de bord n''est encore rendu disponible. Cela se choisit dans Home Assistant : Vision, onglet Écran de veille.' 12 'Texte2' $false '0,6,0,0')) | Out-Null }
    $Contenu.Children.Add($carteL) | Out-Null
}

if ($Depart) { $script:Page = $Depart; Montrer }

[System.Windows.Forms.Application]::Run()
