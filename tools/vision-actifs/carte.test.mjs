// Essai de la carte du tableau de bord, hors Home Assistant : un faux « hass » qui rend la maison
// et retient les gestes envoyés. Usage : node carte.test.mjs <maison.json> <dossier des photos>
import { chromium } from "playwright";
import fs from "fs";
const [, , donnees, sortie] = process.argv;
const js = fs.readFileSync(new URL("../vision-maison/vision-maison-card.js", import.meta.url), "utf8");
const maison = fs.readFileSync(donnees, "utf8");
const nav = await chromium.launch();
const page = await nav.newPage({ viewport: { width: 900, height: 1100 } });
await page.setContent(`<html><body style="background:#fafafa;font-family:sans-serif;--divider-color:#ddd;--primary-color:#8C2F4B;--secondary-text-color:#666;--card-background-color:#fff"><div id="z" style="max-width:820px"></div></body></html>`);
await page.addScriptTag({ content: `customElements.define("ha-card", class extends HTMLElement {}); customElements.define("ha-icon", class extends HTMLElement {});` });
await page.addScriptTag({ content: js });
const erreurs = [];
page.on("pageerror", (e) => erreurs.push(String(e)));
await page.evaluate((m) => {
  window.gestes = [];
  window.monter = (config) => {
    const c = document.createElement("vision-maison-card");
    c.setConfig(config);
    c.hass = { callApi: async (methode, chemin, corps) => { if (corps) window.gestes.push(corps); return JSON.parse(m); } };
    const z = document.getElementById("z"); z.innerHTML = ""; z.appendChild(c); return c;
  };
}, maison);
const racine = () => page.locator("vision-maison-card");
const ok = (cond, quoi) => { console.log((cond ? "ok   " : "ÉCHEC") + " " + quoi); if (!cond) process.exitCode = 1; };

await page.evaluate(() => window.monter({ mode: "maison" }));
await page.waitForTimeout(200);
const lignes = await racine().locator(".ligne").count();
ok(lignes >= 5, `maison : ${lignes} personnes`);
const texte = await racine().locator(".ligne").allInnerTexts();
const ja = texte.find((t) => t.includes("Jacques-Antoine")) || "";
ok(/Pixel 9/.test(ja) && /Téléviseur du salon/.test(ja) && /Télé des parents/.test(ja), "Jacques-Antoine voit son Pixel, sa télé et celle du salon");
ok((texte.find((t) => t.includes("Laetitia")) || "").includes("Télé des parents"), "Laetitia voit la télé des parents");
ok(!texte.some((t) => /^\s*(A\s+)?Affichage/.test(t)), "pas de fausse personne « Affichage »");
await page.screenshot({ path: `${sortie}/carte-1-maison.png`, fullPage: true });

await page.evaluate(() => window.monter({ mode: "personne", personne: "person.jules" }));
await page.waitForTimeout(200);
ok(await racine().locator("[data-duree]").count() === 3, "fiche : +30 min, +1 h, Autre");
await racine().locator('[data-duree="60"]').click();
ok(await racine().locator("[data-choix]").count() === 3, "après la durée, le choix entre ses trois matériels");
await page.screenshot({ path: `${sortie}/carte-2-materiel.png`, fullPage: true });
// On ne garde que le téléphone.
for (const c of await racine().locator("[data-choix]").all()) { if (await c.isChecked()) await c.click(); }
const libelles = await racine().locator(".choix .coche").allInnerTexts();
await racine().locator("[data-choix]").nth(libelles.findIndex((l) => /Pixel/.test(l))).click();
await racine().locator("[data-donner]").click();
await page.waitForTimeout(100);
let g = await page.evaluate(() => window.gestes.pop());
ok(g && g.action === "temps" && g.minutes === 60 && g.appareils.length === 1, `geste envoyé : ${JSON.stringify(g)}`);
// Durée libre, bornes.
await racine().locator('[data-duree="autre"]').click();
await racine().locator("[data-minutes]").fill("3");
ok(await racine().locator("[data-donner]").isDisabled(), "3 minutes : refusé");
await racine().locator("[data-minutes]").fill("45");
ok(!(await racine().locator("[data-donner]").isDisabled()), "45 minutes : accepté");
await page.screenshot({ path: `${sortie}/carte-3-autre.png`, fullPage: true });
await racine().locator("[data-donner]").click();
await page.waitForTimeout(100);
g = await page.evaluate(() => window.gestes.pop());
ok(g && g.minutes === 45 && g.appareils.length >= 1, `durée libre envoyée : ${g && g.minutes} min sur ${g && g.appareils.length} matériel(s)`);
// Les catégories visent un appareil à lui, jamais la télé partagée.
const cibles = await racine().locator("[data-etq]").evaluateAll((els) => [...new Set(els.map((e) => e.dataset.pc))]);
const d = JSON.parse(maison);
const salon = d.appareils.find((a) => a.partage_tous).id;
ok(cibles.length === 1 && cibles[0] !== salon && d.appareils.find((a) => a.id === cibles[0]).personne === "person.jules", "catégories : posées sur un appareil de Jules");
// Partage.
await racine().locator(`[data-apartage="${salon}"]`).click();
ok(await racine().locator(`[data-partage="${salon}"] [data-tous]`).isChecked(), "télé du salon : « Toute la maison » cochée");
await racine().locator(`[data-partage="${salon}"] [data-tous]`).click();
await page.waitForTimeout(100);
g = await page.evaluate(() => window.gestes.pop());
ok(g && g.action === "partage" && g.tous === false && g.personnes.length === 0, `partage retiré : ${JSON.stringify(g)}`);
ok(erreurs.length === 0, "aucune erreur de script" + (erreurs.length ? " : " + erreurs.join(" | ") : ""));
await nav.close();
