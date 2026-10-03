"""Écran de veille : thème, nuit, radios, photos, réglages depuis la télé.
Usage : python3 patch_veille_8.py /dossier (contenant veille.py, esports.py, veille_plus.py)
"""
import py_compile
import shutil
import sys

BASE = "/homeassistant/custom_components/pc_parental/"
src = sys.argv[1].rstrip("/") + "/"


def lire(nom):
    return open(BASE + nom, encoding="utf-8").read()


def ecrire(nom, texte, suffixe):
    shutil.copy2(BASE + nom, BASE + nom + suffixe)
    open(BASE + nom, "w", encoding="utf-8").write(texte)
    py_compile.compile(BASE + nom, doraise=True)


def remplacer(texte, ancien, nouveau):
    assert ancien in texte, ancien[:70]
    return texte.replace(ancien, nouveau, 1)


for nom in ("veille.py", "esports.py"):
    shutil.copy2(BASE + nom, BASE + nom + ".bakveille8")
    shutil.copy(src + nom, BASE + nom)
shutil.copy(src + "veille_plus.py", BASE + "veille_plus.py")
for nom in ("veille.py", "esports.py", "veille_plus.py"):
    py_compile.compile(BASE + nom, doraise=True)

s = lire("store.py")
if "veille_theme" not in s:
    s = remplacer(
        s,
        "        self.veille_musique: str = \"\"\n",
        "        self.veille_musique: str = \"\"\n"
        "        # Thème de couleurs de l'écran de veille, et plage horaire du mode nuit (« 23:00-07:00 », vide = jamais).\n"
        "        self.veille_theme: str = \"Beige\"\n"
        "        self.veille_nuit: str = \"23:00-07:00\"\n",
    )
    s = remplacer(
        s,
        '        self.veille_musique = str(data.get("veille_musique") or "").strip()\n',
        '        self.veille_musique = str(data.get("veille_musique") or "").strip()\n'
        '        self.veille_theme = str(data.get("veille_theme") or "Beige")\n'
        '        self.veille_nuit = str(data.get("veille_nuit") if data.get("veille_nuit") is not None else "23:00-07:00")\n',
    )
    s = remplacer(
        s,
        '                "veille_musique": self.veille_musique,\n',
        '                "veille_musique": self.veille_musique,\n'
        '                "veille_theme": self.veille_theme,\n'
        '                "veille_nuit": self.veille_nuit,\n',
    )
    ecrire("store.py", s, ".bakveille8")

t = lire("text.py")
if "VeilleNuitText" not in t:
    t = remplacer(
        t,
        "        VeilleMusiqueText(coordinator),\n",
        "        VeilleMusiqueText(coordinator),\n        VeilleNuitText(coordinator),\n",
    )
    t += '''

class VeilleNuitText(HubEntity, TextEntity):
    """La plage du mode nuit de l'écran de veille : fond sombre, musique coupée.

    Au format « 23:00-07:00 » ; vide = jamais.
    """

    _attr_name = "Écran de veille : nuit"
    _attr_icon = "mdi:weather-night"
    _attr_native_max = 11
    _attr_mode = "text"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_veille_nuit"

    @property
    def native_value(self) -> str:
        return self.coordinator.store.veille_nuit

    async def async_set_value(self, value: str) -> None:
        import re as _re

        plage = value.strip()
        if plage and not _re.fullmatch(r"\\d\\d:\\d\\d-\\d\\d:\\d\\d", plage):
            raise HomeAssistantError("Format attendu : « 23:00-07:00 » (ou vide pour jamais).")

        def _faire() -> None:
            self.coordinator.store.veille_nuit = plage

        await appliquer(self.coordinator, _faire)
'''
    ecrire("text.py", t, ".bakveille8")

sel = lire("select.py")
if "VeilleThemeSelect" not in sel:
    sel = remplacer(
        sel,
        "        DnsFiltrantSelect(coordinator),\n",
        "        DnsFiltrantSelect(coordinator),\n        VeilleThemeSelect(coordinator),\n        VeilleRadioSelect(coordinator),\n",
    )
    sel += '''

class VeilleThemeSelect(HubEntity, SelectEntity):
    """Les couleurs de l'écran de veille de la télé."""

    _attr_name = "Écran de veille : thème"
    _attr_icon = "mdi:palette"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        from .veille_plus import THEMES

        self._attr_options = list(THEMES)
        self._attr_unique_id = f"{DOMAIN}_veille_theme"

    @property
    def current_option(self) -> str:
        return self.coordinator.store.veille_theme if self.coordinator.store.veille_theme in self._attr_options else self._attr_options[0]

    async def async_select_option(self, option: str) -> None:
        coord = self.coordinator

        def _faire() -> None:
            coord.store.veille_theme = option

        await appliquer(coord, _faire)


class VeilleRadioSelect(HubEntity, SelectEntity):
    """La radio de l'écran de veille, parmi des stations sans publicité.

    « Personnalisée » apparaît quand l'adresse (Écran de veille : musique) n'est pas dans la liste.
    """

    _attr_name = "Écran de veille : radio"
    _attr_icon = "mdi:radio"

    def __init__(self, coordinator: PcParentalCoordinator) -> None:
        super().__init__(coordinator)
        from .veille_plus import RADIOS, RADIO_PERSONNALISEE

        self._radios = dict(RADIOS)
        self._attr_options = [n for n, _ in RADIOS] + [RADIO_PERSONNALISEE]
        self._attr_unique_id = f"{DOMAIN}_veille_radio"

    @property
    def current_option(self) -> str:
        from .veille_plus import radio_nom

        return radio_nom(self.coordinator.store.veille_musique)

    async def async_select_option(self, option: str) -> None:
        if option not in self._radios:
            return  # « Personnalisée » : l'adresse se tape dans le champ texte
        coord = self.coordinator
        url = self._radios[option]

        def _faire() -> None:
            coord.store.veille_musique = url

        await appliquer(coord, _faire)
'''
    ecrire("select.py", sel, ".bakveille8")

h = lire("http.py")
if "PcParentalVeillePhotoView" not in h:
    shutil.copy2(BASE + "http.py", BASE + "http.py.bakveille8")
    ancre = "from .esports import PcParentalVeilleLogoView\n"
    assert ancre in h
    h = h.replace(ancre, ancre + "from .veille_plus import PcParentalVeillePhotoView, PcParentalVeilleReglagesView\n", 1)
    ancre2 = "    hass.http.register_view(PcParentalVeilleLogoView(hass))\n"
    assert ancre2 in h
    h = h.replace(ancre2, ancre2 + "    hass.http.register_view(PcParentalVeillePhotoView(hass))\n    hass.http.register_view(PcParentalVeilleReglagesView(hass))\n", 1)
    open(BASE + "http.py", "w", encoding="utf-8").write(h)
    py_compile.compile(BASE + "http.py", doraise=True)
print("ok")
