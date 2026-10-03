/*
 * Vision — carte « Maison » et carte « Personne »
 *
 * mode: maison    une ligne par personne : ce que font ses appareils en ce
 *                 moment ; un clic ouvre la page de la personne.
 * mode: personne  les appareils d'une personne (accès, temps) et ses
 *                 catégories, en accordéon : on ouvre, on voit le contenu,
 *                 on coupe ou on rouvre. Une catégorie coupée par une règle
 *                 (maison, moyenne, planning) se montre cochée, avec la
 *                 raison, et ne se décoche pas ici.
 */
const API = "pc_parental/maison";
const RAFRAICHIR_MS = 30000;

const esc = (t) =>
  String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const duree = (min) => {
  const m = Math.max(0, Math.round(min || 0));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${String(r).padStart(2, "0")}` : `${h} h`;
};

const heure = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
};

const heureTs = (ts) => (ts ? heure(new Date(ts * 1000).toISOString()) : "");

const CODES = {
  securite: { libelle: "Sécurité", teinte: "var(--error-color, #c62828)" },
  maison: { libelle: "Maison", teinte: "var(--error-color, #c62828)" },
  moyenne: { libelle: "Moyenne", teinte: "var(--warning-color, #ef6c00)" },
  plage: { libelle: "Planning", teinte: "var(--info-color, #1565c0)" },
  age: { libelle: "Âge", teinte: "var(--primary-color)" },
  regle: { libelle: "Parents", teinte: "var(--primary-color)" },
};

class VisionMaisonCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._donnees = null;
    this._erreur = "";
    this._occupe = false;
    this._ouverts = new Set();
    this._details = new Set();
    this._minuteur = null;
  }

  setConfig(config) {
    this._config = Object.assign({ mode: "maison", chemin: "/vision-maison" }, config || {});
  }

  getCardSize() {
    return this._config && this._config.mode === "personne" ? 12 : 4;
  }

  connectedCallback() {
    if (!this._minuteur) this._minuteur = setInterval(() => this._charger(), RAFRAICHIR_MS);
  }

  disconnectedCallback() {
    if (this._minuteur) clearInterval(this._minuteur);
    this._minuteur = null;
  }

  set hass(hass) {
    const premier = !this._hass;
    this._hass = hass;
    if (premier) this._charger();
  }

  async _charger() {
    if (!this._hass) return;
    try {
      this._donnees = await this._hass.callApi("GET", API);
      this._erreur = "";
    } catch (e) {
      this._erreur = "Vision ne répond pas : " + (e.message || e);
    }
    this._rendre();
  }

  async _agir(corps) {
    if (this._occupe) return;
    this._occupe = true;
    this._rendre();
    try {
      this._donnees = await this._hass.callApi("POST", API, corps);
      this._erreur = "";
    } catch (e) {
      const b = e && e.body;
      this._erreur = (b && (b.retour || b.error)) || e.message || String(e);
    }
    this._occupe = false;
    this._rendre();
  }

  _naviguer(chemin) {
    history.pushState(null, "", chemin);
    window.dispatchEvent(new CustomEvent("location-changed", { bubbles: true, composed: true }));
  }

  // --- lecture ------------------------------------------------------------

  _personnes() {
    const d = this._donnees;
    if (!d) return [];
    const appareils = d.appareils || [];
    const liste = (d.personnes || []).map((p) => ({
      ...p,
      appareils: appareils.filter((a) => a.personne === p.entite),
    }));
    const orphelins = appareils.filter((a) => !a.personne);
    if (orphelins.length) liste.push({ entite: "", cle: "autres", prenom: "Sans personne", appareils: orphelins, orphelins: true });
    // Les parents en dernier : on ouvre la page pour les enfants.
    liste.sort((a, b) => {
      const pa = a.appareils.length && a.appareils.every((x) => x.parent);
      const pb = b.appareils.length && b.appareils.every((x) => x.parent);
      if (pa !== pb) return pa ? 1 : -1;
      if (!!a.orphelins !== !!b.orphelins) return a.orphelins ? 1 : -1;
      return a.prenom.localeCompare(b.prenom, "fr");
    });
    return liste;
  }

  _activite(a) {
    if (!a.en_ligne) return { texte: "hors ligne", classe: "off" };
    if (a.verrouille) return { texte: "verrouillé", classe: "lock" };
    if (a.inactif_s > 300) return { texte: `inactif depuis ${duree(a.inactif_s / 60)}`, classe: "idle" };
    const quoi = a.focus_libelle || a.focus;
    return { texte: quoi ? `sur ${quoi}` : "en ligne", classe: "on" };
  }

  _acces(a) {
    const d = a.derogation;
    if (!a.en_ligne) return "Agent injoignable : rien n'est appliqué.";
    if (d && d.mode) {
      const fin = d.fin ? ` jusqu'à ${heureTs(d.fin)}` : "";
      return d.mode === "open" ? `Ouvert par les parents${fin}.` : `Fermé par les parents${fin}.`;
    }
    const prochain = a.prochain ? heure(a.prochain) : "";
    if (a.verrouille) return `Fermé par le planning${prochain ? `, ouvre à ${prochain}` : ""}.`;
    return `Ouvert${prochain ? `, ferme à ${prochain}` : " toute la journée"}.`;
  }

  _categoriesDe(personne) {
    const d = this._donnees;
    if (!d) return [];
    const apps = personne.appareils;
    return (d.categories || [])
      .map((c) => {
        const etats = apps.map((a) => (a.etiquettes_etat || {})[c.nom]).filter(Boolean);
        const base = etats[0] || { choix: "neutre", coupe: false, code: "", raison: "", verrou: false };
        const coupe = etats.find((e) => e.coupe) || base;
        return {
          ...c,
          choix: base.choix,
          coupe: !!coupe.coupe,
          code: coupe.code,
          raison: coupe.raison,
          verrou: !!coupe.verrou,
          partiel: etats.length > 1 && etats.some((e) => e.coupe !== coupe.coupe),
        };
      })
      .filter((c) => c.apps.length || c.sites.length || c.coupe || c.choix !== "neutre");
  }

  // --- rendu : maison ----------------------------------------------------

  _avatar(p) {
    if (p.photo) return `<img class="avatar" src="${esc(p.photo)}" alt="">`;
    const lettre = (p.prenom || "?").trim().charAt(0).toUpperCase();
    return `<div class="avatar lettre ${p.orphelins ? "gris" : ""}">${esc(lettre)}</div>`;
  }

  _puce(a) {
    const act = this._activite(a);
    const icone = a.android ? "mdi:cellphone" : "mdi:desktop-classic";
    const temps = a.usage && a.usage.actif ? ` · ${duree(a.usage.actif)}` : "";
    return `
      <div class="puce ${act.classe}" title="${esc(a.nom)}">
        <ha-icon icon="${icone}"></ha-icon>
        <span class="point"></span>
        <span class="nom">${esc(a.nom)}</span>
        <span class="act">${esc(act.texte)}${esc(temps)}</span>
      </div>`;
  }

  _demande(d) {
    const quoi = d.libelle || d.cle || d.nom || "";
    const lien = d.lien ? `<a href="${esc(d.lien)}" target="_blank" rel="noopener">${esc(d.lien)}</a>` : "";
    const motif = d.motif ? `<span class="motif">« ${esc(d.motif)} »</span>` : "";
    const raison = d.raison ? `<span class="pourquoi">${esc(d.raison)}</span>` : "";
    const b = (dec, txt, min) =>
      `<button data-acces="${esc(d.id)}" data-pc="${esc(d.pc)}" data-dec="${dec}" ${min ? `data-min="${min}"` : ""} ${this._occupe ? "disabled" : ""}>${txt}</button>`;
    return `
      <div class="demande">
        <div class="corps">
          <b>${esc(d.prenom)}</b> demande <b>${esc(quoi)}</b>${d.genre === "temps" ? " de temps" : ""}
          ${lien} ${motif} ${raison}
        </div>
        <div class="actions">${b("temporaire", "1 h", 60)}${b("toujours", "Toujours")}${b("non", "Non")}</div>
      </div>`;
  }

  _rendreMaison() {
    const d = this._donnees;
    const personnes = this._personnes();
    const demandes = (d && d.demandes) || [];
    const lignes = personnes
      .map((p) => {
        const cible = `${this._config.chemin}/personne-${esc(p.cle)}`;
        const moy = p.moyenne && p.moyenne.active && !p.moyenne.ignore && p.moyenne.valeur != null
          ? `<span class="moy ${p.moyenne.valeur < p.moyenne.seuil ? "bas" : ""}">moyenne ${Number(p.moyenne.valeur).toLocaleString("fr-FR", { maximumFractionDigits: 1 })}</span>`
          : "";
        return `
          <div class="ligne" data-nav="${cible}" role="link" tabindex="0">
            ${this._avatar(p)}
            <div class="qui"><div class="prenom">${esc(p.prenom)}</div>${moy}</div>
            <div class="puces">${p.appareils.length ? p.appareils.map((a) => this._puce(a)).join("") : '<span class="vide">aucun appareil</span>'}</div>
            <ha-icon class="chevron" icon="mdi:chevron-right"></ha-icon>
          </div>`;
      })
      .join("");
    return `
      <ha-card>
        <div class="entete">
          <h2>${esc(this._config.titre || "La maison")}</h2>
          ${demandes.length ? `<span class="badge">${demandes.length} demande${demandes.length > 1 ? "s" : ""}</span>` : ""}
        </div>
        ${this._erreur ? `<div class="erreur">${esc(this._erreur)}</div>` : ""}
        ${demandes.length ? `<div class="demandes">${demandes.map((x) => this._demande(x)).join("")}</div>` : ""}
        ${d ? lignes || '<div class="vide">Aucun appareil inscrit.</div>' : '<div class="vide">Chargement…</div>'}
      </ha-card>`;
  }

  // --- rendu : personne --------------------------------------------------

  _appareil(a) {
    const act = this._activite(a);
    const icone = a.android ? "mdi:cellphone" : "mdi:desktop-classic";
    const b = (action, txt, min, classe = "") =>
      `<button class="${classe}" data-action="${action}" data-pc="${esc(a.id)}" ${min ? `data-min="${min}"` : ""} ${this._occupe || !a.en_ligne ? "disabled" : ""}>${txt}</button>`;
    const boutons = [];
    if (a.verrouille) {
      boutons.push(b("ouvrir", "Ouvrir 30 min", 30, "principal"), b("ouvrir", "Ouvrir 1 h", 60));
    } else {
      boutons.push(b("ouvrir", "+30 min", 30), b("ouvrir", "+1 h", 60), b("fermer", "Fermer", 0, "ferme"));
    }
    if (a.derogation && a.derogation.mode) boutons.push(b("annuler", "Revenir au planning"));
    const ouvert = this._details.has(a.id);
    const ferme = [...a.apps.map((x) => ({ ...x, genre: "apps" })), ...a.sites.map((x) => ({ ...x, genre: "sites" }))];
    const motif = (x) => {
      const i = a.raisons && a.raisons[x.nom];
      const m = i != null && a.motifs && a.motifs[i] ? String(a.motifs[i]).split("|").pop() : "";
      return m ? `<span class="pourquoi">${esc(m)}</span>` : "";
    };
    const detail = ouvert
      ? `<div class="liste">${ferme.length
          ? ferme.map((x) => `<div class="item"><ha-icon icon="${x.genre === "apps" ? "mdi:application-outline" : "mdi:web"}"></ha-icon><span>${esc(x.libelle)}</span>${motif(x)}</div>`).join("")
          : '<div class="vide">Rien de fermé sur cet appareil.</div>'}</div>`
      : "";
    return `
      <div class="appareil">
        <div class="tete">
          <ha-icon icon="${icone}"></ha-icon>
          <div class="titre"><b>${esc(a.nom)}</b> <span class="etat ${act.classe}"><span class="point"></span>${esc(act.texte)}</span></div>
          <span class="temps" title="Temps d'écran actif aujourd'hui"><ha-icon icon="mdi:timer-outline"></ha-icon>${duree(a.usage ? a.usage.actif : 0)}</span>
        </div>
        <div class="acces">${esc(this._acces(a))}</div>
        <div class="boutons">${boutons.join("")}</div>
        <button class="lien" data-detail="${esc(a.id)}">
          <ha-icon icon="${ouvert ? "mdi:chevron-down" : "mdi:chevron-right"}"></ha-icon>
          Ce qui est fermé sur cet appareil (${ferme.length})
        </button>
        ${detail}
      </div>`;
  }

  _categorie(c, pc) {
    const ouvert = this._ouverts.has(c.nom);
    const code = c.coupe ? CODES[c.code] || CODES.regle : null;
    const badge = code
      ? `<span class="badge-cat" style="--t:${code.teinte}" title="${esc(c.raison)}">${code.libelle}${c.partiel ? " · selon l'appareil" : ""}</span>`
      : c.choix === "autoriser" ? '<span class="badge-cat" style="--t:var(--success-color,#2e7d32)">Autorisée</span>' : "";
    const compte = [c.apps.length ? `${c.apps.length} appli${c.apps.length > 1 ? "s" : ""}` : "", c.sites.length ? `${c.sites.length} site${c.sites.length > 1 ? "s" : ""}` : ""]
      .filter(Boolean).join(" · ");
    const contenu = ouvert
      ? `<div class="contenu">
          ${c.raison ? `<div class="raison">${esc(c.raison)}</div>` : ""}
          ${c.apps.length ? `<div class="groupe"><span class="g">Applis</span>${c.apps.map((x) => `<span class="chip">${esc(x.libelle)}</span>`).join("")}</div>` : ""}
          ${c.sites.length ? `<div class="groupe"><span class="g">Sites</span>${c.sites.map((x) => `<span class="chip">${esc(x)}</span>`).join("")}</div>` : ""}
          ${!c.apps.length && !c.sites.length ? '<div class="vide">Rien de classé ici pour l’instant.</div>' : ""}
        </div>`
      : "";
    const bloque = c.verrou || this._occupe || !pc;
    return `
      <div class="cat ${c.coupe ? "coupee" : ""}">
        <button class="ouvrir" data-cat="${esc(c.nom)}" aria-expanded="${ouvert}">
          <ha-icon icon="${ouvert ? "mdi:chevron-down" : "mdi:chevron-right"}"></ha-icon>
          <span class="nomcat">${esc(c.nom)}</span>
          <span class="compte">${esc(compte)}</span>
        </button>
        ${badge}
        <label class="inter ${bloque ? "fige" : ""}" title="${c.verrou ? esc(c.raison) : c.coupe ? "Rouvrir pour cette personne" : "Couper pour cette personne, sur tous ses appareils"}">
          <input type="checkbox" data-etq="${esc(c.nom)}" data-pc="${esc(pc || "")}" ${c.coupe ? "checked" : ""} ${bloque ? "disabled" : ""}>
          <span class="glissiere"></span>
        </label>
        ${contenu}
      </div>`;
  }

  _rendrePersonne() {
    const d = this._donnees;
    const voulu = this._config.personne || "";
    const personnes = this._personnes();
    const p = personnes.find((x) => x.entite === voulu || x.cle === voulu || x.cle === String(voulu).split(".").pop());
    if (!d) return `<ha-card><div class="vide">Chargement…</div></ha-card>`;
    if (!p) return `<ha-card><div class="vide">Personne introuvable : ${esc(voulu)}.</div></ha-card>`;
    const pc = p.appareils[0] ? p.appareils[0].id : "";
    const cats = this._categoriesDe(p);
    const coupees = cats.filter((c) => c.coupe).length;
    const moy = p.moyenne
      ? `<div class="sous">Règle de moyenne : ${esc(p.moyenne.etat)}${p.moyenne.valeur != null ? ` (${Number(p.moyenne.valeur).toLocaleString("fr-FR", { maximumFractionDigits: 2 })}, seuil ${Number(p.moyenne.seuil).toLocaleString("fr-FR")})` : ""}</div>`
      : "";
    return `
      <ha-card>
        <div class="entete personne">
          ${this._avatar(p)}
          <div><h2>${esc(p.prenom)}</h2>${moy}</div>
          <button class="retour" data-nav="${this._config.chemin}/maison" title="Retour à la maison"><ha-icon icon="mdi:home-outline"></ha-icon></button>
        </div>
        ${this._erreur ? `<div class="erreur">${esc(this._erreur)}</div>` : ""}
        ${d.retour ? `<div class="retour-texte">${esc(d.retour)}</div>` : ""}
        <h3>Appareils</h3>
        ${p.appareils.length ? p.appareils.map((a) => this._appareil(a)).join("") : '<div class="vide">Aucun appareil.</div>'}
        <h3>Catégories <span class="n">${coupees} coupée${coupees > 1 ? "s" : ""} sur ${cats.length}</span></h3>
        <div class="legende">Couper une catégorie vaut pour ${esc(p.prenom)} sur tous ses appareils. Ce que la maison, la moyenne ou le planning ferment reste coché, avec la raison.</div>
        ${cats.map((c) => this._categorie(c, pc)).join("")}
      </ha-card>`;
  }

  // --- styles et branchement --------------------------------------------

  _styles() {
    return `
      <style>
        :host { display:block; }
        ha-card { padding: 14px 16px; }
        h2 { margin: 0; font-size: 1.25em; font-weight: 500; }
        h3 { margin: 18px 0 6px; font-size: .95em; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: var(--secondary-text-color); }
        h3 .n { text-transform:none; letter-spacing:0; font-weight:400; margin-left:6px; }
        .entete { display:flex; align-items:center; gap:10px; margin-bottom: 6px; }
        .entete.personne { gap:14px; }
        .entete.personne .avatar { width:46px; height:46px; font-size:1.3em; }
        .sous { color: var(--secondary-text-color); font-size:.88em; margin-top:2px; }
        .retour { margin-left:auto; border:none; background:none; color: var(--secondary-text-color); cursor:pointer; }
        .badge { background: var(--primary-color); color: var(--text-primary-color,#fff); border-radius: 12px; padding: 2px 10px; font-size:.82em; }
        .avatar { width:38px; height:38px; border-radius:50%; object-fit:cover; flex:none; }
        .avatar.lettre { display:flex; align-items:center; justify-content:center; background: var(--primary-color); color: var(--text-primary-color,#fff); font-weight:600; }
        .avatar.gris { background: var(--disabled-color, #9e9e9e); }
        .ligne { display:grid; grid-template-columns: 38px minmax(90px, 140px) 1fr 24px; gap:12px; align-items:center; padding:10px 6px; border-top:1px solid var(--divider-color); cursor:pointer; border-radius:10px; }
        .ligne:hover { background: var(--secondary-background-color); }
        .ligne:first-of-type { border-top:none; }
        .prenom { font-weight:600; }
        .moy { font-size:.8em; color: var(--secondary-text-color); }
        .moy.bas { color: var(--warning-color,#ef6c00); }
        .puces { display:flex; flex-wrap:wrap; gap:6px; }
        .puce { display:flex; align-items:center; gap:6px; border:1px solid var(--divider-color); border-radius:14px; padding:3px 10px 3px 7px; font-size:.86em; max-width:100%; }
        .puce ha-icon { --mdc-icon-size: 17px; color: var(--secondary-text-color); }
        .puce .nom { font-weight:500; }
        .puce .act { color: var(--secondary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .point { width:8px; height:8px; border-radius:50%; background: var(--disabled-color,#9e9e9e); flex:none; }
        .on .point { background: var(--success-color,#2e7d32); }
        .idle .point { background: var(--warning-color,#ef6c00); }
        .lock .point { background: var(--error-color,#c62828); }
        .off { opacity:.65; }
        .chevron { color: var(--secondary-text-color); }
        .vide { padding:14px 0; color: var(--secondary-text-color); text-align:center; }
        .erreur { color: var(--error-color); margin:6px 0; }
        .retour-texte { color: var(--success-color,#2e7d32); font-size:.9em; margin:4px 0; }
        .demandes { margin: 6px 0 10px; }
        .demande { display:flex; gap:10px; align-items:center; padding:8px 10px; border-radius:10px; background: var(--secondary-background-color); margin-bottom:6px; flex-wrap:wrap; }
        .demande .corps { flex:1; min-width:200px; }
        .demande a { color: var(--primary-color); word-break:break-all; }
        .motif, .pourquoi { color: var(--secondary-text-color); font-size:.88em; margin-left:6px; }
        .actions, .boutons { display:flex; gap:6px; flex-wrap:wrap; }
        button { border:1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); border-radius:8px; padding:5px 11px; cursor:pointer; font: inherit; font-size:.9em; }
        button:disabled { opacity:.45; cursor:default; }
        button.principal { background: var(--primary-color); color: var(--text-primary-color,#fff); border-color: var(--primary-color); }
        button.ferme { border-color: var(--error-color,#c62828); color: var(--error-color,#c62828); }
        .appareil { border:1px solid var(--divider-color); border-radius:12px; padding:10px 12px; margin-bottom:8px; }
        .tete { display:flex; align-items:center; gap:10px; }
        .tete ha-icon { color: var(--secondary-text-color); }
        .titre { flex:1; display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; }
        .etat { display:inline-flex; align-items:center; gap:5px; font-size:.86em; color: var(--secondary-text-color); }
        .temps { display:inline-flex; align-items:center; gap:3px; font-size:.86em; color: var(--secondary-text-color); }
        .temps ha-icon { --mdc-icon-size: 16px; }
        .acces { font-size:.9em; margin:6px 0 8px; }
        .lien { border:none; background:none; padding:6px 0 0; color: var(--secondary-text-color); display:flex; align-items:center; gap:2px; font-size:.86em; }
        .liste { padding:4px 0 0 4px; }
        .item { display:flex; gap:8px; align-items:center; padding:3px 0; font-size:.9em; }
        .item ha-icon { --mdc-icon-size: 16px; color: var(--secondary-text-color); }
        .legende { font-size:.84em; color: var(--secondary-text-color); margin-bottom:8px; }
        .cat { display:grid; grid-template-columns: 1fr auto 44px; gap:10px; align-items:center; padding:6px 4px; border-top:1px solid var(--divider-color); }
        .cat.coupee .nomcat { font-weight:600; }
        .cat .ouvrir { border:none; background:none; text-align:left; display:flex; align-items:center; gap:4px; padding:4px 0; color: var(--primary-text-color); font-size:1em; }
        .cat .ouvrir ha-icon { color: var(--secondary-text-color); --mdc-icon-size: 20px; }
        .compte { color: var(--secondary-text-color); font-size:.84em; margin-left:6px; }
        .badge-cat { color: var(--t); border:1px solid var(--t); border-radius:10px; padding:0 8px; font-size:.8em; white-space:nowrap; }
        .inter { position:relative; width:40px; height:22px; display:inline-block; cursor:pointer; }
        .inter input { opacity:0; width:0; height:0; }
        .glissiere { position:absolute; inset:0; background: var(--disabled-color,#9e9e9e); border-radius:22px; transition: background .15s; }
        .glissiere:before { content:""; position:absolute; width:18px; height:18px; left:2px; top:2px; background:#fff; border-radius:50%; transition: transform .15s; }
        .inter input:checked + .glissiere { background: var(--error-color,#c62828); }
        .inter input:checked + .glissiere:before { transform: translateX(18px); }
        .inter.fige { cursor:not-allowed; }
        .inter.fige .glissiere { opacity:.6; }
        .contenu { grid-column: 1 / -1; padding: 2px 0 8px 28px; }
        .raison { font-size:.86em; color: var(--secondary-text-color); margin-bottom:6px; }
        .groupe { display:flex; flex-wrap:wrap; gap:5px; align-items:center; margin:4px 0; }
        .g { font-size:.78em; text-transform:uppercase; letter-spacing:.04em; color: var(--secondary-text-color); margin-right:4px; }
        .chip { font-size:.84em; border:1px solid var(--divider-color); border-radius:10px; padding:1px 8px; }
        @media (max-width: 520px) {
          .ligne { grid-template-columns: 38px 1fr 24px; }
          .ligne .puces { grid-column: 1 / -1; }
        }
      </style>`;
  }

  _rendre() {
    const corps = this._config.mode === "personne" ? this._rendrePersonne() : this._rendreMaison();
    this.shadowRoot.innerHTML = this._styles() + corps;
    this._brancher();
  }

  _brancher() {
    const r = this.shadowRoot;
    r.querySelectorAll("[data-nav]").forEach((el) => {
      const aller = (ev) => { ev.stopPropagation(); this._naviguer(el.dataset.nav); };
      el.addEventListener("click", aller);
      el.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") aller(ev); });
    });
    r.querySelectorAll("[data-acces]").forEach((b) =>
      b.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._agir({ action: "acces", pc: b.dataset.pc, demande: b.dataset.acces, decision: b.dataset.dec, minutes: Number(b.dataset.min || 0) });
      }));
    r.querySelectorAll("[data-action]").forEach((b) =>
      b.addEventListener("click", () =>
        this._agir({ action: b.dataset.action, pc: b.dataset.pc, minutes: Number(b.dataset.min || 0) })));
    r.querySelectorAll("[data-detail]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = b.dataset.detail;
        this._details.has(id) ? this._details.delete(id) : this._details.add(id);
        this._rendre();
      }));
    r.querySelectorAll("[data-cat]").forEach((b) =>
      b.addEventListener("click", () => {
        const nom = b.dataset.cat;
        this._ouverts.has(nom) ? this._ouverts.delete(nom) : this._ouverts.add(nom);
        this._rendre();
      }));
    r.querySelectorAll("[data-etq]").forEach((c) =>
      c.addEventListener("change", () =>
        this._agir({ action: "etiquette", pc: c.dataset.pc, etiquette: c.dataset.etq, etat: c.checked ? "bloquer" : "neutre" })));
  }
}

customElements.define("vision-maison-card", VisionMaisonCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "vision-maison-card",
  name: "Vision — Maison",
  description: "Une ligne par personne, et la page d'une personne : appareils, accès, catégories.",
});
