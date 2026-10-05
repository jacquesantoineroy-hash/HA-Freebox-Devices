/* comvision-planning-card — grille semaine des plages ComVision (pc_parental).
   Lit sensor.<pc>_plages (ComVision >= 1.44.0) et pilote les services
   add_schedule / update_schedule / remove_schedule.
   Un bloc plein verrouille la session ; un bloc rayé ferme des étiquettes.
   Créer : glisser sur une colonne (souris) ou bouton +.
   Modifier : glisser une plage (déplacer), tirer ses bords (redimensionner),
   cliquer (éditeur : nom, jours, horaires, portée, étiquettes, couleur). */
(() => {
  "use strict";

  const PALETTE = [
    "#e5405e", "#3b82f6", "#f59e0b", "#10b981", "#8b5cf6",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#64748b",
  ];
  const JOURS_COURTS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
  const JOURS_SVC = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"];
  const SNAP = 900; // 15 minutes
  const H_HEURE = 26; // pixels par heure
  const H_TOTAL = 24 * H_HEURE;
  const JOUR_S = 86400;

  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const snap = (s) => Math.round(s / SNAP) * SNAP;
  const s2y = (s) => (s / 3600) * H_HEURE;

  function hLisible(s) {
    s = ((s % JOUR_S) + JOUR_S) % JOUR_S;
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    return h + "h" + m;
  }
  function hService(s) {
    s = ((s % JOUR_S) + JOUR_S) % JOUR_S;
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    return h + ":" + m + ":00";
  }
  function hDepuisInput(v) {
    if (!v) return null;
    const [h, m] = v.split(":").map((x) => parseInt(x, 10));
    if (isNaN(h) || isNaN(m)) return null;
    return h * 3600 + m * 60;
  }
  function hVersInput(s) {
    s = ((s % JOUR_S) + JOUR_S) % JOUR_S;
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    return h + ":" + m;
  }
  const echap = (t) =>
    String(t == null ? "" : t)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  function cibles(p) {
    const noms = (p.etiquettes || []).concat(
      (p.elements || []).map((e) => e.nom)
    );
    return noms.join(", ");
  }

  function couleurDefaut(id) {
    return PALETTE[Math.abs(parseInt(id, 10) || 0) % PALETTE.length];
  }

  class ComVisionPlanningCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._sel = null;   // plage en cours d'édition (copie de travail)
      this._drag = null;  // glissement en cours
      this._rendered = false;
      this._cat = null;      // catalogue sites + logiciels
      this._filtreEl = "";   // filtre du selecteur d'elements
    }

    async _catalogue() {
      // Les noms des sites et des logiciels ne voyagent pas dans les
      // attributs du capteur : plusieurs centaines de lignes recopiees a
      // chaque changement, ecrites en base pour rien. On les demande.
      if (this._cat || !this._hass) return this._cat;
      try {
        const r = await this._hass.callApi("GET", "pc_parental/catalogue");
        this._cat = (r && r.elements) || [];
      } catch (e) {
        this._cat = [];
      }
      return this._cat;
    }

    setConfig(config) {
      if (!config || !config.entity) {
        throw new Error("Indique l'entité : sensor.<pc>_plages");
      }
      this._config = config;
      this._rendered = false;
    }

    getCardSize() {
      return 14;
    }

    static getStubConfig(hass) {
      const e = Object.keys(hass.states).find(
        (k) => k.startsWith("sensor.") && k.endsWith("_plages")
      );
      return { entity: e || "sensor.pc_jules_plages" };
    }

    set hass(hass) {
      const ancien = this._etat;
      this._hass = hass;
      const etat = hass.states[(this._config || {}).entity];
      this._etat = etat;
      if (!etat) {
        this._renderErreur();
        return;
      }
      if (this._drag || this._sel) return; // ne pas casser un geste en cours
      if (!this._rendered || ancien !== etat) this._render();
    }

    _plages() {
      const attrs = (this._etat || {}).attributes || {};
      return (attrs.plages || []).map((p) => ({
        id: p.id,
        nom: p.nom || "",
        debut: ((p.debut % JOUR_S) + JOUR_S) % JOUR_S,
        fin: ((p.fin % JOUR_S) + JOUR_S) % JOUR_S,
        jours: (() => {
          const j = (p.jours || []).slice(0, 7).map(Boolean);
          while (j.length < 7) j.push(false);
          return j;
        })(),
        active: !!p.active,
        portee: p.portee === "etiquettes" ? "etiquettes" : "session",
        etiquettes: (p.etiquettes || []).slice(),
        elements: (p.elements || []).map((e) => ({
          genre: e.genre,
          nom: e.nom,
        })),
        couleur: p.couleur || null,
        libelle: p.libelle || "",
      }));
    }

    _pc() {
      return ((this._etat || {}).attributes || {}).pc || "";
    }

    // Les appareils de la personne : le planning est le sien, une plage peut en épargner certains.
    _appareils() {
      return ((this._etat || {}).attributes || {}).appareils || [];
    }

    _vocabulaire() {
      return ((this._etat || {}).attributes || {}).vocabulaire || [];
    }

    /* ---------------- segments (une plage = 1 ou 2 blocs par jour) -------- */

    _segments(surcharge) {
      const segs = [];
      for (const p0 of this._plages()) {
        const p =
          surcharge && surcharge.id === p0.id
            ? Object.assign({}, p0, {
                debut: surcharge.debut,
                fin: surcharge.fin,
              })
            : p0;
        const couleur = p.couleur || couleurDefaut(p.id);
        const nuit = p.fin <= p.debut; // enjambe minuit (appartient au jour de début)
        for (let d = 0; d < 7; d++) {
          if (!p.jours[d]) continue;
          if (!nuit) {
            segs.push({ p, jour: d, de: p.debut, a: p.fin, bordHaut: true, bordBas: true, couleur });
          } else {
            segs.push({ p, jour: d, de: p.debut, a: JOUR_S, bordHaut: true, bordBas: p.fin === 0, couleur });
            if (p.fin > 0) {
              segs.push({ p, jour: (d + 1) % 7, de: 0, a: p.fin, bordHaut: false, bordBas: true, couleur });
            }
          }
        }
      }
      return segs;
    }

    /* Répartit les segments qui se chevauchent en colonnes parallèles. */
    _voies(segs) {
      const parJour = new Map();
      for (const s of segs) {
        if (!parJour.has(s.jour)) parJour.set(s.jour, []);
        parJour.get(s.jour).push(s);
      }
      for (const liste of parJour.values()) {
        liste.sort((a, b) => a.de - b.de || b.a - a.a);
        const fins = []; // fin de la derniere plage de chaque voie
        let grappe = [];
        let finGrappe = -1;
        const clore = () => {
          const n = fins.length;
          for (const s of grappe) s.nVoies = n;
          grappe = [];
          fins.length = 0;
        };
        for (const s of liste) {
          if (s.de >= finGrappe && grappe.length) clore();
          let v = fins.findIndex((f) => f <= s.de);
          if (v === -1) {
            v = fins.length;
            fins.push(s.a);
          } else {
            fins[v] = s.a;
          }
          s.voie = v;
          grappe.push(s);
          finGrappe = Math.max(finGrappe, s.a);
        }
        if (grappe.length) clore();
      }
      return segs;
    }

    /* ------------------------------ rendu --------------------------------- */

    _renderErreur() {
      this.shadowRoot.innerHTML =
        '<ha-card><div style="padding:16px;">Entité introuvable : ' +
        ((this._config || {}).entity || "?") +
        "</div></ha-card>";
      this._rendered = false;
    }

    _style() {
      return `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; position: relative; }
        .entete { display: flex; align-items: center; gap: 8px; padding: 12px 16px 4px; }
        .titre { font-size: 1.15em; font-weight: 500; flex: 1; }
        .btn-plus {
          border: none; border-radius: 8px; cursor: pointer;
          background: var(--primary-color); color: var(--text-primary-color, #fff);
          font-size: 14px; padding: 6px 12px; font-weight: 500;
        }
        .aide { padding: 0 16px 8px; font-size: 11px; color: var(--secondary-text-color); }
        .grille-conteneur { padding: 0 12px 12px; }
        .jours-entete { display: flex; margin-left: 34px; }
        .jours-entete div {
          flex: 1; text-align: center; font-size: 12px; font-weight: 500;
          color: var(--secondary-text-color); padding: 4px 0;
        }
        .jours-entete div.vac { color: var(--primary-color); }
        .corps { display: flex; }
        .heures { width: 34px; position: relative; height: ${H_TOTAL}px; flex: none; }
        .heures div {
          position: absolute; right: 6px; transform: translateY(-50%);
          font-size: 10px; color: var(--secondary-text-color);
        }
        .cols {
          flex: 1; display: flex; position: relative; height: ${H_TOTAL}px;
          border-top: 1px solid var(--divider-color);
          background:
            repeating-linear-gradient(
              to bottom,
              transparent 0, transparent ${H_HEURE - 1}px,
              var(--divider-color) ${H_HEURE - 1}px, var(--divider-color) ${H_HEURE}px
            );
        }
        .col { flex: 1; position: relative; border-right: 1px solid var(--divider-color); }
        .col:first-child { border-left: 1px solid var(--divider-color); }
        .col.vac { background: rgba(120, 120, 200, 0.06); }
        .seg {
          position: absolute; left: 2%; width: 96%; border-radius: 6px;
          box-sizing: border-box; overflow: hidden; cursor: grab;
          color: #fff; font-size: 10px; line-height: 1.25;
          padding: 3px 4px; user-select: none; -webkit-user-select: none;
          touch-action: none;
        }
        .seg.inactive { opacity: 0.35; border: 1px dashed rgba(255,255,255,0.9); }
        .seg.etiq {
          background-image: repeating-linear-gradient(
            135deg, rgba(255,255,255,0.30) 0 5px, transparent 5px 11px);
        }
        .suggestion { font-size: 10px; color: var(--secondary-text-color); margin-top: 4px; }
        .seg .nom { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .seg .h { opacity: 0.9; white-space: nowrap; }
        .seg.sans-haut { border-top-left-radius: 0; border-top-right-radius: 0; }
        .seg.sans-bas { border-bottom-left-radius: 0; border-bottom-right-radius: 0; }
        .poignee { position: absolute; left: 0; right: 0; height: 7px; cursor: ns-resize; }
        .poignee.haut { top: 0; }
        .poignee.bas { bottom: 0; }
        .maintenant {
          position: absolute; left: 0; right: 0; height: 0;
          border-top: 2px solid var(--error-color, #e5405e); z-index: 5; pointer-events: none;
        }
        .fantome {
          position: absolute; left: 2%; width: 96%; border-radius: 6px;
          background: var(--primary-color); opacity: 0.45; pointer-events: none; z-index: 6;
        }
        .voile {
          position: absolute; inset: 0; background: rgba(0,0,0,0.45);
          display: flex; align-items: center; justify-content: center; z-index: 10;
        }
        .editeur {
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
          border-radius: 12px; padding: 16px; width: min(340px, 92%);
          box-shadow: 0 8px 32px rgba(0,0,0,0.35);
          max-height: 92%; overflow-y: auto; box-sizing: border-box;
        }
        .editeur h3 { margin: 0 0 12px; font-size: 1.05em; }
        .champ { margin-bottom: 12px; }
        .champ label { display: block; font-size: 11px; color: var(--secondary-text-color); margin-bottom: 4px; }
        .champ input[type="text"] {
          width: 100%; box-sizing: border-box; padding: 8px;
          border: 1px solid var(--divider-color); border-radius: 8px;
          background: var(--card-background-color); color: var(--primary-text-color);
          font-size: 14px;
        }
        .lignes-h { display: flex; gap: 10px; }
        .lignes-h .champ { flex: 1; }
        .champ input[type="time"] {
          width: 100%; box-sizing: border-box; padding: 7px;
          border: 1px solid var(--divider-color); border-radius: 8px;
          background: var(--card-background-color); color: var(--primary-text-color);
          font-size: 14px;
        }
        .chips { display: flex; flex-wrap: wrap; gap: 6px; }
        .chip {
          border: 1px solid var(--divider-color); border-radius: 14px;
          padding: 5px 10px; font-size: 12px; cursor: pointer;
          background: none; color: var(--primary-text-color);
        }
        .chip.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
        .nuancier { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
        .nuance {
          width: 26px; height: 26px; border-radius: 50%; cursor: pointer;
          border: 2px solid transparent; box-sizing: border-box; padding: 0;
        }
        .nuance.on { border-color: var(--primary-text-color); box-shadow: 0 0 0 2px var(--card-background-color) inset; }
        .nuance.auto {
          background: conic-gradient(#e5405e, #f59e0b, #10b981, #3b82f6, #8b5cf6, #e5405e);
          position: relative;
        }
        input[type="color"].nuance { border: 2px solid var(--divider-color); }
        .interrupteur { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
        .boutons { display: flex; gap: 8px; margin-top: 14px; }
        .boutons button {
          border: none; border-radius: 8px; padding: 9px 14px; font-size: 13px;
          cursor: pointer; font-weight: 500;
        }
        .b-ok { background: var(--primary-color); color: var(--text-primary-color, #fff); flex: 1; }
        .b-suppr { background: var(--error-color, #b3261e); color: #fff; }
        .b-annul { background: none; color: var(--primary-text-color); border: 1px solid var(--divider-color) !important; }
        .toast {
          position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);
          background: var(--error-color, #b3261e); color: #fff; padding: 8px 14px;
          border-radius: 8px; font-size: 12px; z-index: 20; max-width: 90%;
        }
      </style>`;
    }

    _render() {
      const titre =
        (this._config || {}).title ||
        "Planning — " + (this._pc() || "?");
      let heures = "";
      for (let h = 2; h < 24; h += 2) {
        heures += `<div style="top:${s2y(h * 3600)}px">${String(h).padStart(2, "0")}h</div>`;
      }
      let entetes = "";
      let cols = "";
      for (let d = 0; d < 7; d++) {
        entetes += `<div>${JOURS_COURTS[d]}</div>`;
        cols += `<div class="col" data-jour="${d}"></div>`;
      }
      this.shadowRoot.innerHTML = `
        ${this._style()}
        <ha-card>
          <div class="entete">
            <div class="titre">${titre}</div>
            <button class="btn-plus" id="plus">+ Plage</button>
          </div>
          <div class="aide">Bloc plein = session verrouillée, bloc rayé = étiquettes fermées.
            Glisser sur une colonne pour créer, déplacer/étirer un bloc pour le modifier,
            cliquer pour tout régler.</div>
          <div class="grille-conteneur">
            <div class="jours-entete">${entetes}</div>
            <div class="corps">
              <div class="heures">${heures}</div>
              <div class="cols" id="cols">${cols}</div>
            </div>
          </div>
          <div id="zone-editeur"></div>
          <div id="zone-toast"></div>
        </ha-card>`;
      this._rendered = true;
      this._renderSegs();
      this._ligneMaintenant();
      const cols_el = this.shadowRoot.getElementById("cols");
      cols_el.addEventListener("pointerdown", (ev) => this._pointerDown(ev));
      this.shadowRoot.getElementById("plus").addEventListener("click", () => {
        this._ouvrirEditeur({
          id: null,
          nom: "Nouvelle plage",
          debut: 17 * 3600,
          fin: 19 * 3600,
          jours: [true, true, true, true, true, true, true],
          active: true,
          portee: "session",
          etiquettes: [],
          elements: [],
          sauf: [],
          couleur: null,
        });
      });
    }

    _renderSegs(surcharge) {
      const cols = this.shadowRoot.getElementById("cols");
      if (!cols) return;
      cols.querySelectorAll(".seg").forEach((n) => n.remove());
      const segs = this._voies(this._segments(surcharge));
      for (const s of segs) {
        const col = cols.querySelector(`.col[data-jour="${s.jour}"]`);
        if (!col) continue;
        const el = document.createElement("div");
        el.className =
          "seg" +
          (s.p.active ? "" : " inactive") +
          (s.p.portee === "etiquettes" ? " etiq" : "") +
          (s.bordHaut ? "" : " sans-haut") +
          (s.bordBas ? "" : " sans-bas");
        const nV = s.nVoies || 1;
        const largeur = 96 / nV;
        el.style.left = 2 + largeur * (s.voie || 0) + "%";
        el.style.width = largeur + "%";
        el.style.top = s2y(s.de) + "px";
        el.style.height = Math.max(6, s2y(s.a - s.de) - 2) + "px";
        el.style.background = s.couleur;
        el.dataset.id = s.p.id;
        el.dataset.bordHaut = s.bordHaut ? "1" : "0";
        el.dataset.bordBas = s.bordBas ? "1" : "0";
        const haut = s.a - s.de >= 5400;
        const sousTitre =
          s.p.portee === "etiquettes"
            ? `<div class="h">${echap(cibles(s.p))}</div>`
            : "";
        el.innerHTML =
          `<div class="nom">${echap(s.p.nom) || "&nbsp;"}</div>` +
          (haut ? sousTitre : "") +
          (haut ? `<div class="h">${hLisible(s.p.debut)}→${hLisible(s.p.fin)}</div>` : "") +
          (s.bordHaut ? '<div class="poignee haut"></div>' : "") +
          (s.bordBas ? '<div class="poignee bas"></div>' : "");
        col.appendChild(el);
      }
    }

    _ligneMaintenant() {
      const cols = this.shadowRoot.getElementById("cols");
      if (!cols) return;
      const now = new Date();
      const jour = (now.getDay() + 6) % 7; // lundi = 0
      const s = now.getHours() * 3600 + now.getMinutes() * 60;
      const col = cols.querySelector(`.col[data-jour="${jour}"]`);
      if (!col) return;
      const l = document.createElement("div");
      l.className = "maintenant";
      l.style.top = s2y(s) + "px";
      col.appendChild(l);
    }

    _toast(msg) {
      const zone = this.shadowRoot.getElementById("zone-toast");
      if (!zone) return;
      zone.innerHTML = `<div class="toast">${msg}</div>`;
      clearTimeout(this._toastT);
      this._toastT = setTimeout(() => (zone.innerHTML = ""), 5000);
    }

    /* --------------------------- interactions ----------------------------- */

    _pointerDown(ev) {
      if (this._sel) return;
      const seg = ev.target.closest(".seg");
      const col = ev.target.closest(".col");
      if (!seg && !col) return;
      ev.preventDefault();
      const cols = this.shadowRoot.getElementById("cols");
      const rect = cols.getBoundingClientRect();
      const ySec = (ev.clientY - rect.top) / H_HEURE * 3600;

      if (seg) {
        const id = parseInt(seg.dataset.id, 10);
        const p = this._plages().find((x) => x.id === id);
        if (!p) return;
        const r = seg.getBoundingClientRect();
        let zone = "deplacer";
        if (ev.target.classList.contains("poignee")) {
          zone = ev.target.classList.contains("haut") ? "debut" : "fin";
        } else if (ev.clientY - r.top < 8 && seg.dataset.bordHaut === "1") {
          zone = "debut";
        } else if (r.bottom - ev.clientY < 8 && seg.dataset.bordBas === "1") {
          zone = "fin";
        }
        this._drag = {
          type: zone, p, ySec, bouge: false,
          debut: p.debut, fin: p.fin,
        };
      } else {
        if (ev.pointerType !== "mouse") return; // au doigt : bouton + Plage
        const jour = parseInt(col.dataset.jour, 10);
        this._drag = {
          type: "creer", jour, ySec, bouge: false,
          de: clamp(snap(ySec), 0, JOUR_S - SNAP), a: null, col,
        };
      }
      this._surMove = (e) => this._pointerMove(e, rect);
      this._surUp = (e) => this._pointerUp(e);
      window.addEventListener("pointermove", this._surMove);
      window.addEventListener("pointerup", this._surUp, { once: true });
    }

    _pointerMove(ev, rect) {
      const d = this._drag;
      if (!d) return;
      const ySec = (ev.clientY - rect.top) / H_HEURE * 3600;
      const delta = ySec - d.ySec;
      if (Math.abs(delta) > 600) d.bouge = true; // ~ 10 minutes = seuil de clic
      if (!d.bouge) return;

      if (d.type === "creer") {
        const a = clamp(snap(ySec), 0, JOUR_S);
        d.a = a;
        let de = d.de;
        let fin = a;
        if (fin < de) [de, fin] = [fin, de];
        if (fin - de < SNAP) fin = de + SNAP;
        let f = d.col.querySelector(".fantome");
        if (!f) {
          f = document.createElement("div");
          f.className = "fantome";
          d.col.appendChild(f);
        }
        f.style.top = s2y(de) + "px";
        f.style.height = s2y(fin - de) + "px";
        d.resultat = { de, fin };
        return;
      }

      const p = d.p;
      const nuit = d.fin <= d.debut;
      let debut = d.debut;
      let fin = d.fin;
      if (d.type === "deplacer") {
        let dd = snap(delta);
        if (!nuit) dd = clamp(dd, -d.debut, JOUR_S - d.fin);
        debut = (d.debut + dd + JOUR_S) % JOUR_S;
        fin = (d.fin + dd + JOUR_S) % JOUR_S;
      } else if (d.type === "debut") {
        debut = snap(d.debut + delta);
        debut = nuit
          ? clamp(debut, d.fin + SNAP, JOUR_S - SNAP)
          : clamp(debut, 0, d.fin - SNAP);
      } else if (d.type === "fin") {
        fin = snap(d.fin + delta);
        fin = nuit
          ? clamp(fin, SNAP, d.debut - SNAP)
          : clamp(fin, d.debut + SNAP, JOUR_S);
      }
      d.apercu = { id: p.id, debut, fin: fin === JOUR_S ? 0 : fin };
      if (fin === JOUR_S && debut === 0) d.apercu.fin = JOUR_S - SNAP; // garde-fou
      if (!d._rafPrevu) {
        d._rafPrevu = true;
        requestAnimationFrame(() => {
          d._rafPrevu = false;
          if (this._drag === d && d.apercu) this._renderSegs(d.apercu);
        });
      }
    }

    _pointerUp() {
      const d = this._drag;
      window.removeEventListener("pointermove", this._surMove);
      this._drag = null;
      if (!d) return;

      if (d.type === "creer") {
        const f = d.col && d.col.querySelector(".fantome");
        if (f) f.remove();
        if (!d.bouge || !d.resultat) return;
        const jours = [false, false, false, false, false, false, false];
        jours[d.jour] = true;
        this._ouvrirEditeur({
          id: null,
          nom: "Nouvelle plage",
          debut: d.resultat.de,
          fin: d.resultat.fin === JOUR_S ? 0 : d.resultat.fin,
          jours,
          active: true,
          portee: "session",
          etiquettes: [],
          elements: [],
          couleur: null,
        });
        return;
      }

      if (!d.bouge) {
        this._ouvrirEditeur(
          Object.assign({}, d.p, {
            jours: d.p.jours.slice(),
            etiquettes: (d.p.etiquettes || []).slice(),
            sauf: (d.p.sauf || []).slice(),
            elements: (d.p.elements || []).map((e) => ({
              genre: e.genre,
              nom: e.nom,
            })),
          })
        );
        return;
      }
      if (!d.apercu) return;
      this._svc("update_schedule", {
        pc: this._pc(),
        id: d.p.id,
        debut: hService(d.apercu.debut),
        fin: hService(d.apercu.fin),
      });
    }

    async _svc(nom, data) {
      try {
        await this._hass.callService("pc_parental", nom, data);
      } catch (e) {
        this._toast((e && e.message) || "Erreur du service " + nom);
        this._render();
      }
    }

    /* ------------------------------ éditeur -------------------------------- */

    _ouvrirEditeur(p) {
      this._sel = p;
      const zone = this.shadowRoot.getElementById("zone-editeur");
      const neuf = p.id === null;
      const couleurCourante = p.couleur || (neuf ? PALETTE[0] : couleurDefaut(p.id));
      let nuancier = `<button class="nuance auto ${p.couleur ? "" : "on"}" data-c="" title="Couleur automatique"></button>`;
      for (const c of PALETTE) {
        nuancier += `<button class="nuance ${p.couleur === c ? "on" : ""}" data-c="${c}" style="background:${c}"></button>`;
      }
      nuancier += `<input type="color" class="nuance" id="ed-cpick" value="${couleurCourante}" title="Autre couleur">`;
      let chips = "";
      for (let d = 0; d < 7; d++) {
        chips += `<button class="chip ${p.jours[d] ? "on" : ""}" data-j="${d}">${JOURS_COURTS[d]}</button>`;
      }
      const vocab = this._vocabulaire();
      zone.innerHTML = `
        <div class="voile" id="ed-voile">
          <div class="editeur">
            <h3>${neuf ? "Nouvelle plage" : "Modifier la plage"}</h3>
            <div class="champ"><label>Nom</label>
              <input type="text" id="ed-nom" value="${echap(p.nom)}" maxlength="40"></div>
            <div class="lignes-h">
              <div class="champ"><label>Début</label><input type="time" id="ed-debut" step="900" value="${hVersInput(p.debut)}"></div>
              <div class="champ"><label>Fin</label><input type="time" id="ed-fin" step="900" value="${hVersInput(p.fin)}"></div>
            </div>
            <div class="champ"><label>Jours</label><div class="chips" id="ed-jours">${chips}</div></div>
            <div class="champ"><label>Cette plage ferme</label><div class="chips" id="ed-portee">
              <button class="chip ${p.portee !== "etiquettes" ? "on" : ""}" data-p="session">La session (PC verrouillé)</button>
              <button class="chip ${p.portee === "etiquettes" ? "on" : ""}" data-p="etiquettes">Des étiquettes</button>
            </div></div>
            <div class="champ" id="ed-zone-etiq" ${p.portee === "etiquettes" ? "" : "hidden"}>
              <label>Étiquettes à fermer</label>
              <div class="chips" id="ed-etiq">${this._chipsEtiq()}</div>
              ${vocab.length ? "" : '<div class="suggestion">Aucune étiquette pour l\'instant — crée-la dans l\'onglet Étiquettes, ou choisis un site ci-dessous.</div>'}
              <label style="margin-top:10px">…ou viser un site / un logiciel précis</label>
              <div class="chips" id="ed-els">${this._chipsEls()}</div>
              <div class="lignes-h">
                <input type="search" id="ed-el-filtre" placeholder="Filtrer la liste…">
                <select id="ed-el-choix"></select>
                <button class="chip" id="ed-el-ajout" type="button">Ajouter</button>
              </div>
              <div class="suggestion">Une plage qui nomme un site l'emporte sur « autorisé » : c'est ce qu'on peut dire de plus précis sur lui.</div>
            </div>
            ${this._appareils().length > 1 ? `<div class="champ"><label>Sauf sur</label>
              <div class="chips" id="ed-sauf">${this._appareils().map((a) => `<button class="chip ${(p.sauf || []).includes(a.id) ? "on" : ""}" data-a="${echap(a.id)}" type="button">${echap(a.nom)}</button>`).join("")}</div>
              <div class="suggestion">Le planning vaut pour tous les appareils de la personne. Coche ceux que cette plage épargne.</div></div>` : ""}
            <div class="champ"><label>Couleur</label><div class="nuancier" id="ed-couleurs">${nuancier}</div></div>
            <div class="champ"><label class="interrupteur">
              <input type="checkbox" id="ed-active" ${p.active ? "checked" : ""}> Plage active</label></div>
            <div class="boutons">
              <button class="b-ok" id="ed-ok">Enregistrer</button>
              ${neuf ? "" : '<button class="b-suppr" id="ed-suppr">Supprimer</button>'}
              <button class="b-annul" id="ed-annul">Annuler</button>
            </div>
          </div>
        </div>`;

      const $ = (id) => zone.querySelector("#" + id);
      zone.querySelector("#ed-voile").addEventListener("pointerdown", (e) => {
        if (e.target.id === "ed-voile") this._fermerEditeur();
      });
      $("ed-annul").addEventListener("click", () => this._fermerEditeur());
      $("ed-jours").addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        const j = parseInt(chip.dataset.j, 10);
        this._sel.jours[j] = !this._sel.jours[j];
        chip.classList.toggle("on", this._sel.jours[j]);
      });
      $("ed-portee").addEventListener("click", (e) => {
        const b = e.target.closest(".chip");
        if (!b) return;
        this._sel.portee = b.dataset.p;
        zone
          .querySelectorAll("#ed-portee .chip")
          .forEach((c) => c.classList.toggle("on", c === b));
        zone.querySelector("#ed-zone-etiq").hidden =
          this._sel.portee !== "etiquettes";
      });
      $("ed-couleurs").addEventListener("click", (e) => {
        const b = e.target.closest("button.nuance");
        if (!b) return;
        this._sel.couleur = b.dataset.c || null;
        zone.querySelectorAll(".nuance").forEach((n) => n.classList.remove("on"));
        b.classList.add("on");
      });
      $("ed-cpick").addEventListener("input", (e) => {
        this._sel.couleur = e.target.value;
        zone.querySelectorAll(".nuance").forEach((n) => n.classList.remove("on"));
        e.target.classList.add("on");
      });
      const zSauf = zone.querySelector("#ed-sauf");
      if (zSauf) {
        zSauf.addEventListener("click", (e) => {
          const b = e.target.closest(".chip");
          if (!b) return;
          const sauf = this._sel.sauf || (this._sel.sauf = []);
          const i = sauf.indexOf(b.dataset.a);
          if (i >= 0) sauf.splice(i, 1);
          else sauf.push(b.dataset.a);
          b.classList.toggle("on", i < 0);
        });
      }
      const zEtiq = zone.querySelector("#ed-etiq");
      if (zEtiq) {
        zEtiq.addEventListener("click", (e) => {
          const b = e.target.closest(".chip");
          if (!b) return;
          const nom = b.dataset.e;
          const prises = this._sel.etiquettes || (this._sel.etiquettes = []);
          const i = prises.findIndex(
            (x) => x.toLowerCase() === nom.toLowerCase()
          );
          if (i >= 0) prises.splice(i, 1);
          else prises.push(nom);
          b.classList.toggle("on", i < 0);
        });
      }
      const zEls = zone.querySelector("#ed-els");
      if (zEls) {
        zEls.addEventListener("click", (e) => {
          const b = e.target.closest(".chip");
          if (!b || b.dataset.el === undefined) return;
          this._sel.elements.splice(parseInt(b.dataset.el, 10), 1);
          this._majEls();
        });
      }
      const filtre = zone.querySelector("#ed-el-filtre");
      if (filtre) {
        filtre.addEventListener("input", () => {
          this._filtreEl = filtre.value;
          const choix = zone.querySelector("#ed-el-choix");
          if (choix) choix.innerHTML = this._optionsEls();
        });
      }
      const ajout = zone.querySelector("#ed-el-ajout");
      if (ajout) {
        ajout.addEventListener("click", () => {
          const choix = zone.querySelector("#ed-el-choix");
          const v = choix ? choix.value : "";
          const i = v.indexOf("|");
          if (i < 0) return;
          this._sel.elements = this._sel.elements || [];
          this._sel.elements.push({
            genre: v.slice(0, i),
            nom: v.slice(i + 1),
          });
          this._majEls();
        });
      }
      // Le catalogue arrive apres coup : la liste se remplit toute seule.
      this._catalogue().then(() => this._majEls());

      $("ed-ok").addEventListener("click", () => this._enregistrer());
      if (!neuf) {
        $("ed-suppr").addEventListener("click", () => {
          this._svc("remove_schedule", { pc: this._pc(), id: this._sel.id });
          this._fermerEditeur();
        });
      }
    }


    /* --- choisir plutot que taper : pastilles et liste deroulante ------- */

    _chipsEtiq() {
      const prises = (this._sel.etiquettes || []).map((e) => e.toLowerCase());
      return this._vocabulaire()
        .map(
          (nom) =>
            `<button class="chip ${
              prises.includes(nom.toLowerCase()) ? "on" : ""
            }" data-e="${echap(nom)}" type="button">${echap(nom)}</button>`
        )
        .join("");
    }

    _chipsEls() {
      const els = this._sel.elements || [];
      if (!els.length) {
        return '<span class="suggestion">Aucun nom visé.</span>';
      }
      return els
        .map(
          (e, i) =>
            `<button class="chip on" data-el="${i}" type="button" ` +
            `title="Retirer">${echap(e.nom)} ×</button>`
        )
        .join("");
    }

    _optionsEls() {
      const cat = this._cat || [];
      const q = (this._filtreEl || "").trim().toLowerCase();
      const deja = new Set(
        (this._sel.elements || []).map((e) => e.genre + "|" + e.nom.toLowerCase())
      );
      const groupe = (genre, titre) => {
        const lignes = cat
          .filter((e) => e.genre === genre)
          .filter((e) => !deja.has(e.genre + "|" + e.nom.toLowerCase()))
          .filter((e) => !q || e.nom.toLowerCase().includes(q))
          .slice(0, 300)
          .map(
            (e) =>
              `<option value="${echap(e.genre + "|" + e.nom)}">${echap(
                e.nom
              )}</option>`
          )
          .join("");
        return lignes ? `<optgroup label="${titre}">${lignes}</optgroup>` : "";
      };
      const corps = groupe("sites", "Sites") + groupe("apps", "Logiciels");
      return corps || '<option value="">— rien à proposer —</option>';
    }

    _majEls() {
      const zone = this.shadowRoot.getElementById("zone-editeur");
      if (!zone || !this._sel) return;
      const choix = zone.querySelector("#ed-el-choix");
      const chips = zone.querySelector("#ed-els");
      if (choix) choix.innerHTML = this._optionsEls();
      if (chips) chips.innerHTML = this._chipsEls();
    }

    _fermerEditeur() {
      this._sel = null;
      const zone = this.shadowRoot.getElementById("zone-editeur");
      if (zone) zone.innerHTML = "";
      this._render();
    }

    _enregistrer() {
      const zone = this.shadowRoot.getElementById("zone-editeur");
      const $ = (id) => zone.querySelector("#" + id);
      const p = this._sel;
      const nom = ($("ed-nom").value || "").trim() || "Plage";
      const debut = hDepuisInput($("ed-debut").value);
      const fin = hDepuisInput($("ed-fin").value);
      if (debut === null || fin === null) {
        this._toast("Heures incomplètes.");
        return;
      }
      if (debut === fin) {
        this._toast("Le début et la fin doivent être différents.");
        return;
      }
      if (!p.jours.some(Boolean)) {
        this._toast("Coche au moins un jour.");
        return;
      }
      const jours = JOURS_SVC.filter((_, i) => p.jours[i]);
      const portee = p.portee === "etiquettes" ? "etiquettes" : "session";
      const etiquettes = (p.etiquettes || []).slice();
      const elements = (p.elements || []).map((e) => ({
        genre: e.genre,
        nom: e.nom,
      }));
      if (portee === "etiquettes" && !etiquettes.length && !elements.length) {
        this._toast("Choisis une étiquette, ou un site à fermer.");
        return;
      }
      const donnees = {
        pc: this._pc(),
        nom,
        debut: hService(debut),
        fin: hService(fin),
        jours,
        active: $("ed-active").checked,
        portee,
        etiquettes: portee === "etiquettes" ? etiquettes : [],
        elements: portee === "etiquettes" ? elements : [],
        sauf: (p.sauf || []).slice(),
      };
      if (p.id === null) {
        if (p.couleur) donnees.couleur = p.couleur;
        this._svc("add_schedule", donnees);
      } else {
        donnees.id = p.id;
        donnees.couleur = p.couleur || "";
        this._svc("update_schedule", donnees);
      }
      this._fermerEditeur();
    }
  }

  customElements.define("comvision-planning-card", ComVisionPlanningCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "comvision-planning-card",
    name: "Planning ComVision (plages des PC)",
    description:
      "Grille semaine des plages d'un PC ComVision : session ou étiquettes, "
      + "création au glisser, déplacement, redimensionnement, couleurs.",
  });
})();
