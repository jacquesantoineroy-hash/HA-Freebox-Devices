"""Branche veille_pages.py (pages de veille composées avec des cartes Home Assistant,
tableau de bord `vision-veille`) dans la liste des tableaux envoyée aux appareils.
Usage sur HA : copier veille_pages.py à côté, puis python3 patch_veille_pages.py
"""
import py_compile
import shutil

BASE = "/homeassistant/custom_components/pc_parental/"
shutil.copy2("veille_pages.py", BASE + "veille_pages.py")
py_compile.compile(BASE + "veille_pages.py", doraise=True)

p = BASE + "veille_tableaux.py"
# Rejouable : on repart toujours du fichier d'avant le premier passage.
import os
if os.path.exists(p + ".bakpages"):
    t = open(p + ".bakpages", encoding="utf-8").read()
else:
    t = open(p, encoding="utf-8").read()
    shutil.copy2(p, p + ".bakpages")


def remplacer(a, b):
    global t
    assert a in t, a[:70]
    t = t.replace(a, b, 1)


remplacer(
    "async def _case(hass: HomeAssistant, c: dict[str, Any]) -> dict[str, Any]:\n",
    "async def _case_page(hass: HomeAssistant, c: dict[str, Any]) -> dict[str, Any]:\n"
    "    \"\"\"Une case venue d'une carte Home Assistant : du texte libre, ou une entité (bornes de jauge de la carte).\"\"\"\n"
    "    from . import veille_pages\n"
    "    if not c.get(\"entite\"):\n"
    "        return {\"entite\": \"\", \"nom\": c.get(\"libelle\") or \"Note\", \"rendu\": \"texte\",\n"
    "                \"texte\": await veille_pages.rendre_texte(hass, str(c.get(\"texte\") or \"\"))}\n"
    "    sortie = await _case(hass, c)\n"
    "    if sortie.get(\"rendu\") == \"jauge\":\n"
    "        for cle in (\"min\", \"max\"):\n"
    "            if cle in c:\n"
    "                sortie[cle] = c[cle]\n"
    "    return sortie\n\n\n"
    "async def _case(hass: HomeAssistant, c: dict[str, Any]) -> dict[str, Any]:\n",
)
remplacer(
    "        liste.append({\"code\": \"entites\", \"id\": t[\"id\"], \"titre\": t[\"titre\"], \"duree\": t[\"duree\"], \"cases\": cases})\n"
    "    return {\"profil\": qui[\"public\"], \"ecran\": ecran, \"liste\": liste}\n",
    "        liste.append({\"code\": \"entites\", \"id\": t[\"id\"], \"titre\": t[\"titre\"], \"duree\": t[\"duree\"], \"cases\": cases})\n"
    "    # Les pages composées avec des cartes dans le tableau de bord « Écran de veille ».\n"
    "    try:\n"
    "        from . import veille_pages\n"
    "        for page in await veille_pages.pages(hass):\n"
    "            if not _vise(page, ecran, qui):\n"
    "                continue\n"
    "            cases = [await _case_page(hass, c) for c in page[\"cases\"]]\n"
    "            cases = [c for c in cases if not c.get(\"absent\")]\n"
    "            if cases:\n"
    "                liste.append({\"code\": \"entites\", \"id\": page[\"id\"], \"titre\": page[\"titre\"], \"duree\": page[\"duree\"], \"cases\": cases})\n"
    "    except Exception:  # noqa: BLE001\n"
    "        pass\n"
    "    return {\"profil\": qui[\"public\"], \"ecran\": ecran, \"liste\": liste}\n",
)
open(p, "w", encoding="utf-8").write(t)
py_compile.compile(p, doraise=True)
print("ok pages")
