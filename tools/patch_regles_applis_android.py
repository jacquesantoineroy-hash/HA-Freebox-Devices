"""Une exception posée sur une appli Android ne doit plus être prise pour un site au redémarrage.

Bogue : au chargement, `_replier_regles` ramenait toute règle contenant un point à « son site ».
« com.snapchat.android » devenait « snapchat.android », qui ne correspond plus à aucune appli :
l'autorisation (ou le blocage) cessait de valoir, sans rien dire, à chaque redémarrage de Home Assistant.

Correctif : une valeur connue comme appli est laissée telle quelle ; une valeur déjà abîmée est réparée
quand une seule appli connue lui correspond.

Usage sur HA : python3 patch_regles_applis_android.py
"""
import py_compile
import shutil

P = "/homeassistant/custom_components/pc_parental/store.py"
s = open(P, encoding="utf-8").read()
shutil.copy2(P, P + ".bakappand")
avant = '''        for champ in ("bloques", "autorises"):
            garde: list[str] = []
            for valeur in pc.get(champ) or []:
                valeur = str(valeur).strip()
                if not valeur:
                    continue
                if "." in valeur and not self._est_etiquette(valeur):
'''
assert s.count(avant) == 1
apres = '''        # Les applis connues (catalogue, relevés des appareils) : un paquet Android a des points
        # (« com.snapchat.android ») sans être un site, on ne le replie donc pas.
        applis: dict[str, str] = {}
        try:
            for n in (self.etiquettes.get("apps") or {}):
                applis.setdefault(str(n).lower(), str(n))
            for autre in [pc, *list((getattr(self, "pcs", None) or {}).values())]:
                for n in (autre.get("apps_vues") or {}):
                    applis.setdefault(str(n).lower(), str(n))
            sites_connus = {str(n).lower() for n in (self.etiquettes.get("sites") or {})}
        except Exception:  # noqa: BLE001 - sans catalogue, on replie comme avant
            applis, sites_connus = {}, set()
        for champ in ("bloques", "autorises"):
            garde: list[str] = []
            for valeur in pc.get(champ) or []:
                valeur = str(valeur).strip()
                if not valeur:
                    continue
                if valeur.lower() in applis:
                    pass
                elif "." in valeur and not self._est_etiquette(valeur):
                    # Une règle déjà abîmée (« snapchat.android ») retrouve son appli quand une seule lui correspond.
                    if valeur.lower() not in sites_connus:
                        retrouvees = [a for bas, a in applis.items() if bas.count(".") >= 2 and (_nom_site(bas) or "") == valeur.lower()]
                        if len(retrouvees) == 1:
                            valeur = retrouvees[0]
                            if valeur.lower() not in [g.lower() for g in garde]:
                                garde.append(valeur)
                            continue
'''
s = s.replace(avant, apres)
open(P, "w", encoding="utf-8").write(s)
py_compile.compile(P, doraise=True)
print("ok regles applis android")
