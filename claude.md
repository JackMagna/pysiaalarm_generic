# Repository: pysiaalarm_generic

## 📂 Struttura della libreria

### Libreria core (`src/pysiaalarm/`)
- **`__init__.py`** - Entry point principale con exports SIAClient, SIAAccount, SIAEvent
- **`account.py`** - Gestione account SIA con cifratura e validazione
- **`base_client.py`** / **`base_server.py`** - Classi base per client/server
- **`event.py`** - Modelli eventi SIA (SIAEvent, OHEvent) 
- **`sync/client.py`** - Client sincrono TCP/UDP
- **`aio/client.py`** - Client asincrono TCP/UDP
- **`data/`** - Codici SIA, mappature ADM e dati di configurazione
- **`utils/`** - Utilità (counter, enums, regex)

### Integrazione Home Assistant (`custom_components/pysiaalarm/`)
- **`manifest.json`** - Manifest dell'integrazione (✅ COMPLETO)
- **`__init__.py`** - Setup integrazione con gestione client SIA (✅ FUNZIONALE)
- **`config_flow.py`** - UI configurazione connessione (✅ COMPLETO)
- **`const.py`** - Costanti condivise (✅ COMPLETO)
- **`sensor.py`** - Sensori monitoraggio eventi per mappatura (✅ FASE 1)
- **`strings.json`** - Traduzioni UI (✅ COMPLETO)
- **~~`alarm_control_panel.py`~~** - Rimosso (non necessario per solo monitoraggio)

### File di supporto
- **`README.md`** - Documentazione completa in italiano
- **`tests/`** - Suite test completa con smoke test
- **`docs/`** - Documentazione Sphinx

## ⚙️ Obiettivi / Funzionalità

### Libreria pySIAAlarm
**Scopo**: Libreria Python per comunicazione con sistemi di allarme via protocollo SIA (Security Industry Association).

**Funzionalità principali**:
- Server TCP/UDP per ricezione messaggi SIA-DCS
- Supporto cifratura AES-CBC (16/24/32 char keys)
- Parsing eventi SIA con validazione CRC e timestamp
- Client sincrono e asincrono
- Compatibilità con sistemi HESA e altri produttori SIA

**Utilizzo attuale**: Libreria generica per ricezione/parsing messaggi SIA senza interpretazione specifica.

### Integrazione Home Assistant (FASE 1 - MONITORAGGIO)
**Scopo attuale**: Solo lettura e monitoraggio eventi SIA per identificare sensori di casa.

**Entità implementate (solo lettura)**:
- `sensor.sia_events_monitor` - Contatore eventi con codici/zone uniche identificate
- `sensor.sia_last_event_details` - Dettagli completi ultimo evento per debug

**NON include**:
- Controllo allarme (arm/disarm)
- Binary sensors specifici per zone
- Automazioni o azioni

**Utilizzo**: Raccogliere dati per identificare tutti i sensori di casa attraverso eventi broadcast dell'allarme.

## ✅ Compatibilità con HACS

### ✅ **PRONTA per HACS** - Implementazione fase 1 completata:

1. **✅ Manifest completo**:
   ```json
   {
     "domain": "pysiaalarm",
     "name": "pySIAAlarm Integration",
     "requirements": ["pysiaalarm"],
     "config_flow": true,
     "iot_class": "local_push"
   }
   ```

2. **✅ Setup monitoraggio**:
   - Setup integrazione con gestione client SIA
   - Gestione lifecycle e listeners eventi
   - Solo lettura eventi per mappatura sensori

3. **✅ File implementati**:
   - ✅ `config_flow.py` - UI configurazione host/porta/account
   - ✅ `const.py` - Costanti condivise
   - ✅ `strings.json` - Traduzioni UI
   - ✅ `hacs.json` - Configurazione HACS

4. **✅ Sensori monitoraggio (FASE 1)**:
   - ✅ `sensor.sia_events_monitor` - Raccoglie codici/zone uniche per mappatura
   - ✅ `sensor.sia_last_event_details` - Debug completo eventi ricevuti
   - ✅ Logging eventi per identificazione sensori casa

