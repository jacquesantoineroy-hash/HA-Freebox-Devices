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
    // Home Assistant recrée parfois le panneau (quand sa liste de panneaux se met à jour) : la veille repartait
    // alors de zéro, horloge comprise. Le premier panneau créé reste donc le seul ; les suivants le reprennent.
    const premier = window.__visionVeille;
    if (premier && premier !== this) {
      if (premier.parentNode !== this.parentNode && this.parentNode) this.parentNode.appendChild(premier);
      this.style.display = "none";
      premier.hass = hass;
      return;
    }
    window.__visionVeille = this;
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
    // Le style graphique (formes, bordures, lettres) est distinct des couleurs : chacun choisit les deux.
    this._style = this._q.get("style") === "neoretro" ? "neoretro" : "doux";
    if (this._style === "neoretro") {
      Object.assign(vars, {
        "--ha-card-border-radius": "3px", "--ha-card-border-width": "0px", "--ha-card-border-color": "transparent",
        "--ha-font-family-body": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--primary-font-family": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--paper-font-common-base_-_font-family": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--chip-border-radius": "3px", "--chip-border-width": "0px", "--mush-chip-border-radius": "3px",
      });
    }
    // Chacun décide : un fond sous ses cartes ou non, un contour ou non.
    const net = this._style === "neoretro";
    if (this._q.get("cfond") === "0") {
      Object.assign(vars, { "--ha-card-background": "transparent", "--card-background-color": "transparent", "--chip-background": "transparent", "--mush-chip-background": "transparent" });
    }
    const contour = this._q.get("ccontour") === "1";
    Object.assign(vars, {
      "--ha-card-border-width": contour ? (net ? "1.5px" : "1px") : "0px",
      "--ha-card-border-color": contour ? ligne : "transparent",
      "--chip-border-width": contour ? (net ? "1.5px" : "1px") : "0px", "--chip-border-color": contour ? ligne : "transparent",
    });
    this._sombre = [1, 3, 5].map((i) => parseInt(fond.slice(i, i + 2), 16)).reduce((a, b) => a + b, 0) < 384;
    this.setAttribute("data-style", this._style);
    for (const [k, v] of Object.entries(vars)) this.style.setProperty(k, v);
    document.body.style.background = fond;
  }
  _rvb(h) { return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(", "); }

  // Avec « diag=1 » dans l'adresse, les temps de chargement s'écrivent en haut de l'écran.
  _note(texte) {
    if (!this._q || this._q.get("diag") !== "1") return;
    let d = this.shadowRoot.querySelector(".diag");
    if (!d) { d = document.createElement("div"); d.className = "diag"; d.style.cssText = "position:absolute;left:1vw;top:1vh;z-index:9;font:14px Consolas,monospace;color:#fff;white-space:pre"; this.shadowRoot.appendChild(d); }
    d.textContent += `${((Date.now() - this._debut) / 1000).toFixed(1)} s  ${texte}\n`;
  }

  async _ressources() {
    // Les cartes de Home Assistant et celles de la communauté (HACS) se chargent avec le moteur des tableaux de bord.
    try {
      if (!window.loadCardHelpers) {
        await customElements.whenDefined("partial-panel-resolver");
        const r = document.createElement("partial-panel-resolver");
        r.hass = { panels: [{ url_path: "tmp", component_name: "lovelace" }] };
        r._updateRoutes();
        this._note("moteur : demandé");
        await r.routerOptions.routes.tmp.load();
        this._note("moteur : chargé");
      }
    } catch (e) { /* on tente quand même */ }
    try {
      const res = await this._hass.callWS({ type: "lovelace/resources" });
      this._note(`ressources : ${(res || []).length} à charger`);
      // Les cartes de la communauté se chargent en même temps ; on ne les attend pas plus de cinq secondes.
      await Promise.race([pause(5000), Promise.all((res || []).map((x) => {
        if (x.type === "module") return import(x.url).catch(() => null);
        if (x.type === "js") return new Promise((ok) => { const s = document.createElement("script"); s.src = x.url; s.onload = s.onerror = ok; document.head.appendChild(s); });
        if (x.type === "css") { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = x.url; document.head.appendChild(l); }
        return null;
      }))]);
    } catch (e) { /* sans ressources, les cartes d'origine suffisent */ }
    this._note("ressources : finies, aides " + (window.loadCardHelpers ? "présentes" : "absentes"));
    for (let i = 0; i < 24 && !window.loadCardHelpers; i++) await pause(250);
    this._note("aides : " + (window.loadCardHelpers ? "ok" : "jamais venues"));
    return window.loadCardHelpers ? window.loadCardHelpers() : null;
  }

  async _demarrer() {
    this._debut = Date.now();
    this._q = new URLSearchParams(location.search);
    try {
      const n = (parseInt(sessionStorage.getItem("visionVeille") || "0", 10) || 0) + 1;
      sessionStorage.setItem("visionVeille", String(n));
      const nav = (performance.getEntriesByType("navigation")[0] || {}).type || "?";
      setTimeout(() => this._note(`chargement n° ${n} (${nav}) à ${new Date().toLocaleTimeString("fr-FR")}, page ouverte depuis ${(performance.now() / 1000).toFixed(1)} s`), 0);
    } catch (e) { /* sans importance */ }
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
        .cadre { position: absolute; left: 3.5vw; right: 3.5vw; top: 11vh; bottom: 9.5vh; overflow: hidden; }
        .grille { position: absolute; left: 0; top: 0; display: grid; gap: 34px 44px; align-items: start; transform-origin: top left; }
        .section { display: grid; grid-template-columns: repeat(12, 1fr); gap: 18px; align-items: start; }
        .section > * { min-width: 0; }
        .sec { grid-column: 1 / -1; font-size: 13px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--v-accent); margin: 2px 2px 0; }
        /* Néo-rétro : filets d'or, angles nets, capitales espacées, chiffres de tableau de bord. */
        :host([data-style="neoretro"]) { font-family: Bahnschrift, "DIN Alternate", "Roboto Condensed", "Segoe UI", sans-serif; }
        :host([data-style="neoretro"]) .tete { margin: 0 3.5vw; padding: 3.2vh 0 1.4vh; border-bottom: 1.5px solid var(--v-accent); align-items: flex-end; }
        :host([data-style="neoretro"]) .titre { text-transform: uppercase; letter-spacing: .22em; font-weight: 400; font-size: 3vh; }
        :host([data-style="neoretro"]) .titre::before { content: ""; display: inline-block; width: 1.5vh; height: 1.5vh; background: var(--v-accent); margin-right: 1.6vh; }
        :host([data-style="neoretro"]) .petite { letter-spacing: .12em; font-variant-numeric: tabular-nums; color: var(--v-texte); }
        :host([data-style="neoretro"]) .sec { letter-spacing: .26em; font-weight: 400; }
        :host([data-style="neoretro"]) .heure { font-weight: 300; letter-spacing: .04em; font-variant-numeric: tabular-nums; font-size: 30vh; }
        :host([data-style="neoretro"]) .horloge::before { content: "VISION"; letter-spacing: .6em; font-size: 2.2vh; color: var(--v-accent); margin-bottom: 4vh; padding-left: .6em; }
        :host([data-style="neoretro"]) .date { text-transform: uppercase; letter-spacing: .3em; font-size: 3vh; margin-top: 3vh; padding-top: 3vh; border-top: 1.5px solid var(--v-accent); min-width: 46vw; text-align: center; }
        :host([data-style="neoretro"]) .ciel { text-transform: uppercase; letter-spacing: .3em; font-size: 2.6vh; }
        /* La marque, en bas à gauche : l'œil de Vision (le même que sur les télés) et son nom. */
        .marque { position: absolute; left: 3.5vw; bottom: 1.6vh; height: 7vh; display: flex; align-items: center; z-index: 5; pointer-events: none; }
        .marque span { margin-left: 1vh; font-size: 2.6vh; font-weight: 700; letter-spacing: .12em; color: var(--v-texte2); opacity: .9; }
        mushroom-chips-card { margin-bottom: 4px; }
        .vide { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--v-texte2); font-size: 3vh; }
      </style>
      <div class="marque"><canvas></canvas><span>Vision</span></div>
      <div class="scene vue" id="s0"><div class="horloge"><div class="heure"></div><div class="date"></div></div></div>`;
    // L'heure s'affiche tout de suite ; les tableaux arrivent dès que Home Assistant a répondu.
    { const j = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }); this.shadowRoot.querySelector(".date").textContent = j.charAt(0).toUpperCase() + j.slice(1); }
    this._tic();
    let page = null, aides = null;
    try {
      [page, aides] = await Promise.all([
        this._hass.callApi("GET", `pc_parental/veille/page?id=${encodeURIComponent(this._q.get("id") || "")}&ecran=${encodeURIComponent(this._q.get("ecran") || "tele")}`).then((r) => { this._note("page : reçue"); return r; }),
        this._ressources(),
      ]);
    } catch (e) { page = null; this._note("erreur : " + e); }
    this._note("page et aides : prêtes");
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
        const cartes = (s.cartes || []).filter((c) => !cachees.has(`${t.id}|${c.cle}`) && !(c.cles && c.cles.length && c.cles.every((k) => cachees.has(`${t.id}|${k}`))));
        if (cartes.length) sections.push({ titre: s.titre, span: s.span || 1, cartes });
      }
      if (sections.length) liste.push({ genre: "tableau", duree: t.duree || 25, titre: t.titre, colonnes: t.colonnes || 4, sections, pages: 1, page: 0 });
    }
    if (!liste.length) liste.push({ genre: "horloge", duree: 30 });
    this._ecrans = liste;
    this._indice = (parseInt(this._q.get("dec") || "0", 10) || 0) % liste.length;
    setInterval(() => this._tic(), 1000);
    this._oeil();
    // L'heure est à l'écran depuis l'ouverture : dès que les cartes sont prêtes (et après quatre secondes
    // d'horloge au moins), on passe au premier tableau au lieu de refaire un tour d'horloge.
    const premier = liste[this._indice];
    if (premier.genre === "horloge" && liste.length > 1) {
      this._indice = (this._indice + 1) % liste.length;
      // Après un rechargement de la page (Home Assistant en fait un à la première ouverture), on n'attend pas.
      const recharge = ((performance.getEntriesByType("navigation")[0] || {}).type === "reload");
      setTimeout(() => this._montrer(), recharge ? 0 : Math.max(0, 4000 - (Date.now() - this._debut)));
    } else this._montrer();
  }

  // L'œil de Vision, dessiné comme sur les télés : une amande claire, l'iris pourpre et or qui regarde
  // ici et là, la paupière qui cligne vite et se rouvre plus doucement, parfois deux fois de suite.
  _oeil() {
    const toile = this.shadowRoot.querySelector(".marque canvas");
    const g = toile.getContext("2d");
    const pourpre = this._sombre ? "#C2577B" : "#8C2F4B";
    const or = this._couleur("accent", "#F2C14E"), encre = this._sombre ? "#1B1418" : this._couleur("texte", "#2A2026");
    let prochainClin = 0, clinDebut = -9, prochainRegard = 0, cibleX = 0, cibleY = 0, rx = 0, ry = 0;
    const pas = () => {
      const t = performance.now() / 1000, H = window.innerHeight, dpr = window.devicePixelRatio || 1;
      const demiL = H * 0.03, demiH = H * 0.017, L = demiL * 2 + H * 0.012, HH = demiH * 4 + H * 0.012;
      if (toile.width !== Math.round(L * dpr)) { toile.width = Math.round(L * dpr); toile.height = Math.round(HH * dpr); toile.style.width = `${L}px`; toile.style.height = `${HH}px`; }
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, L, HH);
      if (t >= prochainClin) { clinDebut = t; prochainClin = t + (Math.random() < 0.18 ? 0.4 : 2.5 + Math.random() * 5); }
      const tt = t - clinDebut;
      const fermeture = tt < 0 ? 0 : tt < 0.10 ? tt / 0.10 : tt < 0.26 ? 1 - (tt - 0.10) / 0.16 : 0;
      if (t >= prochainRegard) { cibleX = (Math.random() - 0.5) * 1.6; cibleY = (Math.random() - 0.5) * 0.9; prochainRegard = t + 1.5 + Math.random() * 4; }
      rx += (cibleX - rx) * 0.18; ry += (cibleY - ry) * 0.18;
      const cx = L / 2, cy = HH / 2, ouverture = demiH * (1 - fermeture * 0.96), bas = demiH * 2 * (1 - fermeture * 0.5);
      const amande = new Path2D();
      amande.moveTo(cx - demiL, cy); amande.quadraticCurveTo(cx, cy - ouverture * 2, cx + demiL, cy); amande.quadraticCurveTo(cx, cy + bas, cx - demiL, cy); amande.closePath();
      g.globalAlpha = 1; g.fillStyle = this._sombre ? "#E9E2D6" : "#FFFBF2"; g.fill(amande);
      g.save(); g.clip(amande);
      const ix = cx + rx * demiL * 0.45, iy = cy + ry * demiH * 0.5, ri = demiH * 0.95;
      const disque = (x, y, r, c, a = 1) => { g.globalAlpha = a; g.fillStyle = c; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); };
      disque(ix, iy, ri, pourpre); disque(ix, iy, ri * 0.62, or); disque(ix, iy, ri * 0.34, encre);
      disque(ix - ri * 0.28, iy - ri * 0.3, ri * 0.14, "#FFFFFF", 0.78);
      g.restore();
      g.lineCap = "round"; g.strokeStyle = pourpre;
      g.globalAlpha = 1; g.lineWidth = H * 0.004; g.beginPath(); g.moveTo(cx - demiL, cy); g.quadraticCurveTo(cx, cy - ouverture * 2, cx + demiL, cy); g.stroke();
      g.globalAlpha = 0.59; g.lineWidth = H * 0.002; g.beginPath(); g.moveTo(cx - demiL, cy); g.quadraticCurveTo(cx, cy + bas, cx + demiL, cy); g.stroke();
      g.globalAlpha = 1;
      requestAnimationFrame(pas);
    };
    pas();
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
    // Un titre ne reste jamais seul en bas d'une colonne : il suit sa carte.
    // Une page web embarquée (carte météo animée…) est dessinée deux fois plus grande puis réduite de moitié :
    // le site dispose d'une vraie largeur et ses boutons ne se chevauchent plus.
    if (config.type === "iframe") {
      el.style.display = "block"; el.style.width = "200%"; el.style.transformOrigin = "0 0"; el.style.transform = "scale(0.5)";
      const boite = document.createElement("div");
      boite.className = "web";
      boite.style.cssText = "overflow:hidden;width:100%;border-radius:var(--ha-card-border-radius,18px);break-inside:avoid;";
      boite.style.gridColumn = `span ${colonnes}`;
      boite.appendChild(el);
      return boite;
    }
    if (config.type === "heading") { el.style.breakAfter = "avoid"; el.style.display = "block"; }
    return el;
  }

  async _montrer(reste) {
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
        // La disposition du tableau de bord est gardée telle quelle : ses sections côte à côte, dans le même
        // ordre et sur le même nombre de colonnes que dans Home Assistant. Seule la taille s'adapte à l'écran.
        const colonnes = document.createElement("div");
        colonnes.className = "grille";
        const blocs = [];
        for (const s of e.sections) {
          const bloc = document.createElement("div");
          bloc.className = "section";
          bloc._span = Math.max(1, Math.min(4, s.span || 1));
          if (s.titre) { const t = document.createElement("div"); t.className = "sec"; t.textContent = s.titre; bloc.appendChild(t); }
          for (const c of s.cartes) { const el = this._carte(c.config); if (el) bloc.appendChild(el); }
          if (bloc.children.length) blocs.push(bloc);
        }
        const voulu = Math.max(1, Math.min(6, e.colonnes || 4));
        const n = Math.max(1, Math.min(voulu, blocs.reduce((a, x) => a + x._span, 0)));
        colonnes.style.gridTemplateColumns = `repeat(${n}, 460px)`;
        colonnes.style.width = `${n * 460 + (n - 1) * 44}px`;
        for (const bloc of blocs) { bloc.style.gridColumn = `span ${Math.min(n, bloc._span)}`; colonnes.appendChild(bloc); }
        e._colonnes = colonnes;
      }
      const tete = document.createElement("div");
      tete.className = "tete";
      tete.innerHTML = `<div class="titre"></div><div class="petite"></div>`;
      scene.appendChild(tete);
      const cadre = document.createElement("div");
      cadre.className = "cadre";
      cadre.appendChild(e._colonnes);
      scene.appendChild(cadre);
      tete.querySelector(".titre").textContent = e.titre + (e.pages > 1 ? `   ${e.page + 1}/${e.pages}` : "");
    }
    this.shadowRoot.appendChild(scene);
    this._tic();
    if (e.genre === "tableau") {
      const c = e._colonnes;
      if (e.page === 0) {
        // Le temps que les cartes se dessinent, puis on compte les écrans nécessaires.
        await pause(1200);
        const cadre = c.parentElement, L = cadre.clientWidth, H = cadre.clientHeight;
        this._uneLigne(c);
        // Une page web embarquée est dessinée en double puis réduite de moitié : sa boîte prend la moitié de sa hauteur.
        for (const b of c.querySelectorAll(".web")) { const h = b.firstElementChild ? b.firstElementChild.offsetHeight : 0; if (h) b.style.height = `${h / 2}px`; }
        // Les rangées de sections, de haut en bas ; ce qui ne tient pas en hauteur passe sur l'écran suivant.
        const sections = [...c.querySelectorAll(".section")];
        const rangees = [];
        for (const s of sections) {
          const derniere = rangees[rangees.length - 1];
          if (derniere && Math.abs(derniere.haut - s.offsetTop) < 4) { derniere.sections.push(s); derniere.bas = Math.max(derniere.bas, s.offsetTop + s.offsetHeight); }
          else rangees.push({ haut: s.offsetTop, bas: s.offsetTop + s.offsetHeight, sections: [s] });
        }
        const larg = c.offsetWidth || 1, haut = c.offsetHeight || 1;
        const zl = Math.min(L / larg, 2.2);
        e._pages = [];
        if (haut * zl <= H || H / haut >= zl * 0.62) {
          // Tout tient sur un écran, quitte à réduire un peu.
          e._pages.push({ haut: 0, bas: haut, sections });
        } else {
          let courante = null;
          for (const r of rangees) {
            if (courante && (r.bas - courante.haut) * zl <= H) { courante.bas = r.bas; courante.sections.push(...r.sections); }
            else { courante = { haut: r.haut, bas: r.bas, sections: [...r.sections] }; e._pages.push(courante); }
          }
        }
        e._pages = e._pages.slice(0, 8);
        e._larg = larg; e._L = L; e._H = H;
        e.pages = e._pages.length || 1;
        scene.querySelector(".titre").textContent = e.titre + (e.pages > 1 ? `   1/${e.pages}` : "");
      }
      // L'écran demandé : ses sections seules, à la plus grande taille qui tient, centrées.
      const pg = e._pages[e.page] || e._pages[0];
      if (pg) {
        const hp = Math.max(1, pg.bas - pg.haut);
        const z = Math.min(e._L / e._larg, e._H / hp, 2.2) * 0.985;
        for (const s of c.querySelectorAll(".section")) s.style.visibility = pg.sections.includes(s) ? "visible" : "hidden";
        const dx = Math.max(0, (e._L - e._larg * z) / 2), dy = Math.max(0, Math.min((e._H - hp * z) / 2, e._H * 0.1));
        c.style.transform = `translate(${dx}px, ${dy - pg.haut * z}px) scale(${z})`;
      }
    }
    requestAnimationFrame(() => { scene.classList.add("vue"); if (ancienne) { ancienne.classList.remove("vue"); setTimeout(() => ancienne.remove(), 700); } });
    clearTimeout(this._minuteur);
    this._minuteur = setTimeout(() => this._suivant(), reste || Math.max(5, e.duree) * 1000);
  }

  // Une rangée de pastilles reste sur une ligne : si elle est trop large, elle rétrécit au lieu de passer dessous.
  // Rien à changer dans le tableau de bord : c'est la veille qui s'adapte.
  _uneLigne(racine) {
    for (const el of racine.querySelectorAll("mushroom-chips-card")) {
      try {
        const rangee = el.shadowRoot && el.shadowRoot.querySelector(".chip-container");
        if (!rangee) continue;
        rangee.style.flexWrap = "nowrap"; rangee.style.justifyContent = "flex-start"; rangee.style.whiteSpace = "nowrap";
        const dispo = el.clientWidth, besoin = rangee.scrollWidth;
        if (besoin > dispo + 2) {
          rangee.style.width = `${besoin}px`;
          rangee.style.transformOrigin = "left center";
          rangee.style.transform = `scale(${dispo / besoin})`;
        }
      } catch (e) { /* la carte reste telle quelle */ }
    }
  }

  _suivant() {
    const e = this._ecrans[this._indice];
    if (e.genre === "tableau" && e.page + 1 < e.pages) e.page += 1;
    else { if (e.genre === "tableau") e.page = 0; this._indice = (this._indice + 1) % this._ecrans.length; }
    if (this._ecrans.length === 1 && e.genre === "horloge") { this._minuteur = setTimeout(() => this._suivant(), 60000); return; }
    this._montrer();
  }
}

if (!customElements.get("vision-veille-coeur")) customElements.define("vision-veille-coeur", VisionVeillePanel);
