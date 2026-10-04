"""Profil du 04-10 (profiler, 15 s) : chaque relevé d'un appareil (/poll) bloquait
la boucle 11 s : la mise à jour du coordinateur fait recalculer les attributs
de 1 800 interrupteurs et des capteurs, chacun refaisant des parcours complets
du catalogue (`catalogue_maison` 3 766 fois, `statut` 120 000 fois,
`_nom_site` 3,3 millions de fois). Ici : mémoïsation des normalisations de noms
(fonctions pures) et caches courts (5 s, effacés à chaque écriture) sur
`catalogue_maison`, `statut`, `etiquettes_de`.
Usage sur HA : python3 patch_perf_store.py
"""
import py_compile
import shutil

p = "/homeassistant/custom_components/pc_parental/store.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakperf3")


def remplacer(a, b):
    global t
    assert a in t, a[:80]
    t = t.replace(a, b, 1)


# 1. Les fonctions de normalisation, pures : mémoïsées.
remplacer("import copy\n", "import copy\nimport functools\n")
for nom in ("_nom_app(nom: str) -> str:", "_hote(adresse: str) -> str:", "domaine_principal(hote: str) -> str:", "_nom_site(domaine: str) -> str:"):
    remplacer("\ndef " + nom, "\n@functools.lru_cache(maxsize=65536)\ndef " + nom)

# 2. Un petit cache sur le magasin, vidé à chaque écriture.
remplacer(
    "    def catalogue_maison(self, genre: str) -> list[str]:\n",
    "    def _memo(self, cle, ttl, calc):\n"
    "        \"\"\"Valeur gardée `ttl` secondes (et oubliée à chaque écriture) : les relevés déclenchent\n"
    "        des milliers de recalculs identiques dans la même seconde.\"\"\"\n"
    "        memos = getattr(self, \"_memos\", None)\n"
    "        if memos is None:\n"
    "            memos = {}\n"
    "            self._memos = memos\n"
    "        v = memos.get(cle)\n"
    "        now = time.monotonic()\n"
    "        if v is not None and now - v[0] < ttl:\n"
    "            return v[1]\n"
    "        r = calc()\n"
    "        memos[cle] = (now, r)\n"
    "        if len(memos) > 50000:\n"
    "            memos.clear()\n"
    "        return r\n\n"
    "    def catalogue_maison(self, genre: str) -> list[str]:\n"
    "        return list(self._memo((\"catalogue\", genre), 5.0, lambda: self._catalogue_maison_calc(genre)))\n\n"
    "    def _catalogue_maison_calc(self, genre: str) -> list[str]:\n",
)
remplacer(
    "    def etiquettes_de(self, genre: str, nom: str) -> list[str]:\n"
    "        \"\"\"Étiquettes posées sur un logiciel ou un site.\"\"\"\n"
    "        cle = _nom_app(nom) if genre == \"apps\" else _nom_site(nom)\n"
    "        return list(self.etiquettes.get(genre, {}).get(cle) or [])",
    "    def etiquettes_de(self, genre: str, nom: str) -> list[str]:\n"
    "        \"\"\"Étiquettes posées sur un logiciel ou un site.\"\"\"\n"
    "        cle = _nom_app(nom) if genre == \"apps\" else _nom_site(nom)\n"
    "        return list(self._memo((\"etq\", genre, cle), 5.0, lambda: list(self.etiquettes.get(genre, {}).get(cle) or [])))",
)
remplacer(
    "    def statut(self, pc: dict[str, Any], genre: str, nom: str) -> str:\n",
    "    def statut(self, pc: dict[str, Any], genre: str, nom: str) -> str:\n"
    "        return self._memo((\"statut\", (pc or {}).get(\"id\") or \"\", genre, nom), 5.0, lambda: self._statut_calc(pc, genre, nom))\n\n"
    "    def _statut_calc(self, pc: dict[str, Any], genre: str, nom: str) -> str:\n",
)
# 3. Toute écriture vide les mémos (déjà posé pour les autres caches en .bakperf).
remplacer(
    "        self.version_cache = getattr(self, \"version_cache\", 0) + 1\n",
    "        self.version_cache = getattr(self, \"version_cache\", 0) + 1\n"
    "        self._memos = {}\n",
)
open(p, "w", encoding="utf-8").write(t)
py_compile.compile(p, doraise=True)
print("ok perf3")
