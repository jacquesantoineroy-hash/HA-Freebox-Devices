"""Un bouton 'Pause' par profil de contrôle parental : coupe l'accès pour
une durée fixe (tmp_mode/tmp_mode_expire natifs de l'API Freebox), puis
retombe automatiquement sur le planning normal — aucune action de reprise
nécessaire côté utilisateur."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_TMP_MODE,
    ATTR_TMP_MODE_EXPIRE,
    DOMAIN,
    PARENTAL_STATE_DENIED,
    PARENTAL_TMP_MODE_DURATION,
)
from .parental_coordinator import FreeboxParentalCoordinator
from .parental_entity import FreeboxParentalEntity

_LOGGER = logging.getLogger(__name__)


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
        async_add_entities(FreeboxParentalPauseButton(coordinator, fid) for fid in new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_profiles))
    _add_new_profiles()


class FreeboxParentalPauseButton(FreeboxParentalEntity, ButtonEntity):
    """Coupe l'accès du profil pendant 1h, reprise automatique ensuite."""

    _attr_translation_key = "pause_profil"
    _attr_icon = "mdi:pause-circle-outline"

    def __init__(self, coordinator: FreeboxParentalCoordinator, filter_id: int) -> None:
        super().__init__(coordinator, filter_id)
        self._attr_unique_id = f"parental_{filter_id}_pause"

    async def async_press(self) -> None:
        await self.coordinator.client.async_update_parental_filter(
            self._filter_id,
            **{
                ATTR_TMP_MODE: PARENTAL_STATE_DENIED,
                ATTR_TMP_MODE_EXPIRE: PARENTAL_TMP_MODE_DURATION,
            },
        )
        await self.coordinator.async_request_refresh()
