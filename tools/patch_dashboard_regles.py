"""Tableau Vision : montrer, par PC, les catégories coupées en plus par les
règles (moyenne, planning), avec la raison. À exécuter sur HA."""
import shutil
BASE = "/homeassistant/custom_components/pc_parental/"

p = BASE + "sensor.py"
s = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakregles")
assert "categories_coupees" not in s
old = '''            "agent_en_ligne": self.coordinator.agent_online(self.pc_id),
            # Ce que l'agent applique vraiment, une fois les étiquettes et'''
new = '''            "agent_en_ligne": self.coordinator.agent_online(self.pc_id),
            # Les catégories fermées en plus par une règle (moyenne, planning) :
            # l'interrupteur de l'étiquette est à « non », et pourtant c'est coupé.
            "categories_coupees": self._categories_coupees(),
            # Ce que l'agent applique vraiment, une fois les étiquettes et'''
assert old in s
s = s.replace(old, new, 1)
old = '''    def _effectif(self) -> dict[str, Any]:'''
new = '''    def _categories_coupees(self) -> list[str]:
        magasin = self.coordinator.store
        pc = self.pc
        noms: set[str] = set()
        for genre in ("apps", "sites"):
            for ets in (magasin.etiquettes.get(genre) or {}).values():
                noms.update(str(e) for e in (ets or []))
        sortie = []
        for nom in sorted(noms, key=str.lower):
            if nom.lower() in ("parents", "enfants"):
                continue
            try:
                if magasin.moyenne_ferme(pc, [nom]):
                    sortie.append("{} : {}".format(nom, magasin.moyenne_raison(pc)))
                    continue
                regle = magasin.plage_ferme(pc, nom)
                if regle:
                    sortie.append("{} : planning « {} »".format(nom, regle.get("name") or "plage"))
            except Exception:  # noqa: BLE001
                continue
        return sortie

    def _effectif(self) -> dict[str, Any]:'''
assert old in s
s = s.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(s)

p = BASE + "dashboard.py"
d = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakregles")
assert "categories_coupees" not in d
old = '''    if coupes:
        cartes.append(
            {
                "type": "heading",
                "heading": "Étiquettes coupées sur ce PC",
                "heading_style": "subtitle",
                "icon": "mdi:tag-off-outline",
            }'''
new = '''    # Ce que les règles coupent en plus, en ce moment : la moyenne et le
    # planning ferment des catégories sans toucher aux interrupteurs. Sans
    # cette ligne, Discord est fermé chez Jules et le tableau n'en dit rien.
    if etat_eid := _eid(hass, "sensor", f"{DOMAIN}_etat_{pc_id}"):
        cartes.append(
            {
                "type": "markdown",
                "content": (
                    "{% set l = state_attr('" + etat_eid + "', 'categories_coupees') or [] %}"
                    "{% if l %}**Coupé en plus par les règles, en ce moment**\\n"
                    "{% for x in l %}- {{ x }}\\n{% endfor %}"
                    "{% else %}_Rien de coupé en plus par la moyenne ou le planning._{% endif %}"
                ),
            }
        )
    if coupes:
        cartes.append(
            {
                "type": "heading",
                "heading": "Étiquettes coupées sur ce PC",
                "heading_style": "subtitle",
                "icon": "mdi:tag-off-outline",
            }'''
assert old in d
d = d.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(d)
import py_compile
for f in ("sensor.py", "dashboard.py"):
    py_compile.compile(BASE + f, doraise=True)
print("ok")
