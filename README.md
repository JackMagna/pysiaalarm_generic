
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
