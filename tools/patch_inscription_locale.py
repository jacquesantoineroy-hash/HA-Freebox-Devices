"""L'appli Android trouve Home Assistant toute seule sur le réseau (mDNS) et
s'inscrit sans qu'on lui colle la clé. Côté serveur : une inscription sans clé
est acceptée seulement si les inscriptions sont ouvertes ET si la demande vient
directement du réseau local (192.168.x.x ou 10.x.x.x, sans passer par un
mandataire). De l'extérieur, la clé reste obligatoire.
Usage sur HA : python3 patch_inscription_locale.py
"""
import py_compile
import shutil

p = "/homeassistant/custom_components/pc_parental/http.py"
t = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakloc")


def remplacer(a, b):
    global t
    assert a in t, a[:70]
    t = t.replace(a, b, 1)


remplacer(
    "class PcParentalEnrollView(HomeAssistantView):\n",
    "def _du_reseau_local(request: web.Request) -> bool:\n"
    "    \"\"\"Vrai si la demande arrive en direct d'un appareil de la maison.\"\"\"\n"
    "    import ipaddress\n"
    "    if request.headers.get(\"X-Forwarded-For\") or request.headers.get(\"Forwarded\"):\n"
    "        return False\n"
    "    try:\n"
    "        ip = ipaddress.ip_address(request.remote or \"\")\n"
    "    except ValueError:\n"
    "        return False\n"
    "    return any(ip in ipaddress.ip_network(r) for r in (\"192.168.0.0/16\", \"10.0.0.0/8\"))\n\n\n"
    "class PcParentalEnrollView(HomeAssistantView):\n",
)
remplacer(
    "        if not store.check_enroll_key(str(corps.get(\"key\") or \"\")):\n",
    "        _cle = str(corps.get(\"key\") or \"\")\n"
    "        _locale = not _cle and store.enroll_open and _du_reseau_local(request)\n"
    "        if not _locale and not store.check_enroll_key(_cle):\n",
)
open(p, "w", encoding="utf-8").write(t)
py_compile.compile(p, doraise=True)
print("ok inscription locale")
