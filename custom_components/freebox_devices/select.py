"""Un select 'Mode' par profil de contrôle parental : bascule rapide entre
planning automatique et un mode forcé (autorisé/bloqué/web uniquement).

Pour les plages horaires détaillées (jours + heures précises), voir le
service `freebox_devices.definir_plage_horaire` plutôt que ce select — ce
sélecteur ne couvre que les 4 grands modes globaux d'un profil.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_FORCED,
    ATTR_FORCED_MODE,
    ATTR_SCHEDULING_MODE,
    ATTR_TMP_MODE_EXPIRE,
    DOMAIN,
    PARENTAL_STATE_ALLOWED,
    PARENTAL_STATE_DENIED,
    PARENTAL_STATE_WEBONLY,
)
from .parental_coordinator import FreeboxParentalCoordinator
from .parental_entity import FreeboxParentalEntity

_LOGGER = logging.getLogger(__name__)

OPTION_PLANNING = "Planning (automatique)"
OPTION_ALLOWED = "Toujours autorisé"
OPTION_DENIED = "Toujours bloqué"
OPTION_WEBONLY = "Web uniquement"

_OPTION_TO_FORCED_MODE = {
    OPTION_ALLOWED: PARENTAL_STATE_ALLOWED,
    OPTION_DENIED: PARENTAL_STATE_DENIED,
    OPTION_WEBONLY: PARENTAL_STATE_WEBONLY,
}
_FORCED_MODE_TO_OPTION = {v: k for k, v in _OPTION_TO_FORCED_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: FreeboxParentalCoordinator = hass.data[DOMAIN][entry.entry_id]["parental"]
    known_ids: set[int] = set()

    @callback
    def _add_new_profiles() -> None:
        new_ids = set(coordinator.data) - known_ids
        if not new_ids:
            return
        known_ids.update(new_ids)
        async_add_entities(FreeboxParentalModeSelect(coordinator, fid) for fid in new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_profiles))
    _add_new_profiles()


class FreeboxParentalModeSelect(FreeboxParentalEntity, SelectEntity):
    """Mode global du profil : planning automatique ou forcé."""

    _attr_translation_key = "mode_profil"
    _attr_icon = "mdi:account-child"
    _attr_options = [OPTION_PLANNING, OPTION_ALLOWED, OPTION_DENIED, OPTION_WEBONLY]

    def __init__(self, coordinator: FreeboxParentalCoordinator, filter_id: int) -> None:
        super().__init__(coordinator, filter_id)
        self._attr_unique_id = f"parental_{filter_id}_mode"

    @property
    def current_option(self) -> str | None:
        profile = self._profile
        if not profile:
            return None
        if profile.get(ATTR_SCHEDULING_MODE) == "forced":
            return _FORCED_MODE_TO_OPTION.get(profile.get(ATTR_FORCED_MODE), OPTION_PLANNING)
        # "planning" ou "temporary" (la pause temporaire retombe seule sur le
        # planning à expiration, pas besoin d'un 5e état ici)
        return OPTION_PLANNING

    async def async_select_option(self, option: str) -> None:
        if option == OPTION_PLANNING:
            fields = {ATTR_FORCED: False, ATTR_TMP_MODE_EXPIRE: 0}
        else:
            forced_mode = _OPTION_TO_FORCED_MODE[option]
            fields = {ATTR_FORCED: True, ATTR_FORCED_MODE: forced_mode}
        await self.coordinator.client.async_update_parental_filter(self._filter_id, **fields)
        await self.coordinator.async_request_refresh()
