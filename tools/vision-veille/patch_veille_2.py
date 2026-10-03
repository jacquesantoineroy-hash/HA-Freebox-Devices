"""Écran de veille : courbe dehors / dedans sur 24 h. Usage : python3 patch_veille_2.py /chemin/veille.py"""
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


shutil.copy(sys.argv[1], BASE + "veille.py")
py_compile.compile(BASE + "veille.py", doraise=True)

s = lire("store.py")
if "veille_courbe" not in s:
    s = remplacer(
        s,
        "        self.veille_entites: list[str] = []\n",
        "        self.veille_entites: list[str] = []\n"
        "        # Les deux températures de la courbe (dehors, dedans) ; vide = déduit des tuiles.\n"
        "        self.veille_courbe: list[str] = []\n",
    )
    s = remplacer(
        s,
        '        choix = str(data.get("dns_filtrant") or DNS_AUCUN)\n',
        '        self.veille_courbe = [\n'
        '            str(v).strip() for v in (data.get("veille_courbe") or []) if str(v).strip()\n'
        '        ]\n'
        '        choix = str(data.get("dns_filtrant") or DNS_AUCUN)\n',
    )
    s = remplacer(
        s,
        '                "veille_entites": self.veille_entites,\n',
        '                "veille_entites": self.veille_entites,\n'
        '                "veille_courbe": self.veille_courbe,\n',
    )
    ecrire("store.py", s, ".bakveille2")

t = lire("text.py")
if "VeilleCourbeText" not in t:
    t = remplacer(
        t,
        "        VeilleText(coordinator),\n",
        "        VeilleText(coordinator),\n        VeilleCourbeText(coordinator),\n",
    )
    t += '''

class VeilleCourbeText(HubEntity, TextEntity):
    """Les deux températures de la courbe de l'écran de veille : dehors, dedans.

    Vide, la courbe prend les deux premières tuiles de température.
    """

    _attr_name = "Écran de veille : courbe"
    _attr_icon = "mdi:chart-bell-curve-cumulative"
    _attr_native_max = 255
    _attr_mode = "text"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_veille_courbe"

    @property
    def native_value(self) -> str:
        return ", ".join(self.coordinator.store.veille_courbe)

    async def async_set_value(self, value: str) -> None:
        choisies: list[str] = []
        for entree in decouper(value):
            eid = entree.split("|")[0].strip()
            if self.hass.states.get(eid) is None:
                raise HomeAssistantError(f"Entité inconnue : « {eid} ».")
            choisies.append(entree)

        def _faire() -> None:
            self.coordinator.store.veille_courbe = choisies[:2]

        await appliquer(self.coordinator, _faire)
'''
    ecrire("text.py", t, ".bakveille2")
print("ok")
