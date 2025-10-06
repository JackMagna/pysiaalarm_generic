"""Sensori per pySIAAlarm integration - Solo monitoraggio eventi."""
from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
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
        if getattr(sia_data, 'mapping', None):
            for label, meta in sia_data.mapping.items():
                try:
                    if isinstance(meta, dict) and meta.get('type') == 'contact':
                        dynamic_entities.append(SIAEventBinarySensor(sia_data, config_entry, code=None, label=label, meta=meta))
                    else:
                        dynamic_entities.append(SIAEventCodeSensor(sia_data, config_entry, code=None, label=label))
                except Exception:
                    dynamic_entities.append(SIAEventCodeSensor(sia_data, config_entry, code=None, label=label))
        else:
            for code, info in sia_data.codes.items():
                dynamic_entities.append(SIAEventCodeSensor(sia_data, config_entry, code=code))

        # Sensor that lists all known codes
        dynamic_entities.append(SIAKnownCodesSensor(sia_data, config_entry))
    except Exception:
        dynamic_entities = []

    if dynamic_entities:
        # Log which dynamic sensors we're about to add (helps debugging mapping/labels)
        try:
            _LOGGER.info("Preparazione sensori dinamici: totale=%d", len(dynamic_entities))
            for ent in dynamic_entities:
                try:
                    _LOGGER.info(
                        "Sensore dinamico pronto: name=%s unique_id=%s label=%s code=%s debounce=%s",
                        getattr(ent, 'name', None),
                        getattr(ent, 'unique_id', None),
                        getattr(ent, '_label', None),
                        getattr(ent, '_code', None),
                        getattr(ent, '_debounce', None),
                    )
                except Exception:
                    _LOGGER.debug("Errore log sensore dinamico pre-creazione", exc_info=True)
        except Exception:
            _LOGGER.debug("Errore durante il logging dei sensori dinamici", exc_info=True)
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
            # Log detailed info about created dynamic sensor
            try:
                _LOGGER.info(
                    "Creato sensore dinamico: name=%s unique_id=%s label=%s code=%s debounce=%s",
                    getattr(ent, 'name', None),
                    getattr(ent, 'unique_id', None),
                    getattr(ent, '_label', None),
                    getattr(ent, '_code', None),
                    getattr(ent, '_debounce', None),
                )
            except Exception:
                _LOGGER.info("Creato sensore dinamico per codice SIA: %s", code)
        except Exception as e:
            _LOGGER.error("Errore creazione sensore dinamico per %s: %s", code, e)

    sia_data.entity_adder = _entity_adder

    # register services to set/reset manual state per sensor (by label or code)
    async def _set_sensor_state(call):
        """Service to set manual state for a sensor.

        Service data:
        - target: { 'label': '<label>' } or { 'code': '<code>' }
        - state: 'open'|'closed'|'on'|'off' or numeric
        """
        data = call.data or {}
        state = data.get('state')
        label = data.get('label')
        code = data.get('code')
        if not state or (not label and not code):
            _LOGGER.error("set_sensor_state missing state or target")
            return
        # normalize key
        key = None
        if label:
            key = str(label)
            sia_data.initial_states[key] = str(state)
            # notify entity if present
            ent = sia_data.entities_by_label.get(key)
            if ent:
                ent._apply_manual_state(str(state))
        elif code:
            key = str(code)
            sia_data.initial_states[key] = str(state)
            ent = sia_data.entities_by_code.get(key)
            if ent:
                ent._apply_manual_state(str(state))
        try:
            # schedule save
            if hasattr(sia_data, '_hass') and sia_data._hass:
                sia_data._hass.async_create_task(sia_data.async_save_initial_states())
        except Exception:
            pass

    async def _reset_sensor_state(call):
        """Service to reset manual state for a sensor (remove override)."""
        data = call.data or {}
        label = data.get('label')
        code = data.get('code')
        key = None
        if label:
            key = str(label)
            if key in sia_data.initial_states:
                sia_data.initial_states.pop(key, None)
            ent = sia_data.entities_by_label.get(key)
            if ent:
                ent._clear_manual_state()
        elif code:
            key = str(code)
            if key in sia_data.initial_states:
                sia_data.initial_states.pop(key, None)
            ent = sia_data.entities_by_code.get(key)
            if ent:
                ent._clear_manual_state()
        try:
            if hasattr(sia_data, '_hass') and sia_data._hass:
                sia_data._hass.async_create_task(sia_data.async_save_initial_states())
        except Exception:
            pass

    try:
        hass.services.async_register(DOMAIN, 'set_sensor_state', _set_sensor_state)
        hass.services.async_register(DOMAIN, 'reset_sensor_state', _reset_sensor_state)
    except Exception:
        _LOGGER.debug('Impossibile registrare servizi set/reset sensor state', exc_info=True)


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
            # detect device type (e.g., contact) from mapping metadata
            self._device_type = meta.get('type') if isinstance(meta, dict) else None
        else:
            self._debounce = float(getattr(sia_data, 'default_debounce_seconds', 1.44))
            self._device_type = None

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

        # Register entity in sia_data for manual state overrides
        try:
            if self._label:
                try:
                    sia_data.entities_by_label[self._label] = self
                except Exception:
                    pass
            if self._code:
                try:
                    sia_data.entities_by_code[self._code] = self
                except Exception:
                    pass
        except Exception:
            pass

        # Initialize manual override state from persisted states if present
        try:
            self._manual_state = None
            if self._label and getattr(sia_data, 'initial_states', None):
                self._manual_state = sia_data.initial_states.get(self._label)
            if self._manual_state is None and self._code and getattr(sia_data, 'initial_states', None):
                self._manual_state = sia_data.initial_states.get(self._code)
        except Exception:
            self._manual_state = None

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
        # If manual override exists, return it (string). For contact devices, return 'open'/'closed'.
        try:
            # check initial user-provided baseline by code or label
            if self._label and getattr(self._sia_data, 'initial_states', None):
                st = self._sia_data.initial_states.get(self._label)
                if st is not None:
                    return st
            if self._code and getattr(self._sia_data, 'initial_states', None):
                st = self._sia_data.initial_states.get(self._code)
                if st is not None:
                    return st
        except Exception:
            pass
        # otherwise return accepted_count for numeric sensors
        if self._device_type == 'contact':
            # convert accepted_count (int) to human state 'closed' if 0 else 'open'
            try:
                return 'open' if self._accepted_count > 0 else 'closed'
            except Exception:
                return 'closed'
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
        # expose manual override if present
        try:
            if hasattr(self, '_manual_state') and self._manual_state is not None:
                attrs['manual_state'] = self._manual_state
        except Exception:
            pass
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
        # normalize timestamp: accept datetime or ISO string, fallback to now
        ts = getattr(ev, 'timestamp', None)
        if isinstance(ts, datetime):
            now = ts
        else:
            # try parse ISO string
            now = None
            try:
                if isinstance(ts, str) and ts:
                    now = datetime.fromisoformat(ts)
            except Exception:
                now = None
            if now is None:
                now = datetime.now()
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
            try:
                now_iso = now.isoformat()
            except Exception:
                now_iso = str(now)
            _LOGGER.info(
                "SIA sensor match accepted: sensor=%s code=%s label=%s now=%s raw_count=%d accepted_count=%d",
                (self._label or self._code), getattr(ev, 'code', None), label, now_iso, self._raw_count, self._accepted_count,
            )
            # schedule HA update
            try:
                # if device is contact, clear any automatic manual state? No: keep manual overrides
                self.schedule_update_ha_state()
            except Exception:
                _LOGGER.debug("schedule_update_ha_state failed for %s", self._label or self._code)
        else:
            try:
                now_iso = now.isoformat()
            except Exception:
                now_iso = str(now)
            last_acc_iso = None
            try:
                last_acc_iso = self._last_accepted_ts.isoformat() if self._last_accepted_ts else None
            except Exception:
                last_acc_iso = str(self._last_accepted_ts)
            _LOGGER.debug(
                "SIA sensor match suppressed by debounce: sensor=%s code=%s label=%s now=%s last_accepted=%s debounce=%.2f",
                (self._label or self._code), getattr(ev, 'code', None), label, now_iso, last_acc_iso, self._debounce,
            )

    def _extract_label_from_event(self, ev: SIAEvent) -> str | None:
        """Try to extract bracket label or similar from event raw message."""
        raw = getattr(ev, 'full_message', None) or getattr(ev, 'message', None) or getattr(ev, 'line', None)
        if not raw:
            return None
        try:
            m = re.search(r"\[(.*?)\]", raw)
            if not m:
                return None
            bracket = m.group(1).strip()

            # Often bracket content is like: "#005544|Nri1UX17^C. P.CUCINA     CASA            ^"
            # We want the human label portion, typically between '^' separators
            if '^' in bracket:
                parts = bracket.split('^')
                # prefer the middle part if present
                if len(parts) >= 2 and parts[1].strip():
                    candidate = parts[1].strip()
                else:
                    # fallback: try last non-empty
                    cand = [p for p in parts if p.strip()]
                    candidate = cand[-1].strip() if cand else bracket
            else:
                # if there's a pipe '|' remove prefix like '#005544|...'
                if '|' in bracket:
                    candidate = bracket.split('|', 1)[-1].strip()
                else:
                    candidate = bracket

            # Sometimes candidate includes receiver/status prefixes like 'C. ' or 'U. '
            # If there's a 'P.' marker inside (e.g. 'C. P.CUCINA'), prefer substring from 'P.'
            pidx = candidate.find('P.')
            if pidx != -1:
                candidate = candidate[pidx:]
            else:
                # remove leading single-letter markers like 'C. ' or 'U. '
                candidate = re.sub(r'^[A-Z]\.\s*', '', candidate)

            # Normalize whitespace
            candidate = re.sub(r"\s+", ' ', candidate).strip()
            return candidate
        except Exception:
            return None

    def _handle_event(self, ev: SIAEvent) -> None:
        """Listener called by SIAAlarmData for every event; filter and update counts."""
        try:
            # if sensor is code-based, match code
            if self._code:
                if hasattr(ev, 'code') and ev.code == self._code:
                    _LOGGER.debug("SIA code sensor matched: sensor=%s code=%s", self._code, ev.code)
                    self._update_on_event(ev)
                return

            # if sensor is label-based, try to extract label from event and compare
            if self._label:
                lbl = self._extract_label_from_event(ev)
                if not lbl:
                    _LOGGER.debug("SIA label sensor: no label extracted from event for sensor=%s", self._label)
                    return
                # Log the extracted label explicitly to help debugging mapping mismatches
                try:
                    _LOGGER.info("SIA extracted label for sensor=%s event_label=%s", self._label, lbl)
                except Exception:
                    _LOGGER.debug("SIA extracted label (logging failed) for sensor=%s", self._label, exc_info=True)
                # compare normalized labels
                def norm(s: str) -> str:
                    return re.sub(r"\s+", ' ', s.strip()).lower()

                if norm(lbl) == norm(self._label):
                    _LOGGER.debug("SIA label sensor matched: sensor_label=%s event_label=%s", self._label, lbl)
                    self._update_on_event(ev, label=lbl)
                else:
                    _LOGGER.debug("SIA label mismatch: sensor_label=%s event_label=%s", self._label, lbl)
        except Exception:
            _LOGGER.debug("Errore matching evento per sensore SIA %s", self._label or self._code)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup quando il sensore viene rimosso: deregistra listener."""
        try:
            self._sia_data.remove_listener(self._handle_event)
        except Exception:
            pass

    # Methods for manual state override via services
    def _apply_manual_state(self, state: str) -> None:
        """Apply manual state override; state is stored as string."""
        try:
            s = str(state)
            self._manual_state = s
        except Exception:
            self._manual_state = str(state)
        try:
            self.schedule_update_ha_state()
        except Exception:
            pass

    def _clear_manual_state(self) -> None:
        try:
            if hasattr(self, '_manual_state'):
                delattr(self, '_manual_state')
            self._manual_state = None
        except Exception:
            pass
        try:
            self.schedule_update_ha_state()
        except Exception:
            pass


class SIAEventBinarySensor(BinarySensorEntity):
    """Binary sensor for SIA contact-type events."""

    def __init__(self, sia_data, config_entry, code: str | None = None, label: str | None = None, meta: dict | None = None):
        self._sia_data = sia_data
        self._config_entry = config_entry
        self._code = str(code) if code is not None else None
        self._label = label if label else None

        # diagnostic counts
        self._raw_count = 0
        self._accepted_count = 0
        self._last_raw_ts = None
        self._last_accepted_ts = None

        # debounce
        self._debounce = float(getattr(sia_data, 'default_debounce_seconds', 1.44))
        if meta and isinstance(meta, dict):
            try:
                self._debounce = float(meta.get('debounce_seconds', self._debounce))
            except Exception:
                pass

        # register listener
        try:
            self._sia_data.add_listener(self._handle_event)
        except Exception:
            pass

        # register in registry
        try:
            if self._label:
                sia_data.entities_by_label[self._label] = self
            if self._code:
                sia_data.entities_by_code[self._code] = self
        except Exception:
            pass

        # initial state baseline
        try:
            self._initial_state = None
            if self._label and getattr(sia_data, 'initial_states', None):
                self._initial_state = sia_data.initial_states.get(self._label)
            if self._initial_state is None and self._code and getattr(sia_data, 'initial_states', None):
                self._initial_state = sia_data.initial_states.get(self._code)
        except Exception:
            self._initial_state = None

    @property
    def name(self) -> str:
        if self._label:
            return f"{self._label}"
        if self._code:
            return f"SIA Contact {self._code} {self._config_entry.data['account_id']}"
        return f"SIA Contact {self._config_entry.data['account_id']}"

    @property
    def unique_id(self) -> str:
        if self._label:
            safe = re.sub(r"[^0-9a-zA-Z]+", '_', self._label).strip('_').lower()
            return f"sia_contact_{self._config_entry.data['account_id']}_{safe}"
        if self._code:
            return f"sia_contact_{self._config_entry.data['account_id']}_{self._code}"
        return f"sia_contact_{self._config_entry.data['account_id']}_unknown"

    @property
    def is_on(self) -> bool:
        # Contact: True = open, False = closed
        try:
            # Determine baseline: if user provided initial_state, use it; otherwise default to CLOSED
            baseline_open = None
            if self._initial_state is not None:
                s = str(self._initial_state).lower()
                if s in ('open', 'on', '1', 'true', 'yes'):
                    baseline_open = True
                if s in ('closed', 'off', '0', 'false', 'no'):
                    baseline_open = False
            # default baseline when missing: closed (False) so parity toggling works
            if baseline_open is None:
                baseline_open = False

            # compute parity of accepted_count: each accepted event toggles
            parity = self._accepted_count % 2
            # parity 0 => baseline, parity 1 => inverted
            return baseline_open if parity == 0 else (not baseline_open)
        except Exception:
            return self._accepted_count > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # compute current derived state for clarity
        try:
            computed = None
            try:
                computed = 'open' if self.is_on() else 'closed'
            except Exception:
                computed = None
        except Exception:
            computed = None
        return {
            'raw_count': self._raw_count,
            'accepted_count': self._accepted_count,
            'debounce_seconds': self._debounce,
            'initial_state': self._initial_state,
            'computed_state': computed,
            'last_raw_ts': self._last_raw_ts.isoformat() if self._last_raw_ts else None,
            'last_accepted_ts': self._last_accepted_ts.isoformat() if self._last_accepted_ts else None,
        }

    def _update_on_event(self, ev: SIAEvent) -> None:
        from datetime import datetime
        ts = getattr(ev, 'timestamp', None)
        if isinstance(ts, datetime):
            now = ts
        else:
            now = None
            try:
                if isinstance(ts, str) and ts:
                    now = datetime.fromisoformat(ts)
            except Exception:
                now = None
            if now is None:
                now = datetime.now()
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
            try:
                self.schedule_update_ha_state()
            except Exception:
                pass

    def _extract_label_from_event(self, ev: SIAEvent) -> str | None:
        # reuse parent extraction logic
        raw = getattr(ev, 'full_message', None) or getattr(ev, 'message', None) or getattr(ev, 'line', None)
        if not raw:
            return None
        try:
            m = re.search(r"\[(.*?)\]", raw)
            if not m:
                return None
            bracket = m.group(1).strip()
            if '^' in bracket:
                parts = bracket.split('^')
                if len(parts) >= 2 and parts[1].strip():
                    candidate = parts[1].strip()
                else:
                    cand = [p for p in parts if p.strip()]
                    candidate = cand[-1].strip() if cand else bracket
            else:
                if '|' in bracket:
                    candidate = bracket.split('|', 1)[-1].strip()
                else:
                    candidate = bracket
            pidx = candidate.find('P.')
            if pidx != -1:
                candidate = candidate[pidx:]
            else:
                candidate = re.sub(r'^[A-Z]\.]\s*', '', candidate)
            candidate = re.sub(r"\s+", ' ', candidate).strip()
            return candidate
        except Exception:
            return None

    def _handle_event(self, ev: SIAEvent) -> None:
        try:
            if self._code:
                if hasattr(ev, 'code') and ev.code == self._code:
                    _LOGGER.debug("SIA contact code matched: %s", self._code)
                    self._update_on_event(ev)
                return
            if self._label:
                lbl = self._extract_label_from_event(ev)
                if not lbl:
                    return
                def norm(s: str) -> str:
                    return re.sub(r"\s+", ' ', s.strip()).lower()
                if norm(lbl) == norm(self._label):
                    _LOGGER.debug("SIA contact label matched: %s", self._label)
                    self._update_on_event(ev)
        except Exception:
            _LOGGER.debug("Errore matching evento per contact %s", self._label or self._code)

    async def async_will_remove_from_hass(self) -> None:
        try:
            self._sia_data.remove_listener(self._handle_event)
        except Exception:
            pass

