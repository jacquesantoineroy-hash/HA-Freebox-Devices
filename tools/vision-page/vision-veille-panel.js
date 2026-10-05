/*
 * Vision — porte du panneau de l'écran de veille. Elle ne fait que charger le
 * panneau lui-même (vision-veille-coeur.js) sous une adresse qui change toutes
 * les dix minutes : une correction arrive ainsi sur les appareils sans
 * redémarrer Home Assistant ni vider le cache des navigateurs.
 */
await import(`/local/vision-veille-coeur.js?v=${Math.floor(Date.now() / 600000)}`);
