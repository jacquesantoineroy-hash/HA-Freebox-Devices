"""La règle de moyenne laisse la place aux catégories fermées par une automatisation, avec leur raison.

Décision du 05-10-2026 : Vision ne décide plus tout seul de fermer le divertissement sous une moyenne. À la
place, deux services que n'importe quelle automatisation de Home Assistant peut appeler :

    pc_parental.fermer_categorie  personne, categorie (une ou plusieurs), raison
    pc_parental.ouvrir_categorie  personne, categorie (rien = toutes celles fermées par automatisation)

Une catégorie fermée ainsi vaut pour la personne, sur tous ses appareils, et dit pourquoi. Elle se place comme
une catégorie coupée par les parents : ce qui est « toujours autorisé » nom par nom reste ouvert, le planning
reste plus fort.

Usage sur HA : python3 patch_fermetures_auto.py
"""
import py_compile
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"


def patch(fichier: str, remplacements: list[tuple[str, str]], ajout: str = "") -> None:
    p = BASE + fichier
    s = open(p, encoding="utf-8").read()
    shutil.copy2(p, p + ".bakferm")
    for avant, apres in remplacements:
        assert s.count(avant) == 1, (fichier, avant[:70], s.count(avant))
        s = s.replace(avant, apres)
    s += ajout
    open(p, "w", encoding="utf-8").write(s)
    if fichier.endswith(".py"):
        py_compile.compile(p, doraise=True)


patch("store.py", [
    ('''        self.moyennes = dict(data.get("moyennes") or {})
''',
     '''        self.moyennes = dict(data.get("moyennes") or {})
        self.fermetures = {
            str(k): {str(e).lower(): dict(f) for e, f in v.items() if isinstance(f, dict)}
            for k, v in (data.get("fermetures") or {}).items() if isinstance(v, dict)
        }
'''),
    ('''                "moyennes": self.moyennes,
''',
     '''                "moyennes": self.moyennes,
                "fermetures": getattr(self, "fermetures", {}),
'''),
    ('''    def moyenne_active(self, pc: dict[str, Any]) -> bool:
        """La règle ferme-t-elle le divertissement sur cet appareil ?"""
''',
     '''    # ------------------------------ Catégories fermées par une automatisation
    # Rangées par personne : {"person.jules": {"jeux": {etiquette, raison, source, depuis}}}.
    def fermer_categorie(self, personne: str, etiquette: str, raison: str = "", source: str = "") -> bool:
        """Ferme une catégorie pour une personne, en disant pourquoi. Rend True si quelque chose a changé."""
        personne = str(personne or "").strip()
        etiquette = str(etiquette or "").strip()
        if not personne or not etiquette:
            return False
        fiches = self.__dict__.setdefault("fermetures", {}).setdefault(personne, {})
        avant = fiches.get(etiquette.lower())
        nouveau = {
            "etiquette": etiquette,
            "raison": str(raison or "").strip()[:200],
            "source": str(source or "").strip()[:80],
            "depuis": (avant or {}).get("depuis") or int(time.time()),
        }
        if avant == nouveau:
            return False
        fiches[etiquette.lower()] = nouveau
        return True

    def ouvrir_categorie(self, personne: str, etiquette: str | None = None) -> int:
        """Rouvre une catégorie fermée par automatisation (toutes si aucune n'est nommée). Rend leur nombre."""
        fiches = self.__dict__.setdefault("fermetures", {}).get(str(personne or "").strip())
        if not fiches:
            return 0
        if etiquette is None:
            n = len(fiches)
            fiches.clear()
            return n
        return 1 if fiches.pop(str(etiquette).strip().lower(), None) is not None else 0

    def fermetures_de(self, personne: str) -> list[dict[str, Any]]:
        fiches = (getattr(self, "fermetures", None) or {}).get(str(personne or "")) or {}
        return sorted((dict(f) for f in fiches.values()), key=lambda f: str(f.get("etiquette") or "").lower())

    def fermeture_de(self, pc: dict[str, Any], etiquettes: list[str]) -> dict[str, Any] | None:
        """La fermeture par automatisation qui touche cet élément, s'il y en a une."""
        fiches = (getattr(self, "fermetures", None) or {}).get(str(pc.get("person") or ""))
        if not fiches or not etiquettes:
            return None
        for e in etiquettes:
            trouve = fiches.get(str(e).lower())
            if trouve is not None:
                return trouve
        return None

    def moyenne_active(self, pc: dict[str, Any]) -> bool:
        """La règle de moyenne a été retirée le 05-10-2026 : ce sont des automatisations qui ferment
        les catégories (services fermer_categorie / ouvrir_categorie). Elle ne ferme donc plus rien."""
        return False
'''),
    ('''        if self._plage_de(pc, genre, nom) is not None:
            return BLOQUE
        if self._dans(autorises, cible):
            return AUTORISE
''',
     '''        if self._plage_de(pc, genre, nom) is not None:
            return BLOQUE
        if self._dans(autorises, cible):
            return AUTORISE
        # Une catégorie fermée par une automatisation : comme une catégorie coupée par les parents, donc
        # derrière le « toujours autorisé » posé sur ce nom, qui reste ouvert.
        if self.fermeture_de(pc, etiquettes) is not None:
            return BLOQUE
'''),
    ('''        for e in etiquettes:
            if self._dans(bloques, e):
                if e.lower() in self.ETIQUETTES_AGE:
''',
     '''        if not self._dans(pc.get("autorises") or [], cible):
            fermeture = self.fermeture_de(pc, etiquettes)
            if fermeture is not None:
                # Code « regle » : les applis déjà installées savent le ranger ; le texte dit la vraie raison.
                return {"code": "regle", "texte": str(fermeture.get("raison") or "") or "Catégorie {} fermée pour le moment.".format(fermeture.get("etiquette") or "")}
        for e in etiquettes:
            if self._dans(bloques, e):
                if e.lower() in self.ETIQUETTES_AGE:
'''),
])

