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
import re
# entity id generation: we'll sanitize labels ourselves

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
        # Create dynamic sensors based on mapping if available, else fallback to codes
        try:
            if getattr(sia_data, 'mapping', None):
                for label, meta in sia_data.mapping.items():
                    dynamic_entities.append(SIAEventCodeSensor(sia_data, config_entry, code=None, label=label))
            else:
                for code, info in sia_data.codes.items():
                    dynamic_entities.append(SIAEventCodeSensor(sia_data, config_entry, code=code))
        except Exception:
            dynamic_entities = []
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
            # If mapping exists, try to find label for this code (best-effort)
            label = None
            if getattr(sia_data, 'mapping', None):
                # mapping keys are labels; we do not have a reverse map here, so just create code-based sensor
                label = None
            ent = SIAEventCodeSensor(sia_data, config_entry, code=code, label=label)
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
    """Sensor per codice o label SIA con debounce e diagnostica.

    Costruttore accetta `code` (string) o `label` (friendly label estratto dal bracket).
    Se `label` è fornito, il sensore userà il nome leggibile come friendly name e entity_id.
    """

    def __init__(self, sia_data, config_entry, code: str | None = None, label: str | None = None):
        self._sia_data = sia_data
        self._config_entry = config_entry
        self._code = str(code) if code is not None else None
        self._label = label if label else None

        # diagnostic counts
        self._raw_count = 0
        self._accepted_count = 0
        self._last_raw_ts = None
        self._last_accepted_ts = None

        # determine debounce seconds from mapping or default
        self._debounce = None
        if self._label and getattr(sia_data, 'mapping', None):
            meta = sia_data.mapping.get(self._label) or {}
            try:
                self._debounce = float(meta.get('debounce_seconds', sia_data.default_debounce_seconds))
            except Exception:
                self._debounce = float(sia_data.default_debounce_seconds)
        else:
            self._debounce = float(getattr(sia_data, 'default_debounce_seconds', 1.44))

        # entity_id generation if label provided
        self._entity_id = None
        if self._label:
            # sanitize label to entity id format: lowercase, replace non-alnum with _
            ent = re.sub(r"[^0-9a-zA-Z]+", '_', self._label).strip('_').lower()
            base = f"sensor.pysiaalarm_{ent}"
            # We don't have access to hass.generate_entity_id here; use sanitized base
            self._entity_id = base

        # register listener so sensor receives events
        try:
            self._sia_data.add_listener(self._handle_event)
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        if self._label:
            return f"{self._label}"
        if self._code:
            return f"SIA Code {self._code} {self._config_entry.data['account_id']}"
        return f"SIA Sensor {self._config_entry.data['account_id']}"

    @property
    def unique_id(self) -> str:
        if self._label:
            safe = re.sub(r"[^0-9a-zA-Z]+", '_', self._label).strip('_').lower()
            return f"sia_sensor_{self._config_entry.data['account_id']}_{safe}"
        if self._code:
            return f"sia_code_{self._config_entry.data['account_id']}_{self._code}"
        return f"sia_sensor_{self._config_entry.data['account_id']}_unknown"

    @property
    def state(self) -> int:
        # accepted count is the usable state
        return self._accepted_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {
            'raw_count': self._raw_count,
            'accepted_count': self._accepted_count,
            'debounce_seconds': self._debounce,
            'last_raw_ts': self._last_raw_ts.isoformat() if self._last_raw_ts else None,
            'last_accepted_ts': self._last_accepted_ts.isoformat() if self._last_accepted_ts else None,
        }
        if self._code:
            entry = self._sia_data.codes.get(self._code, {})
            attrs.update({
                'zones': list(entry.get('zones', [])),
                'last_seen': entry.get('last_seen'),
                'samples': entry.get('samples', []),
            })
        return attrs

    def _update_on_event(self, ev: SIAEvent, label: str | None = None) -> None:
        """Called by SIAEvent listeners: update counts and apply debounce."""
        from datetime import datetime
        now = getattr(ev, 'timestamp', datetime.now())
        self._raw_count += 1
        self._last_raw_ts = now

        last_acc = self._last_accepted_ts
        allow = False
        if last_acc is None:
            allow = True
        else:
            diff = (now - last_acc).total_seconds()
            if diff >= self._debounce:
                allow = True

        if allow:
            self._accepted_count += 1
            self._last_accepted_ts = now
            # schedule HA update
            self.schedule_update_ha_state()

    def _extract_label_from_event(self, ev: SIAEvent) -> str | None:
        """Try to extract bracket label or similar from event raw message."""
        raw = getattr(ev, 'full_message', None) or getattr(ev, 'message', None) or getattr(ev, 'line', None)
        if not raw:
            return None
        try:
            m = re.search(r"\[(.*?)\]", raw)
            if m:
                lbl = m.group(1).strip()
                return lbl
        except Exception:
            pass
        return None

    def _handle_event(self, ev: SIAEvent) -> None:
        """Listener called by SIAAlarmData for every event; filter and update counts."""
        try:
            # if sensor is code-based, match code
            if self._code:
                if hasattr(ev, 'code') and ev.code == self._code:
                    self._update_on_event(ev)
                return

            # if sensor is label-based, try to extract label from event and compare
            if self._label:
                lbl = self._extract_label_from_event(ev)
                if not lbl:
                    return
                # compare normalized labels
                def norm(s: str) -> str:
                    return re.sub(r"\s+", ' ', s.strip()).lower()

                if norm(lbl) == norm(self._label):
                    self._update_on_event(ev, label=lbl)
        except Exception:
            _LOGGER.debug("Errore matching evento per sensore SIA %s", self._label or self._code)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup quando il sensore viene rimosso: deregistra listener."""
        try:
            self._sia_data.remove_listener(self._handle_event)
        except Exception:
            pass

