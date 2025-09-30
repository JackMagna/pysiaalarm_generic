
![CI](https://github.com/eavanvalkenburg/pysiaalarm/workflows/CI/badge.svg?branch=master)
![Build](https://github.com/eavanvalkenburg/pysiaalarm/workflows/Build/badge.svg)
[![PyPI version](https://badge.fury.io/py/pysiaalarm.svg)](https://badge.fury.io/py/pysiaalarm)

# pySIAAlarm

Pacchetto Python per la creazione di un client che comunica con sistemi di allarme basati su protocollo SIA. Compatibile con qualsiasi sistema che utilizza il protocollo SIA (ad esempio HESA). Il pacchetto può essere integrato in Home Assistant o altri ambienti. La logica di interpretazione dei messaggi e la creazione di entità specifiche verrà aggiunta in una fase successiva.

## Descrizione


Questo pacchetto è stato creato per comunicare con sistemi di allarme che utilizzano il protocollo SIA. Supporta tutti i codici SIA definiti e non è vincolato a nessun produttore specifico.
Puoi creare un nuovo thread con un server TCP oppure una coroutine asyncio che rimane in ascolto sull’host e la porta specificati; il sistema di allarme agisce da client e invia messaggi al server, che li riconosce e chiama la funzione fornita.
In questa fase il pacchetto si limita a ricevere e gestire i messaggi SIA in modo generico, senza interpretare o creare entità specifiche. La logica di interpretazione e la creazione di entità sarà sviluppata successivamente, in base ai loghi/messaggi ricevuti.

La versione asyncio sembra essere più veloce, ma dipende dal sistema.

## Configurazione

Scegli se usare l’approccio Threaded o Asyncio.

### SIAClient

Versione Threaded:
```python
from pysiaalarm import SIAClient, SIAAccount
```
Versione Asyncio:
```python
from pysiaalarm.aio import SIAClient, SIAAccount
```

Gli argomenti di SIAClient sono:

- host: l’host specifico con cui comunicare, solitamente '' per localhost.
- port: la porta TCP su cui comunica il sistema di allarme.
- accounts: lista di oggetti SIAAccount autorizzati a inviare messaggi al server.
- function: funzione chiamata per ogni evento gestito, accetta solo un parametro SIAEvent e non restituisce nulla.

### SIAAccount

Gli argomenti di SIAAccount sono:

- account_id: ID account da 3 a 16 caratteri ASCII esadecimali.
- [opzionale] key: chiave di cifratura specificata nel sistema di allarme, 16, 24 o 32 caratteri ASCII.
- [opzionale] allowed_timeband: intervallo di tempo accettato per i messaggi cifrati, di default tra -40 e +20 secondi rispetto al timestamp del server.


Consulta [`tests/run.py`](tests/run.py) o [`tests/run_aio.py`](tests/run_aio.py) per un esempio completo di utilizzo generico. Gli esempi non creano entità o logiche specifiche, ma mostrano solo la ricezione e gestione dei messaggi SIA.

## Logging di default

Per facilitare il debug (anche in Home Assistant), il pacchetto abilita di default il logging a livello DEBUG per il namespace "pysiaalarm" e aggiunge un semplice StreamHandler. Se la tua applicazione configura già i logger o preferisci disattivare questo comportamento, imposta la variabile d'ambiente:

- PYSIA_DISABLE_DEFAULT_LOGGING=1

Quando impostata, il pacchetto non aggiungerà handler né modificherà i livelli di logging. In Home Assistant in genere non devi fare nulla: i log compariranno automaticamente; se non desiderati, puoi disabilitarli con la variabile d'ambiente sopra.

## Note SIA per HESA (indicative)

- Protocollo: SIA DC-09 (SIA-DCS) su TCP o UDP. Questo pacchetto supporta entrambi.
- Account ID: deve corrispondere all’ID configurato nella centrale HESA.
- Cifratura: AES-CBC con chiave ASCII di 16/24/32 caratteri (se abilitata in centrale). Usa lo stesso valore in `SIAAccount(key=...)`.
- Timestamp: la centrale deve avere orario corretto; la finestra di validità predefinita è -40/+20s. Messaggi fuori finestra saranno NAK.
- Porta: aprire/forwardare la porta selezionata sul server che esegue pySIAAlarm.
- Formati: i messaggi SIA sono accettati in modo generico; la logica di interpretazione verrà aggiunta in seguito.

Nota: le specifiche reali possono variare tra modelli/firmware HESA; considera queste note come guida generale per SIA.

## Guida rapida per Home Assistant

Questo pacchetto è una libreria Python. Può essere usato:

- come dipendenza di un’integrazione personalizzata (custom component),
- oppure tramite AppDaemon / Python script esterni che avviano un `SIAClient`.

Indicazioni pratiche:

1. Esegui un server SIA all’avvio dell’integrazione/script, indicando host, porta e account autorizzati.
2. Fornisci una funzione callback che riceve `SIAEvent` e gestisce l’evento (per ora in modo generico).
3. Configura la centrale HESA per inviare SIA DC-09 verso l’IP/porta di Home Assistant.
4. Usa il logging di default già attivo per il debug, o disattivalo con `PYSIA_DISABLE_DEFAULT_LOGGING=1`.

Esempio minimale (sincrono):

```python
from pysiaalarm import SIAClient, SIAAccount

def on_event(event):
	# TODO: logica personalizzata (HA): invia evento al bus, crea notifiche, ecc.
	print("Evento SIA ricevuto:", event)

client = SIAClient(host="0.0.0.0", port=7777,
				   accounts=[SIAAccount(account_id="1111", key="AAAAAAAAAAAAAAAA")],
				   function=on_event)
client.start()
```

In un’integrazione HA reale, incapsula l’avvio/arresto del server nel ciclo di vita dell’integrazione e non bloccare il thread principale.

## Troubleshooting rapido

- Ricevi NAK: controlla timestamp del messaggio (orologio centrale), account ID e CRC/chiave.
- Nessun evento: verifica che la porta sia in ascolto e raggiungibile (NAT/firewall).
- Duplicazione log: imposta `PYSIA_DISABLE_DEFAULT_LOGGING=1` se HA o la tua app gestisce già i logger.

## Come provarlo in Codespaces

Ambiente usato: Debian bullseye con Python 3.9 senza privilegi sudo. Esegui i comandi seguenti nel terminale del Codespace.

1) Installazione locale (user-space) e test:

```bash
# Installa pip in user-space (se mancante) e dipendenze di test + pacchetto in editable
curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
/usr/bin/python3 get-pip.py --user
~/.local/bin/pip install --user -e .[testing]

# Esegui test
~/.local/bin/pytest -q
```

2) Esecuzione smoke test end-to-end (TCP):

```bash
# Opzionale: crea una config locale di esempio
/usr/bin/python3 - <<'PY'
import json
cfg = {"account_id": "1111", "key": "AAAAAAAAAAAAAAAA", "host": "127.0.0.1", "port": 7777}
open('local_config.json','w').write(json.dumps(cfg))
print('local_config.json scritto')
PY

# Avvia lo smoke test (avvia server su porta libera, invia un pacchetto e verifica ACK)
/usr/bin/python3 tests/smoke_test.py
```

Nota: se ricevi NAK per timestamp non valido, verifica l’orario della centrale o ritesta: lo smoke test genera il timestamp corrente in UTC.

## Modifiche recenti

Consulta il file `CHANGELOG.rst` per le ultime modifiche e correzioni.

## TODO / Fasi successive

- Implementazione della logica di interpretazione dei messaggi SIA.
- Creazione di entità e automazioni specifiche in base ai loghi/messaggi ricevuti.
- Integrazione avanzata con Home Assistant e altri ambienti.

## Riepilogo rapido — cosa mi serve per riprendere l'implementazione

Quando vuoi che io (o un altro sviluppatore) riprenda il lavoro sulle funzionalità, inviami per favore questo insieme minimo di informazioni:

- Branch/git: nome del branch attivo (se diverso da `master`) e eventuale PR aperta
- Log Home Assistant (file `home-assistant_*.log`) con i messaggi relativi all'integrazione e ai messaggi SIA
- Esempi raw dei messaggi ricevuti dalla centrale (es. riga TCP completa così come appare nei log)
- Config entry: `host`, `port`, `account_id` (non inviare chiavi segrete in pubblico)
- Descrizione del comportamento atteso vs. comportamento osservato (es. quali sensori non si aggiornano)
- Elenco di codici/zone che vorresti mappare esplicitamente (se già noti)

Con questi elementi posso:
- replicare i messaggi e i casi in unit test o test di integrazione
- migliorare il parser e le euristiche di estrazione di `code`, `ri`, `zone`
- creare sensori dinamici o mappature predefinite per i codici più usati

## Rilasci recenti (funzionalità aggiunte)

Le modifiche più recenti incluse in questa fork / integrazione standalone:

- Parser SIA più permissivo: riconosce messaggi con prefissi/hex e estrae L/R separatamente
- Estrazione euristica di contenuti tra parentesi quadre per ricavare `code`, `ri` e `zone`
- Modalità "learning" per raccogliere codici osservati e crearne la lista persistente
- Persistenza dei codici via Home Assistant Storage (chiave: `pysiaalarm.codes`)
- Sensori dinamici generati per ogni codice conosciuto (creazione on-demand)
- Sanificazione degli attributi dei sensori (solo tipi JSON-serializzabili)
- Esportazione CSV: sintesi dei codici + file RAW con tutti gli eventi registrati
- Avvio/stop export periodico (start_auto_export / stop_auto_export)
- Nome file di export con timestamp (formato: `pysiaalarm_codes_YYYYMMDD_HHMMSS.csv`) per evitare sovrascritture
- Aumento del numero di sample conservati per codice (fino a 50) per analisi

## Verifica dei servizi in Home Assistant — guida passo-passo

Questa guida mostra come verificare i servizi aggiunti dall'integrazione usando Developer Tools → Services nella UI di Home Assistant.

1) Accedi a Home Assistant e vai su Developer Tools → Services.

2) Avvia/ragiona la learning mode
- Domain: `pysiaalarm`  
- Service: `start_learning`  
- Service Data: `{}`  

