/*
 * Vision — le panneau de l'écran de veille.
 *
 * Il montre les vraies cartes de Home Assistant, dessinées par Home Assistant,
 * dans le thème de l'appareil (ses couleurs arrivent dans l'adresse). L'horloge
 * d'abord, puis chaque tableau de bord rendu disponible : ses sections sont
 * rangées en colonnes, et ce qui dépasse l'écran passe sur l'écran suivant, en fondu.
 * Rien n'est cliquable : c'est un affichage.
 */
const CIEL = { sunny: "Ensoleillé", "clear-night": "Nuit claire", partlycloudy: "Éclaircies", cloudy: "Nuageux", rainy: "Pluie", pouring: "Forte pluie", fog: "Brouillard", snowy: "Neige", "snowy-rainy": "Neige fondue", lightning: "Orage", "lightning-rainy": "Orage", windy: "Vent", "windy-variant": "Vent", hail: "Grêle", exceptional: "Exceptionnel" };
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

class VisionVeillePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cartes = [];
    this._ecrans = [];
    this._indice = 0;
    this._pret = false;
  }

  set hass(hass) {
    this._hass = hass;
    for (const c of this._cartes) { try { c.hass = hass; } catch (e) { /* une carte en panne ne bloque pas les autres */ } }
    if (!this._pret) { this._pret = true; this._demarrer(); }
  }
  set narrow(v) {} set route(v) {} set panel(v) {}

  _couleur(nom, defaut) {
    const v = this._q.get(nom);
    return v && /^[0-9a-fA-F]{6}$/.test(v) ? "#" + v : defaut;
  }

  _theme() {
    const fond = this._couleur("fond", "#120609"), carte = this._couleur("carte", "#27111A"), texte = this._couleur("texte", "#FBF3EE");
    const texte2 = this._couleur("texte2", "#CDA8A6"), accent = this._couleur("accent", "#F2C14E"), ligne = this._couleur("ligne", "#4C2231");
    const vars = {
      "--primary-background-color": fond, "--secondary-background-color": carte, "--lovelace-background": fond,
      "--card-background-color": carte, "--ha-card-background": carte, "--ha-card-border-color": ligne, "--ha-card-border-radius": "18px",
      "--ha-card-box-shadow": "none", "--divider-color": ligne, "--outline-color": ligne,
      "--primary-text-color": texte, "--secondary-text-color": texte2, "--disabled-text-color": texte2, "--text-primary-color": fond,
      "--primary-color": accent, "--accent-color": accent, "--state-icon-color": accent, "--paper-item-icon-color": accent,
      "--state-active-color": accent, "--mdc-theme-primary": accent, "--mdc-theme-surface": carte, "--mdc-theme-on-surface": texte,
      "--ha-color-text-primary": texte, "--ha-color-text-secondary": texte2, "--ha-color-surface-default": carte,
      "--chip-background": carte, "--rgb-primary-text-color": this._rvb(texte), "--rgb-primary-color": this._rvb(accent),
      "--rgb-card-background-color": this._rvb(carte), "--rgb-secondary-text-color": this._rvb(texte2),
      "--v-fond": fond, "--v-carte": carte, "--v-texte": texte, "--v-texte2": texte2, "--v-accent": accent,
    };
    for (const [k, v] of Object.entries(vars)) this.style.setProperty(k, v);
    document.body.style.background = fond;
  }
  _rvb(h) { return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(", "); }

  async _ressources() {
    // Les cartes de Home Assistant et celles de la communauté (HACS) se chargent avec le moteur des tableaux de bord.
    try {
      if (!window.loadCardHelpers) {
        await customElements.whenDefined("partial-panel-resolver");
        const r = document.createElement("partial-panel-resolver");
        r.hass = { panels: [{ url_path: "tmp", component_name: "lovelace" }] };
        r._updateRoutes();
        await r.routerOptions.routes.tmp.load();
        await Promise.race([customElements.whenDefined("ha-panel-lovelace"), pause(8000)]);
      }
    } catch (e) { /* on tente quand même */ }
    try {
      const res = await this._hass.callWS({ type: "lovelace/resources" });
      await Promise.all((res || []).map((x) => {
        if (x.type === "module") return import(x.url).catch(() => null);
        if (x.type === "js") return new Promise((ok) => { const s = document.createElement("script"); s.src = x.url; s.onload = s.onerror = ok; document.head.appendChild(s); });
        if (x.type === "css") { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = x.url; document.head.appendChild(l); }
        return null;
      }));
    } catch (e) { /* sans ressources, les cartes d'origine suffisent */ }
    for (let i = 0; i < 40 && !window.loadCardHelpers; i++) await pause(250);
    return window.loadCardHelpers ? window.loadCardHelpers() : null;
  }

  async _demarrer() {
    this._q = new URLSearchParams(location.search);
    this._theme();
    this.shadowRoot.innerHTML = `
      <style>
        :host { position: fixed; inset: 0; z-index: 9999; background: var(--v-fond); color: var(--v-texte); overflow: hidden; cursor: none;
                font-family: "Segoe UI", Roboto, sans-serif; }
        * { cursor: none !important; }
        .scene { position: absolute; inset: 0; opacity: 0; transition: opacity .6s ease; pointer-events: none; }
        .scene.vue { opacity: 1; }
        .horloge { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; }
        .heure { font-size: 26vh; font-weight: 300; line-height: 1; letter-spacing: -.02em; }
        .date { font-size: 4.6vh; color: var(--v-texte2); margin-top: 2vh; }
        .ciel { font-size: 3.8vh; color: var(--v-accent); margin-top: 3vh; }
        .tete { display: flex; justify-content: space-between; align-items: baseline; padding: 3.2vh 3.5vw 1.6vh; }
        .titre { font-size: 3.6vh; font-weight: 600; }
        .petite { font-size: 3.2vh; color: var(--v-texte2); }
        .colonnes { position: absolute; left: 3.5vw; right: 3.5vw; top: 11vh; bottom: 3vh; overflow: hidden;
                    column-width: 400px; column-gap: 24px; column-fill: auto; }
        .section { break-inside: avoid; margin: 0 0 18px; display: grid; grid-template-columns: repeat(12, 1fr); gap: 10px; }
        .section.longue { break-inside: auto; display: block; }
        .section.longue > * { margin-bottom: 10px; break-inside: avoid; }
        .section > * { min-width: 0; }
        .sec { grid-column: 1 / -1; font-size: 13px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--v-accent); margin: 2px 2px 0; }
        .vide { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--v-texte2); font-size: 3vh; }
      </style>
      <div class="scene vue" id="s0"><div class="vide">Vision</div></div>`;
    let page = null, aides = null;
    try {
      [page, aides] = await Promise.all([
        this._hass.callApi("GET", `pc_parental/veille/page?id=${encodeURIComponent(this._q.get("id") || "")}&ecran=${encodeURIComponent(this._q.get("ecran") || "tele")}`),
        this._ressources(),
      ]);
    } catch (e) { page = null; }
    this._page = page || { horloge: { actif: true, duree: 30 }, tableaux: [] };
    this._aides = aides;
    const masques = new Set((this._q.get("masques") || "").split(",").filter(Boolean));
    const cachees = new Set((this._q.get("cartes") || "").split(",").filter(Boolean));
    // La liste des écrans à enchaîner : l'horloge, puis les tableaux (découpés à l'affichage).
    const liste = [];
    if (this._page.horloge && this._page.horloge.actif && !masques.has("horloge")) liste.push({ genre: "horloge", duree: this._page.horloge.duree || 15 });
    for (const t of this._page.tableaux || []) {
      if (masques.has(t.id)) continue;
      const sections = [];
      for (const s of t.sections || []) {
        const cartes = (s.cartes || []).filter((c) => !(c.cles && c.cles.length && c.cles.every((k) => cachees.has(`${t.id}|${k}`))));
        if (cartes.length) sections.push({ titre: s.titre, cartes });
      }
      if (sections.length) liste.push({ genre: "tableau", duree: t.duree || 25, titre: t.titre, sections, pages: 1, page: 0 });
    }
    if (!liste.length) liste.push({ genre: "horloge", duree: 30 });
    this._ecrans = liste;
    this._indice = (parseInt(this._q.get("dec") || "0", 10) || 0) % liste.length;
    setInterval(() => this._tic(), 1000);
    this._montrer();
  }

  _tic() {
    const d = new Date();
    const h = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    this.shadowRoot.querySelectorAll(".heure, .petite").forEach((e) => { if (e.textContent !== h) e.textContent = h; });
  }

  _carte(config) {
    let el;
    try { el = this._aides ? this._aides.createCardElement(config) : null; } catch (e) { el = null; }
    if (!el) return null;
    try { el.hass = this._hass; } catch (e) { /* idem */ }
    this._cartes.push(el);
    // La largeur voulue dans Home Assistant (sur 12), reprise telle quelle.
    let colonnes = 12;
    const o = config.grid_options || config.layout_options || {};
    const v = o.columns ?? o.grid_columns;
    if (v === "full") colonnes = 12;
    else if (typeof v === "number") colonnes = Math.max(3, Math.min(12, v));
    else { try { const g = el.getGridOptions && el.getGridOptions(); if (g && typeof g.columns === "number") colonnes = Math.max(3, Math.min(12, g.columns)); } catch (e) { /* 12 */ } }
    el.style.gridColumn = `span ${colonnes}`;
    return el;
  }

  async _montrer() {
    const e = this._ecrans[this._indice];
    const ancienne = this.shadowRoot.querySelector(".scene.vue");
    const scene = document.createElement("div");
    scene.className = "scene";
    if (e.genre === "horloge") {
      const d = new Date();
      let jour = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
      jour = jour.charAt(0).toUpperCase() + jour.slice(1);
      const m = this._page.meteo ? this._hass.states[this._page.meteo] : null;
      const morceaux = [];
      if (m && m.attributes && typeof m.attributes.temperature === "number") morceaux.push(`${Math.round(m.attributes.temperature)}°`);
      if (m && CIEL[m.state]) morceaux.push(CIEL[m.state]);
      scene.innerHTML = `<div class="horloge"><div class="heure"></div><div class="date">${jour}</div><div class="ciel">${morceaux.join("  ·  ")}</div></div>`;
    } else {
      if (e.page === 0) {
        // Les cartes sont créées une fois par passage, pour des valeurs à jour.
        this._cartes = [];
        const colonnes = document.createElement("div");
        colonnes.className = "colonnes";
        for (const s of e.sections) {
          const bloc = document.createElement("div");
          bloc.className = "section";
          if (s.titre) { const t = document.createElement("div"); t.className = "sec"; t.textContent = s.titre; bloc.appendChild(t); }
          for (const c of s.cartes) { const el = this._carte(c.config); if (el) bloc.appendChild(el); }
          if (bloc.children.length) colonnes.appendChild(bloc);
        }
        e._colonnes = colonnes;
      }
      const tete = document.createElement("div");
      tete.className = "tete";
      tete.innerHTML = `<div class="titre"></div><div class="petite"></div>`;
      scene.appendChild(tete);
      scene.appendChild(e._colonnes);
      tete.querySelector(".titre").textContent = e.titre + (e.pages > 1 ? `   ${e.page + 1}/${e.pages}` : "");
    }
    this.shadowRoot.appendChild(scene);
    this._tic();
    if (e.genre === "tableau") {
      const c = e._colonnes;
      if (e.page === 0) {
        // Le temps que les cartes se dessinent, puis on compte les écrans nécessaires.
        await pause(1800);
        for (const s of c.querySelectorAll(".section")) if (s.offsetHeight > c.clientHeight) s.classList.add("longue");
        await pause(200);
        e.pas = c.clientWidth + 24;
        e.pages = Math.max(1, Math.min(8, Math.ceil((c.scrollWidth - 4) / e.pas)));
        scene.querySelector(".titre").textContent = e.titre + (e.pages > 1 ? `   1/${e.pages}` : "");
      }
      c.scrollLeft = e.page * e.pas;
    }
    requestAnimationFrame(() => { scene.classList.add("vue"); if (ancienne) { ancienne.classList.remove("vue"); setTimeout(() => ancienne.remove(), 700); } });
    clearTimeout(this._minuteur);
    this._minuteur = setTimeout(() => this._suivant(), Math.max(5, e.duree) * 1000);
  }

  _suivant() {
    const e = this._ecrans[this._indice];
    if (e.genre === "tableau" && e.page + 1 < e.pages) e.page += 1;
    else { if (e.genre === "tableau") e.page = 0; this._indice = (this._indice + 1) % this._ecrans.length; }
    if (this._ecrans.length === 1 && e.genre === "horloge") { this._minuteur = setTimeout(() => this._suivant(), 60000); return; }
    this._montrer();
  }
}

if (!customElements.get("vision-veille-panel")) customElements.define("vision-veille-panel", VisionVeillePanel);
