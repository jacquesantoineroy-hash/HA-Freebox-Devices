/*
 * Vision — carte « Écran de veille » : les tableaux que la télé fait défiler.
 *
 * Une ligne par tableau, dans l'ordre du tour. Les tableaux intégrés
 * (horloge, météo, caméras…) s'activent, se règlent en durée et en public.
 * Les tableaux composés se créent ici : un titre, des cases (une entité
 * Home Assistant chacune, avec son rendu), un public. Tout s'enregistre
 * dans l'intégration ; la télé le reçoit dans la minute.
 */
const API = "pc_parental/veille/tableaux";

const esc = (t) =>
  String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ICONES = {
  horloge: "mdi:clock-outline", vigilance: "mdi:alert-outline", meteo: "mdi:weather-partly-cloudy", courbe: "mdi:chart-line",
  maison: "mdi:home-heart", tuiles: "mdi:view-grid-outline", cameras: "mdi:cctv", esports: "mdi:controller", courses: "mdi:flag-checkered",
  avenir: "mdi:calendar-clock", ecole: "mdi:school-outline", agenda: "mdi:calendar", chauffage: "mdi:fire", batteries: "mdi:battery-70",
  photos: "mdi:image-multiple-outline", entites: "mdi:shape-plus",
};

const nouvelId = () => "t" + Math.random().toString(36).slice(2, 9);

class VisionVeilleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._donnees = null;
    this._erreur = "";
    this._occupe = false;
    this._ouverts = new Set();
    this._modifie = false;
    this._apercus = {};
  }

  setConfig(config) { this._config = Object.assign({}, config || {}); }
  getCardSize() { return 12; }
  getGridOptions() { return { columns: "full" }; }

  set hass(hass) {
    const premier = !this._hass;
    this._hass = hass;
    if (premier) this._charger();
  }

  async _charger() {
    if (!this._hass || this._modifie) return;
    try {
      this._donnees = await this._hass.callApi("GET", API);
      this._erreur = "";
    } catch (e) {
      this._erreur = (e && (e.message || e.body?.message)) || "Impossible de lire les tableaux.";
    }
    this._rendre();
  }

  async _enregistrer() {
    if (!this._donnees || this._occupe) return;
    this._occupe = true; this._rendre();
    try {
      this._donnees = await this._hass.callApi("POST", API, { tableaux: this._donnees.tableaux });
      this._modifie = false; this._erreur = "";
    } catch (e) {
      this._erreur = (e && (e.message || e.body?.message)) || "Enregistrement refusé.";
    }
    this._occupe = false; this._rendre();
  }

  async _apercu(id) {
    try {
      const r = await this._hass.callApi("GET", `${API}?apercu=${encodeURIComponent(id)}`);
      this._apercus[id] = r.apercu || [];
    } catch (_) { this._apercus[id] = []; }
    this._rendre();
  }

  _toucher() { this._modifie = true; this._rendre(); }

  _cle(t) { return t.code === "entites" ? "entites:" + t.id : t.code; }

  _deplacer(i, delta) {
    const l = this._donnees.tableaux; const j = i + delta;
    if (j < 0 || j >= l.length) return;
    [l[i], l[j]] = [l[j], l[i]];
    this._toucher();
  }

  _ajouter() {
    const t = { code: "entites", id: nouvelId(), titre: "Nouveau tableau", actif: true, duree: 22, ecrans: ["tele", "telephone"], publics: ["affichage", "parent", "enfant"], personnes: [], cases: [{ entite: "", libelle: "", rendu: "auto" }] };
    this._donnees.tableaux.push(t);
    this._ouverts.add(this._cle(t));
    this._toucher();
  }

  _entitesTriees() {
    const s = this._hass ? this._hass.states : {};
    return Object.keys(s).filter((e) => !e.startsWith("update.") && !e.startsWith("automation.") && !e.startsWith("script.") && !e.startsWith("scene.")).sort();
  }

  _tour(liste) {
    const total = liste.filter((t) => t.actif).reduce((a, t) => a + (t.duree || 0), 0);
    const m = Math.floor(total / 60), s = total % 60;
    return m ? `${m} min ${String(s).padStart(2, "0")} s` : `${s} s`;
  }

  _rendre() {
    const d = this._donnees;
    const style = `
      :host { display: block; }
      ha-card { padding: 16px; }
      .entete { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
      .entete h2 { margin: 0; font-size: 1.15em; font-weight: 500; flex: 1; }
      .sous { color: var(--secondary-text-color); font-size: 0.9em; }
      .ligne { display: grid; grid-template-columns: 28px 36px 1fr auto auto auto; gap: 8px; align-items: center; padding: 8px 6px; border-top: 1px solid var(--divider-color); }
      .ligne.inactif .nom { opacity: 0.5; }
      .nom { font-weight: 500; }
      .nom small { display: block; font-weight: 400; color: var(--secondary-text-color); }
      .pub { display: flex; gap: 4px; flex-wrap: wrap; }
      .puce { font-size: 0.75em; padding: 1px 8px; border-radius: 999px; background: var(--secondary-background-color); color: var(--secondary-text-color); border: 1px solid var(--divider-color); cursor: pointer; user-select: none; }
      .puce.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
      .duree { display: inline-flex; align-items: center; gap: 2px; }
      .duree button, .fleches button, .btn { background: none; border: 1px solid var(--divider-color); color: var(--primary-text-color); border-radius: 8px; width: 28px; height: 28px; cursor: pointer; font-size: 1em; }
      .duree span { min-width: 42px; text-align: center; font-variant-numeric: tabular-nums; }
      .fleches { display: inline-flex; gap: 2px; }
      .detail { grid-column: 1 / -1; padding: 6px 0 10px 64px; display: flex; flex-direction: column; gap: 8px; }
      .case { display: grid; grid-template-columns: 1fr 160px 120px 28px; gap: 8px; align-items: center; }
      input, select { background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); border-radius: 8px; padding: 6px 8px; font: inherit; width: 100%; box-sizing: border-box; }
      .titre input { font-weight: 500; }
      .actions { display: flex; gap: 8px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
      .primaire { background: var(--primary-color); color: var(--text-primary-color, #fff); border: none; border-radius: 10px; padding: 8px 16px; cursor: pointer; font: inherit; }
      .primaire[disabled] { opacity: 0.5; cursor: default; }
      .secondaire { background: none; border: 1px solid var(--divider-color); color: var(--primary-text-color); border-radius: 10px; padding: 8px 14px; cursor: pointer; font: inherit; }
      .erreur { color: var(--error-color); margin-top: 8px; }
      .apercu { display: flex; gap: 8px; flex-wrap: wrap; }
      .apercu .c { border: 1px solid var(--divider-color); border-radius: 10px; padding: 6px 10px; min-width: 110px; }
      .apercu .c b { display: block; font-size: 1.2em; }
      .apercu .c small { color: var(--secondary-text-color); }
      ha-icon { --mdc-icon-size: 22px; color: var(--secondary-text-color); }
      .supp { color: var(--error-color); }
      @media (max-width: 700px) { .ligne { grid-template-columns: 28px 30px 1fr auto; } .pub, .fleches { grid-column: 3 / -1; } .detail { padding-left: 0; } .case { grid-template-columns: 1fr 1fr; } }
    `;
    if (!d) {
      this.shadowRoot.innerHTML = `<style>${style}</style><ha-card><div class="entete"><h2>Écran de veille</h2></div><div class="sous">${this._erreur ? esc(this._erreur) : "Chargement…"}</div></ha-card>`;
      return;
    }
    const noms = {}; d.integres.forEach((i) => { noms[i.code] = i; });
    const lignes = d.tableaux.map((t, i) => {
      const cle = this._cle(t);
      const ouvert = this._ouverts.has(cle);
      const integre = t.code !== "entites";
      const nom = integre ? noms[t.code]?.nom || t.code : t.titre;
      const expl = integre ? noms[t.code]?.explication || "" : `${t.cases.length} case${t.cases.length > 1 ? "s" : ""}`;
      const puces = [
        ...d.ecrans.map((e) => `<span class="puce ${t.ecrans.includes(e.code) ? "on" : ""}" data-i="${i}" data-ecran="${e.code}">${esc(e.nom)}</span>`),
        `<span style="width:6px"></span>`,
        ...d.publics.map((p) => `<span class="puce ${t.publics.includes(p.code) ? "on" : ""}" data-i="${i}" data-public="${p.code}">${esc(p.nom)}</span>`),
      ].join("");
      let detail = "";
      if (ouvert) {
        const personnes = d.personnes.map((p) => `<span class="puce ${t.personnes.includes(p.id) ? "on" : ""}" data-i="${i}" data-personne="${p.id}">${esc(p.nom)}</span>`).join("");
        let cases = "";
        if (!integre) {
          const options = this._entitesTriees();
          cases = `<div class="titre"><input data-i="${i}" data-champ="titre" value="${esc(t.titre)}" placeholder="Titre du tableau"></div>
            <datalist id="ents-${i}">${options.map((e) => `<option value="${esc(e)}">${esc(this._hass.states[e]?.attributes?.friendly_name || "")}</option>`).join("")}</datalist>` +
            t.cases.map((c, k) => `<div class="case">
              <input list="ents-${i}" data-i="${i}" data-k="${k}" data-champ="entite" value="${esc(c.entite)}" placeholder="entité (sensor.…)">
              <input data-i="${i}" data-k="${k}" data-champ="libelle" value="${esc(c.libelle)}" placeholder="libellé (optionnel)">
              <select data-i="${i}" data-k="${k}" data-champ="rendu">${d.rendus.map((r) => `<option value="${r.code}" ${c.rendu === r.code ? "selected" : ""}>${esc(r.nom)}</option>`).join("")}</select>
              <button class="btn supp" data-i="${i}" data-k="${k}" data-action="supprimer-case" title="Retirer">×</button>
            </div>`).join("") +
            `<div class="actions"><button class="secondaire" data-i="${i}" data-action="ajouter-case" ${t.cases.length >= 8 ? "disabled" : ""}>+ une case</button>
             <button class="secondaire" data-i="${i}" data-action="apercu">Aperçu</button>
             <button class="secondaire supp" data-i="${i}" data-action="supprimer">Supprimer ce tableau</button></div>` +
            (this._apercus[t.id] ? `<div class="apercu">${this._apercus[t.id].map((c) => `<div class="c"><small>${esc(c.nom)}</small><b>${c.rendu === "etat" || c.rendu === "texte" || c.valeur == null ? esc(c.texte) : esc(c.valeur) + " " + esc(c.unite)}</b><small>${esc(c.rendu)}</small></div>`).join("") || "<small>Aucune case lisible.</small>"}</div>` : "");
        }
        detail = `<div class="detail">
          ${cases}
          <div class="sous">Personnes précises (vide = selon le public ci-dessus) : <span class="pub">${personnes}</span></div>
        </div>`;
      }
      return `<div class="ligne ${t.actif ? "" : "inactif"}">
        <input type="checkbox" data-i="${i}" data-champ="actif" ${t.actif ? "checked" : ""} title="Afficher ce tableau">
        <ha-icon icon="${ICONES[t.code] || "mdi:television"}"></ha-icon>
        <div class="nom" data-i="${i}" data-action="ouvrir" style="cursor:pointer">${esc(nom)}<small>${esc(expl)}</small></div>
        <div class="pub">${puces}</div>
        <div class="duree"><button data-i="${i}" data-action="moins">−</button><span>${t.duree} s</span><button data-i="${i}" data-action="plus">+</button></div>
        <div class="fleches"><button data-i="${i}" data-action="haut" title="Monter">↑</button><button data-i="${i}" data-action="bas" title="Descendre">↓</button></div>
        ${detail}
      </div>`;
    }).join("");

    this.shadowRoot.innerHTML = `<style>${style}</style><ha-card>
      <div class="entete"><h2>Écran de veille : les tableaux</h2><span class="sous">Un tour complet dure ${this._tour(d.tableaux)}.</span></div>
      <div class="sous">Coche pour afficher, règle la durée, choisis les écrans et les publics. Clique un nom pour le détail. Un tableau composé prend n'importe quelles entités.</div>
      ${lignes}
      <div class="actions">
        <button class="primaire" data-action="enregistrer" ${this._modifie && !this._occupe ? "" : "disabled"}>${this._occupe ? "Enregistrement…" : "Enregistrer"}</button>
        <button class="secondaire" data-action="ajouter">+ Tableau composé</button>
        <button class="secondaire" data-action="annuler" ${this._modifie ? "" : "disabled"}>Annuler</button>
      </div>
      ${this._erreur ? `<div class="erreur">${esc(this._erreur)}</div>` : ""}
    </ha-card>`;
    this._brancher();
  }

  _brancher() {
    const root = this.shadowRoot;
    const l = () => this._donnees.tableaux;
    root.querySelectorAll("[data-action]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        const a = el.dataset.action; const i = Number(el.dataset.i); const k = Number(el.dataset.k);
        if (a === "enregistrer") return this._enregistrer();
        if (a === "annuler") { this._modifie = false; return this._charger(); }
        if (a === "ajouter") return this._ajouter();
        if (a === "ouvrir") { const c = this._cle(l()[i]); this._ouverts.has(c) ? this._ouverts.delete(c) : this._ouverts.add(c); return this._rendre(); }
        if (a === "moins") { l()[i].duree = Math.max(this._donnees.duree_min, l()[i].duree - 5); return this._toucher(); }
        if (a === "plus") { l()[i].duree = Math.min(this._donnees.duree_max, l()[i].duree + 5); return this._toucher(); }
        if (a === "haut") return this._deplacer(i, -1);
        if (a === "bas") return this._deplacer(i, 1);
        if (a === "ajouter-case") { l()[i].cases.push({ entite: "", libelle: "", rendu: "auto" }); return this._toucher(); }
        if (a === "supprimer-case") { l()[i].cases.splice(k, 1); return this._toucher(); }
        if (a === "supprimer") { l().splice(i, 1); return this._toucher(); }
        if (a === "apercu") return this._apercu(l()[i].id);
      });
    });
    root.querySelectorAll(".puce[data-ecran], .puce[data-public], .puce[data-personne]").forEach((el) => {
      el.addEventListener("click", () => {
        const t = l()[Number(el.dataset.i)];
        const champ = el.dataset.ecran ? "ecrans" : el.dataset.public ? "publics" : "personnes";
        const v = el.dataset.ecran || el.dataset.public || el.dataset.personne;
        const idx = t[champ].indexOf(v);
        if (idx >= 0) { if (champ === "personnes" || t[champ].length > 1) t[champ].splice(idx, 1); } else t[champ].push(v);
        this._toucher();
      });
    });
    root.querySelectorAll("input[data-champ], select[data-champ]").forEach((el) => {
      const ev = el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input";
      el.addEventListener(ev, () => {
        const t = l()[Number(el.dataset.i)];
        if (el.dataset.champ === "actif") t.actif = el.checked;
        else if (el.dataset.k !== undefined) t.cases[Number(el.dataset.k)][el.dataset.champ] = el.value;
        else t[el.dataset.champ] = el.value;
        this._modifie = true;
        // Pas de re-rendu pendant la frappe : seul le bouton Enregistrer change.
        const b = root.querySelector('[data-action="enregistrer"]'); if (b) b.disabled = false;
        if (el.type === "checkbox") this._rendre();
      });
    });
  }
}

customElements.define("vision-veille-card", VisionVeilleCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "vision-veille-card", name: "Vision : écran de veille", description: "Les tableaux que la télé fait défiler, à composer depuis les entités." });
