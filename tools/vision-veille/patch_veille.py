"""Écran de veille Vision côté HA : vue /api/pc_parental/veille, réglage
« Écran de veille : entités ». Usage : python3 patch_veille.py /chemin/veille.py
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"


def lire(nom):
    return open(BASE + nom, encoding="utf-8").read()


def ecrire(nom, texte, suffixe):
    shutil.copy2(BASE + nom, BASE + nom + suffixe)
    open(BASE + nom, "w", encoding="utf-8").write(texte)
    py_compile.compile(BASE + nom, doraise=True)


def remplacer(texte, ancien, nouveau):
    assert ancien in texte, ancien[:70]
    return texte.replace(ancien, nouveau, 1)


# 1. veille.py
shutil.copy(sys.argv[1], BASE + "veille.py")
py_compile.compile(BASE + "veille.py", doraise=True)

# 2. store.py : la liste des entités de l'écran de veille
s = lire("store.py")
if "veille_entites" not in s:
    s = remplacer(
        s,
        "        self.divertissement: list[str] = list(DIVERTISSEMENT_DEFAUT)\n",
        "        self.divertissement: list[str] = list(DIVERTISSEMENT_DEFAUT)\n"
        "        # Ce que la télé montre en veille : des entités, « id|Titre » au choix.\n"
        "        self.veille_entites: list[str] = []\n",
    )
    s = remplacer(
        s,
        '        choix = str(data.get("dns_filtrant") or DNS_AUCUN)\n',
        '        self.veille_entites = [\n'
        '            str(v).strip() for v in (data.get("veille_entites") or []) if str(v).strip()\n'
        '        ]\n'
        '        choix = str(data.get("dns_filtrant") or DNS_AUCUN)\n',
    )
    s = remplacer(
        s,
        '                "divertissement": self.divertissement,\n            }\n',
        '                "divertissement": self.divertissement,\n'
        '                "veille_entites": self.veille_entites,\n            }\n',
    )
    ecrire("store.py", s, ".bakveille")

# 3. text.py : l'entité de réglage
t = lire("text.py")
if "VeilleText" not in t:
    t = remplacer(
        t,
        "        DivertissementText(coordinator),\n",
        "        DivertissementText(coordinator),\n        VeilleText(coordinator),\n",
    )
    t += '''

class VeilleText(HubEntity, TextEntity):
    """Les entités que la télé affiche en veille, séparées par des virgules.

    `sensor.exterieur|Dehors` renomme la tuile. Une entité inconnue est
    refusée tout de suite : mieux vaut une erreur ici qu'une tuile vide
    sur l'écran du salon.
    """

    _attr_name = "Écran de veille : entités"
    _attr_icon = "mdi:television-ambient-light"
    _attr_native_max = 255
    _attr_mode = "text"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_veille_entites"

    @property
    def native_value(self) -> str:
        return ", ".join(self.coordinator.store.veille_entites)

    async def async_set_value(self, value: str) -> None:
        choisies: list[str] = []
        for entree in decouper(value):
            eid = entree.split("|")[0].strip()
            if self.hass.states.get(eid) is None:
                raise HomeAssistantError(f"Entité inconnue : « {eid} ».")
            if entree not in choisies:
                choisies.append(entree)

        def _faire() -> None:
            self.coordinator.store.veille_entites = choisies

        await appliquer(self.coordinator, _faire)
'''
    ecrire("text.py", t, ".bakveille")

# 4. http.py : enregistrer la vue
h = lire("http.py")
if "PcParentalVeilleView" not in h:
    h = remplacer(
        h,
        "from .demandes import PcParentalDemandeView\n",
        "from .demandes import PcParentalDemandeView\nfrom .veille import PcParentalVeilleView\n",
    )
    h = remplacer(
        h,
        "    hass.http.register_view(PcParentalDemandeView(hass))\n",
        "    hass.http.register_view(PcParentalDemandeView(hass))\n"
        "    hass.http.register_view(PcParentalVeilleView(hass))\n",
    )
    ecrire("http.py", h, ".bakveille")
print("ok")
