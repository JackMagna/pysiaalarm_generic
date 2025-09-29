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
from typing import Coroutine
from homeassistant.helpers import storage

from .const import DOMAIN, CONF_ACCOUNT_ID, CONF_ENCRYPTION_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
STORE_VERSION = 1
STORAGE_KEY = DOMAIN + ".codes"


class SIAAlarmData:
    """Classe per gestire dati condivisi dell'integrazione."""
    
    def __init__(self, client: SIAClient):
        self.client = client
        self.events: list[SIAEvent] = []
        self.listeners: list[callable] = []
        self.codes: dict[str, dict] = {}
        self.learning: bool = False
        self._hass = None
        self.entity_adder = None
    
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
        # Se siamo in learning mode, registra il codice per persistenza
        if self.learning and hasattr(event, 'code') and event.code:
            try:
                self.add_code(event.code, getattr(event, 'zone', None), event.full_message)
            except Exception as err:
                _LOGGER.error("Errore registrazione codice in learning mode: %s", err)

        # Notifica tutti i listeners
        for listener in self.listeners:
            try:
                listener(event)
            except Exception as err:
                _LOGGER.error("Errore nel listener SIA: %s", err)

    def add_code(self, code: str, zone: str | None = None, sample: str | None = None) -> None:
        """Aggiunge o aggiorna un codice rilevato e programma il salvataggio asincrono."""
        now = None
        try:
            from datetime import datetime
            now = datetime.now().isoformat()
        except Exception:
            now = None

        entry = self.codes.get(code, {"count": 0, "zones": set(), "last_seen": None, "samples": []})
        entry["count"] += 1
        if zone is not None:
            try:
                entry["zones"].add(str(zone))
            except Exception:
                entry["zones"] = set(list(entry.get("zones", [])) + [str(zone)])
        entry["last_seen"] = now
        if sample:
            samples = entry.get("samples", [])
            samples.insert(0, sample)
            entry["samples"] = samples[:10]
        self.codes[code] = entry

        # schedule async save
        if self._hass:
            try:
                self._hass.async_create_task(self.async_save_codes())
            except Exception as e:
                _LOGGER.debug("Impossibile schedulare salvataggio codici: %s", e)
        # If we have an entity adder callback, request creation of a new sensor for this code
        try:
            if self.entity_adder and callable(self.entity_adder):
                # pass code only; entity_adder should handle dedup
                self.entity_adder(code)
        except Exception as e:
            _LOGGER.debug("Errore chiamata entity_adder: %s", e)

    async def async_save_codes(self) -> None:
        """Salva i codici nel storage di Home Assistant."""
        if not self._hass:
            return
        try:
            store = storage.Store(self._hass, STORE_VERSION, STORAGE_KEY)
            # convert set to list for JSON
            serializable = {
                k: {**v, "zones": list(v.get("zones", []))} for k, v in self.codes.items()
            }
            await store.async_save(serializable)
            _LOGGER.debug("Codici SIA salvati: %s", list(serializable.keys()))
        except Exception as e:
            _LOGGER.error("Errore salvataggio codici: %s", e)

    async def async_load_codes(self, hass) -> None:
        """Carica i codici dal storage di Home Assistant."""
        self._hass = hass
        try:
            store = storage.Store(hass, STORE_VERSION, STORAGE_KEY)
            data = await store.async_load()
            if data:
                # convert zones back to set
                for k, v in data.items():
                    v["zones"] = set(v.get("zones", []))
                self.codes = data
                _LOGGER.info("Caricati %d codici SIA dallo storage", len(self.codes))
            else:
                self.codes = {}
        except Exception as e:
            _LOGGER.error("Errore caricamento codici: %s", e)

    def start_learning(self) -> None:
        self.learning = True

    def stop_learning(self) -> None:
        self.learning = False

    def clear_codes(self) -> None:
        self.codes = {}
        if self._hass:
            self._hass.async_create_task(self.async_save_codes())


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
    
    # Carica codici persi dallo storage
    await sia_data.async_load_codes(hass)

    # Registra servizi per learning mode e gestione codici
    async def _start_learning(call):
        sia_data.start_learning()
        _LOGGER.info("SIA learning mode avviato")

    async def _stop_learning(call):
        sia_data.stop_learning()
        _LOGGER.info("SIA learning mode fermato")

    async def _clear_codes(call):
        sia_data.clear_codes()
        _LOGGER.info("SIA codice list pulita")

    hass.services.async_register(DOMAIN, "start_learning", _start_learning)
    hass.services.async_register(DOMAIN, "stop_learning", _stop_learning)
    hass.services.async_register(DOMAIN, "clear_codes", _clear_codes)

    async def _export_codes(call):
        """Export codes to CSV file.

        Service data:
        - filename (optional): path relative to HA config directory or absolute path
        """
        filename = call.data.get("filename") if call and call.data else None

        # default filename in HA config dir
        account = entry.data.get(CONF_ACCOUNT_ID)
        default_name = f"pysiaalarm_codes_{account}.csv" if account else "pysiaalarm_codes.csv"
        if filename:
            # if relative path, write under config dir
            import os
            if not os.path.isabs(filename):
                filepath = hass.config.path(filename)
            else:
                filepath = filename
        else:
            filepath = hass.config.path(default_name)

        codes = sia_data.codes or {}

        def _write_csv(path, codes_dict):
            import csv
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["code", "count", "zones", "last_seen", "samples"])
                    for code, info in sorted(codes_dict.items()):
                        zones = ";".join(sorted(list(info.get("zones", []))))
                        samples = "|".join(info.get("samples", [])) if info.get("samples") else ""
                        writer.writerow([code, info.get("count", 0), zones, info.get("last_seen", ""), samples])
                return True
            except Exception as e:
                _LOGGER.error("Errore scrittura CSV %s: %s", path, e)
                return False

        ok = await hass.async_add_executor_job(_write_csv, filepath, codes)
        if ok:
            _LOGGER.info("Codici SIA esportati in %s", filepath)
        else:
            _LOGGER.error("Esportazione codici SIA fallita per %s", filepath)

    hass.services.async_register(DOMAIN, "export_codes", _export_codes)

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
