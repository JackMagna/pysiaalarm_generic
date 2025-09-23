"""Sensori per pySIAAlarm integration - Solo monitoraggio eventi."""
from __future__ import annotations

import logging
from typing import Any

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
        
        # Raccoglie tutti gli attributi disponibili dell'evento
        attrs = {
            "account_id": self._config_entry.data["account_id"],
            "raw_event": str(self._last_event),
        }
        
        # Aggiunge tutti gli attributi dell'evento SIA
        for attr in dir(self._last_event):
            if not attr.startswith('_') and hasattr(self._last_event, attr):
                try:
                    value = getattr(self._last_event, attr)
                    if not callable(value):
                        attrs[f"event_{attr}"] = value
                except:
                    pass
        
        return attrs

    def _handle_sia_event(self, event: SIAEvent) -> None:
        """Salva ultimo evento per debug dettagliato."""
        self._last_event = event
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup quando il sensore viene rimosso."""
        self._sia_data.remove_listener(self._handle_sia_event)