patch("parent.py", [
    ('''            if store.moyenne_ferme(pc, [nom]):
                personne = str(pc.get("person") or "")
                cfg = store.moyennes.get(personne) or {}
                valeur = store.moyenne_de(personne) or 0.0
                code, texte = "moyenne", "Coupé par la règle de moyenne ({:g} sous {:g}).".format(valeur, float(cfg.get("seuil") or 12))
            else:
''',
     '''            fermeture = store.fermeture_de(pc, [nom])
            if fermeture is not None:
                code, texte = "automatisation", str(fermeture.get("raison") or "") or "Fermé par une automatisation."
            else:
'''),
    ('''"verrou": code in ("securite", "maison", "moyenne", "plage")}''',
     '''"verrou": code in ("securite", "maison", "moyenne", "plage", "automatisation")}'''),
])

patch("__init__.py", [
    ('''    for service, schema in (
        (SERVICE_LOCK, SCHEMA_LOCK),
''',
     '''    def _personne(valeur: str) -> str:
        """« person.jules », ou un prénom : rend l'entité de la personne."""
        valeur = str(valeur or "").strip()
        if valeur.startswith("person."):
            return valeur
        for etat in hass.states.async_all("person"):
            if str(etat.name or "").strip().lower() == valeur.lower() or etat.entity_id.split(".", 1)[1] == valeur.lower():
                return etat.entity_id
        raise HomeAssistantError(f"Personne « {valeur} » introuvable.")

    async def _categorie(call: ServiceCall) -> None:
        coord = _coordinator()
        personne = _personne(call.data["personne"])
        categories = [str(c).strip() for c in (call.data.get("categorie") or []) if str(c).strip()]
        change = False
        if call.service == "fermer_categorie":
            source = str(getattr(call.context, "parent_id", "") or "")
            for c in categories:
                change = coord.store.fermer_categorie(personne, c, call.data.get("raison", ""), source) or change
        elif categories:
            for c in categories:
                change = bool(coord.store.ouvrir_categorie(personne, c)) or change
        else:
            change = bool(coord.store.ouvrir_categorie(personne))
        if change:
            await coord.async_ecrire(structurel=False)

    hass.services.async_register(DOMAIN, "fermer_categorie", _categorie, schema=vol.Schema({
        vol.Required("personne"): cv.string,
        vol.Required("categorie"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("raison", default=""): cv.string,
    }))
    hass.services.async_register(DOMAIN, "ouvrir_categorie", _categorie, schema=vol.Schema({
        vol.Required("personne"): cv.string,
        vol.Optional("categorie", default=list): vol.All(cv.ensure_list, [cv.string]),
    }))

    for service, schema in (
        (SERVICE_LOCK, SCHEMA_LOCK),
'''),
])

patch("services.yaml", [], ajout='''
fermer_categorie:
  name: Fermer une catégorie
  description: Ferme une ou plusieurs catégories pour une personne, sur tous ses appareils, en disant pourquoi. Ce qui est toujours autorisé nom par nom reste ouvert. À appeler depuis une automatisation.
  fields:
    personne:
      name: Personne
      description: La personne concernée.
      required: true
      selector:
        entity:
          domain: person
    categorie:
      name: Catégories
      description: Les catégories à fermer (Jeux, Vidéos, Réseaux sociaux…).
      required: true
      selector:
        text:
          multiple: true
    raison:
      name: Raison
      description: Ce que la personne lira sur son écran (« Moyenne à 9,5 sur 20 »).
      selector:
        text:
ouvrir_categorie:
  name: Rouvrir une catégorie
  description: Rouvre des catégories fermées par une automatisation. Sans catégorie, les rouvre toutes pour cette personne.
  fields:
    personne:
      name: Personne
      description: La personne concernée.
      required: true
      selector:
        entity:
          domain: person
    categorie:
      name: Catégories
      description: Les catégories à rouvrir. Vide, toutes celles fermées par automatisation.
      selector:
        text:
          multiple: true
''')

# Le tableau de bord ne montre plus la règle de moyenne dans la page d'une personne.
patch("dashboard.py", [(
    '''    if personne["entite"]:
        if regle := _section_moyenne_personne(hass, personne):
            sections.append(regle)
''',
    '''    # La règle de moyenne a été retirée (05-10-2026) : les catégories se ferment par automatisation.
''',
)])
print("ok fermetures par automatisation")
