"""pySIAAlarm integration per Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .sia import SIAAccount, SIAEvent
from .sia.aio import SIAClient

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
        
        # Notifica tutti i listeners
        for listener in self.listeners:
            try:
                listener(event)
            except Exception as err:
                _LOGGER.error("Errore nel listener SIA: %s", err)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Setup dell'integrazione pysiaalarm."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup di una config entry."""
    _LOGGER.info("🚀 AVVIO SETUP PYSIAALARM per entry: %s", entry.data)
    
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    account_id = entry.data[CONF_ACCOUNT_ID]
    encryption_key = entry.data.get(CONF_ENCRYPTION_KEY)
    
    _LOGGER.info("📋 Configurazione: Host=%s, Port=%s, Account=%s, Encryption=%s", 
                host, port, account_id, "Sì" if encryption_key else "No")
    
    # Crea account SIA
    # NOTE: imposto `allowed_timeband=None` per bypassare temporaneamente
    # la validazione del timestamp nella libreria durante il debug.
    # Questo evita che eventi legittimi vengano scartati se ci sono
    # discrepanze di orologio o comportamenti diversi nella versione
    # installata della libreria. Rimuovere o modificare dopo fix permanente.
    account = SIAAccount(account_id, encryption_key, allowed_timeband=None)
    
    # Inizializza dati condivisi PRIMA di definire l'handler
    sia_data = SIAAlarmData(None)
    
    # Definisce l'handler per eventi SIA PRIMA del try
    async def async_event_handler(event: SIAEvent):
        """Handler asincrono per eventi SIA."""
        _LOGGER.info("🔥 EVENTO SIA RICEVUTO: %s", event)
        # Forza il processing anche con timestamp vecchi
        _LOGGER.info("📅 Timestamp evento: %s (ignorando validità)", getattr(event, 'timestamp', 'N/A'))
        sia_data._on_sia_event(event)
    
    # Verifica che la funzione sia effettivamente una coroutine
    import asyncio
    _LOGGER.info("🔍 Verifica handler: asyncio.iscoroutinefunction() = %s", 
                asyncio.iscoroutinefunction(async_event_handler))

    # Crea client SIA
    try:
        _LOGGER.info("Creazione client SIA su %s:%s per account %s", host, port, account_id)
        
        # Crea il client con impostazioni più permissive
        client = SIAClient(
            host=host,
            port=port,
            accounts=[account],
            function=async_event_handler
        )
        
        # Modifica il client per accettare timestamp vecchi
        # Patchamo il metodo di validazione timestamp se esiste
        if hasattr(client, '_server') and hasattr(client._server, 'allowed_timeframe'):
            client._server.allowed_timeframe = 86400  # 24 ore invece del default
            _LOGGER.info("⏰ Timeframe esteso a 24 ore per accettare eventi vecchi")
        
        sia_data.client = client
        
        # Avvia il client asincrono in background
        _LOGGER.info("🔄 Avvio client SIA in background...")
        hass.async_create_task(client.start())
        _LOGGER.info("✅ Task client SIA creato su %s:%s per account %s", host, port, account_id)
        
        # Test che il client sia effettivamente avviato
        import asyncio
        await asyncio.sleep(1)  # Breve pausa per permettere l'avvio
        
        # Prova a modificare il timeframe dopo l'avvio
        try:
            if hasattr(client, '_server'):
                if hasattr(client._server, 'allowed_timeframe'):
                    client._server.allowed_timeframe = 86400  # 24 ore
                    _LOGGER.info("⏰ Timeframe server esteso a 24 ore")
                else:
                    _LOGGER.info("⚠️ Attributo allowed_timeframe non trovato")
            else:
                _LOGGER.info("⚠️ Attributo _server non trovato")
        except Exception as e:
            _LOGGER.info("⚠️ Non è stato possibile modificare il timeframe: %s", e)
        
        _LOGGER.info("🎯 Client SIA dovrebbe essere in ascolto su %s:%s", host, port)
        
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
