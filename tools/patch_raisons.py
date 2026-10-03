"""Vision : dire pourquoi un logiciel ou un site est coupé.

store.raison(pc, genre, nom) reproduit l'ordre de store.statut et rend un
motif lisible ; effectif() transmet aux agents `raisons` (nom → index) et
`motifs` (textes). demandes.py joint le motif à la demande d'accès.
À exécuter sur HA : python3 patch_raisons.py
"""
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"

# --- store.py ---------------------------------------------------------------------
p = BASE + "store.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakand12")
assert "def raison_enfant(" not in t

old = "    def effectif(self, pc: dict[str, Any]) -> dict[str, list[str]]:"
new = '''    # Étiquettes qui relèvent de la sécurité : la maison les coupe pour tout le monde.
    ETIQUETTES_SECURITE = ("dangereux", "contournement", "pub & traçage", "pub & tracage")
    ETIQUETTES_AGE = ("pegi 12", "pegi 16", "pegi 18", "adulte")

    def raison_enfant(self, pc: dict[str, Any], genre: str, nom: str) -> dict[str, str] | None:
        """Pourquoi cet élément est fermé sur ce PC, dit pour l'enfant.

        Même ordre que `statut` : la première règle qui ferme est la raison.
        Rend None si l'élément n'est pas bloqué. `code` : securite, maison,
        moyenne, plage, age, regle.
        """
        cible = _nom_app(nom) if genre == "apps" else _nom_site(nom)
        etiquettes = self.etiquettes_de(genre, nom)
        bas = [e.lower() for e in etiquettes]

        if self.est_banni(cible):
            if any(e in self.ETIQUETTES_SECURITE for e in bas):
                return {"code": "securite", "texte": "Bloqué pour ta sécurité : site dangereux, piège ou traçage."}
            return {"code": "maison", "texte": "Interdit pour toute la maison."}
        for e in etiquettes:
            if self.est_banni(e):
                if e.lower() in self.ETIQUETTES_SECURITE:
                    return {"code": "securite", "texte": "Bloqué pour ta sécurité ({}).".format(e)}
                return {"code": "maison", "texte": "Interdit pour toute la maison ({}).".format(e)}
        if self._laissez_passer(pc, genre, nom) or self._excepte(pc, genre, nom):
            return None
        if self.moyenne_ferme(pc, etiquettes):
            personne = str(pc.get("person") or "")
            cfg = self.moyennes.get(personne) or {}
            valeur = self.moyenne_de(personne) or 0.0
            seuil = float(cfg.get("seuil") or MOYENNE_SEUIL)
            return {"code": "moyenne", "texte": "Fermé tant que ta moyenne est sous {:g} (elle est à {:g}). Ça rouvrira avec les notes.".format(seuil, valeur)}
        regle = self.plage_nomme(pc, genre, nom)
        if regle is not None:
            return {"code": "plage", "texte": "Fermé par le planning « {} » ({} → {}).".format(
                regle.get("name") or "plage", _hm(regle.get("start")), _hm(regle.get("end")))}
        bloques = pc.get("bloques") or []
        if self._dans(bloques, cible):
            return {"code": "regle", "texte": "Coupé par tes parents sur tes appareils."}
        trouve = self._plage_de(pc, genre, nom)
        if trouve is not None:
            regle, etiquette = trouve
            return {"code": "plage", "texte": "Fermé par le planning « {} » pour {} ({} → {}).".format(
                regle.get("name") or "plage", etiquette, _hm(regle.get("start")), _hm(regle.get("end")))}
        for e in etiquettes:
            if self._dans(bloques, e):
                if e.lower() in self.ETIQUETTES_AGE:
                    return {"code": "age", "texte": "Réservé aux plus grands ({}).".format(e)}
                return {"code": "regle", "texte": "Coupé par tes parents : {}.".format(e)}
        if self.statut(pc, genre, nom) == BLOQUE:
            return {"code": "regle", "texte": "Coupé par tes parents."}
        return None

    def effectif(self, pc: dict[str, Any]) -> dict[str, list[str]]:'''
assert old in t
t = t.replace(old, new, 1)

