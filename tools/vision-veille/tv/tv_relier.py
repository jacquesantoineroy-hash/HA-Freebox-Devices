"""Relie un appareil Android TV à Vision sans clavier : python3 tv_relier.py 192.168.1.5:35659 [Affichage]

L'adresse publique de Home Assistant se lit dans la variable d'environnement
VISION_ADRESSE, ou dans le fichier /homeassistant/vision_adb/adresse.txt.

Envoie le bloc adresse / clé à l'écran d'inscription par un intent (l'appareil
ne doit pas être déjà inscrit).
"""
import json
import subprocess
import sys

ADB = "/homeassistant/vision_adb/platform-tools/adb"
import os
ADRESSE = os.environ.get("VISION_ADRESSE") or open("/homeassistant/vision_adb/adresse.txt").read().strip()
serie = sys.argv[1]
d = json.load(open("/homeassistant/.storage/pc_parental"))["data"]
cle = d.get("enroll_key") or ""
print("inscription ouverte :", d.get("enroll_open"))
bloc = f"adresse: {ADRESSE} cle: {cle}"
# Le shell distant doit recevoir le bloc en un seul argument : on le cite nous-mêmes.
distant = f"am start -n fr.familleroy.vision/.SetupActivity --es bloc '{bloc}'"
if len(sys.argv) > 2:
    distant += f" --es utilisateur '{sys.argv[2]}'"
cmd = [ADB, "-s", serie, "shell", distant]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
print(r.stdout.strip(), r.stderr.strip())
