"""Essai du catalogue : le verdict « désinstaller », sans Home Assistant.

python3 essai/desinstall_catalogue_test.py
"""
import importlib.util
import pathlib
import sys

chemin = pathlib.Path(__file__).resolve().parent.parent / "pc_parental" / "processus_catalogue.py"
spec = importlib.util.spec_from_file_location("processus_catalogue", chemin)
m = importlib.util.module_from_spec(spec)
sys.modules["processus_catalogue"] = m
spec.loader.exec_module(m)

rates = 0


def verifier(quoi, obtenu, attendu):
    global rates
    if obtenu == attendu:
        print("ok   ", quoi)
    else:
        rates += 1
        print("RATE ", quoi, ": obtenu", repr(obtenu), "attendu", repr(attendu))


def leve(f):
    try:
        f()
    except (ValueError, KeyError) as e:
        return str(e)
    return ""


c = m.Catalogue()
releve = [
    {"g": "processus", "id": "nortonui", "nom": "NortonUI", "exe": "nortonui", "chemin": r"C:\Program Files\Norton\Suite\NortonUI.exe", "signataire": "Gen Digital Inc.", "editeur": "Gen Digital Inc."},
    {"g": "processus", "id": "vgc", "nom": "vgc", "exe": "vgc", "chemin": r"C:\Program Files\Riot Vanguard\vgc.exe", "signataire": "Riot Games, Inc.", "editeur": "Riot Games"},
    {"g": "processus", "id": "msedge", "nom": "msedge", "exe": "msedge", "chemin": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "signataire": "Microsoft Corporation", "editeur": "Microsoft Corporation"},
    {"g": "service", "id": "nvcontainer", "nom": "NVIDIA Container", "exe": "nvcontainer", "chemin": r"C:\Program Files\NVIDIA Corporation\NvContainer\nvcontainer.exe", "signataire": "NVIDIA Corporation", "editeur": "NVIDIA Corporation"},
    {"g": "processus", "id": "agent", "nom": "agent", "exe": "powershell_x", "chemin": r"C:\ProgramData\HAParental\x.exe", "signataire": "", "editeur": ""},
    {"g": "processus", "id": "sanschemin", "nom": "sanschemin", "exe": "sanschemin", "chemin": "", "signataire": "", "editeur": ""},
]
print("retenus :", c.noter("pc1", releve, 1000.0))
c.noter("pc2", releve[:1], 1000.0)
cles = {f["id"]: k for k, f in c.elements.items()}
print("champs :", sorted(c.elements[cles["nortonui"]].keys()))

verifier("Norton : désinstallable", m.raison_non_desinstallable(c.elements[cles["nortonui"]]), "")
for ident in ("vgc", "msedge", "nvcontainer", "agent", "sanschemin"):
    verifier(f"{ident} : refusé", bool(m.raison_non_desinstallable(c.elements[cles[ident]])), True)
    verifier(f"{ident} : decider lève", bool(leve(lambda i=ident: c.decider(cles[i], "desinstaller", 1001.0))), True)
verifier("proposer : refusé", bool(leve(lambda: c.proposer(cles["nortonui"], "desinstaller", "x", 90, "classeur", 1001.0))), True)

f = c.decider(cles["nortonui"], "desinstaller", 1002.0)
jeton = f["decision"]["jeton"]
verifier("jeton posé", len(jeton), 12)
verifier("interrupteur éteint : rien", "desinstaller" in c.consignes("pc1", False), False)
k = c.consignes("pc1", True)
verifier("interrupteur allumé : une consigne", [d["cle"] for d in k.get("desinstaller", [])], [cles["nortonui"]])
verifier("pas dans les nuisibles", "nortonui" in k["arreter"], False)
verifier("pc sans le logiciel : rien", "desinstaller" in c.consignes("pc3", True), False)
verifier("mauvais jeton ignoré", c.noter_desinstallations("pc1", [{"cle": cles["nortonui"], "jeton": "faux", "etat": "fait"}]), False)
verifier("compte rendu noté", c.noter_desinstallations("pc1", [{"cle": cles["nortonui"], "jeton": jeton, "etat": "echec", "detail": "x", "produit": "Norton 360", "date": 1003}]), True)
verifier("même compte rendu : rien de neuf", c.noter_desinstallations("pc1", [{"cle": cles["nortonui"], "jeton": jeton, "etat": "echec", "detail": "x", "produit": "Norton 360", "date": 1003}]), False)
verifier("plus de consigne pour pc1", "desinstaller" in c.consignes("pc1", True), False)
c.noter("pc1", releve, 2000.0)
verifier("un nouvel inventaire ne relance pas", "desinstaller" in c.consignes("pc1", True), False)
verifier("toujours pour pc2", len(c.consignes("pc2", True).get("desinstaller", [])), 1)
vue = c.lister("tous", 100, {"pc1": "PC 1", "pc2": "PC 2"})
ligne = [e for e in vue["elements"] if e["cle"] == cles["nortonui"]][0]
verifier("lister : compte rendu par appareil", [p.get("desinstall", {}) and p["desinstall"]["etat"] for p in ligne["pcs"] if p["pc"] == "PC 1"], ["echec"])
verifier("lister : raison de refus", bool([e for e in vue["elements"] if e["cle"] == cles["vgc"]][0]["non_desinstallable"]), True)
# Redécider (nouvel essai) : nouveau jeton, la consigne repart.
f = c.decider(cles["nortonui"], "desinstaller", 1004.0)
verifier("redécider : nouveau jeton", f["decision"]["jeton"] != jeton, True)
verifier("redécider : consigne repart", len(c.consignes("pc1", True).get("desinstaller", [])), 1)
c.decider(cles["nortonui"], "neutre", 1005.0)
verifier("défaire : plus de consigne", "desinstaller" in c.consignes("pc1", True), False)
print(rates, "raté(s)")
sys.exit(1 if rates else 0)
