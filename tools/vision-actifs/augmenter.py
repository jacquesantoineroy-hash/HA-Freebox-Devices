# Simule la réponse de la nouvelle intégration à partir du maison.json actuel.
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8-sig"))
pers = {p["entite"]: p for p in d.get("personnes", [])}
maison = [{"entite": e, "prenom": p["prenom"]} for e, p in pers.items() if p["prenom"].lower() != "affichage"]
for nom, ent in (("Laetitia", "person.laetitia"),):
    if ent not in [m["entite"] for m in maison]:
        maison.append({"entite": ent, "prenom": nom})
tous = [m["entite"] for m in maison]
for a in d["appareils"]:
    prin = a.get("personne") or ""
    base = [prin] if prin in tous else []
    a["partage_tous"] = False
    if "salon" in a["nom"].lower():
        a["partage_tous"] = True
        a["proprietaires"] = base + [e for e in sorted(tous) if e not in base]
    elif "parents" in a["nom"].lower():
        a["proprietaires"] = base + ["person.laetitia"]
    else:
        a["proprietaires"] = base
personnes = []
for m in maison:
    e = m["entite"]
    siens = [a for a in d["appareils"] if e in a["proprietaires"]]
    siens.sort(key=lambda a: (a.get("personne") != e, a["nom"].lower()))
    propres = [a for a in siens if a.get("personne") == e]
    if not siens:
        continue
    p = dict(pers.get(e) or {"entite": e, "cle": e.split(".")[-1], "prenom": m["prenom"], "photo": "", "moyenne": None})
    p.update(appareils=[a["id"] for a in siens], principal=propres[0]["id"] if propres else "", parent=any(a.get("parent") for a in propres))
    personnes.append(p)
personnes.sort(key=lambda p: (p["parent"], p["prenom"].lower()))
# 1.57 : limites de temps, logiciels installés, désinstallation permise.
d["desinstallation"] = True
for a in d["appareils"]:
    total = (a.get("temps") or {}).get("total") or []
    a["limites"] = [{"nom": x["nom"], "libelle": x["libelle"], "minutes": 45 if i == 0 else 120, "passe": 3100 if i == 0 else 600} for i, x in enumerate(total[:2])]
    if not a.get("android"):
        a["logiciels"] = [
            {"cle": "logiciel|norton 360", "nom": "Norton 360", "editeur": "Gen Digital Inc.", "version": "25.9", "exes": ["nortonui"], "decision": "", "refus": "", "retour": None},
            {"cle": "logiciel|roblox player", "nom": "Roblox Player", "editeur": "Roblox Corporation", "version": "2.6", "exes": ["robloxplayerbeta"], "decision": "", "refus": "", "retour": None},
            {"cle": "logiciel|vieux jeu", "nom": "Vieux jeu", "editeur": "Petit Studio", "version": "", "exes": [], "decision": "desinstaller", "refus": "", "retour": {"etat": "impossible", "detail": "Vieux jeu n'a pas de désinstallation silencieuse connue : à retirer à la main"}},
            {"cle": "logiciel|truc en attente", "nom": "Truc en attente", "editeur": "", "version": "1.0", "exes": [], "decision": "desinstaller", "refus": "", "retour": None},
            {"cle": "logiciel|microsoft edge", "nom": "Microsoft Edge", "editeur": "Microsoft Corporation", "version": "141", "exes": ["msedge"], "decision": "", "refus": "est un logiciel Microsoft", "retour": None},
            {"cle": "logiciel|riot vanguard", "nom": "Riot Vanguard", "editeur": "Riot Games, Inc.", "version": "", "exes": [], "decision": "", "refus": "est l'anti-triche d'un jeu", "retour": None},
        ]
d["personnes"] = personnes
d["maison"] = maison
json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
print([(p["prenom"], len(p["appareils"]), p["parent"]) for p in personnes])
