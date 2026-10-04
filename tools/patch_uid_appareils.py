"""Deux appareils du même modèle (deux « Google Chromecast HD ») s'inscrivaient
sous le même nom de machine et partageaient donc une seule fiche : la personne,
les règles et le filtre DNS de l'un s'appliquaient à l'autre.

L'appli (1.32+) envoie maintenant un identifiant propre à l'appareil (`uid`) et,
sur télé, son nom (`nom`, ex. « Chambre De Jules »).
- Inscription : on retrouve la fiche par uid ; par nom de machine seulement si
  cette fiche n'appartient encore à personne ; sinon nouvelle fiche.
- Relevé : la première appli à présenter un uid prend la fiche. Une autre appli
  qui se présente sur cette fiche avec un autre uid reçoit une fiche neuve
  (`reinscription`). Une ancienne appli sans uid sur une fiche déjà prise
  reçoit une réponse neutre (ouvert, aucun filtre) et l'offre de mise à jour.
Usage sur HA : python3 patch_uid_appareils.py
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
        "    def enroll(self, host: str, user: str = \"\") -> tuple[str, bool]:\n",
        "    def by_uid(self, uid: str) -> str | None:\n"
        "        \"\"\"Retrouve la fiche d'un appareil par son identifiant propre.\"\"\"\n"
        "        if not uid:\n"
        "            return None\n"
        "        for pc_id, pc in self.pcs.items():\n"
        "            if pc.get(\"uid\") == uid:\n"
        "                return pc_id\n"
        "        return None\n\n"
        "    def nouvelle_fiche(self, host: str, nom: str = \"\", uid: str = \"\", user: str = \"\") -> str:\n"
        "        \"\"\"Une fiche neuve pour un appareil, même si un autre porte déjà ce nom de machine.\"\"\"\n"
        "        base = (nom or host or \"Appareil\").strip()\n"
        "        libelle, suffixe = base, 2\n"
        "        while self.by_name(libelle) is not None:\n"
        "            libelle = f\"{base} ({suffixe})\"\n"
        "            suffixe += 1\n"
        "        pc_id = self.create_pc(libelle)\n"
        "        # Le nom de machine d'une fiche à uid n'est jamais réutilisé par un autre appareil.\n"
        "        self.pcs[pc_id][\"host\"] = libelle if self.by_host(host) else host\n"
        "        self.pcs[pc_id][\"uid\"] = uid\n"
        "        self.pcs[pc_id][\"agent\"] = {\"user\": user}\n"
        "        self.pcs[pc_id][\"person\"] = self.devine_personne(user) or \"\"\n"
        "        return pc_id\n\n"
        "    def enroll(self, host: str, user: str = \"\", uid: str = \"\", nom: str = \"\") -> tuple[str, bool]:\n",
    ),
    (
        "        existant = self.by_host(host)\n"
        "        if existant:\n"
        "            return existant, False\n",
        "        if uid:\n"
        "            a_lui = self.by_uid(uid)\n"
        "            if a_lui:\n"
        "                return a_lui, False\n"
        "        existant = self.by_host(host)\n"
        "        if existant:\n"
        "            pris = self.pcs[existant].get(\"uid\")\n"
        "            if not uid or not pris:\n"
        "                if uid:\n"
        "                    self.pcs[existant][\"uid\"] = uid\n"
        "                return existant, False\n"
        "            # Même modèle, autre appareil : sa propre fiche.\n"
        "            return self.nouvelle_fiche(host, nom, uid, user), True\n",
    ),
], ".bakuid")

patch("http.py", [
    (
        "        # Le rapport de l'agent : session ouverte, état appliqué, version.\n"
        "        precedent = float(pc.get(\"last_seen\") or 0)\n",
        "        # --- À qui est cette fiche ? ---------------------------------------\n"
        "        # Deux appareils du même modèle ont pu s'inscrire sous le même nom de\n"
        "        # machine et partager une fiche. L'identifiant propre à l'appareil\n"
        "        # les départage : le premier la garde, l'autre en reçoit une neuve.\n"
        "        _uid = str(corps.get(\"uid\") or \"\")[:64]\n"
        "        _nom_app = str(corps.get(\"nom\") or \"\").strip()[:64]\n"
        "        if _uid and not pc.get(\"uid\"):\n"
        "            pc[\"uid\"] = _uid\n"
        "            if _nom_app and pc.get(\"name\") == pc.get(\"host\") and coord.store.by_name(_nom_app) is None:\n"
        "                pc[\"name\"] = _nom_app\n"
        "            await coord.store.async_save()\n"
        "        elif _uid and pc.get(\"uid\") != _uid:\n"
        "            _neuf = coord.store.nouvelle_fiche(\n"
        "                str(corps.get(\"host\") or \"\")[:64], _nom_app, _uid, str(corps.get(\"user\") or \"\")[:64]\n"
        "            )\n"
        "            _fiche = coord.store.get(_neuf)\n"
        "            _fiche[\"platform\"] = str(corps.get(\"platform\") or \"\")[:16]\n"
        "            _pers0 = str(corps.get(\"person\") or \"\")\n"
        "            if _pers0.startswith(\"person.\") and self.hass.states.get(_pers0) is not None:\n"
        "                _fiche[\"person\"] = _pers0\n"
        "            await coord.store.async_save()\n"
        "            self.hass.config_entries.async_schedule_reload(coord.config_entry.entry_id)\n"
        "            _LOGGER.info(\"%s : « %s » partageait une fiche, il a maintenant la sienne.\", PRODUIT, _fiche[\"name\"])\n"
        "            return self.json({\n"
        "                \"ok\": True, \"action\": \"none\", \"poll\": 5, \"apps\": [], \"sites\": [], \"message\": \"\", \"warn\": 0,\n"
        "                \"reinscription\": {\"id\": _neuf, \"secret\": _fiche[\"secret\"], \"name\": _fiche[\"name\"]},\n"
        "            })\n"
        "        elif not _uid and pc.get(\"uid\") and pc.get(\"platform\") == \"android\":\n"
        "            # Une ancienne appli sur une fiche qui appartient à un autre appareil :\n"
        "            # rien ne s'applique chez elle, on lui propose seulement la mise à jour.\n"
        "            _neutre: dict[str, Any] = {\n"
        "                \"ok\": True, \"action\": \"none\", \"poll\": POLL_SECONDS, \"apps\": [], \"sites\": [],\n"
        "                \"message\": \"\", \"warn\": 0, \"liste_noire\": \"\", \"dns\": [], \"safesearch\": False, \"parent\": False,\n"
        "            }\n"
        "            _maj0 = android_maj.infos(self.hass)\n"
        "            if _maj0 and str(corps.get(\"version\") or \"\") != _maj0[\"version\"]:\n"
        "                _neutre[\"update\"] = _maj0\n"
        "            return self.json(_neutre)\n\n"
        "        # Le rapport de l'agent : session ouverte, état appliqué, version.\n"
        "        precedent = float(pc.get(\"last_seen\") or 0)\n",
    ),
    (
        "            pc_id, cree = store.enroll(host, user)\n",
        "            pc_id, cree = store.enroll(\n"
        "                host, user, str(corps.get(\"uid\") or \"\")[:64], str(corps.get(\"nom\") or \"\").strip()[:64]\n"
        "            )\n",
    ),
], ".bakuid")
print("ok uid")
