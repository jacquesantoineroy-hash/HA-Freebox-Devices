"""Canal d'essai pour l'appli Android : une version peut être proposée à quelques
appareils nommés avant d'être publiée pour tous. Fichiers à côté de vision.apk :
`essai.apk` et `essai.json` = {"version", "sha256", "appareils": ["Nom de la fiche", ...]}.
Sans essai.json, rien ne change. Usage sur HA : python3 patch_canal_essai.py
"""
import py_compile
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"


def patch(nom, remplacements):
    p = BASE + nom
    t = open(p, encoding="utf-8").read()
    shutil.copy2(p, p + ".bakessai")
    for a, b in remplacements:
        assert a in t, (nom, a[:70])
        t = t.replace(a, b, 1)
    open(p, "w", encoding="utf-8").write(t)
    py_compile.compile(p, doraise=True)


patch("android_maj.py", [
    ('    if nom not in ("vision.apk", "vision.json"):\n',
     '    if nom not in ("vision.apk", "vision.json", "essai.apk", "essai.json"):\n'),
    ('def infos(hass: HomeAssistant) -> dict[str, Any]:\n',
     'def infos_pour(hass: HomeAssistant, appareil: str) -> dict[str, Any]:\n'
     '    """La version à proposer à cet appareil : celle à l\'essai s\'il fait partie des appareils d\'essai."""\n'
     '    try:\n'
     '        essai = fichier("essai.json")\n'
     '        if essai and fichier("essai.apk"):\n'
     '            with open(essai, encoding="utf-8") as f:\n'
     '                d = json.load(f)\n'
     '            noms = {str(n).strip().lower() for n in (d.get("appareils") or [])}\n'
     '            if d.get("version") and (appareil or "").strip().lower() in noms:\n'
     '                return {\n'
     '                    "version": str(d["version"]),\n'
     '                    "sha256": str(d.get("sha256") or "").lower(),\n'
     '                    "path": "/api/pc_parental/android/essai.apk?v={}".format(d["version"]),\n'
     '                }\n'
     '    except (OSError, ValueError):\n'
     '        pass\n'
     '    return infos(hass)\n\n\n'
     'def infos(hass: HomeAssistant) -> dict[str, Any]:\n'),
])
patch("http.py", [
    ('            _maj = android_maj.infos(self.hass)\n            if _maj and installee and installee != _maj["version"]:\n',
     '            _maj = android_maj.infos_pour(self.hass, str(pc.get("name") or ""))\n            if _maj and installee and installee != _maj["version"]:\n'),
])
print("ok essai")
