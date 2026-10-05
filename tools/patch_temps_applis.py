"""Temps passé par appli et par heure, jour par jour, pour l'espace parents.

Jusqu'ici Vision ne gardait que deux totaux par jour (actif, ouvert) et un cumul par logiciel depuis toujours.
Il retient maintenant, pour chaque jour, le temps actif de chaque heure et de chaque appli ou logiciel, et la
fiche de l'appareil les donne (« temps ») : sept derniers jours, plus le cumul depuis le premier relevé.
Le détail par jour ne commence qu'à partir de cette mise à jour.

Usage sur HA : python3 patch_temps_applis.py
"""
import py_compile
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"


def patch(fichier: str, remplacements: list[tuple[str, str]]) -> None:
    p = BASE + fichier
    s = open(p, encoding="utf-8").read()
    shutil.copy2(p, p + ".baktemps")
    for avant, apres in remplacements:
        assert s.count(avant) == 1, (fichier, avant[:70], s.count(avant))
        s = s.replace(avant, apres)
    open(p, "w", encoding="utf-8").write(s)
    py_compile.compile(p, doraise=True)


patch("store.py", [
    ('''        if presence == PRESENCE_ACTIF:
            journee["actif"] = int(journee.get("actif", 0) + ecart)
        self._purger_usage(pc)
''',
     '''        if presence == PRESENCE_ACTIF:
            journee["actif"] = int(journee.get("actif", 0) + ecart)
            # Heure par heure : c'est ce qui montre quand l'appareil sert vraiment.
            heures = journee.setdefault("heures", {})
            heure = dt_util.now().strftime("%H")
            heures[heure] = int(heures.get(heure, 0) + ecart)
        self._purger_usage(pc)
'''),
    ('''        if 0 < secondes <= USAGE_ECART_MAX:
            fiche["secondes"] = int(fiche.get("secondes", 0) + secondes)
''',
     '''        if 0 < secondes <= USAGE_ECART_MAX:
            fiche["secondes"] = int(fiche.get("secondes", 0) + secondes)
            # Et le même temps, rangé dans la journée : « combien de Roblox aujourd'hui ? ».
            try:
                journee = pc.setdefault("usage", {}).setdefault(dt_util.now().strftime("%Y-%m-%d"), {"actif": 0, "ouvert": 0})
                par_app = journee.setdefault("apps", {})
                par_app[nom] = int(par_app.get(nom, 0) + secondes)
            except Exception:  # noqa: BLE001 - le cumul reste juste même si le détail du jour échoue
                pass
'''),
])

patch("parent.py", [
    ('''def _fiche(hass: HomeAssistant, coord: PcParentalCoordinator, pc: dict[str, Any], parents: list[str]) -> dict[str, Any]:''',
     '''def _temps(pc: dict[str, Any]) -> dict[str, Any]:
    """Le temps passé : sept derniers jours (par heure et par appli), et le cumul par appli depuis le début."""
    vues = pc.get("apps_vues") or {}

    def libelle(nom: str) -> str:
        fiche = vues.get(nom)
        return (str(fiche.get("libelle") or "") if isinstance(fiche, dict) else "") or nom

    usage = pc.get("usage") or {}
    jours = []
    for jour in sorted(usage)[-7:]:
        j = usage.get(jour) or {}
        heures = j.get("heures") or {}
        applis = sorted(((str(n), int(s or 0)) for n, s in (j.get("apps") or {}).items()), key=lambda x: -x[1])[:12]
        jours.append({
            "jour": jour,
            "actif": int(j.get("actif", 0)),
            "ouvert": int(j.get("ouvert", 0)),
            "heures": [int(heures.get("%02d" % h, 0)) for h in range(24)],
            "apps": [{"nom": n, "libelle": libelle(n), "secondes": s} for n, s in applis if s >= 30],
        })
    total = sorted(
        ((str(n), int(f.get("secondes") or 0), int(float(f.get("premier") or 0))) for n, f in vues.items() if isinstance(f, dict)),
        key=lambda x: -x[1],
    )[:15]
    return {"jours": jours, "total": [{"nom": n, "libelle": libelle(n), "secondes": s, "depuis": p} for n, s, p in total if s >= 60]}


def _fiche(hass: HomeAssistant, coord: PcParentalCoordinator, pc: dict[str, Any], parents: list[str]) -> dict[str, Any]:'''),
    ('''        "usage": {"actif": int(usage.get("actif", 0)) // 60, "ouvert": int(usage.get("ouvert", 0)) // 60},
''',
     '''        "usage": {"actif": int(usage.get("actif", 0)) // 60, "ouvert": int(usage.get("ouvert", 0)) // 60},
        "temps": _temps(pc),
'''),
])
print("ok temps par appli")
