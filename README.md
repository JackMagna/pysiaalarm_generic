
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

## Modifiche recenti

Consulta il file `CHANGELOG.rst` per le ultime modifiche e correzioni.

## TODO / Fasi successive

- Implementazione della logica di interpretazione dei messaggi SIA.
- Creazione di entità e automazioni specifiche in base ai loghi/messaggi ricevuti.
- Integrazione avanzata con Home Assistant e altri ambienti.
