"""Relie un appareil Android TV à Vision sans clavier : python3 tv_relier.py 192.168.1.5:35659 [Affichage]

Envoie le bloc adresse / clé à l'écran d'inscription par un intent (l'appareil
ne doit pas être déjà inscrit). adb protège lui-même les espaces des arguments.
"""
import json
import subprocess
import sys

ADB = "/homeassistant/vision_adb/platform-tools/adb"
ADRESSE = "https://familleroy.duckdns.org:44380"
serie = sys.argv[1]
d = json.load(open("/homeassistant/.storage/pc_parental"))["data"]
cle = d.get("enroll_key") or ""
print("inscription ouverte :", d.get("enroll_open"))
bloc = f"adresse: {ADRESSE} cle: {cle}"
cmd = [ADB, "-s", serie, "shell", "am", "start", "-n", "fr.familleroy.vision/.SetupActivity", "--es", "bloc", bloc]
if len(sys.argv) > 2:
    cmd.extend(["--es", "utilisateur", sys.argv[2]])
r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
print(r.stdout.strip(), r.stderr.strip())
