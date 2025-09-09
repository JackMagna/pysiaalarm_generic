"""Config flow per pySIAAlarm integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from pysiaalarm import SIAAccount, InvalidAccountLengthError, InvalidKeyLengthError

from .const import DOMAIN, CONF_ACCOUNT_ID, CONF_ENCRYPTION_KEY

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="0.0.0.0"): str,
        vol.Required(CONF_PORT, default=7777): int,
        vol.Required(CONF_ACCOUNT_ID): str,
        vol.Optional(CONF_ENCRYPTION_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Valida i dati inseriti dall'utente."""
    
    account_id = data[CONF_ACCOUNT_ID]
    encryption_key = data.get(CONF_ENCRYPTION_KEY)
    
    # Valida account SIA
    try:
        SIAAccount(account_id, encryption_key)
    except (InvalidAccountLengthError, InvalidKeyLengthError) as err:
        raise InvalidAuth from err
    
    # Test connessione (opzionale)
    # Qui si potrebbe testare la connessione al sistema SIA
    
    return {"title": f"SIA Alarm {account_id}"}


class ConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow per pySIAAlarm."""

    domain = DOMAIN

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Errore inaspettato")
                errors["base"] = "unknown"
            else:
                # Controlla se già configurato
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
