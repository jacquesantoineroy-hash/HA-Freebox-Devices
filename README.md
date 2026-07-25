# Freebox Devices

Intégration Home Assistant (HACS) qui parle **directement** à l'API locale de
la Freebox — aucun service intermédiaire (pas de Raspberry Pi, pas de relais
HTTP). Elle expose, pour chaque appareil connu du réseau local :

- un **device_tracker** (présence, IP, fabricant, type d'appareil) ;
- un **switch "Wifi allowed"** par appareil (coupe/rétablit via la blacklist
  Wifi de la Freebox) ;
- un **sensor "Wifi signal"** (dBm), `None` si l'appareil est filaire.

## Pourquoi une intégration à part de la core `freebox` ?

L'intégration core `freebox` fait déjà de la présence basique et quelques
sensors globaux, mais ne permet pas de couper le Wifi d'un appareil
individuel ni de voir son signal. Plutôt que de contribuer un patch massif à
core, cette intégration est autonome et peut cohabiter avec `freebox` core
(ou la remplacer entièrement, selon vos besoins).

## Authentification

Au premier démarrage de la configuration, l'intégration déclare une
application dédiée (`fr.familleroy.freebox_devices`) auprès de la Freebox :

1. Renseignez l'hôte (`mafreebox.freebox.fr` par défaut) et le port (`443`).
2. **Appuyez sur la flèche droite** en façade de la Freebox dans les ~2
   minutes qui suivent, pour valider l'appairage.
3. Une fois appairée, **allez dans Freebox OS → Paramètres → Gestion des
   accès → Applications**, et accordez à "Freebox Devices (Home Assistant)"
   la permission **"Modification des réglages de la Freebox"** — sans elle,
   la lecture des appareils fonctionne mais le switch blacklist échouera
   avec une erreur de droits explicite dans les logs HA.

Le `app_token` obtenu est stocké dans l'entrée de configuration HA (comme le
fait l'intégration core `freebox`), pas de secret à gérer manuellement.

## Installation

### Via HACS (dépôt personnalisé)

1. HACS → Intégrations → menu ⋮ → **Dépôts personnalisés**.
2. Ajouter l'URL de ce dépôt GitHub, catégorie **Intégration**.
3. Installer, redémarrer Home Assistant, puis **Paramètres → Appareils et
   services → Ajouter une intégration → Freebox Devices**.

### Manuellement

Copier `custom_components/freebox_devices/` dans le dossier
`custom_components/` de la configuration HA, puis redémarrer.

## Ce que ça remplace (bricolage historique, à retirer une fois validé)

- `rest_command.freebox_toggle_blacklist`, `rest_command.freebox_kick_device`
- le `sensor` REST + le `template` sensor de filtrage
- `input_select.freebox_filtre_appareils`
- `script.freebox_toggle_blacklist_refresh`
- la carte `custom:flex-table-card` du dashboard Freebox
- **côté Pi** : le service `freebox-api.service` et `~/sniffer/` en entier

Ce nettoyage se fait après confirmation que la nouvelle intégration
fonctionne (présence, signal, bascule blacklist) — pas avant, pour éviter un
trou de service.

## Vérifications effectuées avant publication

- [x] Structure conforme aux exigences HACS (un seul dossier sous
      `custom_components/`, `hacs.json` à la racine).
- [x] `manifest.json` : clés obligatoires présentes (domain, documentation,
      issue_tracker, codeowners, name, version).
- [x] Tous les `.py` compilent (`python3 -m py_compile`).
- [x] Tous les `.json` sont valides.
- [ ] **`hassfest` / `hacs/action`** (CI GitHub, à activer après le premier push).
- [ ] **Icône de marque** (`brand/icon.png`) — placeholder laissé, à fournir.
- [ ] **Test réel du flow d'appairage** — le bouton flèche physique et le
      polling `login/authorize/{track_id}/` n'ont pas pu être testés depuis
      cet environnement (pas d'accès réseau à la Freebox). À valider en
      conditions réelles.
- [ ] **Noms de champs de `wifi/ap/{id}/stations/`** (signal dBm) — implémentés
      avec plusieurs noms de repli (`signal`, `rssi`, `rx.signal`) faute de
      pouvoir vérifier la réponse exacte de l'API en direct depuis cet
      environnement. À confirmer/ajuster après le premier test réel (voir
      logs si `sensor.*_signal_wifi` reste toujours `None` pour un appareil
      Wifi actif).
- [x] Placeholder `@jaroy` / URL GitHub dans `manifest.json` corrigé
      (`@jacquesantoineroy-hash`, dépôt `HA-Freebox-Devices`).

## Roadmap

- Notification "nouvel appareil détecté" (event/persistent_notification).
- Option de configuration pour `consider_home` (délai avant "absent").
