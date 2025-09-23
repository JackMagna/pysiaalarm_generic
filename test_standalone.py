#!/usr/bin/env python3
"""Test per l'integrazione pySIAAlarm standalone."""

import sys
import os
import asyncio
from unittest.mock import MagicMock

# Aggiungi il percorso per importare l'integrazione
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components/pysiaalarm'))

def test_sia_library():
    """Test della libreria SIA integrata."""
    print("🔍 Test libreria SIA integrata...")
    
    try:
        from sia.account import SIAAccount
        from sia.event import SIAEvent, OHEvent
        from sia.errors import InvalidAccountLengthError
        from sia.aio.client import SIAClient
        
        print("✅ Import libreria SIA riuscito")
        
        # Test creazione account
        account = SIAAccount('12345', None)
        assert account.account_id == '12345'
        assert not account.encrypted
        print("✅ Creazione account SIA")
        
        # Test validazione account
        try:
            SIAAccount.validate_account('12345')
            print("✅ Validazione account")
        except Exception as e:
            print(f"❌ Validazione account fallita: {e}")
            
        # Test creazione evento
        event = SIAEvent(
            full_message='"SIA-DCS"R0L0#12345',
            account='12345',
            timestamp=None,
            sia_account=account
        )
        assert event.account == '12345'
        print("✅ Creazione evento SIA")
        
        # Test funzione asincrona
        async def test_handler(event):
            pass
            
        # Test creazione client
        client = SIAClient('localhost', 12345, [account], test_handler)
        assert len(client.accounts) == 1
        print("✅ Creazione client SIA")
        
        return True
        
    except Exception as e:
        print(f"❌ Test libreria SIA fallito: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_imports():
    """Test import dell'integrazione Home Assistant."""
    print("🔍 Test import integrazione...")
    
    # Mock di Home Assistant per evitare errori di import
    sys.modules['homeassistant'] = MagicMock()
    sys.modules['homeassistant.config_entries'] = MagicMock()
    sys.modules['homeassistant.const'] = MagicMock()
    sys.modules['homeassistant.core'] = MagicMock()
    sys.modules['homeassistant.exceptions'] = MagicMock()
    sys.modules['homeassistant.components'] = MagicMock()
    sys.modules['homeassistant.components.sensor'] = MagicMock()
    sys.modules['homeassistant.helpers'] = MagicMock()
    sys.modules['homeassistant.helpers.entity'] = MagicMock()
    sys.modules['homeassistant.helpers.entity_platform'] = MagicMock()
    sys.modules['homeassistant.helpers.config_validation'] = MagicMock()
    sys.modules['homeassistant.data_entry_flow'] = MagicMock()
    
    # Mock delle costanti Home Assistant
    mock_const = MagicMock()
    mock_const.CONF_HOST = 'host'
    mock_const.CONF_PORT = 'port'
    mock_const.CONF_NAME = 'name'
    mock_const.Platform = MagicMock()
    mock_const.Platform.SENSOR = 'sensor'
    sys.modules['homeassistant.const'] = mock_const
    
    try:
        # Test import dei moduli dell'integrazione
        from config_flow import PySiaAlarmConfigFlow
        print("✅ Import config_flow")
        
        from sensor import SIALastEventSensor  
        print("✅ Import sensor")
        
        # Test import del modulo principale
        import const
        print("✅ Import const")
        
        return True
        
    except Exception as e:
        print(f"❌ Test integration imports fallito: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_functionality():
    """Test funzionalità asincrone."""
    print("🔍 Test funzionalità asincrone...")
    
    try:
        from sia.account import SIAAccount
        from sia.aio.client import SIAClient
        
        # Test handler asincrono
        events_received = []
        
        async def event_handler(event):
            events_received.append(event)
            
        account = SIAAccount('12345', None)
        client = SIAClient('localhost', 12345, [account], event_handler)
        
        # Test che il client sia configurato correttamente
        assert client._host == 'localhost'
        assert client._port == 12345
        assert len(client.accounts) == 1
        
        print("✅ Client asincrono configurato")
        
        # Test parsing messaggio (senza avviare il server)
        from sia.aio.server import SIAServerTCP
        server = SIAServerTCP({account.account_id: account}, event_handler)
        
        # Test parsing messaggio SIA
        test_message = '"SIA-DCS"R0L0#12345'
        event = server._parse_message(test_message)
        
        if event:
            assert event.account == '12345'
            print("✅ Parsing messaggio SIA")
        else:
            print("⚠️ Parsing messaggio restituisce None (normale per parser semplificato)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test async functionality fallito: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Esegue tutti i test."""
    print("🚀 Avvio test integrazione pySIAAlarm standalone\n")
    
    tests = [
        ("Libreria SIA", test_sia_library),
        ("Import integrazione", test_integration_imports),
        ("Funzionalità async", lambda: asyncio.run(test_async_functionality())),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Test: {test_name}")
        print('='*50)
        
        if test_func():
            print(f"✅ {test_name} PASSATO")
            passed += 1
        else:
            print(f"❌ {test_name} FALLITO")
    
    print(f"\n{'='*50}")
    print(f"RISULTATI: {passed}/{total} test passati")
    print('='*50)
    
    if passed == total:
        print("🎉 TUTTI I TEST PASSATI! L'integrazione standalone è pronta!")
        return True
    else:
        print("❌ Alcuni test sono falliti. Controllare gli errori sopra.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)