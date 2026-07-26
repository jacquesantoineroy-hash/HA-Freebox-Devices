# Freebox Devices

Intégration Home Assistant (HACS) qui parle **directement** à l'API locale de
la Freebox — aucun service intermédiaire (pas de Raspberry Pi, pas de relais
HTTP). Elle expose, pour chaque appareil connu du réseau local :

- un **device_tracker** (présence, IP, fabricant, type d'appareil) — icône
  dynamique selon le mode de connexion (`mdi:wifi` / `mdi:ethernet` /
  `mdi:lan-disconnect` si absent) ;
- un **lock "Wifi lock"** par appareil — verrouillé = coupé (blacklisté sur le
  Wifi), déverrouillé = autorisé. Rendu natif en cadenas dans les cartes HA
  (entities, plus d'infos), pas de template nécessaire côté dashboard ;
- un **sensor "Wifi signal"** (dBm), `None` si l'appareil est filaire — icône
  à barres (`mdi:wifi-strength-1` à `4`) selon la force du signal ;
- un **switch "Masqué du dashboard"** par appareil (catégorie config, masqué
  par défaut dans l'UI standard des entités) — ON = retiré des cartes du
  dashboard (Connectés/Déconnectés), OFF = visible (défaut). Purement un
  filtre d'affichage : l'appareil continue d'être suivi normalement en
  arrière-plan (présence, signal, verrou Wifi) même masqué, et redevient
  visible instantanément si on repasse le switch sur OFF — rien n'est jamais
  perdu ni supprimé. Persistant entre redémarrages HA.

Un événement `freebox_devices_new_device` est émis dès qu'une MAC jamais vue
auparavant apparaît (voir [Alertes](#alertes--notifications) plus bas).

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
   la lecture des appareils fonctionne mais le lock Wifi échouera avec une
   erreur de droits explicite dans les logs HA.

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

## Alertes / notifications

### Nouvel appareil jamais vu

L'intégration mémorise (persistant, survit aux redémarrages HA) toutes les
MAC déjà vues depuis son installation. Dès qu'une MAC totalement inconnue
apparaît, elle émet l'événement `freebox_devices_new_device` avec les
données `mac`, `hostname`, `ip`, `vendor`. **Au tout premier démarrage de
l'intégration, tous les appareils déjà connus de la Freebox déclenchent
l'événement d'un coup** (rien n'était encore mémorisé) — normal, pas un bug.

Automatisation exemple :

```yaml
triggers:
  - trigger: event
    event_type: freebox_devices_new_device
actions:
  - action: notify.mobile_app_pixel_ja
    data:
      title: "Nouvel appareil : {{ trigger.event.data.hostname }}"
      message: >-
        {{ trigger.event.data.mac }} ({{ trigger.event.data.vendor or 'fabricant inconnu' }})
        vient de se connecter, IP {{ trigger.event.data.ip }}.
```

### Connexion/déconnexion récurrente d'un appareil précis

Pas besoin de fonctionnalité dédiée : chaque appareil a déjà son propre
`device_tracker`, qui déclenche normalement sur un changement d'état HA.
Automatisation exemple (alerte à chaque connexion ET déconnexion d'un
appareil choisi) :

```yaml
triggers:
  - trigger: state
    entity_id: device_tracker.telephone_arthur
    to:
      - "home"
      - "not_home"
actions:
  - action: notify.mobile_app_pixel_ja
    data:
      title: "{{ state_attr(trigger.entity_id, 'friendly_name') }}"
      message: >-
        {{ 'connecté' if trigger.to_state.state == 'home' else 'déconnecté' }}
        du réseau.
```

Pour ne suivre que les déconnexions (ou que les connexions), retirer la
valeur non voulue de la liste `to:`.

## Gérer un vieil appareil (ex-invité, matériel revendu...)

La Freebox garde en mémoire tout appareil qu'elle a déjà vu, donc
l'intégration fait pareil — un appareil ne disparaît jamais tout seul,
même après des mois d'absence. Pour un appareil dont vous ne voulez plus
qu'il pollue le dashboard :

- **Le masquer** : basculez son switch "Masqué du dashboard" sur ON (via
  Paramètres → Appareils et services → l'appareil → l'entité switch, ou
  directement depuis une carte "Masqués" du dashboard si configurée). Il
  disparaît des listes Connectés/Déconnectés mais continue d'être suivi.
- **Le remettre** : rebasculez le même switch sur OFF, il réapparaît
  immédiatement avec son historique intact (rien n'a été supprimé).
- **S'il se reconnecte** : aucune action nécessaire — masquer n'arrête pas
  le suivi, l'état présence/signal/verrou reste à jour même masqué ; seul
  l'affichage dans les listes du dashboard est filtré.

## Roadmap

- Option de configuration pour `consider_home` (délai avant "absent").
- Icône de marque officielle (`brand/icon.png`).
