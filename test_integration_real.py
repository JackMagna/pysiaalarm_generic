"""Test configurazione integrazione con evento reale dai log."""
import asyncio
import logging
from pysiaalarm import SIAAccount, SIAEvent
from pysiaalarm.aio import SIAClient

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger("test_integration")

async def test_real_event():
    """Test con l'account e evento reale dai log."""
    
    # Configurazione dall'account visto nei log
    account = SIAAccount("005544")  # Nessuna chiave di cifratura
    
    events_received = []
    
    async def on_event(event: SIAEvent):
        """Handler asincrono per eventi."""
        events_received.append(event)
        _LOGGER.info("✅ Evento ricevuto: Code=%s, Zone=%s, Message=%s, Account=%s", 
                    event.code, getattr(event, 'zone', 'N/A'), 
                    getattr(event, 'message', 'N/A'), event.account)
    
    # Crea client che ascolta sulla porta 7777 (default HESA)
    client = SIAClient(
        host="0.0.0.0",
        port=7777,
        accounts=[account],
        function=on_event
    )
    
    try:
        _LOGGER.info("🚀 Avvio client SIA su porta 7777 per account 005544...")
        await client.start()
        _LOGGER.info("✅ Client avviato, in attesa eventi...")
        
        # Attendi eventi per 30 secondi
        await asyncio.sleep(30)
        
        _LOGGER.info("📊 Eventi ricevuti: %d", len(events_received))
        for i, event in enumerate(events_received):
            _LOGGER.info("📝 Evento %d: %s", i+1, event)
            
    except Exception as e:
        _LOGGER.error("❌ Errore: %s", e)
    finally:
        await client.stop()
        _LOGGER.info("🛑 Client fermato")

if __name__ == "__main__":
    asyncio.run(test_real_event())
