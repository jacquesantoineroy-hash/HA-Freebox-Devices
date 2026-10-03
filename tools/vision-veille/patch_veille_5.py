"""Écran de veille : flux secondaire des caméras. Usage : python3 patch_veille_5.py /chemin/veille.py"""
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


shutil.copy2(BASE + "veille.py", BASE + "veille.py.bakveille5")
shutil.copy(sys.argv[1], BASE + "veille.py")
py_compile.compile(BASE + "veille.py", doraise=True)

s = lire("store.py")
if "veille_flux_suffixe" not in s:
    s = remplacer(
        s,
        "        self.veille_courbe: list[str] = []\n",
        "        self.veille_courbe: list[str] = []\n"
        "        # Suffixe du flux secondaire des caméras pour la télé (« _sub » chez Frigate) ; vide = flux normal.\n"
        "        self.veille_flux_suffixe: str = \"\"\n",
    )
    s = remplacer(
        s,
        '        choix = str(data.get("dns_filtrant") or DNS_AUCUN)\n',
        '        self.veille_flux_suffixe = str(data.get("veille_flux_suffixe") or "").strip()\n'
        '        choix = str(data.get("dns_filtrant") or DNS_AUCUN)\n',
    )
    s = remplacer(
        s,
        '                "veille_courbe": self.veille_courbe,\n',
        '                "veille_courbe": self.veille_courbe,\n'
        '                "veille_flux_suffixe": self.veille_flux_suffixe,\n',
    )
    ecrire("store.py", s, ".bakveille5")

t = lire("text.py")
if "VeilleFluxText" not in t:
    t = remplacer(
        t,
        "        VeilleCourbeText(coordinator),\n",
        "        VeilleCourbeText(coordinator),\n        VeilleFluxText(coordinator),\n",
    )
    t += '''

class VeilleFluxText(HubEntity, TextEntity):
    """Suffixe du flux secondaire des caméras pour l'écran de veille.

    Une télé ne décode pas plusieurs flux 4K : avec « _sub » (Frigate, go2rtc),
    l'écran de veille lit le flux léger de chaque caméra. Vide = flux normal.
    """

    _attr_name = "Écran de veille : flux secondaire"
    _attr_icon = "mdi:video-switch"
    _attr_native_max = 40
    _attr_mode = "text"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_veille_flux_suffixe"

    @property
    def native_value(self) -> str:
        return self.coordinator.store.veille_flux_suffixe

    async def async_set_value(self, value: str) -> None:
        suffixe = value.strip()

        def _faire() -> None:
            self.coordinator.store.veille_flux_suffixe = suffixe

        await appliquer(self.coordinator, _faire)
'''
    ecrire("text.py", t, ".bakveille5")
print("ok")
