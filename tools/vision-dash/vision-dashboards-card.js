/*
 * Vision — carte « Tableaux de bord sur l'écran de veille ».
 *
 * La liste des tableaux de bord de Home Assistant. On coche ceux que l'écran
 * de veille reprend ; pour chacun, la durée, les écrans, le public, puis ses
 * vues et ses cartes. Tout s'enregistre dans l'intégration ; les appareils le
 * reçoivent dans la minute et redessinent les cartes dans leur thème.
 */
const API_DASH = "pc_parental/veille/dashboards";
const echap = (t) =>
  String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const NOMS_ECRANS = { tele: "Télé", telephone: "Téléphone" };
const NOMS_PUBLICS = { affichage: "Affichage commun", parent: "Parents", enfant: "Enfants" };

class VisionDashboardsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tableaux = null;
    this._erreur = "";
    this._occupe = false;
    this._modifie = false;
    this._ouverts = new Set();
  }

  setConfig(config) { this._config = Object.assign({}, config || {}); }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: "full" }; }

  set hass(hass) {
    const premier = !this._hass;
    this._hass = hass;
    if (premier) this._charger();
  }

  async _charger() {
    if (!this._hass) return;
    try {
      const r = await this._hass.callApi("GET", API_DASH);
      this._tableaux = r.tableaux || [];
      this._erreur = "";
      this._modifie = false;
    } catch (e) {
      this._erreur = (e && (e.message || e.body?.message)) || "Impossible de lire les tableaux de bord.";
    }
    this._rendre();
  }

  _choix() {
    const choix = {};
    for (const t of this._tableaux || []) {
      const vues = {}, cartes = {};
      for (const v of t.vues) {
        if (!v.actif) vues[v.cle] = false;
        for (const c of v.cartes) if (!c.actif) cartes[`${v.cle}/${c.cle}`] = false;
      }
      if (t.actif || Object.keys(vues).length || Object.keys(cartes).length) {
        choix[t.adresse] = { actif: t.actif, duree: t.duree, ecrans: t.ecrans, publics: t.publics, vues, cartes };
      }
    }
    return choix;
  }

  async _enregistrer() {
    if (!this._tableaux || this._occupe) return;
    this._occupe = true; this._rendre();
    try {
      const r = await this._hass.callApi("POST", API_DASH, { choix: this._choix() });
      this._tableaux = r.tableaux || [];
      this._erreur = "";
      this._modifie = false;
    } catch (e) {
      this._erreur = (e && (e.message || e.body?.message)) || "Enregistrement impossible.";
    }
    this._occupe = false;
    this._rendre();
  }

  _coches(t, i, cle, noms) {
    return Object.keys(noms).map((k) =>
      `<label class="puce"><input type="checkbox" data-a="${cle}" data-i="${i}" data-k="${k}" ${t[cle].includes(k) ? "checked" : ""}>${noms[k]}</label>`).join("");
  }

  _vue(t, i, v, j) {
    const cle = `${t.adresse}/${v.cle}`;
    const ouverte = this._ouverts.has(cle);
    const visibles = v.cartes.filter((c) => c.comprise && c.actif).length;
    const possibles = v.cartes.filter((c) => c.comprise).length;
    let cartes = "";
    if (ouverte) {
      let section = null;
      cartes = `<div class="cartes">` + v.cartes.map((c, k) => {
        const tete = c.section !== section ? `<div class="section">${echap(c.section || "Sans titre")}</div>` : "";
        section = c.section;
        return tete + (c.comprise
          ? `<label class="carte"><input type="checkbox" data-a="carte" data-i="${i}" data-j="${j}" data-k="${k}" ${c.actif ? "checked" : ""}>
               <span>${echap(c.libelle)}</span><em>${echap(c.type)}${c.cases > 1 ? ` · ${c.cases} cases` : ""}</em></label>`
          : `<div class="carte inconnue"><span>${echap(c.libelle)}</span><em>${echap(c.type)} · non reprise</em></div>`);
      }).join("") + `</div>`;
    }
    return `<div class="vue">
      <div class="ligne">
        <input type="checkbox" data-a="vue" data-i="${i}" data-j="${j}" ${v.actif ? "checked" : ""} ${possibles ? "" : "disabled"}>
        <button class="titre" data-a="ouvrir" data-c="${echap(cle)}">${echap(v.titre)}</button>
        <span class="compte">${possibles ? `${visibles} / ${possibles} cartes` : "aucune carte reprise"}</span>
        <button class="fleche" data-a="ouvrir" data-c="${echap(cle)}">${ouverte ? "▾" : "▸"}</button>
      </div>${cartes}</div>`;
  }

  _tableau(t, i) {
    const detail = !t.actif ? "" : `
      <div class="reglages">
        <label>Durée <input type="number" min="5" max="120" value="${t.duree}" data-a="duree" data-i="${i}"> s</label>
        <span class="groupe">${this._coches(t, i, "ecrans", NOMS_ECRANS)}</span>
        <span class="groupe">${this._coches(t, i, "publics", NOMS_PUBLICS)}</span>
      </div>
      <div class="vues">${t.vues.map((v, j) => this._vue(t, i, v, j)).join("")}</div>`;
    const note = t.lisible ? `${t.vues.length} vue${t.vues.length > 1 ? "s" : ""}` : (t.genere ? "généré automatiquement, sans cartes à reprendre" : "vide");
    return `<div class="tableau ${t.actif ? "actif" : ""}">
      <div class="ligne tete">
        <label class="bascule"><input type="checkbox" data-a="actif" data-i="${i}" ${t.actif ? "checked" : ""} ${t.lisible ? "" : "disabled"}><b>${echap(t.titre)}</b></label>
        <span class="compte">${note}</span>
      </div>${detail}</div>`;
  }

  _rendre() {
    const corps = this._tableaux === null
      ? `<p class="info">${this._erreur ? echap(this._erreur) : "Chargement…"}</p>`
      : this._tableaux.map((t, i) => this._tableau(t, i)).join("") || `<p class="info">Aucun tableau de bord.</p>`;
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        h2 { margin: 0 0 4px; font-size: 1.15rem; font-weight: 600; }
        p.aide { margin: 0 0 14px; color: var(--secondary-text-color); font-size: .9rem; line-height: 1.4; }
        .info { color: var(--secondary-text-color); }
        .erreur { color: var(--error-color); margin: 8px 0; }
        .tableau { border: 1px solid var(--divider-color); border-radius: 12px; padding: 10px 12px; margin-bottom: 8px; }
        .tableau.actif { border-color: var(--primary-color); }
        .ligne { display: flex; align-items: center; gap: 8px; min-height: 36px; }
        .tete b { font-weight: 600; }
        .bascule { display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer; }
        .compte { color: var(--secondary-text-color); font-size: .82rem; white-space: nowrap; }
        .reglages { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; padding: 6px 0 8px 28px; font-size: .9rem; }
        .reglages input[type=number] { width: 62px; padding: 4px 6px; border: 1px solid var(--divider-color); border-radius: 6px; background: var(--card-background-color); color: var(--primary-text-color); }
        .groupe { display: flex; flex-wrap: wrap; gap: 4px 12px; }
        .puce { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
        .vues { padding-left: 28px; }
        .vue { border-top: 1px solid var(--divider-color); }
        button.titre, button.fleche { background: none; border: 0; color: var(--primary-text-color); font: inherit; cursor: pointer; padding: 6px 2px; text-align: left; }
        button.titre { flex: 1; }
        button.fleche { color: var(--secondary-text-color); }
        .cartes { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 2px 14px; padding: 2px 0 10px 28px; }
        .section { grid-column: 1 / -1; margin-top: 6px; font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: var(--secondary-text-color); }
        .carte { display: flex; align-items: center; gap: 6px; min-height: 30px; cursor: pointer; min-width: 0; }
        .carte span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .carte em { color: var(--secondary-text-color); font-size: .78rem; font-style: normal; white-space: nowrap; }
        .carte.inconnue { opacity: .5; cursor: default; padding-left: 24px; }
        .pied { display: flex; gap: 10px; align-items: center; margin-top: 12px; }
        .pied button { padding: 8px 16px; border-radius: 8px; border: 0; font: inherit; cursor: pointer; }
        .pied .principal { background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .pied .second { background: none; color: var(--primary-color); }
        .pied button[disabled] { opacity: .5; cursor: default; }
      </style>
      <ha-card>
        <h2>Tableaux de bord sur l'écran de veille</h2>
        <p class="aide">Coche les tableaux de bord à reprendre. Leurs sections, leurs colonnes et la taille de leurs cartes sont gardées, puis redessinées dans le thème de chaque appareil. S'il y a trop de cartes pour un écran, la suite arrive en fondu.</p>
        ${this._erreur && this._tableaux !== null ? `<div class="erreur">${echap(this._erreur)}</div>` : ""}
        ${corps}
        <div class="pied">
          <button class="principal" data-a="enregistrer" ${this._modifie && !this._occupe ? "" : "disabled"}>${this._occupe ? "Enregistrement…" : "Enregistrer"}</button>
          <button class="second" data-a="annuler" ${this._modifie ? "" : "disabled"}>Annuler</button>
        </div>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("[data-a]").forEach((el) => {
      const a = el.dataset.a;
      if (el.tagName === "BUTTON") {
        el.addEventListener("click", () => {
          if (a === "enregistrer") return this._enregistrer();
          if (a === "annuler") return this._charger();
          if (a === "ouvrir") { const c = el.dataset.c; this._ouverts.has(c) ? this._ouverts.delete(c) : this._ouverts.add(c); this._rendre(); }
        });
        return;
      }
      el.addEventListener("change", () => {
        const t = this._tableaux[+el.dataset.i];
        if (!t) return;
        if (a === "actif") t.actif = el.checked;
        else if (a === "duree") t.duree = Math.max(5, Math.min(120, parseInt(el.value, 10) || 25));
        else if (a === "ecrans" || a === "publics") {
          const k = el.dataset.k;
          t[a] = el.checked ? Array.from(new Set([...t[a], k])) : t[a].filter((x) => x !== k);
          if (!t[a].length) t[a] = [k];
        } else if (a === "vue") t.vues[+el.dataset.j].actif = el.checked;
        else if (a === "carte") t.vues[+el.dataset.j].cartes[+el.dataset.k].actif = el.checked;
        this._modifie = true;
        this._rendre();
      });
    });
  }
}

if (!customElements.get("vision-dashboards-card")) customElements.define("vision-dashboards-card", VisionDashboardsCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "vision-dashboards-card", name: "Vision : tableaux de bord sur l'écran de veille", description: "Choisir les tableaux de bord, vues et cartes repris par l'écran de veille." });
