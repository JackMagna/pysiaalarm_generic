"""Config flow per pySIAAlarm integration."""
from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util.network import is_valid_listen_port

from pysiaalarm import SIAAccount, InvalidAccountLengthError, InvalidKeyLengthError
from pysiaalarm.aio import SIAClient

from .const import DOMAIN, CONF_ACCOUNT_ID, CONF_ENCRYPTION_KEY

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "SIA Alarm Panel"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7777

# Schema per configurazione manuale  
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST, default=DEFAULT_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=65535, mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_ACCOUNT_ID, default="005544"): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.TEXT,
                placeholder="Account ID (3-16 caratteri hex)"
            )
        ),
        vol.Optional(CONF_ENCRYPTION_KEY): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.PASSWORD,
                placeholder="Chiave AES (16/24/32 caratteri, opzionale)"
            )
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Valida i dati di configurazione inseriti dall'utente."""
    
    host = data[CONF_HOST]
    port = data[CONF_PORT] 
    account_id = data[CONF_ACCOUNT_ID]
    encryption_key = data.get(CONF_ENCRYPTION_KEY)
    name = data[CONF_NAME]
    
    # Validazione porta
    if not is_valid_listen_port(port):
        raise InvalidPort(f"Porta {port} non valida")
    
    # Validazione account SIA
    try:
        account = SIAAccount(account_id, encryption_key)
    except (InvalidAccountLengthError, InvalidKeyLengthError) as err:
        _LOGGER.error("Account SIA non valido: %s", err)
        raise InvalidAuth from err
    
    # Test connessione (opzionale ma utile)
    try:
        # Verifica se la porta è già in uso
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind((host, port))
        test_socket.close()
    except OSError as err:
        _LOGGER.error("Impossibile bind su %s:%s - %s", host, port, err)
        raise CannotConnect(f"Porta {port} già in uso o indirizzo non valido") from err
    
    return {
        "title": name,
        "host": host,
        "port": port,
        "account_id": account_id,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow per pySIAAlarm."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - configurazione manuale."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect as err:
                _LOGGER.error("Errore connessione: %s", err)
                errors["base"] = "cannot_connect"
            except InvalidAuth as err:
                _LOGGER.error("Credenziali non valide: %s", err) 
                errors["base"] = "invalid_auth"
            except InvalidPort as err:
                _LOGGER.error("Porta non valida: %s", err)
                errors[CONF_PORT] = "invalid_port"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Errore inaspettato durante validazione: %s", err)
                errors["base"] = "unknown"
            else:
                # Controlla se già configurato per questo account
                await self.async_set_unique_id(user_input[CONF_ACCOUNT_ID])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/JackMagna/pysiaalarm_generic"
            },
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow per modificare configurazione esistente."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Schema per opzioni (impostazioni avanzate)
        options_schema = vol.Schema(
            {
                vol.Optional(
                    "ping_interval",
                    default=self.config_entry.options.get("ping_interval", 30),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10, max=300, step=5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    "zones_to_monitor",
                    default=self.config_entry.options.get("zones_to_monitor", ""),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        placeholder="1,2,3,4 (vuoto = tutte le zone)"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidPort(HomeAssistantError):
    """Error to indicate invalid port configuration."""
