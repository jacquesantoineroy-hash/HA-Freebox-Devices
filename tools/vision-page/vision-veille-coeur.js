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

/*
 * Vision — les horloges de l'écran de veille : une par thème, chacune la sienne.
 *
 * Chaque horloge donne son dessin (html) et sa façon d'avancer (tic, appelée chaque seconde).
 * Les couleurs viennent du thème de l'appareil (--v-texte, --v-texte2, --v-accent, --v-carte, --v-ligne).
 */
const p2 = (n) => String(n).padStart(2, "0");
const hm = (d) => `${p2(d.getHours())}:${p2(d.getMinutes())}`;
const poser = (el, sel, texte) => { const x = el.querySelector(sel); if (x && x.textContent !== texte) x.textContent = texte; };
const tourner = (el, sel, deg) => { const x = el.querySelector(sel); if (x) x.setAttribute("transform", `rotate(${deg.toFixed(2)})`); };
const pt = (r, deg) => { const a = (deg * Math.PI) / 180; return [(Math.sin(a) * r).toFixed(2), (-Math.cos(a) * r).toFixed(2)]; };
// Un arc de cercle, de l'angle a0 à l'angle a1 (degrés, 0 en haut, sens des aiguilles).
const arc = (r, a0, a1) => { const [x0, y0] = pt(r, a0), [x1, y1] = pt(r, a1); return `M ${x0} ${y0} A ${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`; };
const traits = (n, r1, r2, classe, saut = 0) => { let o = ""; for (let i = 0; i < n; i++) { if (saut && i % saut === 0) continue; const [x1, y1] = pt(r1, (i * 360) / n), [x2, y2] = pt(r2, (i * 360) / n); o += `<line class="${classe}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`; } return o; };
const autour = (liste, r, classe) => liste.map((t, i) => { if (!t) return ""; const [x, y] = pt(r, (i * 360) / liste.length); return `<text class="${classe}" x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central">${t}</text>`; }).join("");
const aiguilles = (el, d) => { const s = d.getSeconds(), m = d.getMinutes() + s / 60, h = (d.getHours() % 12) + m / 60; tourner(el, ".ah", h * 30); tourner(el, ".am", m * 6); tourner(el, ".as", s * 6); };
const svg = (contenu, classe = "") => `<svg class="cadran ${classe}" viewBox="-100 -100 200 200">${contenu}</svg>`;

