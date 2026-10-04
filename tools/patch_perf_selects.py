"""Les trois listes « constaté » (select.comvision_site_*) refaisaient, à chaque
relevé d'un appareil, plusieurs passages complets sur le catalogue avec
`classe()` et `_est_etiquette()` (qui recalculait toutes les étiquettes en
minuscules à chaque appel) : 0,4 s de boucle d'événements bloquée par entité,
plusieurs fois par dix secondes, d'où les poignées de main TLS de 3 s et les
« Home Assistant injoignable » du téléphone. Ici : caches de 5 s.
Usage sur HA : python3 patch_perf_selects.py
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
        "    def a_classer(self, pc: dict[str, Any] | None) -> int:\n"
        "        \"\"\"Combien d'éléments attendent encore une décision sur ce PC.\"\"\"\n"
        "        return sum(",
        "    def a_classer(self, pc: dict[str, Any] | None) -> int:\n"
        "        \"\"\"Combien d'éléments attendent encore une décision sur ce PC (compté au plus toutes les 5 s).\"\"\"\n"
        "        import time as _t\n"
        "        cle = (pc or {}).get(\"id\") or \"\"\n"
        "        cache = getattr(self, \"_cache_a_classer\", None) or {}\n"
        "        if cle in cache and _t.monotonic() - cache[cle][0] < 5:\n"
        "            return cache[cle][1]\n"
        "        n = self._compter_a_classer(pc)\n"
        "        cache[cle] = (_t.monotonic(), n)\n"
        "        self._cache_a_classer = cache\n"
        "        return n\n\n"
        "    def _compter_a_classer(self, pc: dict[str, Any] | None) -> int:\n"
        "        return sum(",
    ),
    (
        "    def _est_etiquette(self, valeur: str) -> bool:\n"
        "        bas = valeur.strip().lower()\n"
        "        return any(e.lower() == bas for e in self.toutes_etiquettes())",
        "    def _est_etiquette(self, valeur: str) -> bool:\n"
        "        import time as _t\n"
        "        bas = valeur.strip().lower()\n"
        "        # L'ensemble des étiquettes en minuscules, recalculé au plus toutes les 5 s : cette\n"
        "        # fonction est appelée des milliers de fois par relevé.\n"
        "        cache = getattr(self, \"_cache_etiquettes_bas\", None)\n"
        "        if cache is None or _t.monotonic() - cache[0] > 5:\n"
        "            cache = (_t.monotonic(), {e.lower() for e in self.toutes_etiquettes()})\n"
        "            self._cache_etiquettes_bas = cache\n"
        "        return bas in cache[1]",
    ),
    (
        "    async def async_save(self) -> None:",
        "    async def async_save(self) -> None:\n"
        "        # Toute écriture invalide les caches de classement (listes, compteurs, étiquettes).\n"
        "        self.version_cache = getattr(self, \"version_cache\", 0) + 1\n"
        "        self._cache_a_classer = {}\n"
        "        self._cache_etiquettes_bas = None",
    ),
], ".bakperf")

patch("select.py", [
    (
        "        pc = self._pc()\n"
        "        magasin = self.coordinator.store\n"
        "        return [\n"
        "            n for n in self._noms() if magasin.classe(pc, self._genre, n) == etat\n"
        "        ]",
        "        pc = self._pc()\n"
        "        magasin = self.coordinator.store\n"
        "        # Un seul passage sur le catalogue toutes les 5 s pour les trois états : les trois\n"
        "        # listes et leurs attributs s'y servent, au lieu de reclasser des milliers de noms\n"
        "        # à chaque relevé d'un appareil (ce qui bloquait la boucle d'événements).\n"
        "        import time as _t\n"
        "        cle = (self._genre, (pc or {}).get(\"id\") or \"\", getattr(magasin, \"version_cache\", 0))\n"
        "        cache = _PAR_ETAT.get(cle)\n"
        "        if cache is None or _t.monotonic() - cache[0] > 5:\n"
        "            seaux: dict[str, list[str]] = {}\n"
        "            for n in self._noms():\n"
        "                seaux.setdefault(magasin.classe(pc, self._genre, n), []).append(n)\n"
        "            cache = (_t.monotonic(), seaux)\n"
        "            _PAR_ETAT[cle] = cache\n"
        "        return list(cache[1].get(etat, []))",
    ),
    (
        "class _ConstateSelect(HubEntity, SelectEntity):",
        "_PAR_ETAT: dict = {}\n\n\nclass _ConstateSelect(HubEntity, SelectEntity):",
    ),
], ".bakperf")
print("ok perf")
