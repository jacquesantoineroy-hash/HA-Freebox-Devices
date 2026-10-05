/*
 * Vision — porte du panneau de l'écran de veille. Elle existe tout de suite pour
 * Home Assistant, puis charge le panneau lui-même (vision-veille-coeur.js) sous
 * une adresse qui change toutes les dix minutes : une correction arrive ainsi sur
 * les appareils sans redémarrer Home Assistant ni vider le cache des navigateurs.
 */
class VisionVeillePorte extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (this._coeur) { this._coeur.hass = hass; return; }
    if (this._charge) return;
    this._charge = true;
    import(`/local/vision-veille-coeur.js?v=${Math.floor(Date.now() / 600000)}`).then(() => {
      this._coeur = document.createElement("vision-veille-coeur");
      this.appendChild(this._coeur);
      this._coeur.hass = this._hass;
    });
  }
  set narrow(v) {} set route(v) {} set panel(v) {}
}
if (!customElements.get("vision-veille-panel")) customElements.define("vision-veille-panel", VisionVeillePorte);
