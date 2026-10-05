# Vision 1.53.0 : les actifs, matériels partagés, temps par personne

- `vision-1.53.0.json` : le patch (intégration 1.52.0 vers 1.53.0, agent PC 1.72.0 vers 1.73.0, carte du tableau de bord).
- `installer_patch.py` : l'applique dans Home Assistant. Tout ou rien, empreintes vérifiées avant et après, anciens fichiers gardés dans `sauvegardes/`.
- `fabriquer_patch.py` : fabrique un patch à partir du dépôt de travail (lignes changées et contexte, pas les fichiers entiers).
- `banc.py`, `augmenter.py` : banc d'essai de la fenêtre PC (elle se photographie vue par vue, hors de l'écran).
- `carte.test.mjs` : essai de la carte du tableau de bord dans un navigateur sans tête.

Installation, depuis le dossier de configuration de Home Assistant :

    python3 installer_patch.py vision-1.53.0.json /homeassistant

puis redémarrer Home Assistant.
