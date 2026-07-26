"""DataUpdateCoordinator dédié aux profils de contrôle parental
(ParentalFilter). Séparé du coordinator des appareils LAN car ces profils
changent rarement — poll moins fréquent (30s par défaut) pour ne pas
solliciter la Freebox inutilement.
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_FILTER_ID, DEFAULT_PARENTAL_SCAN_INTERVAL, DOMAIN
from .freebox_client import FreeboxApiError, FreeboxLocalClient

_LOGGER = logging.getLogger(__name__)


class FreeboxParentalCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Poll la Freebox et expose les profils de contrôle parental, indexés par id."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: FreeboxLocalClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_parental",
            update_interval=timedelta(seconds=DEFAULT_PARENTAL_SCAN_INTERVAL),
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            filters = await self.client.async_get_parental_filters()
        except FreeboxApiError as err:
            raise UpdateFailed(str(err)) from err
        return {f[ATTR_FILTER_ID]: f for f in filters}
