"""Classe de base commune pour les entités liées à un profil de contrôle
parental (regroupées sous un appareil HA distinct par profil, rattaché au
hub Freebox)."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DESC, DOMAIN
from .parental_coordinator import FreeboxParentalCoordinator


class FreeboxParentalEntity(CoordinatorEntity[FreeboxParentalCoordinator]):
    """Entité liée à un profil précis (identifié par son id de filtre Freebox)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreeboxParentalCoordinator, filter_id: int) -> None:
        super().__init__(coordinator)
        self._filter_id = filter_id

    @property
    def _profile(self) -> dict:
        return self.coordinator.data.get(self._filter_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._filter_id in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        profile = self._profile
        name = profile.get(ATTR_DESC) or f"Profil {self._filter_id}"
        return DeviceInfo(
            identifiers={(DOMAIN, f"parental_{self._filter_id}")},
            name=f"Contrôle parental : {name}",
            manufacturer="Freebox SAS",
            model="Profil de contrôle parental",
            via_device=(DOMAIN, self.coordinator.entry.entry_id),
        )
