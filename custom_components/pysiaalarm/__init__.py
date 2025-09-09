"""pySIAAlarm integration per Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from pysiaalarm import SIAAccount, SIAEvent
from pysiaalarm.aio import SIAClient

from .const import DOMAIN, CONF_ACCOUNT_ID, CONF_ENCRYPTION_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


class SIAAlarmData:
    """Classe per gestire dati condivisi dell'integrazione."""
    
    def __init__(self, client: SIAClient):
        self.client = client
        self.events: list[SIAEvent] = []
        self.listeners: list[callable] = []
    
    def add_listener(self, callback: callable):
        """Aggiunge un listener per eventi SIA."""
        self.listeners.append(callback)
    
    def remove_listener(self, callback: callable):
        """Rimuove un listener per eventi SIA."""
        if callback in self.listeners:
            self.listeners.remove(callback)
    
    def _on_sia_event(self, event: SIAEvent):
        """Gestisce eventi SIA ricevuti."""
        _LOGGER.debug("Evento SIA ricevuto: %s", event)
        self.events.append(event)
        
        # Notifica tutti i listeners in modo thread-safe
        for listener in self.listeners:
            try:
                # Chiama il listener (può essere sync o async)
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(event))
                else:
                    listener(event)
            except Exception as err:
                _LOGGER.error("Errore nel listener SIA: %s", err)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Setup dell'integrazione pysiaalarm."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup di una config entry."""
    _LOGGER.debug("Setup entry: %s", entry.data)
    
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    account_id = entry.data[CONF_ACCOUNT_ID]
    encryption_key = entry.data.get(CONF_ENCRYPTION_KEY)
    
    # Crea account SIA
    account = SIAAccount(account_id, encryption_key)
    
    # Inizializza dati condivisi
    sia_data = SIAAlarmData(None)
    
    # Crea client SIA asincrono
    try:
        # Wrapper asincrono per il callback
        async def async_event_handler(event: SIAEvent):
            """Wrapper asincrono per gestire eventi SIA."""
            sia_data._on_sia_event(event)
        
        client = SIAClient(
            host=host,
            port=port,
            accounts=[account],
            function=async_event_handler
        )
        sia_data.client = client
        
        # Avvia il client asincrono
        await client.start()
        _LOGGER.info("Client SIA avviato su %s:%s per account %s", host, port, account_id)
        
    except Exception as err:
        _LOGGER.error("Errore setup client SIA: %s", err)
        raise ConfigEntryNotReady(f"Impossibile connettersi a {host}:{port}") from err
    
    # Salva dati nell'hass
    hass.data[DOMAIN][entry.entry_id] = sia_data
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload di una config entry."""
    _LOGGER.debug("Unload entry: %s", entry.entry_id)
    
    # Ferma il client SIA asincrono
    if entry.entry_id in hass.data[DOMAIN]:
        sia_data: SIAAlarmData = hass.data[DOMAIN][entry.entry_id]
        if sia_data.client:
            await sia_data.client.stop()
            _LOGGER.info("Client SIA fermato per account %s", entry.data[CONF_ACCOUNT_ID])
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