### ✅ **Funzionalità FASE 1**:
- **Setup via UI**: Configurazione connessione sistema allarme
- **Monitoraggio passivo**: Solo ricezione e log eventi SIA
- **Identificazione**: Raccolta codici eventi e zone per mappatura futura
- **Debug**: Attributi completi eventi per analisi

## 💡 Migliorie opzionali per produzione

### � **Miglioramenti raccomandati**:

1. **Testing integrazione HA**:
   - Test automatici per config_flow
   - Test entità e stati
   - Mock client SIA per test isolati

## 💡 Roadmap sviluppo prossime fasi

### 🔵 **FASE 2 - PANNELLO MAPPATURA SENSORI**

**Obiettivo**: Creare interfaccia per associare eventi SIA ai sensori fisici di casa.

**Sviluppi necessari**:

1. **Pannello configurazione avanzata**:
   ```yaml
   # Esempio configurazione futura
   pysiaalarm:
     sensors:
       - zone: "001"
         code: "OP"
         name: "Porta Ingresso"
         device_class: "door"
         room: "Ingresso"
       - zone: "002" 
         code: "CL"
         name: "Finestra Soggiorno"
         device_class: "window"
         room: "Soggiorno"
   ```

2. **UI Mappatura nella config**:
   - Lista eventi SIA ricevuti con frequenza
   - Form associazione: evento → nome sensore → stanza → tipo
   - Anteprima entità che verranno create
   - Test attivazione per verifica mappatura

3. **Entità dinamiche**:
   - `binary_sensor.porta_ingresso` (da zona 001)
   - `binary_sensor.finestra_soggiorno` (da zona 002)
   - Device grouping per stanza
   - Stati personalizzati per tipo sensore

4. **Storage configurazione**:
   - File persistente mappatura sensori
   - Import/export configurazione
   - Backup/restore associazioni

### 🔵 **FASE 3 - AUTOMAZIONI E SERVIZI**

**Sviluppi avanzati**:

1. **Servizi personalizzati**:
   - `pysiaalarm.map_sensor` - Associa evento a sensore
   - `pysiaalarm.test_zone` - Test attivazione zona
   - `pysiaalarm.export_config` - Esporta mappatura

2. **Eventi personalizzati HA**:
   - `pysiaalarm_sensor_triggered` - Evento sensore attivato
   - `pysiaalarm_zone_discovered` - Nuova zona identificata
   - `pysiaalarm_mapping_complete` - Mappatura completata

3. **Automazioni pre-configurate**:
   - Notifiche apertura/chiusura
   - Gruppi sensori per stanza
   - Stati presenza in base a sensori

### 🔵 **FASE 4 - DASHBOARD E ANALYTICS**

**Miglioramenti UX**:

1. **Dashboard mappatura**:
   - Mappa casa con sensori
   - Timeline eventi per zona
   - Statistiche attivazioni

2. **Analytics**:
   - Pattern aperture/chiusure
   - Sensori più/meno attivi
   - Suggerimenti automazioni

**Priorità sviluppo**: FASE 2 → FASE 3 → FASE 4

## 🎯 Conclusione FASE 1

**Stato attuale**: ✅ **FASE 1 COMPLETATA** - Solo monitoraggio eventi SIA

L'integrazione attuale implementa solo la **ricezione e analisi eventi** per identificare sensori:

- ✅ **Connessione sistema allarme** - Client SIA configurabile via UI
- ✅ **Monitoraggio passivo** - Raccolta eventi senza controllo allarme  
- ✅ **Identificazione sensori** - Codici/zone uniche per mappatura futura
- ✅ **Debug completo** - Attributi dettagliati per analisi eventi
- ✅ **Compatibilità HACS** - Installabile come custom repository

**Prossimo obiettivo**: FASE 2 - Sviluppo pannello per associare eventi SIA ai sensori fisici di casa.