Premi Call Service. Se vuoi fermarla:  
- Service: `stop_learning`  
- Service Data: `{}`

3) Esporta i codici (export manuale)
- Domain: `pysiaalarm`  
- Service: `export_codes`  
- Service Data (opzionale - salva con nome custom sotto la cartella di configurazione HA):

	{
		"filename": "pysiaalarm_codes_miaCasa_20250930_123000.csv"
	}

Se non fornisci `filename`, l'integrazione genererà automaticamente un file con timestamp nel formato `pysiaalarm_codes_YYYYMMDD_HHMMSS.csv` nella directory di configurazione di HA.

4) Avvia export automatico periodico
- Domain: `pysiaalarm`  
- Service: `start_auto_export`  
- Service Data (esempio per export ogni 24h):

	{
		"interval_seconds": 86400,
		"filename": "pysiaalarm_codes_daily.csv"  # opzionale: se relativo, sarà salvato sotto la config dir
	}

Per fermare l'export automatico:  
- Service: `stop_auto_export`  
- Service Data: `{}`

5) Pulire la lista di codici salvati
- Domain: `pysiaalarm`  
- Service: `clear_codes`  
- Service Data: `{}`

6) Controllare i file esportati
- Dopo un export, trova i file sotto la directory di configurazione di Home Assistant (es. `/config/pysiaalarm_codes_YYYYMMDD_HHMMSS.csv` e `_raw.csv`).
- Se non trovi i file, controlla i log di Home Assistant per messaggi `Export automatico SIA completato` o `Codici SIA esportati`.

## Comandi locali utili (terminal) per debug

Esempi da eseguire nella macchina che esegue Home Assistant (o nel dev container):

```bash
# Cerca i file di export nella config directory di HA
ls -l $HOME/.homeassistant | grep pysiaalarm_codes || true

# Visualizza gli ultimi log relativi a pysiaalarm
grep -i "pysiaalarm" home-assistant_*.log | tail -n 200
```

## Note finali
- Se vuoi che crei automaticamente mapping precisi tra codici e sensori (con nomi friendly), invia una lista iniziale di codici e la loro descrizione.
- Se preferisci posso aggiungere la persistenza della configurazione dell'export automatico per riattivare il job dopo il riavvio di HA.

