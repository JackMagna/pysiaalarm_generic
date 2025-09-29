"""Sensori per pySIAAlarm integration - Solo monitoraggio eventi."""
from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sia import SIAEvent

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup sensori da config entry - Solo monitoraggio per mappatura futura."""
    sia_data = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = [
        SIAEventMonitorSensor(sia_data, config_entry),
        SIAEventLogSensor(sia_data, config_entry),
    ]
    async_add_entities(entities)

    # Create dynamic sensors for known codes (persisted)
    dynamic_entities = []
    created_codes = set()
    try:
        for code, info in sia_data.codes.items():
            dynamic_entities.append(SIAEventCodeSensor(sia_data, config_entry, code))
            created_codes.add(code)
        # Sensor that lists all known codes
        dynamic_entities.append(SIAKnownCodesSensor(sia_data, config_entry))
    except Exception:
        dynamic_entities = []

    if dynamic_entities:
        async_add_entities(dynamic_entities)

    # Provide a callback so sia_data can request creation of a sensor when a new code is added
    def _entity_adder(code: str) -> None:
        # run in the event loop
        if code in created_codes:
            return
        created_codes.add(code)
        try:
            hass.async_create_task(_async_add_code_entity(code))
        except Exception:
            pass

    async def _async_add_code_entity(code: str) -> None:
        try:
            ent = SIAEventCodeSensor(sia_data, config_entry, code)
            async_add_entities([ent])
            _LOGGER.info("Creato sensore dinamico per codice SIA: %s", code)
        except Exception as e:
            _LOGGER.error("Errore creazione sensore dinamico per %s: %s", code, e)

    sia_data.entity_adder = _entity_adder


class SIAEventMonitorSensor(SensorEntity):
    """Sensore che monitora eventi SIA per identificazione sensori casa."""

    def __init__(self, sia_data, config_entry):
        """Inizializza il sensore monitor eventi."""
        self._sia_data = sia_data
        self._config_entry = config_entry
        self._total_events = 0
        self._unique_codes = set()
        self._unique_zones = set()
        
        # Registra listener per eventi SIA
        self._sia_data.add_listener(self._handle_sia_event)

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore."""
        return f"SIA Events Monitor {self._config_entry.data['account_id']}"

    @property
    def unique_id(self) -> str:
        """Restituisce un ID unico per il sensore."""
        return f"sia_monitor_{self._config_entry.data['account_id']}"

    @property
    def state(self) -> int:
        """Restituisce il numero totale di eventi ricevuti."""
        return self._total_events

    @property
    def icon(self) -> str:
        """Restituisce l'icona del sensore."""
        return "mdi:home-search"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Restituisce attributi per mappatura sensori."""
        return {
            "account_id": self._config_entry.data["account_id"],
            "total_events": self._total_events,
            "unique_codes": list(self._unique_codes),
            "unique_zones": list(self._unique_zones),
            "total_unique_codes": len(self._unique_codes),
            "total_unique_zones": len(self._unique_zones),
            "purpose": "Monitoraggio per mappatura sensori casa"
        }

    def _handle_sia_event(self, event: SIAEvent) -> None:
        """Raccoglie dati per identificazione sensori."""
        _LOGGER.info("📊 Sensore monitor ricevuto evento: %s", event)
        
        self._total_events += 1
        if hasattr(event, 'code') and event.code:
            self._unique_codes.add(event.code)
        if hasattr(event, 'zone') and event.zone:
            self._unique_zones.add(str(event.zone))
        
        _LOGGER.info("Evento SIA ricevuto - Codice: %s, Zona: %s (Totale: %d)", 
                    getattr(event, 'code', 'N/A'), 
                    getattr(event, 'zone', 'N/A'),
                    self._total_events)
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup quando il sensore viene rimosso."""
        self._sia_data.remove_listener(self._handle_sia_event)


