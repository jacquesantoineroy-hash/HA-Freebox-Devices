# Vision Android

Appli Android de Vision (lanceur, écran de veille, contrôle parental), reliée à
l'intégration Home Assistant `pc_parental`. Un seul APK pour téléphones,
Android TV et Google TV (API 21 et plus).

- `src/` : le projet Gradle complet (Kotlin, sans bibliothèque d'interface, Media3 pour les flux HLS).
- `vision.apk` + `vision.json` : la version publiée, servie par l'intégration pour la mise à jour automatique des appareils.

## Compiler

Prérequis : JDK 17, Android SDK (compileSdk 34), Gradle 8.

```bash
cd src
gradle --no-daemon :app:assembleRelease -x lintVitalRelease
# → app/build/outputs/apk/release/app-release.apk
```

Sans fichier de signature, Gradle produit un APK non signé (installable seulement
en debug). Pour un APK signé, voir ci-dessous.

## Signer

La clé n'est pas dans le dépôt. Une fois pour toutes :

```bash
cd src
keytool -genkeypair -v -keystore vision-release.jks -alias vision -keyalg RSA -keysize 2048 -validity 10000
cp keystore.properties.example keystore.properties   # puis renseigner les mots de passe
```

`keystore.properties` et `*.jks` sont ignorés par git. Tous les appareils doivent
recevoir des APK signés par la même clé, sinon Android refuse la mise à jour
(il faut alors désinstaller puis réinstaller).

## Publier

1. Monter `versionCode` et `versionName` dans `src/app/build.gradle.kts`, compiler.
2. Copier l'APK en `vision-android/vision.apk` et écrire `vision.json` :

```bash
cp src/app/build/outputs/apk/release/app-release.apk vision.apk
python3 - <<'EOF'
import hashlib, json
sha = hashlib.sha256(open("vision.apk", "rb").read()).hexdigest()
json.dump({"version": "1.34.2", "sha256": sha, "path": "/api/pc_parental/android/vision.apk?v=1.5.0"}, open("vision.json", "w"), indent=2)
EOF
```

3. Déposer les deux fichiers sur Home Assistant dans
   `/config/custom_components/pc_parental/android/`. L'intégration sert
   `/api/pc_parental/android/vision.json` et `vision.apk` ; chaque appareil compare
   la version, vérifie le sha256 et s'installe tout seul (silencieusement sur les
   télés où Vision a le droit d'installer, avec confirmation sinon).

4. Télé : pour installer directement par ADB et accorder les droits qui n'ont pas
   d'écran sur TV (admin, installation, accessibilité, écran de veille, réglages
   système), `src/outils/install-tv.sh <ip de la télé>`.

## Code

`src/app/src/main/java/fr/familleroy/vision/` : `LanceurActivity` (accueil télé et
téléphone), `VeilleView` / `VeilleActivity` / `VeilleService` (écran de veille),
`ReglagesTvActivity` (réglages de l'appareil), `CouleursActivity`, `Local`
(réglages locaux), `Palette` / `Themes` / `Ui` (charte), `AgentService`
(contrôle parental, mise à jour), `DnsVpnService` (filtre DNS), `VerrouActivity`
(écran de verrouillage du téléphone).
