"""Un switch 'Masquer' par appareil LAN — permet de retirer un appareil des
listes du dashboard (Connectés/Déconnectés) sans jamais le supprimer ni
arrêter son suivi : purement un filtre d'affichage, réversible à tout moment
(demande utilisateur 2026-07-26 : "je dois pouvoir le retirer, le remettre
ou encore le reconnecter si besoin"). L'appareil masqué continue d'être
suivi normalement en arrière-plan (device_tracker/lock/sensor toujours à
jour) — masquer n'affecte que la visibilité dans les cartes du dashboard,
pas le suivi réel ni le blocage Wifi.

État géré localement par l'entité (RestoreEntity), pas par le coordinator :
contrairement au lock (qui reflète l'état réel côté Freebox), "masqué" est
une préférence purement locale à Home Assistant sans équivalent côté
Freebox, donc pas besoin d'aller-retour API pour la lire/écrire."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import FreeboxDevicesCoordinator
from .entity import FreeboxDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FreeboxDevicesCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_macs: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_macs = set(coordinator.data) - known_macs
        if not new_macs:
            return
        known_macs.update(new_macs)
        async_add_entities(FreeboxHideSwitch(coordinator, mac) for mac in new_macs)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()


class FreeboxHideSwitch(FreeboxDeviceEntity, SwitchEntity, RestoreEntity):
    """ON = masqué (retiré des listes du dashboard), OFF = visible (défaut)."""

    _attr_translation_key = "masque"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: FreeboxDevicesCoordinator, mac: str) -> None:
        super().__init__(coordinator, mac)
        self._attr_unique_id = f"{mac}_hidden"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