# _hm : secondes depuis minuit → "HH:MM" (module)
old = "def _nom_app(nom: str) -> str:"
new = '''def _hm(secondes) -> str:
    s = int(secondes or 0) % 86400
    return "{:02d}:{:02d}".format(s // 3600, (s % 3600) // 60)


def _nom_app(nom: str) -> str:'''
assert old in t
t = t.replace(old, new, 1)

# effectif : relever la raison de chaque nom bloqué
old = '''        self.purger_laissez_passer(pc)
        apps: list[str] = []
        sites: list[str] = []

        def _ajouter(genre: str, nom: str) -> None:
            # Une décision porte sur un service, l'agent bloque des noms :
            # on lui transmet toute la famille, sans quoi couper
            # « roblox.com » laisserait le jeu vivre sur « rbxcdn.com ».
            cible = apps if genre == "apps" else sites
            membres = membres_app(nom) if genre == "apps" else membres_site(nom)
            for membre in membres:
                if membre and membre not in cible:
                    cible.append(membre)
'''
new = '''        self.purger_laissez_passer(pc)
        apps: list[str] = []
        sites: list[str] = []
        # Pourquoi chaque nom est fermé : l'agent le dit à l'enfant. Les textes
        # sont mutualisés (motifs) et chaque nom pointe dessus (raisons).
        motifs: list[str] = []
        raisons: dict[str, int] = {}

        def _ajouter(genre: str, nom: str) -> None:
            # Une décision porte sur un service, l'agent bloque des noms :
            # on lui transmet toute la famille, sans quoi couper
            # « roblox.com » laisserait le jeu vivre sur « rbxcdn.com ».
            cible = apps if genre == "apps" else sites
            membres = membres_app(nom) if genre == "apps" else membres_site(nom)
            idx = -1
            try:
                r = self.raison_enfant(pc, genre, nom)
            except Exception:  # noqa: BLE001
                r = None
            if r:
                texte = "{}|{}".format(r["code"], r["texte"])
                if texte not in motifs:
                    motifs.append(texte)
                idx = motifs.index(texte)
            for membre in membres:
                if membre and membre not in cible:
                    cible.append(membre)
                if membre and idx >= 0 and membre not in raisons:
                    raisons[membre] = idx
'''
assert old in t, "effectif"
t = t.replace(old, new, 1)
old = '''            "exceptions": sorted(epargnes),
        }

    def definir_bloques('''
new = '''            "exceptions": sorted(epargnes),
            "motifs": motifs,
            "raisons": raisons,
        }

    def definir_bloques('''
assert old in t, "retour effectif"
t = t.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(t)

# --- demandes.py : la raison voyage avec la demande ------------------------------
p = BASE + "demandes.py"
d = open(p, encoding="utf-8").read()
if '"raison"' not in d:
    d = d.replace(
        '''    qui = prenom(hass, pc)
    joli = libelle.strip() or cle
''',
        '''    qui = prenom(hass, pc)
    joli = libelle.strip() or cle
    try:
        _r = coord.store.raison_enfant(pc, genre, cle)
    except Exception:  # noqa: BLE001
        _r = None
    raison = _r["texte"] if _r else ""
    code = _r["code"] if _r else ""
''', 1)
    d = d.replace(
        '''        "lien": lien[:300], "motif": motif[:120],
    }''',
        '''        "lien": lien[:300], "motif": motif[:120], "raison": raison, "code": code,
    }''', 1)
    d = d.replace(
        '''    if motif:
        texte = "{} ({})".format(texte, motif[:120])''',
        '''    if motif:
        texte = "{} ({})".format(texte, motif[:120])
    if raison:
        texte = "{} Pourquoi c'est fermé : {}".format(texte, raison)''', 1)
    d = d.replace(
        '''            "nom": nom, "libelle": joli, "lien": lien[:300], "motif": motif[:120],
        }''',
        '''            "nom": nom, "libelle": joli, "lien": lien[:300], "motif": motif[:120],
            "raison": raison, "code": code,
        }''', 1)
    assert d.count("raison") >= 6
    open(p, "w", encoding="utf-8").write(d)

import py_compile
for f in ("store.py", "demandes.py"):
    py_compile.compile(BASE + f, doraise=True)
print("ok")
