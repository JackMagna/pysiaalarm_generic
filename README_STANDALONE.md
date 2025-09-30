# Integrazione pySIAAlarm per Home Assistant - Versione Standalone

Questa versione dell'integrazione pySIAAlarm include una **libreria SIA integrata** che elimina completamente la dipendenza esterna da `pysiaalarm`.

## 🎯 Vantaggi della Versione Integrata

- ✅ **Nessuna dipendenza esterna**: La libreria SIA è integrata direttamente nell'integrazione
- ✅ **Controllo completo**: Modifiche e patch applicate direttamente nel codice
- ✅ **Installazione semplificata**: Non richiede installazione di pacchetti Python aggiuntivi
- ✅ **Timestamp tolerance**: Include la patch per tolleranza timestamp di 5 minuti
- ✅ **Ridotte dipendenze**: Solo `pytz` come dipendenza esterna

## 📁 Struttura della Libreria Integrata

```
custom_components/pysiaalarm/
├── __init__.py              # Integrazione Home Assistant
├── config_flow.py          # Configurazione
├── sensor.py               # Sensori
├── manifest.json           # Manifest aggiornato
└── sia/                    # 🆕 Libreria SIA integrata
    ├── __init__.py         # Esportazioni principali
    ├── account.py          # Gestione account SIA
    ├── event.py            # Eventi SIA con timestamp patch
    ├── errors.py           # Eccezioni
    ├── const.py            # Costanti
    ├── utils.py            # Utilità
    ├── utils/              # Moduli utilità
    │   ├── __init__.py
    │   └── enums.py        # Enumerazioni
    └── aio/               # Moduli asincroni
        ├── __init__.py
        ├── client.py      # Client SIA semplificato
        └── server.py      # Server SIA semplificato
```

## 🔧 Modifiche Principali

### 1. Libreria SIA Integrata
- Copiati e adattati i componenti essenziali di `pysiaalarm`
- Rimossa dipendenza da librerie di crittografia (versione semplificata)
- Parser SIA semplificato ma funzionale

### 2. Patch Timestamp
Il modulo `sia/event.py` include la patch per la tolleranza timestamp:

```python
@property
def valid_timestamp(self) -> bool:
    """Check if the timestamp is within bounds with extended tolerance."""
    # PATCH: Tolleranza di 5 minuti per eventi SIA con timestamp skew
    tolerance_seconds = 300  # 5 minuti di tolleranza
    current_min = current_time - timedelta(seconds=tolerance_seconds)
    current_plus = current_time + timedelta(seconds=tolerance_seconds)
    
    is_valid = current_min <= self.timestamp <= current_plus
    return is_valid
```

### 3. Manifest Aggiornato
```json
{
    "requirements": [
        "pytz"
    ]
}
```

## 🚀 Installazione

1. Copiare la cartella `custom_components/pysiaalarm` in Home Assistant
2. Riavviare Home Assistant
3. Configurare l'integrazione tramite UI

## ⚡ Funzionalità

- ✅ Ricezione eventi SIA su TCP
- ✅ Gestione account multipli
- ✅ Sensori per ultimo evento
- ✅ Tolleranza timestamp estesa (5 minuti)
- ✅ Parser messaggi SIA e OH (keep-alive)
- ✅ Risposte ACK/DUH automatiche

## 🔍 Test

Per testare la libreria integrata:

```bash
cd custom_components/pysiaalarm
python -c "
from sia.account import SIAAccount
from sia.aio.client import SIAClient
print('✅ Libreria SIA integrata funzionante!')
"
```

## 📝 Note Tecniche

- La libreria integrata è una versione semplificata di `pysiaalarm`
- Non include funzionalità di crittografia avanzate
- Ottimizzata per integrazione Home Assistant
- Include solo protocollo TCP (UDP rimosso per semplicità)

## 🔄 Migrazione dalla Versione con Dipendenze

Per migrare da una versione precedente:

1. Rimuovere l'integrazione esistente
2. Rimuovere il pacchetto `pysiaalarm` se installato manualmente
3. Installare questa versione standalone
4. Riconfigurare l'integrazione

## Riepilogo rapido — cosa fornire per riprendere lo sviluppo

Se vuoi che lo sviluppo continui o venga eseguita una diagnosi più approfondita, per favore fornisci:

- Branch git o PR attiva
- Log Home Assistant (`home-assistant_*.log`) contenenti le righe relative ai messaggi ricevuti
- Esempi raw dei messaggi TCP ricevuti (se possibile: la riga completa così come appare nei log)
- Informazioni di configurazione: `host`, `port`, `account_id` (non inviare chiavi private pubblicamente)

Questi elementi permettono di riprodurre i casi in test automatici e migliorare il parser per la tua centrale.

## Novità in questo rilascio (funzionalità aggiunte)

- Parser SIA più permissivo con estrazione L/R
- Estrazione euristica di contenuto tra parentesi quadre per `code`/`ri`/`zone`
- Modalità learning per raccogliere codici osservati e persisterli
- Sensori dinamici per codici rilevati
- Esportazione CSV manuale e RAW events
- Export automatico periodico (start/stop)
- Nome dei file di export con timestamp per evitare sovrascritture

## Come testare i servizi in Home Assistant

1) Avvia Home Assistant e carica l'integrazione `pysiaalarm`.
2) Vai su Developer Tools → Services.

- Start learning:

    Domain: `pysiaalarm`
    Service: `start_learning`
    Service Data: `{}`

- Stop learning:

    Domain: `pysiaalarm`
    Service: `stop_learning`
    Service Data: `{}`

- Export manuale:

    Domain: `pysiaalarm`
    Service: `export_codes`
    Service Data (opzionale):

    {
        "filename": "pysiaalarm_codes_esempio_20250930_123000.csv"
    }

- Start auto export (ogni 24h):

    Domain: `pysiaalarm`
    Service: `start_auto_export`
    Service Data:

    {
        "interval_seconds": 86400,
        "filename": "pysiaalarm_codes_daily.csv"
    }

- Stop auto export:

    Domain: `pysiaalarm`
    Service: `stop_auto_export`
    Service Data: `{}`

3) Controlla i file generati nella directory di configurazione di Home Assistant.

---

Se vuoi, posso anche aggiungere una sezione di debug con comandi `curl` o script Python per simulare l'invio di messaggi SIA alla porta TCP del server locale.