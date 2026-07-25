"""Config flow : hôte de la Freebox, puis appairage (bouton flèche)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AUTHORIZE_STATUS_DENIED,
    AUTHORIZE_STATUS_GRANTED,
    AUTHORIZE_STATUS_TIMEOUT,
    CONF_APP_TOKEN,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)
from .freebox_client import FreeboxApiError, FreeboxLocalClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

# Le bouton flèche de la Freebox expire l'appairage après ~90s côté firmware.
_AUTHORIZE_POLL_INTERVAL = 2
_AUTHORIZE_MAX_ATTEMPTS = 60  # ~120s


class PairingDenied(Exception):
    """Appairage refusé ou expiré."""


class FreeboxDevicesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flow de configuration en 2 étapes : hôte, puis appairage."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int | None = None
        self._client: FreeboxLocalClient | None = None
        self._app_token: str | None = None
        self._track_id: int | None = None
        self._task_authorize: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            unique_id = f"{self._host}:{self._port}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass, verify_ssl=False)
            self._client = FreeboxLocalClient(session, self._host, self._port)
            try:
                self._app_token, self._track_id = (
                    await self._client.async_request_authorization()
                )
            except FreeboxApiError as err:
                _LOGGER.warning("Échec démarrage appairage: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_pair()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._task_authorize is None:
            self._task_authorize = self.hass.async_create_task(
                self._async_wait_for_authorization()
            )

        if not self._task_authorize.done():
            return self.async_show_progress(
                step_id="pair",
                progress_action="wait_for_button",
                progress_task=self._task_authorize,
            )

        try:
            await self._task_authorize
        except PairingDenied:
            return self.async_show_progress_done(next_step_id="pair_denied")
        except FreeboxApiError as err:
            _LOGGER.warning("Échec appairage: %s", err)
            return self.async_show_progress_done(next_step_id="pair_failed")

        return self.async_show_progress_done(next_step_id="pair_done")

    async def _async_wait_for_authorization(self) -> None:
        assert self._client is not None and self._track_id is not None
        for _ in range(_AUTHORIZE_MAX_ATTEMPTS):
            status = await self._client.async_get_authorization_status(self._track_id)
            if status == AUTHORIZE_STATUS_GRANTED:
                return
            if status in (AUTHORIZE_STATUS_DENIED, AUTHORIZE_STATUS_TIMEOUT):
                raise PairingDenied(status)
            await asyncio.sleep(_AUTHORIZE_POLL_INTERVAL)
        raise PairingDenied("timeout_local")

    async def async_step_pair_done(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_create_entry(
            title=f"Freebox ({self._host})",
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_APP_TOKEN: self._app_token,
            },
        )

    async def async_step_pair_denied(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_abort(reason="pairing_denied")

    async def async_step_pair_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_abort(reason="cannot_connect")