// L'heure en toutes lettres : « onze heures cinquante-deux ».
const NOMBRES = ["zéro", "une", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"];
const DIZAINES = { 2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante" };
const enLettres = (n) => (n < 20 ? NOMBRES[n] : DIZAINES[Math.floor(n / 10)] + (n % 10 === 0 ? "" : n % 10 === 1 ? " et une" : "-" + NOMBRES[n % 10]));
const heureEnLettres = (d) => { const h = d.getHours(), m = d.getMinutes(); const hh = h === 0 ? "minuit" : h === 12 ? "midi" : `${enLettres(h)} heure${h > 1 ? "s" : ""}`; return [hh, m === 0 ? "pile" : enLettres(m)]; };

// Des chiffres faits de briques (5 de large, 7 de haut).
const BRIQUES = { 0: "01110100011001110101110011000101110", 1: "00100011000010000100001000010001110", 2: "01110100010000100010001000100011111", 3: "11110000010000101110000010000111110", 4: "00010001100101010010111110001000010", 5: "11111100001111000001000011000101110", 6: "00110010001000011110100011000101110", 7: "11111000010001000100010000100001000", 8: "01110100011000101110100011000101110", 9: "01110100011000101111000010001001100", ":": "00000001000010000000001000010000000" };
const enBriques = (texte) => {
  let o = "", x0 = 0;
  for (const c of texte) {
    const g = BRIQUES[c] || BRIQUES[0], etroit = c === ":";
    for (let i = 0; i < 35; i++) {
      if (g[i] !== "1") continue;
      const col = i % 5, lig = Math.floor(i / 5);
      if (etroit && col !== 2) continue;
      const x = x0 + (etroit ? 0 : col) * 10, y = lig * 10;
      o += `<rect class="${etroit ? "b2" : "b1"}" x="${x}" y="${y}" width="9" height="9" rx="1.6"/><circle class="bp" cx="${x + 4.5}" cy="${y + 4.5}" r="2.1"/>`;
    }
    x0 += etroit ? 20 : 60;
  }
  return `<svg class="briques" viewBox="-4 -4 ${x0 - 2} 78">${o}</svg>`;
};

const semaine = (d) => { const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())); const j = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - j); return Math.ceil(((t - Date.UTC(t.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7); };
const ROMAINS = ["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"];

const HORLOGES = {
  // Vision : de grands chiffres fins, la date, le ciel.
  defaut: {
    html: (c) => `<div class="heure"></div><div class="date">${c.jour}</div><div class="ciel">${c.ciel}</div>`,
    tic: (el, d) => poser(el, ".heure", hm(d)),
  },
  // Sombre : les chiffres, et la minute qui se remplit en un trait.
  sombre: {
    html: (c) => `<div class="heure"></div><div class="fil"><i></i></div><div class="date">${c.jour}</div>`,
    tic: (el, d) => { poser(el, ".heure", hm(d)); const i = el.querySelector(".fil i"); if (i) i.style.width = `${((d.getSeconds() + 1) / 60) * 100}%`; },
  },
  // Bleu nuit : un cadran de points, des aiguilles fines, un croissant de lune.
  "bleu-nuit": {
    html: (c) => svg(`${traits(60, 92, 94, "t1", 5)}${Array.from({ length: 12 }, (_, i) => { const [x, y] = pt(92, i * 30); return `<circle class="pt${i % 3 === 0 ? " gros" : ""}" cx="${x}" cy="${y}" r="${i % 3 === 0 ? 2.6 : 1.5}"/>`; }).join("")}
      <path class="lune" d="M 0 -52 a 11 11 0 1 0 9 17 a 8.5 8.5 0 1 1 -9 -17"/>
      <line class="ah" x1="0" y1="8" x2="0" y2="-48"/><line class="am" x1="0" y1="10" x2="0" y2="-76"/><line class="as" x1="0" y1="14" x2="0" y2="-84"/><circle class="axe" r="3"/>`) + `<div class="date">${c.jour}</div>`,
    tic: aiguilles,
  },
  // Beige : l'heure écrite en toutes lettres, comme dans un livre.
  beige: {
    html: (c) => `<div class="mots"><span class="m1"></span><span class="m2"></span></div><div class="filet"></div><div class="date"><b class="hm"></b> · ${c.jour}</div>`,
    tic: (el, d) => { const [a, b] = heureEnLettres(d); poser(el, ".m1", a); poser(el, ".m2", b); poser(el, ".hm", hm(d)); },
  },
  // Sauge : l'heure sur les minutes, en deux étages.
  sauge: {
    html: (c) => `<div class="etages"><span class="hh"></span><span class="mm"></span></div><div class="date">${c.jour}</div>`,
    tic: (el, d) => { poser(el, ".hh", p2(d.getHours())); poser(el, ".mm", p2(d.getMinutes())); },
  },
  // Salon : la pendule murale, quatre grands chiffres et des aiguilles d'acier.
  salon: {
    html: (c) => svg(`<circle class="bord" r="97"/>${traits(12, 82, 92, "t2", 3)}${autour(["12", "", "", "3", "", "", "6", "", "", "9", "", ""], 74, "ch")}
      <path class="ah" d="M -3.2 10 L -2.2 -46 L 2.2 -46 L 3.2 10 Z"/><path class="am" d="M -2.4 12 L -1.5 -74 L 1.5 -74 L 2.4 12 Z"/><line class="as" x1="0" y1="16" x2="0" y2="-80"/><circle class="axe" r="4.5"/>`) + `<div class="date">${c.jour}</div>`,
    tic: aiguilles,
  },
  // Rose poudré : un anneau qui se ferme au fil de l'heure, les chiffres au centre.
  "rose-poudre": {
    html: (c) => `<div class="rond">${svg(`<circle class="piste" r="90"/><path class="tour" d=""/>`)}<div class="dedans"><div class="heure"></div><div class="date">${c.jourCourt}</div></div></div>`,
    tic: (el, d) => { poser(el, ".heure", hm(d)); const t = el.querySelector(".tour"); if (t) t.setAttribute("d", arc(90, 0, Math.max(0.5, Math.min(359.5, (d.getMinutes() * 60 + d.getSeconds()) / 10)))); },
  },
  // Tactique : des chiffres penchés, coupés au couteau, une barre d'accent.
  tactique: {
    html: (c) => `<div class="bloc"><div class="rep">// ${c.jourCourt.toUpperCase()}</div><div class="heure"></div><div class="barres"><i></i><i></i><i></i></div><div class="sec"></div></div>`,
    tic: (el, d) => { poser(el, ".heure", hm(d)); poser(el, ".sec", `${p2(d.getSeconds())} S`); },
  },
  // Briques : les chiffres montés brique par brique.
  briques: {
    html: (c) => `<div class="mur"></div><div class="date">${c.jour}</div>`,
    tic: (el, d) => { const m = el.querySelector(".mur"), t = hm(d); if (m && m.dataset.t !== t) { m.dataset.t = t; m.innerHTML = enBriques(t); } },
  },
  // Corsaire : une rose des vents pour cadran.
  corsaire: {
    html: (c) => svg(`<circle class="bord" r="96"/><circle class="bord fin" r="84"/>${traits(72, 84, 90, "t1")}${traits(12, 78, 90, "t2")}
      <path class="rose" d="M 0 -70 L 9 -9 L 70 0 L 9 9 L 0 70 L -9 9 L -70 0 L -9 -9 Z"/><path class="rose2" d="M 0 -70 L 0 0 L 9 -9 Z M 70 0 L 0 0 L 9 9 Z M 0 70 L 0 0 L -9 9 Z M -70 0 L 0 0 L -9 -9 Z"/>
      ${autour(["N", "E", "S", "O"], 60, "ch")}
      <path class="ah" d="M 0 12 L -3.5 0 L 0 -44 L 3.5 0 Z"/><path class="am" d="M 0 14 L -2.6 0 L 0 -72 L 2.6 0 Z"/><line class="as" x1="0" y1="16" x2="0" y2="-80"/><circle class="axe" r="3.6"/>`) + `<div class="date"><b class="hm"></b> · ${c.jour}</div>`,
    tic: (el, d) => { aiguilles(el, d); poser(el, ".hm", hm(d)); },
  },
  // Royale : des chiffres épais et penchés, en dégradé, posés sur leur ombre.
  royale: {
    html: (c) => `<div class="pile"><div class="heure ombre"></div><div class="heure face"></div></div><div class="pastille">${c.jour}</div>`,
    tic: (el, d) => { const t = hm(d); el.querySelectorAll(".heure").forEach((x) => { if (x.textContent !== t) x.textContent = t; }); },
  },
  // Circuit : un compte-tours dont l'aiguille suit les minutes, zone rouge en fin d'heure.
  circuit: {
    html: (c) => svg(`<path class="piste" d="${arc(86, -120, 120)}"/><path class="rouge" d="${arc(86, 80, 120)}"/>
      ${Array.from({ length: 13 }, (_, i) => { const a = -120 + i * 20, [x1, y1] = pt(74, a), [x2, y2] = pt(86, a), [tx, ty] = pt(62, a); return `<line class="t2" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>${i % 2 === 0 ? `<text class="ch" x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="central">${i * 5}</text>` : ""}`; }).join("")}
      <g class="aig"><path d="M -2.4 10 L -1 -80 L 1 -80 L 2.4 10 Z"/></g><circle class="axe" r="7"/>
      <text class="num" x="0" y="60" text-anchor="middle"></text><text class="unite" x="0" y="74" text-anchor="middle">MIN</text>`) + `<div class="date">${c.jour}</div>`,
    tic: (el, d) => { tourner(el, ".aig", -120 + ((d.getMinutes() + d.getSeconds() / 60) / 60) * 240); poser(el, ".num", hm(d)); },
  },
  // Cockpit : un instrument de bord sur vingt-quatre heures, heure locale et heure universelle.
  cockpit: {
    html: (c) => svg(`<circle class="bord" r="97"/>${traits(120, 88, 92, "t1", 5)}${traits(24, 82, 92, "t2")}${autour(["24", "", "", "3", "", "", "6", "", "", "9", "", "", "12", "", "", "15", "", "", "18", "", "", "21", "", ""], 71, "ch")}
      <g class="a24"><path d="M 0 -80 L -4 -66 L 4 -66 Z"/></g>
      <text class="num" x="0" y="-8" text-anchor="middle"></text><text class="unite" x="0" y="10" text-anchor="middle">LOCALE</text>
      <text class="utc" x="0" y="34" text-anchor="middle"></text>`) + `<div class="date">${c.jour}</div>`,
    tic: (el, d) => { tourner(el, ".a24", ((d.getHours() * 60 + d.getMinutes()) / 1440) * 360); poser(el, ".num", `${hm(d)}:${p2(d.getSeconds())}`); poser(el, ".utc", `${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())} UTC`); },
  },
  // Bourse : des chiffres de téléscripteur, et les soixante secondes de la minute en bâtons.
  bourse: {
    html: (c) => `<div class="tele"><span class="heure"></span><span class="sec"></span></div><div class="batons">${Array.from({ length: 60 }, (_, i) => `<i style="height:${(30 + 62 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.6))).toFixed(0)}%"></i>`).join("")}</div><div class="date">${c.jourCourt.toUpperCase()} · SEMAINE ${semaine(new Date())}</div>`,
    tic: (el, d) => { poser(el, ".heure", hm(d)); poser(el, ".sec", `:${p2(d.getSeconds())}`); const s = d.getSeconds(), b = el.querySelector(".batons"); if (b && b.dataset.s !== String(s)) { b.dataset.s = String(s); [...b.children].forEach((x, i) => x.classList.toggle("fait", i <= s)); } },
  },
  // Écrin : chiffres romains, aiguilles fines, double filet.
  ecrin: {
    html: (c) => svg(`<circle class="bord" r="97"/><circle class="bord fin" r="92"/>${traits(60, 80, 84, "t1", 5)}${autour(ROMAINS, 70, "ch")}
      <text class="marque" x="0" y="-36" text-anchor="middle">VISION</text>
      <path class="ah" d="M 0 10 L -2.6 -8 L 0 -46 L 2.6 -8 Z"/><path class="am" d="M 0 12 L -1.9 -10 L 0 -74 L 1.9 -10 Z"/><line class="as" x1="0" y1="18" x2="0" y2="-80"/><circle class="axe" r="2.6"/>`) + `<div class="date">${c.jour}</div>`,
    tic: aiguilles,
  },
  // Prairie : la course du soleil sur la journée, les chiffres dessous.
  prairie: {
    html: (c) => `<svg class="ciel-arc" viewBox="-110 -100 220 112"><path class="piste" d="${arc(90, -90, 90)}"/><line class="sol" x1="-108" y1="0" x2="108" y2="0"/><g class="astre"><circle r="9"/></g></svg><div class="heure"></div><div class="date">${c.jour}</div>`,
    tic: (el, d) => {
      poser(el, ".heure", hm(d));
      // De 6 h à 22 h le soleil va d'un bord à l'autre ; la nuit, c'est la lune qui fait le trajet.
      const h = d.getHours() + d.getMinutes() / 60, jour = h >= 6 && h < 22, part = jour ? (h - 6) / 16 : ((h + 2) % 24) / 8;
      const [x, y] = pt(90, -90 + part * 180), a = el.querySelector(".astre");
      if (a) { a.setAttribute("transform", `translate(${x} ${y})`); a.classList.toggle("lune", !jour); }
    },
  },
  // Large : les chiffres au-dessus de la houle.
  large: {
    html: (c) => `<div class="heure"></div><div class="date">${c.jour}</div><svg class="houle" viewBox="0 0 400 40" preserveAspectRatio="none"><path class="v1" d="M 0 20 Q 25 6 50 20 T 100 20 T 150 20 T 200 20 T 250 20 T 300 20 T 350 20 T 400 20 T 450 20 T 500 20"/><path class="v2" d="M 0 28 Q 25 16 50 28 T 100 28 T 150 28 T 200 28 T 250 28 T 300 28 T 350 28 T 400 28 T 450 28 T 500 28"/></svg>`,
    tic: (el, d) => poser(el, ".heure", hm(d)),
  },
  // Sommet : une ligne de crête, l'heure au-dessus des cimes.
  sommet: {
    html: (c) => `<div class="heure"></div><div class="date">${c.jour}</div><svg class="crete" viewBox="0 0 400 90" preserveAspectRatio="none"><path class="loin" d="M 0 90 L 0 62 L 46 40 L 84 58 L 132 22 L 176 54 L 214 36 L 262 60 L 310 30 L 352 52 L 400 34 L 400 90 Z"/><path class="pres" d="M 0 90 L 0 76 L 60 54 L 104 72 L 168 38 L 190 50 L 206 42 L 252 74 L 300 56 L 344 76 L 400 58 L 400 90 Z"/><path class="neige" d="M 168 38 L 152 47 L 164 46 L 172 52 L 180 45 L 190 50 Z"/></svg>`,
    tic: (el, d) => poser(el, ".heure", hm(d)),
  },
  // Sous-bois : les cernes d'un arbre, un par aiguille (heures, minutes, secondes).
  "sous-bois": {
    html: (c) => `<div class="rond">${svg(`<circle class="piste" r="92"/><circle class="piste" r="78"/><circle class="piste" r="64"/><path class="c1" d=""/><path class="c2" d=""/><path class="c3" d=""/>`)}<div class="dedans"><div class="heure"></div><div class="date">${c.jourCourt}</div></div></div>`,
    tic: (el, d) => {
      poser(el, ".heure", hm(d));
      const borne = (v) => Math.max(0.5, Math.min(359.5, v));
      const s = d.getSeconds(), m = d.getMinutes() + s / 60, h = (d.getHours() % 12) + m / 60;
      const dessiner = (sel, r, a) => { const x = el.querySelector(sel); if (x) x.setAttribute("d", arc(r, 0, borne(a))); };
      dessiner(".c1", 92, h * 30); dessiner(".c2", 78, m * 6); dessiner(".c3", 64, (s + 1) * 6);
    },
  },
};

const CSS_HORLOGES = `
  .horloge .cadran { width: min(62vh, 78vw); height: min(62vh, 78vw); overflow: visible; }
  .horloge .cadran + .date { margin-top: 3.5vh; }
  .h-circuit .cadran { margin-top: 6vh; } .h-circuit .cadran + .date { margin-top: 0; }
  .horloge svg text { font-family: inherit; fill: var(--v-texte); }
  .horloge .t1 { stroke: var(--v-texte2); stroke-width: .7; opacity: .7; }
  .horloge .t2 { stroke: var(--v-texte); stroke-width: 1.8; }
  .horloge .ah, .horloge .am { stroke: var(--v-texte); stroke-width: 3; stroke-linecap: round; fill: var(--v-texte); }
  .horloge .am { stroke-width: 2; }
  .horloge .as { stroke: var(--v-accent); stroke-width: 1; stroke-linecap: round; }
  .horloge .axe { fill: var(--v-accent); }
  .horloge .bord { fill: none; stroke: var(--v-texte); stroke-width: 1.6; }
  .horloge .bord.fin { stroke-width: .6; stroke: var(--v-accent); }
  .horloge .piste { fill: none; stroke: var(--v-ligne); stroke-width: 3; stroke-linecap: round; }
  .horloge .rond { position: relative; width: min(62vh, 78vw); height: min(62vh, 78vw); }
  .horloge .rond .cadran { position: absolute; inset: 0; width: 100%; height: 100%; }
  .horloge .rond .dedans { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .horloge .rond .heure { font-size: min(15vh, 19vw); }
  .horloge .rond .date { font-size: min(3vh, 4vw); margin-top: 1.2vh; }

  .h-sombre .heure { font-weight: 200; letter-spacing: .02em; }
  .h-sombre .fil { width: min(46vw, 70vh); height: 3px; background: var(--v-ligne); margin-top: 3vh; border-radius: 2px; overflow: hidden; }
  .h-sombre .fil i { display: block; height: 100%; width: 0; background: var(--v-accent); transition: width 1s linear; }

  .h-bleu-nuit .pt { fill: var(--v-texte2); } .h-bleu-nuit .pt.gros { fill: var(--v-accent); }
  .h-bleu-nuit .lune { fill: var(--v-accent); opacity: .85; }
  .h-bleu-nuit .ah { stroke-width: 2.6; } .h-bleu-nuit .am { stroke-width: 1.6; }

  .h-beige { font-family: Georgia, "Times New Roman", serif; }
  .h-beige .mots { display: flex; flex-direction: column; align-items: center; line-height: 1.06; }
  .h-beige .m1 { font-size: min(12vh, 11vw); font-style: italic; }
  .h-beige .m2 { font-size: min(12vh, 11vw); color: var(--v-accent); }
  .h-beige .filet { width: 9vh; height: 1.5px; background: var(--v-texte2); margin: 4vh 0 0; }
  .h-beige .date { font-style: italic; } .h-beige .date b { font-style: normal; font-weight: 400; color: var(--v-texte); }

  .h-sauge .etages { display: flex; flex-direction: column; align-items: center; line-height: .86; font-weight: 700; font-size: min(34vh, 40vw); letter-spacing: -.03em; }
  .h-sauge .mm { color: var(--v-accent); }
  .h-sauge .date { margin-top: 3vh; }

  .h-salon .bord { stroke-width: 3.4; }
  .h-salon .ch { font-size: 22px; font-weight: 300; fill: var(--v-accent); }
  .h-salon .t2 { stroke-width: 2.4; }
  .h-salon .ah, .h-salon .am { stroke: none; } .h-salon .axe { fill: var(--v-texte); }

  .h-rose-poudre .piste { stroke-width: 2; }
  .h-rose-poudre .tour { fill: none; stroke: var(--v-accent); stroke-width: 5; stroke-linecap: round; }
  .h-rose-poudre .heure { font-weight: 200; }

  .h-tactique { font-family: Bahnschrift, "DIN Alternate", "Roboto Condensed", Impact, sans-serif; }
  .h-tactique .bloc { transform: skewX(-9deg); display: flex; flex-direction: column; align-items: flex-start; }
  .h-tactique .rep { font-size: min(2.8vh, 4vw); letter-spacing: .32em; color: var(--v-accent); margin-bottom: 1vh; }
  .h-tactique .heure { font-size: min(34vh, 34vw); font-weight: 700; line-height: .9; letter-spacing: -.01em; clip-path: polygon(0 0, 100% 0, 100% 84%, 96% 100%, 0 100%); }
  .h-tactique .barres { display: flex; gap: 1vh; margin-top: 2.4vh; width: 100%; }
  .h-tactique .barres i { height: 1vh; background: var(--v-accent); flex: 5; } .h-tactique .barres i:nth-child(2) { flex: 1; } .h-tactique .barres i:nth-child(3) { flex: .5; background: var(--v-texte); }
  .h-tactique .sec { font-size: min(3vh, 4.4vw); letter-spacing: .3em; color: var(--v-texte2); margin-top: 1.6vh; font-variant-numeric: tabular-nums; }

  .h-briques .mur { width: min(78vw, 118vh); }
  .h-briques .briques { width: 100%; height: auto; display: block; overflow: visible; }
  .h-briques .b1 { fill: var(--v-accent); } .h-briques .b2 { fill: var(--v-texte); }
  .h-briques .bp { fill: #fff; opacity: .22; }
  .h-briques .date { margin-top: 4vh; font-weight: 700; }

  .h-corsaire .rose { fill: none; stroke: var(--v-texte2); stroke-width: .8; opacity: .8; }
  .h-corsaire .rose2 { fill: var(--v-texte2); opacity: .22; }
  .h-corsaire .ch { font-size: 11px; font-family: Georgia, serif; fill: var(--v-accent); }
  .h-corsaire .ah, .h-corsaire .am { stroke: none; }
  .h-corsaire .date { font-family: Georgia, serif; font-style: italic; } .h-corsaire .date b { font-style: normal; color: var(--v-texte); }

  .h-royale .pile { position: relative; transform: rotate(-4deg) skewX(-6deg); }
  .h-royale .heure { font-size: min(36vh, 36vw); font-weight: 900; line-height: 1; letter-spacing: -.02em; font-family: "Segoe UI Black", "Arial Black", Impact, sans-serif; }
  .h-royale .ombre { position: absolute; left: .09em; top: .08em; color: var(--v-carte); -webkit-text-stroke: .03em var(--v-ligne); }
  .h-royale .face { position: relative; background: linear-gradient(180deg, var(--v-texte) 8%, var(--v-accent) 78%); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .h-royale .pastille { margin-top: 3vh; padding: 1.1vh 3vh; border-radius: 99px; background: var(--v-accent); color: var(--v-fond); font-weight: 800; font-size: min(3vh, 4.4vw); text-transform: uppercase; letter-spacing: .08em; transform: rotate(-4deg); }

  .h-circuit .piste { stroke-width: 7; stroke-linecap: butt; } .h-circuit .rouge { fill: none; stroke: var(--v-accent); stroke-width: 7; }
  .h-circuit .ch { font-size: 10px; fill: var(--v-texte2); font-weight: 600; }
  .h-circuit .aig path { fill: var(--v-accent); } .h-circuit .aig { transition: transform 1s linear; }
  .h-circuit .axe { fill: var(--v-carte); stroke: var(--v-texte); stroke-width: 1.5; }
  .h-circuit .num { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; } .h-circuit .unite { font-size: 8px; letter-spacing: .4em; fill: var(--v-texte2); }

  .h-cockpit { font-family: Consolas, "Roboto Mono", "DejaVu Sans Mono", monospace; }
  .h-cockpit .bord { stroke-width: 2.6; } .h-cockpit .ch { font-size: 9.5px; fill: var(--v-texte); }
  .h-cockpit .a24 path { fill: var(--v-accent); }
  .h-cockpit .num { font-size: 21px; font-weight: 700; } .h-cockpit .unite { font-size: 6.5px; letter-spacing: .5em; fill: var(--v-texte2); }
  .h-cockpit .utc { font-size: 11px; fill: var(--v-accent); letter-spacing: .12em; }

  .h-bourse { font-family: Consolas, "Roboto Mono", "DejaVu Sans Mono", monospace; }
  .h-bourse .tele { display: flex; align-items: baseline; }
  .h-bourse .tele .heure { font-size: min(26vh, 26vw); font-weight: 700; letter-spacing: -.02em; }
  .h-bourse .tele .sec { font-size: min(9vh, 9vw); color: var(--v-accent); margin-left: .12em; }
  .h-bourse .batons { display: flex; align-items: flex-end; gap: .35vw; height: 11vh; width: min(70vw, 110vh); margin-top: 2vh; }
  .h-bourse .batons i { flex: 1; background: var(--v-ligne); border-radius: 1px; } .h-bourse .batons i.fait { background: var(--v-accent); }
  .h-bourse .date { letter-spacing: .16em; font-size: min(2.8vh, 3.8vw); margin-top: 3vh; }

  .h-ecrin { font-family: Georgia, "Times New Roman", serif; }
  .h-ecrin .bord { stroke: var(--v-accent); stroke-width: 1.2; } .h-ecrin .t1 { stroke: var(--v-accent); }
  .h-ecrin .ch { font-size: 12.5px; fill: var(--v-accent); letter-spacing: .04em; }
  .h-ecrin .marque { font-size: 5.6px; letter-spacing: .5em; fill: var(--v-texte2); }
  .h-ecrin .ah, .h-ecrin .am { stroke: none; fill: var(--v-texte); } .h-ecrin .as { stroke-width: .6; } .h-ecrin .axe { fill: var(--v-accent); }
  .h-ecrin .date { font-style: italic; letter-spacing: .04em; }

  .h-prairie .ciel-arc { width: min(72vw, 96vh); height: auto; overflow: visible; }
  .h-prairie .piste { stroke-dasharray: 1 6; stroke-width: 2; } .h-prairie .sol { stroke: var(--v-texte2); stroke-width: 1; }
  .h-prairie .astre circle { fill: var(--v-accent); } .h-prairie .astre.lune circle { fill: var(--v-texte2); }
  .h-prairie .heure { font-size: min(20vh, 24vw); margin-top: 2vh; }

  .h-large .heure { font-weight: 200; }
  .h-large .houle { width: min(80vw, 120vh); height: 9vh; margin-top: 3vh; overflow: hidden; }
  .h-large .houle path { fill: none; stroke: var(--v-accent); stroke-width: 2.2; stroke-linecap: round; animation: houle 7s linear infinite; }
  .h-large .houle .v2 { stroke: var(--v-texte2); opacity: .55; animation-duration: 11s; animation-direction: reverse; }
  @keyframes houle { from { transform: translateX(0); } to { transform: translateX(-100px); } }

  .h-sommet .heure { font-weight: 600; letter-spacing: .01em; }
  .h-sommet .crete { width: min(84vw, 126vh); height: 20vh; margin-top: 2vh; }
  .h-sommet .loin { fill: var(--v-ligne); } .h-sommet .pres { fill: var(--v-texte2); opacity: .75; } .h-sommet .neige { fill: var(--v-carte); }

  .h-sous-bois .piste { stroke-width: 1; }
  .h-sous-bois .c1, .h-sous-bois .c2, .h-sous-bois .c3 { fill: none; stroke-linecap: round; stroke-width: 6; stroke: var(--v-accent); }
  .h-sous-bois .c2 { stroke: var(--v-texte); stroke-width: 4.5; } .h-sous-bois .c3 { stroke: var(--v-texte2); stroke-width: 3; }
  .h-sous-bois .rond .heure { font-size: min(11vh, 14vw); font-weight: 300; }
`;


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
    for (const c of this._cartes) { try { c.hass = this._pourCartes(); } catch (e) { /* une carte en panne ne bloque pas les autres */ } }
    if (!this._pret) { this._pret = true; this._demarrer(); }
  }
  set narrow(v) {} set route(v) {} set panel(v) {}

  // Les cartes reçoivent Home Assistant avec le mode clair ou sombre du thème de l'appareil : la carte du lieu,
  // les graphiques et les cartes de la communauté s'y fient pour choisir leurs propres teintes.
  _pourCartes() {
    const h = this._hass;
    if (!h || this._sombre === undefined) return h;
    if (this._hassVu !== h) { this._hassVu = h; this._hassCartes = { ...h, themes: { ...(h.themes || {}), darkMode: this._sombre } }; }
    return this._hassCartes;
  }

  // Un mélange de deux couleurs : « part » de la seconde dans la première.
  _melange(a, b, part) {
    const x = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16)), y = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
    return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * part).toString(16).padStart(2, "0")).join("");
  }

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
    // Tout ce que Home Assistant colore de lui-même d'après son propre mode (champs, listes, interrupteurs,
    // curseurs, états éteints, graphiques) est ramené aux couleurs de l'appareil : sinon un thème clair
    // garde des champs noirs, et un thème sombre des aplats gris.
    const doux = this._melange(carte, texte, 0.07), moyen = this._melange(carte, texte, 0.14), fort = this._melange(carte, texte, 0.28);
    const accentDoux = this._melange(carte, accent, 0.22), eteint = this._melange(carte, texte2, 0.55);
    Object.assign(vars, {
      "--input-fill-color": doux, "--input-ink-color": texte, "--input-label-ink-color": texte2, "--input-idle-line-color": ligne,
      "--input-hover-line-color": texte2, "--input-disabled-fill-color": doux, "--input-disabled-ink-color": texte2, "--input-dropdown-icon-color": texte2,
      "--mdc-text-field-fill-color": doux, "--mdc-text-field-ink-color": texte, "--mdc-text-field-label-ink-color": texte2,
      "--mdc-text-field-idle-line-color": ligne, "--mdc-select-fill-color": doux, "--mdc-select-ink-color": texte,
      "--mdc-select-label-ink-color": texte2, "--mdc-select-dropdown-icon-color": texte2, "--mdc-select-idle-line-color": ligne,
      "--mdc-theme-text-primary-on-background": texte, "--mdc-theme-text-secondary-on-background": texte2, "--mdc-theme-on-primary": fond,
      "--ha-color-form-background": doux, "--clear-background-color": fond, "--primary-background-color-rgb": this._rvb(fond),
      "--state-inactive-color": eteint, "--state-unavailable-color": fort, "--disabled-color": fort, "--state-off-color": eteint,
      "--switch-checked-button-color": accent, "--switch-checked-track-color": accent, "--switch-unchecked-button-color": eteint,
      "--switch-unchecked-track-color": fort, "--switch-checked-color": accent, "--slider-track-color": moyen, "--slider-color": accent,
      "--md-sys-color-primary": accent, "--md-sys-color-on-primary": fond, "--md-sys-color-surface": carte, "--md-sys-color-on-surface": texte,
      "--md-sys-color-on-surface-variant": texte2, "--md-sys-color-surface-variant": moyen, "--md-sys-color-outline": ligne,
      "--md-sys-color-surface-container": doux, "--md-sys-color-surface-container-high": doux, "--md-sys-color-surface-container-highest": moyen,
      "--md-sys-color-secondary-container": accentDoux, "--md-sys-color-on-secondary-container": texte,
      "--control-select-background": moyen, "--control-slider-background": accent, "--control-number-buttons-background-color": texte,
      "--info-color": accent, "--scrollbar-thumb-color": "transparent", "--rgb-disabled": this._rvb(fort), "--rgb-state-inactive-color": this._rvb(eteint),
      "--graph-color-1": accent, "--graph-color-2": "#5B8FD9", "--graph-color-3": "#4FAE8C", "--graph-color-4": "#D9705F", "--graph-color-5": "#9C7AD1", "--graph-color-6": "#49A9C2",
      "--v-ligne": ligne, "--v-doux": doux, "--v-moyen": moyen, "--v-fort": fort, "--v-eteint": eteint, "--v-accent-doux": this._melange(carte, accent, 0.38),
    });
    for (const fam of ["neutral", "primary"]) {
      const base = fam === "primary" ? accent : texte;
      const fills = { quiet: this._melange(carte, base, 0.08), normal: this._melange(carte, base, 0.16), loud: fam === "primary" ? accent : this._melange(carte, base, 0.6) };
      for (const [force, c] of Object.entries(fills)) {
        for (const etat of ["resting", "hover", "active"]) vars[`--ha-color-fill-${fam}-${force}-${etat}`] = c;
        vars[`--ha-color-on-${fam}-${force}`] = force === "loud" ? fond : (fam === "primary" ? accent : texte);
        vars[`--ha-color-border-${fam}-${force}`] = force === "quiet" ? ligne : this._melange(carte, base, 0.4);
      }
    }
    // L'échelle de la couleur principale (interrupteurs, curseurs) part de l'accent de l'appareil.
    for (const n of [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95]) {
      vars[`--ha-color-primary-${String(n).padStart(2, "0")}`] = n <= 50 ? this._melange("#000000", accent, 0.25 + 0.75 * n / 50) : this._melange(accent, carte, (n - 50) / 50 * 0.85);
    }
    for (const n of ["default", "low", "lower", "lowest", "raised"]) vars[`--ha-color-surface-${n}`] = carte;
    // Le style graphique (formes, bordures, lettres) est distinct des couleurs : chacun choisit les deux.
    this._style = this._q.get("style") === "neoretro" ? "neoretro" : "doux";
    if (this._style === "neoretro") {
      Object.assign(vars, {
        "--ha-card-border-radius": "3px", "--ha-card-border-width": "0px", "--ha-card-border-color": "transparent",
        "--ha-font-family-body": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--primary-font-family": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--paper-font-common-base_-_font-family": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--chip-border-radius": "3px", "--chip-border-width": "0px", "--mush-chip-border-radius": "3px",
        "--ha-card-header-font-family": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--ha-font-family-heading": "Bahnschrift, 'DIN Alternate', 'Roboto Condensed', 'Segoe UI', sans-serif",
        "--mush-control-border-radius": "3px", "--mush-icon-border-radius": "3px", "--ha-border-radius-md": "3px", "--ha-border-radius-lg": "3px",
        "--ha-border-radius-sm": "2px", "--ha-border-radius-xl": "3px", "--ha-border-radius-pill": "3px", "--control-button-border-radius": "3px",
        "--feature-border-radius": "3px", "--tile-icon-border-radius": "3px", "--ha-tile-icon-border-radius": "3px",
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
    // La carte du lieu : des teintes calmes, proches du fond, dans les deux modes.
    this.style.setProperty("--v-plan", this._sombre ? "grayscale(1) contrast(0.9)" : "saturate(0.55) contrast(0.94) sepia(0.12)");
    this._feuille = null;
    this._jetons = Object.entries(vars).filter(([k]) => k.startsWith("--ha-color-") || k.startsWith("--md-sys-color-")).map(([k, v]) => `${k}: ${v} !important;`).join(" ");
    // Home Assistant passe lui-même en clair ou en sombre, comme le thème de l'appareil : ses composants
    // (interrupteurs, curseurs, carte du lieu) choisissent alors les bonnes nuances d'eux-mêmes.
    try { this.dispatchEvent(new CustomEvent("settheme", { detail: { dark: this._sombre }, bubbles: true, composed: true })); } catch (e) { /* le thème du compte reste */ }
    this.setAttribute("data-style", this._style);
    // Posées aussi à la racine de la page : les teintes que Home Assistant en déduit là-haut (interrupteurs,
    // boutons) se recalculent alors avec les couleurs de l'appareil.
    for (const [k, v] of Object.entries(vars)) { this.style.setProperty(k, v); document.documentElement.style.setProperty(k, v); }
    document.body.style.background = fond;
  }
  _rvb(h) { return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(", "); }

  // Une veille se regarde, elle ne se touche pas : les boutons, menus, flèches et champs de saisie des cartes
  // n'ont rien à y faire. Cette feuille de style est posée dans chaque carte, jusque dans ses éléments internes.
  _regles() {
    const net = this._style === "neoretro";
    return `
      :host { ${this._jetons} }
      :host(ha-switch) {
        --ha-switch-checked-background-color: var(--v-accent-doux) !important; --ha-switch-checked-background-color-hover: var(--v-accent-doux) !important;
        --ha-switch-checked-border-color: var(--v-accent-doux) !important; --ha-switch-checked-border-color-hover: var(--v-accent-doux) !important;
        --ha-switch-checked-thumb-background-color: var(--v-accent) !important; --ha-switch-checked-thumb-background-color-hover: var(--v-accent) !important;
        --ha-switch-checked-thumb-border-color: var(--v-accent) !important; --ha-switch-checked-thumb-border-color-hover: var(--v-accent) !important;
        --ha-switch-background-color: var(--v-moyen) !important; --ha-switch-background-color-hover: var(--v-moyen) !important;
        --ha-switch-border-color: var(--v-fort) !important; --ha-switch-thumb-background-color: var(--v-eteint) !important;
        --ha-switch-thumb-background-color-hover: var(--v-eteint) !important; --ha-switch-thumb-border-color: var(--v-eteint) !important; --ha-switch-thumb-border-color-hover: var(--v-eteint) !important;
      }
      :host(ha-slider), :host(wa-slider), ha-slider {
        --track-color-inactive: var(--v-moyen) !important; --track-color-active: var(--v-accent) !important; --thumb-color: var(--v-accent) !important;
        --ha-slider-track-color: var(--v-moyen) !important; --ha-slider-indicator-color: var(--v-accent) !important; --ha-slider-thumb-color: var(--v-accent) !important;
        --wa-color-neutral-fill-normal: var(--v-moyen) !important; --wa-color-brand-fill-loud: var(--v-accent) !important; --wa-form-control-activated-color: var(--v-accent) !important;
        --md-sys-color-surface-container-highest: var(--v-moyen) !important; --md-slider-inactive-track-color: var(--v-moyen) !important;
      }
      ::-webkit-scrollbar { display: none !important; }
      * { scrollbar-width: none !important; }
      ha-icon-button, ha-button-menu, ha-icon-next, ha-icon-button-next, ha-icon-button-prev, mwc-icon-button, .more-info { display: none !important; }
      hui-target-temperature-card-feature, hui-numeric-input-card-feature, hui-select-options-card-feature, hui-counter-actions-card-feature,
      hui-update-actions-card-feature, hui-cover-open-close-card-feature, hui-valve-open-close-card-feature, hui-button-card-feature,
      hui-climate-hvac-modes-card-feature, hui-climate-preset-modes-card-feature, hui-climate-fan-modes-card-feature,
      hui-water-heater-operation-modes-card-feature, hui-alarm-modes-card-feature, hui-vacuum-commands-card-feature,
      hui-lawn-mower-commands-card-feature, hui-lock-commands-card-feature, hui-media-player-playback-card-feature { display: none !important; }
      mushroom-number-value-control, mushroom-select-option-control, mushroom-climate-temperature-control, mushroom-climate-hvac-modes-control,
      mushroom-media-player-media-control, mushroom-media-player-volume-control, mushroom-cover-buttons-control, mushroom-fan-percentage-control { display: none !important; }
      :host(mushroom-number-card) .actions, :host(mushroom-select-card) .actions, :host(mushroom-climate-card) .actions,
      :host(mushroom-media-player-card) .actions, :host(mushroom-cover-card) .actions, :host(mushroom-fan-card) .actions { display: none !important; }
      :host(ha-full-calendar) .header { display: none !important; }
      :host(hui-todo-list-card) .addRow { display: none !important; }
      .leaflet-top, .leaflet-control-zoom { display: none !important; }
      .leaflet-tile-pane { filter: var(--v-plan) !important; }
      :host(hui-media-control-card) .background.off, :host(hui-media-control-card) .background.unavailable { display: none !important; }
      :host(hui-media-control-card) .background.off ~ .player, :host(hui-media-control-card) .background.unavailable ~ .player { color: var(--v-texte) !important; }
      :host(hui-media-control-card) .controls { display: none !important; }
      ${net ? `
      .card-header { text-transform: uppercase; letter-spacing: .16em; font-size: 15px !important; font-weight: 400 !important; color: var(--v-accent) !important; line-height: 1.4 !important; padding-bottom: 8px !important; }
      :host(ha-card) { border-radius: 3px !important; }
      ` : ""}`;
  }

  _percer(racine) {
    if (!this._feuille) { try { this._feuille = new CSSStyleSheet(); this._feuille.replaceSync(this._regles()); } catch (e) { this._feuille = false; } }
    if (!this._feuille) return;
    const voir = (noeud) => {
      const r = noeud.shadowRoot;
      if (r) {
        try { if (!r.adoptedStyleSheets.includes(this._feuille)) r.adoptedStyleSheets = [...r.adoptedStyleSheets, this._feuille]; } catch (e) { /* cette carte garde son allure */ }
        for (const x of r.children) voir(x);
      }
      for (const x of noeud.children) voir(x);
    };
    try { voir(racine); } catch (e) { /* sans gravité */ }
  }

  // Avec « diag=1 » dans l'adresse, les temps de chargement s'écrivent en haut de l'écran.
  _note(texte) {
    if (!this._q || !["1", "3"].includes(this._q.get("diag"))) return;
    if (this._q.get("diag") === "3") console.log(`VISION ${((Date.now() - this._debut) / 1000).toFixed(1)} s  ${texte}`);
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
    this._sans = new Set((this._q.get("sans") || "").split(",").filter(Boolean));
    this._theme();
    this.shadowRoot.innerHTML = `
      <style>
        :host { position: fixed; inset: 0; z-index: 9999; background: var(--v-fond); color: var(--v-texte); overflow: hidden; cursor: none;
                font-family: "Segoe UI", Roboto, sans-serif; }
        * { cursor: none !important; }
        .scene { position: absolute; inset: 0; opacity: 0; transition: opacity .6s ease; pointer-events: none; }
        .scene.vue { opacity: 1; }
        .horloge { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; }
        .heure { font-size: min(26vh, 30vw); font-weight: 300; line-height: 1; letter-spacing: -.02em; }
        .date { font-size: min(4.6vh, 6vw); color: var(--v-texte2); margin-top: 2vh; }
        .ciel { font-size: min(3.8vh, 5vw); color: var(--v-accent); margin-top: 3vh; }
        /* Anti-marquage : tout dérive de quelques points au fil des minutes (écrans OLED, vieilles dalles). */
        @keyframes derive { 0% { transform: translate(0, 0); } 25% { transform: translate(.5vw, .35vh); } 50% { transform: translate(0, .7vh); } 75% { transform: translate(-.5vw, .35vh); } 100% { transform: translate(0, 0); } }
        .scene, .marque { animation: derive 420s linear infinite; }
        :host([data-fixe]) .scene, :host([data-fixe]) .marque { animation: none; }
        .annonce { position: absolute; right: 3.5vw; bottom: 2.6vh; z-index: 6; max-width: 60vw; padding: .9vh 2.2vh; border-radius: 99px; background: var(--v-carte); color: var(--v-texte2);
                   font-size: min(2.4vh, 3.6vw); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; opacity: 0; transition: opacity .5s ease; }
        .annonce::before { content: ""; display: inline-block; width: 1.1vh; height: 1.1vh; border-radius: 50%; background: var(--v-accent); margin-right: 1.2vh; }
        .annonce.vu { opacity: .96; }
        :host([data-style="neoretro"]) .annonce { border-radius: 3px; letter-spacing: .06em; }
        :host([data-style="neoretro"]) .annonce::before { border-radius: 0; }
        .fige { position: absolute; left: 0; right: 0; text-align: center; bottom: 3vh; z-index: 6; pointer-events: none; font-size: min(2.4vh, 4vw); letter-spacing: .14em; text-transform: uppercase; color: var(--v-texte2); opacity: 0; transition: opacity .4s ease; }
        .fige.vu { opacity: .95; }
        .tete { display: flex; justify-content: space-between; align-items: baseline; padding: 3.2vh 3.5vw 1.6vh; }
        .titre { font-size: min(3.6vh, 6.5vw); font-weight: 600; }
        .petite { font-size: min(3.2vh, 5.5vw); color: var(--v-texte2); }
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
        :host([data-style="neoretro"]) .h-defaut .heure { font-weight: 300; letter-spacing: .04em; font-variant-numeric: tabular-nums; font-size: min(30vh, 28vw); }
        :host([data-style="neoretro"]) .h-defaut::before { content: "VISION"; letter-spacing: .6em; font-size: 2.2vh; color: var(--v-accent); margin-bottom: 4vh; padding-left: .6em; }
        :host([data-style="neoretro"]) .h-defaut .date { text-transform: uppercase; letter-spacing: .3em; font-size: min(3vh, 4.2vw); margin-top: 3vh; padding-top: 3vh; border-top: 1.5px solid var(--v-accent); min-width: 46vw; text-align: center; }
        :host([data-style="neoretro"]) .h-defaut .ciel { text-transform: uppercase; letter-spacing: .3em; font-size: min(2.6vh, 3.8vw); }
        /* La marque, en bas à gauche : l'œil de Vision (le même que sur les télés) et son nom. */
        .marque { position: absolute; left: 3.5vw; bottom: 1.6vh; height: 7vh; display: flex; align-items: center; z-index: 5; pointer-events: none; }
        .marque span { margin-left: 1vh; font-size: 2.6vh; font-weight: 700; letter-spacing: .12em; color: var(--v-texte2); opacity: .9; }
        mushroom-chips-card { margin-bottom: 4px; }
        ${CSS_HORLOGES}
        .vide { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--v-texte2); font-size: 3vh; }
      </style>
      <div class="marque"><canvas></canvas><span>Vision</span></div><div class="fige"></div><div class="annonce"></div>
      <div class="scene vue" id="s0">${this._horloge("")}</div>`;
    // L'heure s'affiche tout de suite ; les tableaux arrivent dès que Home Assistant a répondu.
    this._tic();
    // L'appli Android garde son propre dessin tant que cette page n'a pas dit qu'elle est là.
    try { if (window.VisionAndroid && window.VisionAndroid.pret) window.VisionAndroid.pret(); } catch (e) { /* hors de l'appli */ }
    // Plusieurs écrans : jamais la même chose sur deux d'entre eux. L'heure est sur le premier dès l'ouverture ;
    // les autres attendent leur tableau sans la répéter.
    const nbEcrans = parseInt(this._q.get("ecrans") || "1", 10) || 1;
    this._rang = parseInt(this._q.get("dec") || "0", 10) || 0;
    if (nbEcrans > 1 && this._rang > 0) this.shadowRoot.querySelector("#s0 .horloge").style.visibility = "hidden";
    let page = null, aides = null;
    try {
      [page, aides] = await Promise.all([
        this._hass.callApi("GET", `pc_parental/veille/page?id=${encodeURIComponent(this._q.get("id") || "")}&ecran=${encodeURIComponent(this._q.get("ecran") || "tele")}&essai=${encodeURIComponent(this._q.get("essai") || "")}`).then((r) => { this._note("page : reçue"); return r; }),
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
    // Chaque appareil peut donner sa durée à chaque tableau (« durees=horloge:20,dash_x_y:35 »).
    const durees = {};
    for (const m of (this._q.get("durees") || "").split(",")) { const k = m.lastIndexOf(":"); const v = parseInt(m.slice(k + 1), 10); if (k > 0 && v > 0) durees[m.slice(0, k)] = Math.max(5, Math.min(600, v)); }
    if (this._page.horloge && this._page.horloge.actif && !masques.has("horloge")) liste.push({ genre: "horloge", duree: durees.horloge || this._page.horloge.duree || 15 });
    for (const t of this._page.tableaux || []) {
      if (masques.has(t.id)) continue;
      const sections = [];
      for (const s of t.sections || []) {
        const cartes = (s.cartes || []).filter((c) => !cachees.has(`${t.id}|${c.cle}`) && !(c.cles && c.cles.length && c.cles.every((k) => cachees.has(`${t.id}|${k}`))));
        // Une section dont il ne reste que le titre (toutes ses cartes sont décochées) disparaît avec lui.
        if (cartes.some((c) => c.config && c.config.type !== "heading")) sections.push({ titre: s.titre, span: s.span || 1, cartes });
      }
      if (durees[t.id]) t.duree = durees[t.id];
      if (parseInt(this._q.get("duree") || "0", 10) > 0) t.duree = parseInt(this._q.get("duree"), 10);
      if (sections.length) liste.push({ genre: "tableau", duree: t.duree || 25, titre: t.titre, colonnes: t.colonnes || 4, sections, pages: 1, page: 0 });
    }
    if (!liste.length) liste.push({ genre: "horloge", duree: 30 });
    this._ecrans = liste;
    this._indice = this._rang % liste.length;
    setInterval(() => this._tic(), 1000);
    this._oeil();
    // Les écrans avancent ensemble, au même pas, chacun décalé d'un cran : l'écran 1 montre l'horloge quand le 2
    // montre le premier tableau, puis le 1 passe au premier tableau et le 2 au suivant, et ainsi de suite.
    // L'heure de départ commune (donnée par l'appareil) et l'horloge du système tiennent les écrans d'accord.
    this._synchro = nbEcrans > 1 && liste.length > 1;
    if (this._synchro) {
      this._t0 = parseInt(this._q.get("t0") || "0", 10) || 0;
      const impose = parseInt(this._q.get("duree") || "0", 10);
      this._pas = impose > 0 ? Math.max(5, impose) : Math.max(12, Math.round(liste.reduce((a, x) => a + (x.duree || 20), 0) / liste.length));
      this._montrer();
      return;
    }
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
      if (!this._sans.has("oeil")) requestAnimationFrame(pas);
    };
    pas();
  }

  // Chaque thème a son horloge (« horloge=<thème> » dans l'adresse) ; sans thème connu, celle de Vision.
  _horloge(ciel) {
    const cle = HORLOGES[this._q.get("horloge") || ""] ? this._q.get("horloge") : "defaut";
    const d = new Date(), maj = (t) => t.charAt(0).toUpperCase() + t.slice(1);
    const jour = maj(d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }));
    const jourCourt = maj(d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }));
    return `<div class="horloge h-${cle}" data-cle="${cle}">${HORLOGES[cle].html({ jour, jourCourt, ciel: ciel || "" })}</div>`;
  }

  _tic() {
    const d = new Date();
    const h = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    this.shadowRoot.querySelectorAll(".petite").forEach((e) => { if (e.textContent !== h) e.textContent = h; });
    this.shadowRoot.querySelectorAll(".horloge").forEach((e) => { try { HORLOGES[e.dataset.cle].tic(e, d); } catch (err) { /* l'horloge garde son dernier dessin */ } });
  }

  _carte(config) {
    let el;
    try { el = this._aides ? this._aides.createCardElement(config) : null; } catch (e) { el = null; }
    if (!el) return null;
    try { el.hass = this._pourCartes(); } catch (e) { /* idem */ }
    this._cartes.push(el);
    // La largeur voulue dans Home Assistant (sur 12), reprise telle quelle.
    let colonnes = 12;
    const o = config.grid_options || config.layout_options || {};
    const v = o.columns ?? o.grid_columns;
    if (v === "full") colonnes = 12;
    else if (typeof v === "number") colonnes = Math.max(3, Math.min(12, v));
    else { try { const g = el.getGridOptions && el.getGridOptions(); if (g && typeof g.columns === "number") colonnes = Math.max(3, Math.min(12, g.columns)); } catch (e) { /* 12 */ } }
    el.style.gridColumn = `span ${colonnes}`;
    // Sans largeur écrite dans le tableau de bord, c'est la carte qui dit la sienne ; elle ne la connaît
    // qu'une fois chargée, on la relit donc au moment de mesurer.
    if (v === undefined) el._largeurLibre = true;
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

  // L'appli garde cette page chargée entre deux veilles, pour qu'elle apparaisse tout de suite. Entre-temps
  // elle dort : plus de défilement, plus de cartes à tenir à jour, seule l'horloge reste prête.
  dormir() {
    this._dort = true; this._fige = false;
    this._passage = (this._passage || 0) + 1;
    clearTimeout(this._minuteur);
    this._cartes = [];
    for (const e of this._ecrans) { if (e.genre === "tableau") { e.page = 0; e._colonnes = null; } }
    this.shadowRoot.querySelectorAll(".scene").forEach((x) => x.remove());
    const scene = document.createElement("div");
    scene.className = "scene vue";
    scene.innerHTML = this._horloge("");
    this.shadowRoot.appendChild(scene);
    const f = this.shadowRoot.querySelector(".fige"); if (f) f.classList.remove("vu");
    this._tic();
  }
  // La veille s'ouvre : on repart du début (l'horloge si elle est montrée), avec des cartes fraîches.
  reprendre() {
    const dormait = this._dort;
    this._dort = false; this._fige = false;
    if (!this._ecrans.length) return;
    if (!dormait && this.shadowRoot.querySelector(".scene .grille")) return;
    this._indice = this._rang % this._ecrans.length;
    for (const e of this._ecrans) { if (e.genre === "tableau") e.page = 0; }
    this._tic();
    this._montrer();
  }

  // Les gestes de l'appareil (télécommande, doigt) : précédent, suivant, figer.
  aller(delta) {
    if (!this._ecrans.length) return;
    clearTimeout(this._minuteur);
    if (this._synchro) { this._montrer(); return; }
    if (delta > 0) { this._suivant(true); return; }
    const e = this._ecrans[this._indice];
    if (e.genre === "tableau" && e.page > 0) e.page -= 1;
    else { if (e.genre === "tableau") e.page = 0; const n = this._ecrans.length; this._indice = (this._indice - 1 + n) % n; const p = this._ecrans[this._indice]; if (p.genre === "tableau") p.page = 0; }
    this._montrer();
  }
  // Un mot de l'appareil, en bas à droite (une demande d'accès en attente, par exemple) ; vide pour l'effacer.
  annoncer(texte) {
    const b = this.shadowRoot.querySelector(".annonce");
    if (!b) return;
    if (texte) b.textContent = String(texte).slice(0, 140);
    b.classList.toggle("vu", !!texte);
  }
  figer() {
    this._fige = !this._fige;
    const f = this.shadowRoot.querySelector(".fige");
    if (f) { f.textContent = this._fige ? "Figé" : "Reprise"; f.classList.add("vu"); clearTimeout(this._figeT); if (!this._fige) this._figeT = setTimeout(() => f.classList.remove("vu"), 1500); }
    clearTimeout(this._minuteur);
    if (!this._fige) this._minuteur = setTimeout(() => (this._synchro ? this._montrer() : this._suivant()), 4000);
    return this._fige;
  }

  // Avec « diag=3 », chaque image qui tarde (plus de 50 ms) s'écrit avec l'étape en cours : c'est ce qui se voit comme une secousse.
  _sonde() {
    if (this._sondeLancee || !this._q || this._q.get("diag") !== "3") return;
    this._sondeLancee = true;
    let avant = performance.now();
    // Un bilan toutes les deux secondes, pour que la sonde ne pèse pas elle-même sur l'affichage.
    let n = 0, lentes = 0, pire = 0, etapes = new Set();
    const pas = (t) => { const d = t - avant; avant = t; n++; if (d > 34) { lentes++; pire = Math.max(pire, d); etapes.add(this._etape || "-"); } requestAnimationFrame(pas); };
    requestAnimationFrame(pas);
    const bilan = [];
    setInterval(() => { bilan.push(`${n}/${lentes}${etapes.has("pose") ? "p" : ""}`); document.title = "VISION " + bilan.join(" "); this._note(`${n} images, ${lentes} lentes, pire ${Math.round(pire)} ms  [${[...etapes].join(" ")}]`); n = 0; lentes = 0; pire = 0; etapes = new Set(); }, 2000);
    if (this._q.get("derive") === "0") this.setAttribute("data-fixe", "1");
    // D'où vient le temps perdu : script (lequel), calcul des styles et de la mise en page, ou dessin.
    try {
      let dits = 0;
      new PerformanceObserver((liste) => {
        for (const f of liste.getEntries()) {
          if (this._etape !== "pose" || dits >= 6) continue;
          dits++;
          const fin = f.startTime + f.duration;
          const scripts = (f.scripts || []).map((x) => `${Math.round(x.duration)} ms ${x.invoker || "?"} ${x.sourceFunctionName || ""} ${(x.sourceURL || "").split("/").pop().slice(0, 40)} (mise en page forcée ${Math.round(x.forcedStyleAndLayoutDuration || 0)})`).join("\n            ");
          this._note(`longue ${Math.round(f.duration)} ms : scripts jusqu'à ${Math.round((f.renderStart || fin) - f.startTime)}, rendu ${Math.round((f.styleAndLayoutStart || fin) - (f.renderStart || fin))}, styles et mise en page ${Math.round(fin - (f.styleAndLayoutStart || fin))}\n            ${scripts}`);
        }
      }).observe({ type: "long-animation-frame", buffered: false });
    } catch (err) { this._note("sonde longue : " + err); }
  }

  async _montrer(reste) {
    if (this._dort) return;
    this._sonde();
    this._etape = "cartes";
    const passage = this._passage = (this._passage || 0) + 1;
    let cran = 0;
    if (this._synchro) {
      const n = this._ecrans.length;
      cran = Math.max(0, Math.floor((Date.now() / 1000 - this._t0) / this._pas));
      const p = cran + this._rang;
      this._indice = p % n; this._tour = Math.floor(p / n);
      if (this._ecrans[this._indice].genre === "tableau") this._ecrans[this._indice].page = 0;
    }
    const e = this._ecrans[this._indice];
    const ancienne = this.shadowRoot.querySelector(".scene.vue");
    const scene = document.createElement("div");
    scene.className = "scene";
    if (e.genre === "horloge") {
      const m = this._page.meteo ? this._hass.states[this._page.meteo] : null;
      const morceaux = [];
      if (m && m.attributes && typeof m.attributes.temperature === "number") morceaux.push(`${Math.round(m.attributes.temperature)}°`);
      if (m && CIEL[m.state]) morceaux.push(CIEL[m.state]);
      scene.innerHTML = this._horloge(morceaux.join("  ·  "));
    } else {
      if (e.page === 0 || !e._colonnes) {
        e.page = 0;
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
          for (const c of s.cartes) { const el = this._carte(c.config); if (el && !this._sans.has(el.localName)) bloc.appendChild(el); }
          if (bloc.children.length) blocs.push(bloc);
        }
        // Écran en hauteur (téléphone, tablette debout) : les sections passent les unes sous les autres, comme
        // Home Assistant le fait lui-même sur un téléphone ; l'ordre reste celui du tableau de bord.
        const debout = window.innerWidth < window.innerHeight;
        const voulu = debout ? (window.innerWidth >= 700 ? 2 : 1) : Math.max(1, Math.min(6, e.colonnes || 4));
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
        this._etape = "attente";
        await pause(900);
        if (passage !== this._passage) { scene.remove(); return; }
        this._etape = "mesure";
        this._percer(c);
        await pause(300);
        if (passage !== this._passage) { scene.remove(); return; }
        const cadre = c.parentElement, L = cadre.clientWidth, H = cadre.clientHeight;
        for (const el of c.querySelectorAll(".section > *")) {
          if (!el._largeurLibre) continue;
          if (this._q.get("diag") === "1") { try { this._note(`${el.localName} : ${el.getGridOptions ? JSON.stringify(el.getGridOptions()) : "sans largeur propre"}`); } catch (err) { this._note(`${el.localName} : ${err}`); } }
          try { const g = el.getGridOptions && el.getGridOptions(); if (g && typeof g.columns === "number") el.style.gridColumn = `span ${Math.max(3, Math.min(12, g.columns))}`; } catch (err) { /* reste pleine largeur */ }
        }
        await pause(120);
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
      // À plusieurs écrans, un tableau trop grand pour un écran montre sa partie suivante à chaque tour.
      if (this._synchro) { e.page = this._tour % (e.pages || 1); scene.querySelector(".titre").textContent = e.titre + (e.pages > 1 ? `   ${e.page + 1}/${e.pages}` : ""); }
      // L'écran demandé : ses sections seules, à la plus grande taille qui tient, centrées.
      const pg = e._pages[e.page] || e._pages[0];
      if (pg) {
        const hp = Math.max(1, pg.bas - pg.haut);
        const z = this._sans.has("echelle") ? 1 : Math.min(e._L / e._larg, e._H / hp, 2.2) * 0.985;
        for (const s of c.querySelectorAll(".section")) s.style.visibility = pg.sections.includes(s) ? "visible" : "hidden";
        const dx = Math.max(0, (e._L - e._larg * z) / 2), dy = Math.max(0, Math.min((e._H - hp * z) / 2, e._H * 0.1));
        c.style.transform = `translate(${dx}px, ${dy - pg.haut * z}px) scale(${z})`;
      }
    }
    if (e.genre === "tableau") { this._percer(e._colonnes); for (const t of [700, 2000, 4500]) setTimeout(() => this._percer(e._colonnes), t); }
    if (this._q.get("diag") === "3" && e.genre === "tableau") setTimeout(() => {
      try {
        const vus = {};
        for (const a of document.getAnimations()) { if (a.playState !== "running") continue; const c = a.effect && a.effect.target; const hote = c && c.getRootNode && c.getRootNode().host; const k = `${a.animationName || a.transitionProperty || "?"} sur ${c ? c.localName + (c.className && c.className.baseVal === undefined ? "." + c.className : "") : "?"} dans ${hote ? hote.localName : "page"}`; vus[k] = (vus[k] || 0) + 1; }
        this._note("animations : " + (Object.entries(vus).map(([k, n]) => `${n} x ${k}`).join("\n          ") || "aucune"));
      } catch (err) { this._note("animations : " + err); }
    }, 3000);
    this._etape = "fondu"; setTimeout(() => { if (passage === this._passage) this._etape = "pose"; }, 800);
    requestAnimationFrame(() => { scene.classList.add("vue"); if (ancienne) { ancienne.classList.remove("vue"); setTimeout(() => ancienne.remove(), 700); } });
    clearTimeout(this._minuteur);
    if (this._fige) return;
    if (this._synchro) { this._minuteur = setTimeout(() => this._montrer(), Math.max(2500, ((cran + 1) * this._pas + this._t0) * 1000 - Date.now())); return; }
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

  _suivant(force) {
    if (this._dort) return;
    const e = this._ecrans[this._indice];
    if (e.genre === "tableau" && e.page + 1 < e.pages) e.page += 1;
    else { if (e.genre === "tableau") e.page = 0; this._indice = (this._indice + 1) % this._ecrans.length; }
    if (this._ecrans.length === 1 && e.genre === "horloge" && !force) { this._minuteur = setTimeout(() => this._suivant(), 60000); return; }
    this._montrer();
  }
}

if (!customElements.get("vision-veille-coeur")) customElements.define("vision-veille-coeur", VisionVeillePanel);
