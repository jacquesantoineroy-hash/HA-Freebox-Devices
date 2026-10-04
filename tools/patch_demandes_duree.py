"""Demandes d'accès avec durée souhaitée (1h / toujours / categorie) et
décision « catégorie » côté parent. Usage sur HA : python3 patch_demandes_duree.py
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


DUREES = {"1h": "pour 1 h", "toujours": "en permanence (quand l'écran est ouvert)", "categorie": "pour toute la catégorie"}

patch("demandes.py", [
    (
        "    genre: str, nom: str, libelle: str, lien: str = \"\", motif: str = \"\",\n) -> dict[str, Any] | None:",
        "    genre: str, nom: str, libelle: str, lien: str = \"\", motif: str = \"\", duree: str = \"\",\n) -> dict[str, Any] | None:",
    ),
    (
        "    raison = _r[\"texte\"] if _r else \"\"\n    code = _r[\"code\"] if _r else \"\"\n    d = {",
        "    raison = _r[\"texte\"] if _r else \"\"\n    code = _r[\"code\"] if _r else \"\"\n"
        "    duree = duree if duree in DUREES else \"\"\n"
        "    try:\n        etiquettes = [e for e in coord.store.etiquettes_de(genre, cle) if not coord.store.est_banni(e)]\n"
        "    except Exception:  # noqa: BLE001\n        etiquettes = []\n"
        "    d = {",
    ),
    (
        "        \"lien\": lien[:300], \"motif\": motif[:120], \"raison\": raison, \"code\": code,\n    }\n    liste.append(d)",
        "        \"lien\": lien[:300], \"motif\": motif[:120], \"raison\": raison, \"code\": code,\n"
        "        \"duree\": duree, \"etiquettes\": etiquettes[:6],\n    }\n    liste.append(d)",
    ),
    (
        "    if motif:\n        texte = \"{} ({})\".format(texte, motif[:120])\n    if raison:",
        "    if duree:\n        texte = \"{} {}\".format(texte.rstrip(\".\"), DUREES[duree]) + \".\"\n"
        "        if duree == \"categorie\" and etiquettes:\n            texte = \"{} Catégorie : {}.\".format(texte, \", \".join(etiquettes[:6]))\n"
        "    if motif:\n        texte = \"{} ({})\".format(texte, motif[:120])\n    if raison:",
    ),
    (
        "            \"raison\": raison, \"code\": code,\n        }\n    return d",
        "            \"raison\": raison, \"code\": code, \"duree\": duree, \"etiquettes\": etiquettes[:6],\n        }\n    return d",
    ),
    (
        "        motif = str(corps.get(\"motif\") or \"\").strip()[:120]\n        if not nom:",
        "        motif = str(corps.get(\"motif\") or \"\").strip()[:120]\n        duree = str(corps.get(\"duree\") or \"\").strip()\n        if not nom:",
    ),
    (
        "        d = deposer(self.hass, coord, pc, genre, nom, libelle, lien, motif)",
        "        d = deposer(self.hass, coord, pc, genre, nom, libelle, lien, motif, duree)",
    ),
    (
        "REPOS_S = 15 * 60\n",
        "REPOS_S = 15 * 60\n# Ce que l'enfant souhaite : une heure, une exception permanente (quand son écran est ouvert), ou toute la catégorie.\nDUREES = {\"1h\": \"pour 1 h\", \"toujours\": \"en permanence (quand l'écran est ouvert)\", \"categorie\": \"pour toute la catégorie\"}\n",
    ),
], ".bakduree")

patch("parent.py", [
    (
        "        elif decision == \"temporaire\":\n            minutes = minutes or 60\n            if d.get(\"genre\") == \"apps\":",
        "        elif decision == \"categorie\":\n"
        "            # Toute la catégorie : les étiquettes qui classent ce nom passent en « autorisé » pour l'enfant.\n"
        "            ets = [e for e in (d.get(\"etiquettes\") or coord.store.etiquettes_de(d.get(\"genre\") or \"sites\", d[\"cle\"])) if not coord.store.est_banni(e)]\n"
        "            if not ets:\n"
        "                if coord.store.est_banni(d[\"cle\"]):\n"
        "                    retour = \"Impossible : {} est interdit pour toute la maison.\".format(joli)\n"
        "                else:\n"
        "                    coord.store.basculer(cible, d[\"cle\"], False)\n"
        "                    retour = \"{} a autorisé {} (pas de catégorie à ouvrir).\".format(qui, joli)\n"
        "            else:\n"
        "                for e in ets:\n"
        "                    coord.store.basculer(cible, e, False)\n"
        "                retour = \"{} a autorisé la catégorie {} ({} compris).\".format(qui, \", \".join(ets), joli)\n"
        "        elif decision == \"temporaire\":\n            minutes = minutes or 60\n            if d.get(\"genre\") == \"apps\":",
    ),
], ".bakduree")
print("ok demandes + parent")
