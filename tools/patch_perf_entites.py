"""Suite de patch_perf_store.py (profil après celui-ci : /poll encore 3,6 s).
Ce qui restait : les 1 800 interrupteurs d'étiquette recalculaient chacun, à
chaque relevé, la liste des logiciels et sites portant leur étiquette (deux
passages complets du catalogue par interrupteur) ; `_dans` remettait en
minuscules toute la liste à chaque appel (270 000 appels, 5 millions de
comparaisons) ; `effectif` (ce que l'agent applique) était recalculé 54 fois
en 20 s. Ici : un index étiquette → noms partagé (5 s), `_dans` sur des
ensembles mémoïsés, `effectif` gardé 5 s par PC.
Usage sur HA : python3 patch_perf_entites.py
"""
import py_compile
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"


def patch(nom, remplacements, bak):
    p = BASE + nom
    t = open(p, encoding="utf-8").read()
    shutil.copy2(p, p + bak)
    for a, b in remplacements:
        assert a in t, (nom, a[:70])
        t = t.replace(a, b, 1)
    open(p, "w", encoding="utf-8").write(t)
    py_compile.compile(p, doraise=True)


patch("store.py", [
    (
        "    @staticmethod\n"
        "    def _dans(liste: list[str] | None, valeur: str) -> bool:\n"
        "        bas = valeur.strip().lower()\n"
        "        return any((m or \"\").strip().lower() == bas for m in (liste or []))\n",
        "    @staticmethod\n"
        "    def _dans(liste: list[str] | None, valeur: str) -> bool:\n"
        "        bas = valeur.strip().lower()\n"
        "        if not liste:\n"
        "            return False\n"
        "        try:\n"
        "            return bas in _ensemble_bas(tuple(liste))\n"
        "        except TypeError:\n"
        "            return any((m or \"\").strip().lower() == bas for m in liste)\n"
        "\n"
        "    def noms_par_etiquette(self, genre: str, etiquette: str) -> list[str]:\n"
        "        \"\"\"Les logiciels (ou sites) du catalogue qui portent cette étiquette.\n"
        "        Un seul index pour tous les interrupteurs, refait au plus toutes les 5 s.\"\"\"\n"
        "        def _index() -> dict[str, list[str]]:\n"
        "            idx: dict[str, list[str]] = {}\n"
        "            for n in self.catalogue_maison(genre):\n"
        "                for e in self.etiquettes_de(genre, n):\n"
        "                    idx.setdefault(str(e).lower(), []).append(n)\n"
        "            return idx\n"
        "        return list(self._memo((\"index_etq\", genre), 5.0, _index).get(etiquette.lower(), []))\n",
    ),
    (
        "    def effectif(self, pc: dict[str, Any]) -> dict[str, list[str]]:\n",
        "    def effectif(self, pc: dict[str, Any]) -> dict[str, list[str]]:\n"
        "        # Demandé par le relevé de l'agent, le capteur et l'espace parents dans la même\n"
        "        # seconde : calculé une fois par PC toutes les 5 s (et à chaque écriture).\n"
        "        return copy.deepcopy(self._memo((\"effectif\", (pc or {}).get(\"id\") or \"\"), 5.0, lambda: self._effectif_calc(pc)))\n\n"
        "    def _effectif_calc(self, pc: dict[str, Any]) -> dict[str, list[str]]:\n",
    ),
    (
        "\n@functools.lru_cache(maxsize=65536)\ndef _nom_app(",
        "\n@functools.lru_cache(maxsize=4096)\n"
        "def _ensemble_bas(valeurs: tuple) -> frozenset:\n"
        "    \"\"\"Les valeurs d'une liste en minuscules, mémoïsées par contenu : `_dans` est appelé\n"
        "    des centaines de milliers de fois par relevé sur les mêmes listes.\"\"\"\n"
        "    return frozenset((m or \"\").strip().lower() for m in valeurs)\n\n\n"
        "@functools.lru_cache(maxsize=65536)\ndef _nom_app(",
    ),
], ".bakperf4")

patch("switch.py", [
    (
        "            \"logiciels\": [\n"
        "                n\n"
        "                for n in magasin.catalogue_maison(\"apps\")\n"
        "                if any(\n"
        "                    e.lower() == nom.lower()\n"
        "                    for e in magasin.etiquettes_de(\"apps\", n)\n"
        "                )\n"
        "            ],\n"
        "            \"sites\": [\n"
        "                n\n"
        "                for n in magasin.catalogue_maison(\"sites\")\n"
        "                if any(\n"
        "                    e.lower() == nom.lower()\n"
        "                    for e in magasin.etiquettes_de(\"sites\", n)\n"
        "                )\n"
        "            ],\n",
        "            \"logiciels\": magasin.noms_par_etiquette(\"apps\", nom),\n"
        "            \"sites\": magasin.noms_par_etiquette(\"sites\", nom),\n",
    ),
], ".bakperf4")
print("ok perf4")
