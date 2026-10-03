"""Écran de veille : musique de fond. Usage : python3 patch_veille_7.py /chemin/veille.py"""
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


shutil.copy2(BASE + "veille.py", BASE + "veille.py.bakveille7")
shutil.copy(sys.argv[1], BASE + "veille.py")
py_compile.compile(BASE + "veille.py", doraise=True)

s = lire("store.py")
if "veille_musique" not in s:
    s = remplacer(
        s,
        "        self.veille_flux_suffixe: str = \"\"\n",
        "        self.veille_flux_suffixe: str = \"\"\n"
        "        # Adresse d'un flux audio (radio sans publicité) joué par l'écran de veille ; vide = silence.\n"
        "        self.veille_musique: str = \"\"\n",
    )
    s = remplacer(
        s,
        '        self.veille_flux_suffixe = str(data.get("veille_flux_suffixe") or "").strip()\n',
        '        self.veille_flux_suffixe = str(data.get("veille_flux_suffixe") or "").strip()\n'
        '        self.veille_musique = str(data.get("veille_musique") or "").strip()\n',
    )
    s = remplacer(
        s,
        '                "veille_flux_suffixe": self.veille_flux_suffixe,\n',
        '                "veille_flux_suffixe": self.veille_flux_suffixe,\n'
        '                "veille_musique": self.veille_musique,\n',
    )
    ecrire("store.py", s, ".bakveille7")

t = lire("text.py")
if "VeilleMusiqueText" not in t:
    t = remplacer(
        t,
        "        VeilleFluxText(coordinator),\n",
        "        VeilleFluxText(coordinator),\n        VeilleMusiqueText(coordinator),\n",
    )
    t += '''

class VeilleMusiqueText(HubEntity, TextEntity):
    """La musique de l'écran de veille : l'adresse d'un flux audio (radio sans publicité).

    Vide, l'écran de veille reste silencieux. Le volume se règle à la télécommande.
    """

    _attr_name = "Écran de veille : musique"
    _attr_icon = "mdi:music-note"
    _attr_native_max = 255
    _attr_mode = "text"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_veille_musique"

    @property
    def native_value(self) -> str:
        return self.coordinator.store.veille_musique

    async def async_set_value(self, value: str) -> None:
        adresse = value.strip()
        if adresse and not adresse.startswith(("http://", "https://")):
            raise HomeAssistantError("L'adresse doit commencer par http:// ou https://.")

        def _faire() -> None:
            self.coordinator.store.veille_musique = adresse

        await appliquer(self.coordinator, _faire)
'''
    ecrire("text.py", t, ".bakveille7")
print("ok")
