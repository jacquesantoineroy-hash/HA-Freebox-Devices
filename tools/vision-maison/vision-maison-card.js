/*
 * Vision — carte « Maison » et carte « Personne »
 *
 * mode: maison    une ligne par personne : ce que font ses appareils en ce
 *                 moment ; un clic ouvre la page de la personne.
 * mode: personne  la fiche d'une personne : du temps en plus (durée, puis
 *                 matériel), ses appareils, les siens comme ceux qu'elle
 *                 partage, et ses
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
    this._mots = new Map();
    this._partages = new Set();
    // Le temps qu'on s'apprête à donner : { minutes, autre, choix:Set d'appareils } ou null.
    this._temps = null;
    this._minuteur = null;
  }

  setConfig(config) {
    this._config = Object.assign({ mode: "maison", chemin: "/vision-maison" }, config || {});
  }

  getCardSize() {
    return this._config && this._config.mode === "personne" ? 12 : 4;
  }

  // Toute la largeur de la section, même quand elle enjambe deux colonnes.
  getGridOptions() {
    return { columns: "full" };
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
      // Les siens d'abord, puis ceux qu'elle partage (la télé du salon est à tout le monde).
      appareils: appareils
        .filter((a) => (a.proprietaires ? a.proprietaires.includes(p.entite) : a.personne === p.entite))
        .sort((a, b) => (a.personne === p.entite ? 0 : 1) - (b.personne === p.entite ? 0 : 1)),
    }));
    const orphelins = appareils.filter((a) => (a.proprietaires ? !a.proprietaires.length : !a.personne));
    if (orphelins.length) liste.push({ entite: "", cle: "autres", prenom: "Sans personne", appareils: orphelins, orphelins: true });
    // Les parents en dernier : on ouvre la page pour les enfants.
    liste.sort((a, b) => {
      const pa = !!a.parent;
      const pb = !!b.parent;
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
    const brut = String(a.focus || "").replace(/\.exe$/i, "");
    const quoi = a.focus_libelle || (brut ? brut.charAt(0).toUpperCase() + brut.slice(1) : "");
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
    // Les catégories suivent la personne : seuls ses propres appareils comptent, pas ceux qu'elle partage.
    const apps = personne.appareils.filter((a) => a.personne === personne.entite);
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
        ${this._partage(a) ? '<ha-icon class="part" icon="mdi:account-multiple-outline" title="Appareil partagé"></ha-icon>' : ""}
        <span class="act">${esc(act.texte)}${esc(temps)}</span>
      </div>`;
  }

  _partage(a) {
    return !!a.partage_tous || (a.proprietaires || []).length > 1;
  }

  _aQui(a) {
    if (a.partage_tous) return "À toute la maison";
    const d = this._donnees || {};
    const noms = (a.proprietaires || []).map((e) => ((d.maison || []).find((m) => m.entite === e) || {}).prenom || e.split(".").pop());
    return noms.length > 1 ? `Partagé : ${noms.join(", ")}` : "";
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
    // Le temps en plus se donne plus haut, pour la personne : ici ne restent que les gestes propres à l'appareil.
    const boutons = [];
    if (!a.verrouille) boutons.push(b("fermer", "Fermer", 0, "ferme"));
    if (a.derogation && a.derogation.mode) boutons.push(b("annuler", "Revenir au planning"));
    boutons.push(`<button data-mot="${esc(a.id)}" ${this._occupe ? "disabled" : ""}><ha-icon icon="mdi:message-text-outline"></ha-icon> Un mot</button>`);
    const mot = this._mots.has(a.id)
      ? `<form class="mot" data-envoi="${esc(a.id)}">
          <input type="text" maxlength="200" placeholder="Un mot sur son écran…" value="${esc(this._mots.get(a.id) || "")}">
          <button type="submit" class="principal" ${this._occupe ? "disabled" : ""}>Envoyer</button>
        </form>`
      : "";
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
    const aQui = this._aQui(a);
    const partageOuvert = this._partages.has(a.id);
    const d = this._donnees || {};
    const partage = partageOuvert
      ? `<div class="partage" data-partage="${esc(a.id)}">
          <label class="coche"><input type="checkbox" data-tous ${a.partage_tous ? "checked" : ""} ${this._occupe ? "disabled" : ""}> Toute la maison</label>
          ${(d.maison || []).map((m) => `<label class="coche"><input type="checkbox" data-qui="${esc(m.entite)}" ${(a.proprietaires || []).includes(m.entite) ? "checked" : ""} ${this._occupe || a.partage_tous || m.entite === a.personne ? "disabled" : ""}> ${esc(m.prenom)}${m.entite === a.personne ? " (ses règles s'y appliquent)" : ""}</label>`).join("")}
          <div class="legende">Partager ne change aucune règle : l'appareil apparaît chez chacun, et chacun peut y recevoir du temps.</div>
        </div>`
      : "";
    return `
      <div class="appareil">
        <div class="tete">
          <ha-icon icon="${icone}"></ha-icon>
          <div class="titre"><b>${esc(a.nom)}</b> <span class="etat ${act.classe}"><span class="point"></span>${esc(act.texte)}</span>${aQui ? `<span class="aqui">${esc(aQui)}</span>` : ""}</div>
          <span class="temps" title="Temps d'écran actif aujourd'hui"><ha-icon icon="mdi:timer-outline"></ha-icon>${duree(a.usage ? a.usage.actif : 0)}</span>
        </div>
        <div class="acces">${esc(this._acces(a))}</div>
        <div class="boutons">${boutons.join("")}</div>
        ${mot}
        <button class="lien" data-detail="${esc(a.id)}">
          <ha-icon icon="${ouvert ? "mdi:chevron-down" : "mdi:chevron-right"}"></ha-icon>
          Ce qui est fermé sur cet appareil (${ferme.length})
        </button>
        ${detail}
        <button class="lien" data-apartage="${esc(a.id)}">
          <ha-icon icon="${partageOuvert ? "mdi:chevron-down" : "mdi:chevron-right"}"></ha-icon>
          À qui est cet appareil
        </button>
        ${partage}
      </div>`;
  }

  // Donner du temps : d'abord la durée, puis le matériel. Un seul appareil : pas de seconde question.
  _blocTemps(p) {
    const apps = p.appareils;
    if (!apps.length) return "";
    const t = this._temps;
    const off = this._occupe ? "disabled" : "";
    const duree_b = (min, txt) => `<button data-duree="${min}" class="${t && !t.autre && t.minutes === min ? "principal" : ""}" ${off}>${txt}</button>`;
    let etape = "";
    if (t) {
      const saisie = t.autre
        ? `<label class="saisie">Durée <input type="number" data-minutes min="5" max="720" step="5" value="${esc(t.minutes || "")}" placeholder="45"> min</label>`
        : "";
      const choix = apps.length > 1
        ? `<div class="question">Pour quel matériel ?</div>
           <div class="choix">
             ${apps.map((a) => `<label class="coche"><input type="checkbox" data-choix="${esc(a.id)}" ${t.choix.has(a.id) ? "checked" : ""}> ${esc(a.nom)}${a.en_ligne ? "" : " (hors ligne)"}</label>`).join("")}
             <button class="lien" data-tous-choix>${t.choix.size === apps.length ? "Aucun" : "Tous"}</button>
           </div>`
        : "";
      const m = Number(t.minutes || 0);
      const bon = m >= 5 && m <= 720 && t.choix.size > 0;
      etape = `
        <div class="etape">
          ${saisie}${choix}
          <div class="boutons">
            <button class="principal" data-donner ${bon && !this._occupe ? "" : "disabled"}>Donner ${m ? duree(m) : "…"}</button>
            <button data-temps-annuler ${off}>Annuler</button>
          </div>
        </div>`;
    }
    const encours = apps
      .filter((a) => a.derogation && a.derogation.mode === "open")
      .map((a) => `<div class="bonus"><ha-icon icon="mdi:timer-sand"></ha-icon><span><b>${esc(a.nom)}</b> ouvert${a.derogation.fin ? ` jusqu'à ${heureTs(a.derogation.fin)}` : " jusqu'au prochain créneau"}</span><button data-action="annuler" data-pc="${esc(a.id)}" ${off}>Retirer</button></div>`)
      .join("");
    return `
      <h3>Ajouter du temps</h3>
      <div class="temps-bloc">
        <div class="boutons">${duree_b(30, "+30 min")}${duree_b(60, "+1 h")}<button data-duree="autre" class="${t && t.autre ? "principal" : ""}" ${off}>Autre…</button></div>
        ${etape}
        ${encours}
      </div>`;
  }

  _choisirDuree(p, valeur) {
    const apps = p.appareils;
    const autre = valeur === "autre";
    const minutes = autre ? (this._temps && this._temps.autre ? this._temps.minutes : 0) : Number(valeur);
    // Un seul appareil et une durée toute faite : rien d'autre à demander.
    if (!autre && apps.length === 1) {
      this._temps = null;
      this._agir({ action: "temps", appareils: [apps[0].id], minutes });
      return;
    }
    // Cochés d'avance : ce qui sert en ce moment ; sinon tout.
    let choix = this._temps ? this._temps.choix : null;
    if (!choix) {
      const actifs = apps.filter((a) => a.en_ligne && !(a.inactif_s > 300)).map((a) => a.id);
      choix = new Set(actifs.length ? actifs : apps.map((a) => a.id));
    }
    this._temps = { minutes, autre, choix };
    this._rendre();
    if (autre) {
      const champ = this.shadowRoot.querySelector("[data-minutes]");
      if (champ) champ.focus();
    }
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
    // Les règles de la personne se posent sur un appareil à elle, jamais sur un appareil partagé.
    const propre = p.appareils.find((a) => a.personne === p.entite);
    const pc = p.principal || (propre ? propre.id : "");
    this._personne = p;
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
        ${this._blocTemps(p)}
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
        .mot { display:flex; gap:6px; margin-top:8px; }
        .mot input { flex:1; padding:6px 10px; border:1px solid var(--divider-color); border-radius:8px; background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
        .boutons button ha-icon { --mdc-icon-size: 16px; vertical-align: -3px; }
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
        .puce .part { --mdc-icon-size: 14px; }
        .aqui { font-size:.8em; color: var(--secondary-text-color); border:1px solid var(--divider-color); border-radius:10px; padding:0 8px; }
        .temps-bloc { border:1px solid var(--divider-color); border-radius:12px; padding:10px 12px; margin-bottom:8px; }
        .etape { margin-top:10px; padding-top:10px; border-top:1px solid var(--divider-color); }
        .question { font-size:.9em; font-weight:600; margin-bottom:4px; }
        .choix, .partage { display:flex; flex-wrap:wrap; gap:4px 16px; align-items:center; margin-bottom:10px; }
        .partage { margin:6px 0 0 4px; }
        .partage .legende { flex-basis:100%; margin:4px 0 0; }
        .coche { display:inline-flex; align-items:center; gap:6px; font-size:.92em; cursor:pointer; padding:3px 0; }
        .coche input { width:17px; height:17px; accent-color: var(--primary-color); }
        .saisie { display:flex; align-items:center; gap:8px; font-size:.92em; margin-bottom:10px; }
        .saisie input { width:84px; padding:6px 8px; border:1px solid var(--divider-color); border-radius:8px; background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
        .bonus { display:flex; align-items:center; gap:8px; font-size:.9em; margin-top:8px; }
        .bonus span { flex:1; }
        .bonus ha-icon { --mdc-icon-size: 17px; color: var(--secondary-text-color); }
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
    // --- temps : durée, puis matériel
    r.querySelectorAll("[data-duree]").forEach((b) =>
      b.addEventListener("click", () => this._choisirDuree(this._personne, b.dataset.duree)));
    r.querySelectorAll("[data-minutes]").forEach((c) =>
      c.addEventListener("input", () => {
        if (!this._temps) return;
        this._temps.minutes = Math.round(Number(c.value) || 0);
        const m = this._temps.minutes;
        const ok = r.querySelector("[data-donner]");
        if (ok) {
          ok.disabled = !(m >= 5 && m <= 720 && this._temps.choix.size > 0);
          ok.textContent = `Donner ${m ? duree(m) : "…"}`;
        }
      }));
    r.querySelectorAll("[data-choix]").forEach((c) =>
      c.addEventListener("change", () => {
        if (!this._temps) return;
        c.checked ? this._temps.choix.add(c.dataset.choix) : this._temps.choix.delete(c.dataset.choix);
        this._rendre();
      }));
    r.querySelectorAll("[data-tous-choix]").forEach((b) =>
      b.addEventListener("click", () => {
        if (!this._temps || !this._personne) return;
        const tous = this._personne.appareils.map((a) => a.id);
        this._temps.choix = this._temps.choix.size === tous.length ? new Set() : new Set(tous);
        this._rendre();
      }));
    r.querySelectorAll("[data-temps-annuler]").forEach((b) =>
      b.addEventListener("click", () => { this._temps = null; this._rendre(); }));
    r.querySelectorAll("[data-donner]").forEach((b) =>
      b.addEventListener("click", () => {
        const t = this._temps;
        if (!t) return;
        this._temps = null;
        this._agir({ action: "temps", appareils: [...t.choix], minutes: Number(t.minutes) });
      }));
    // --- à qui est l'appareil
    r.querySelectorAll("[data-apartage]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = b.dataset.apartage;
        this._partages.has(id) ? this._partages.delete(id) : this._partages.add(id);
        this._rendre();
      }));
    r.querySelectorAll("[data-partage]").forEach((bloc) =>
      bloc.querySelectorAll("input").forEach((c) =>
        c.addEventListener("change", () => {
          const tous = bloc.querySelector("[data-tous]").checked;
          // « Toute la maison » qu'on vient de cocher ou de décocher : la liste repart de zéro.
          const personnes = tous || c.hasAttribute("data-tous")
            ? []
            : [...bloc.querySelectorAll("[data-qui]")].filter((x) => x.checked && !x.disabled).map((x) => x.dataset.qui);
          this._agir({ action: "partage", pc: bloc.dataset.partage, personnes, tous });
        })));
    r.querySelectorAll("[data-mot]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = b.dataset.mot;
        this._mots.has(id) ? this._mots.delete(id) : this._mots.set(id, "");
        this._rendre();
        const champ = this.shadowRoot.querySelector(`[data-envoi="${id}"] input`);
        if (champ) champ.focus();
      }));
    r.querySelectorAll("[data-envoi]").forEach((f) => {
      const champ = f.querySelector("input");
      champ.addEventListener("input", () => this._mots.set(f.dataset.envoi, champ.value));
      f.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const texte = champ.value.trim();
        if (!texte) return;
        this._mots.delete(f.dataset.envoi);
        await this._agir({ action: "message", pc: f.dataset.envoi, texte });
      });
    });
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
