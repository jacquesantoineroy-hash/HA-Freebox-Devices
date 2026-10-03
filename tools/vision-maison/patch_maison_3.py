"""Vision : les cartes de personne prennent toute la largeur de leur section
(une section élargie compte 24 colonnes, une carte à 12 n'en faisait que la moitié)."""
import py_compile
import shutil

p = "/homeassistant/custom_components/pc_parental/dashboard.py"
d = open(p, encoding="utf-8").read()
shutil.copy2(p, p + ".bakmaison3")
n = 0
for mode in ("maison", "personne"):
    ancien = '"type": "custom:vision-maison-card",\n                        "mode": "%s",' % mode
    if ancien not in d:
        ancien = '"type": "custom:vision-maison-card",\n                    "mode": "%s",' % mode
    assert ancien in d, mode
    indent = " " * (len(ancien.split("\n")[1]) - len(ancien.split("\n")[1].lstrip()))
    d = d.replace(ancien, ancien + '\n' + indent + '"grid_options": {"columns": "full"},', 1)
    n += 1
open(p, "w", encoding="utf-8").write(d)
py_compile.compile(p, doraise=True)
print("ok", n)
