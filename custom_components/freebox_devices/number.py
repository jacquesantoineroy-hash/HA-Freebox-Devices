"""Entité 'Colonnes tableau de bord' : un curseur number qui ajuste en
direct le nombre de colonnes des sections Connectés/Déconnectés du
dashboard Freebox.

Pas de dépendance externe (pas de card-mod) : la valeur choisie patche
directement la config Lovelace stockée côté serveur, via l'API interne du
composant lovelace (`hass.data["lovelace"]["dashboards"][url_path]`) —
c'est exactement le même mécanisme que la commande WebSocket
`lovelace/config/save` utilisée par le frontend (cf.
homeassistant/components/lovelace/websocket.py: `await
config.async_save(msg["config"])`). Cette API est interne/non documentée
publiquement : si elle change lors d'une future mise à jour majeure de HA
Core, cette entité échouera silencieusement (log d'avertissement) sans
casser le reste de l'intégration.
"""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DASHBOARD_URL_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

_MIN_COLUMNS = 2
_MAX_COLUMNS = 8
_DEFAULT_COLUMNS = 3

# Sections ciblées par sous-chaîne présente dans leur carte "heading" — pas
# d'index fixe, pour rester robuste si l'ordre des sections change.
_TARGET_HEADINGS = ("Connectés", "Déconnectés")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([FreeboxDashboardColumnsNumber(hass, entry)])


class FreeboxDashboardColumnsNumber(NumberEntity, RestoreEntity):
    """Nombre de colonnes des listes Connectés/Déconnectés du dashboard Freebox."""

    _attr_has_entity_name = True
    _attr_translation_key = "dashboard_colonnes"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = _MIN_COLUMNS
    _attr_native_max_value = _MAX_COLUMNS
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:view-grid-plus"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_dashboard_columns"
        self._attr_native_value = _DEFAULT_COLUMNS

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            None,
            "unknown",
            "unavailable",
        ):
            try:
                self._attr_native_value = float(last_state.state)
            except ValueError:
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        try:
            await self._async_apply_to_dashboard(int(value))
        except Exception:  # noqa: BLE001 - ne doit jamais planter l'entité
            _LOGGER.exception("Impossible de mettre à jour le dashboard Freebox")

    async def _async_apply_to_dashboard(self, columns: int) -> None:
        lovelace_data = self.hass.data.get("lovelace")
        if not lovelace_data:
            _LOGGER.warning(
                "Composant lovelace introuvable, dashboard non mis à jour"
            )
            return
        store = lovelace_data.get("dashboards", {}).get(DASHBOARD_URL_PATH)
        if store is None:
            _LOGGER.warning("Dashboard '%s' introuvable", DASHBOARD_URL_PATH)
            return

        try:
            config = await store.async_load(False)
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Impossible de charger le dashboard '%s'", DASHBOARD_URL_PATH
            )
            return

        changed = False
        for view in config.get("views", []):
            for section in view.get("sections", []):
                cards = section.get("cards", [])
                heading_card = next(
                    (c for c in cards if c.get("type") == "heading"), None
                )
                heading = (heading_card or {}).get("heading", "")
                if not any(target in heading for target in _TARGET_HEADINGS):
                    continue
                auto_card = next(
                    (c for c in cards if c.get("type") == "custom:auto-entities"),
                    None,
                )
                if auto_card is None:
                    continue

                auto_card.setdefault("card", {})["columns"] = columns
                if columns > 3:
                    section["column_span"] = 2
                    auto_card["layout_options"] = {"grid_columns": "full"}
                else:
                    section.pop("column_span", None)
                    auto_card.pop("layout_options", None)
                changed = True

        if not changed:
            _LOGGER.warning(
                "Aucune section Connectés/Déconnectés trouvée dans '%s'",
                DASHBOARD_URL_PATH,
            )
            return

        await store.async_save(config)
        _LOGGER.debug(
            "Dashboard '%s' mis à jour : %s colonnes", DASHBOARD_URL_PATH, columns
        )