class SIAEventLogSensor(SensorEntity):
    """Sensore che mostra dettagli ultimo evento per debug mappatura."""

    def __init__(self, sia_data, config_entry):
        """Inizializza il sensore log eventi."""
        self._sia_data = sia_data
        self._config_entry = config_entry
        self._last_event = None
        
        # Registra listener per eventi SIA
        self._sia_data.add_listener(self._handle_sia_event)

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore."""
        return f"SIA Last Event Details {self._config_entry.data['account_id']}"

    @property
    def unique_id(self) -> str:
        """Restituisce un ID unico per il sensore."""
        return f"sia_last_details_{self._config_entry.data['account_id']}"

    @property
    def state(self) -> str:
        """Restituisce il codice dell'ultimo evento."""
        return self._last_event.code if self._last_event else "waiting"

    @property
    def icon(self) -> str:
        """Restituisce l'icona del sensore."""
        return "mdi:message-alert"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Restituisce tutti i dettagli per debug mappatura."""
        if not self._last_event:
            return {
                "account_id": self._config_entry.data["account_id"],
                "status": "In attesa primo evento"
            }
        # Raccoglie solo campi semplici e serializzabili dell'evento per evitare
        # problemi con JSON serialization (es. SIAAccount, tzinfo non serializzabili)
        attrs: dict[str, Any] = {
            "account_id": self._config_entry.data["account_id"],
            "raw_event": str(self._last_event),
        }

        # Lista di campi dell'evento che vogliamo esportare nello stato (se presenti)
        keys = [
            "account",
            "code",
            "ri",
            "zone",
            "message",
            "ti",
            "id",
            "x_data",
            "timestamp",
            "line",
            "receiver",
            "sequence",
            "calc_crc",
            "message_type",
        ]

        for key in keys:
            if hasattr(self._last_event, key):
                try:
                    val = getattr(self._last_event, key)
                    # Converti datetime in string ISO
                    if isinstance(val, datetime):
                        attrs[f"event_{key}"] = val.isoformat()
                        continue
                    # Se è un oggetto account o ha account_id, serializziamo solo l'id
                    if hasattr(val, "account_id"):
                        try:
                            attrs[f"event_{key}"] = getattr(val, "account_id")
                            continue
                        except Exception:
                            pass
                    # Se è un tipo semplice lo aggiungiamo direttamente
                    if isinstance(val, (str, int, float, bool, list, dict)) or val is None:
                        attrs[f"event_{key}"] = val
                    else:
                        # Fallback: rappresentazione testuale
                        attrs[f"event_{key}"] = str(val)
                except Exception:
                    # Non blocchiamo l'aggiornamento dello stato per un attributo non serializzabile
                    attrs[f"event_{key}"] = "<unserializable>"

        return attrs

    def _handle_sia_event(self, event: SIAEvent) -> None:
        """Salva ultimo evento per debug dettagliato."""
        self._last_event = event
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup quando il sensore viene rimosso."""
        self._sia_data.remove_listener(self._handle_sia_event)



class SIAKnownCodesSensor(SensorEntity):
    """Sensor that lists all known codes persisted."""

    def __init__(self, sia_data, config_entry):
        self._sia_data = sia_data
        self._config_entry = config_entry

    @property
    def name(self) -> str:
        return f"SIA Known Codes {self._config_entry.data['account_id']}"

    @property
    def unique_id(self) -> str:
        return f"sia_known_codes_{self._config_entry.data['account_id']}"

    @property
    def state(self) -> int:
        return len(self._sia_data.codes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"codes": list(self._sia_data.codes.keys())}


class SIAEventCodeSensor(SensorEntity):
    """Sensor per un singolo codice SIA rilevato durante learning."""

    def __init__(self, sia_data, config_entry, code: str):
        self._sia_data = sia_data
        self._config_entry = config_entry
        self._code = str(code)

    @property
    def name(self) -> str:
        return f"SIA Code {self._code} {self._config_entry.data['account_id']}"

    @property
    def unique_id(self) -> str:
        return f"sia_code_{self._config_entry.data['account_id']}_{self._code}"

    @property
    def state(self) -> int:
        entry = self._sia_data.codes.get(self._code)
        return entry.get("count", 0) if entry else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self._sia_data.codes.get(self._code, {})
        return {
            "zones": list(entry.get("zones", [])),
            "last_seen": entry.get("last_seen"),
            "samples": entry.get("samples", []),
        }
