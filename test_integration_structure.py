#!/usr/bin/env python3
"""
Test per verificare la struttura dell'integrazione Home Assistant.
Questo script simula la validazione che HA fa quando carica un'integrazione.
"""

import os
import json
import importlib.util
import sys

def test_integration_structure():
    """Test della struttura dell'integrazione."""
    
    integration_path = "/workspaces/pysiaalarm_generic/custom_components/pysiaalarm"
    
    print("🔍 Test struttura integrazione Home Assistant")
    print(f"📁 Path: {integration_path}")
    print()
    
    # 1. Verifica esistenza cartella
    if not os.path.exists(integration_path):
        print("❌ Cartella integrazione non trovata")
        return False
    print("✅ Cartella integrazione esistente")
    
    # 2. Verifica manifest.json
    manifest_path = os.path.join(integration_path, "manifest.json")
    if not os.path.exists(manifest_path):
        print("❌ manifest.json mancante")
        return False
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        print("✅ manifest.json valido")
        print(f"   Domain: {manifest.get('domain')}")
        print(f"   Config flow: {manifest.get('config_flow')}")
        print(f"   Version: {manifest.get('version')}")
    except json.JSONDecodeError as e:
        print(f"❌ manifest.json non valido: {e}")
        return False
    
    # 3. Verifica __init__.py
    init_path = os.path.join(integration_path, "__init__.py")
    if not os.path.exists(init_path):
        print("❌ __init__.py mancante")
        return False
    print("✅ __init__.py esistente")
    
    # 4. Verifica config_flow.py (se config_flow=true)
    if manifest.get('config_flow'):
        config_flow_path = os.path.join(integration_path, "config_flow.py")
        if not os.path.exists(config_flow_path):
            print("❌ config_flow.py mancante ma config_flow=true nel manifest")
            return False
        print("✅ config_flow.py esistente")
        
        # Test import del config_flow
        try:
            spec = importlib.util.spec_from_file_location("config_flow", config_flow_path)
            if spec is None:
                print("❌ Impossibile creare spec per config_flow.py")
                return False
            
            print("✅ config_flow.py importabile")
            print("   Nota: Import completo non testato (dipendenze HA mancanti)")
            
        except Exception as e:
            print(f"❌ Errore nell'analisi config_flow.py: {e}")
            return False
    
    # 5. Verifica const.py
    const_path = os.path.join(integration_path, "const.py")
    if not os.path.exists(const_path):
        print("⚠️  const.py mancante (raccomandato)")
    else:
        print("✅ const.py esistente")
    
    # 6. Verifica che domain in manifest e const corrispondano
    try:
        spec = importlib.util.spec_from_file_location("const", const_path)
        const_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(const_module)
        
        domain_const = getattr(const_module, 'DOMAIN', None)
        domain_manifest = manifest.get('domain')
        
        if domain_const != domain_manifest:
            print(f"❌ Domain mismatch: const.py='{domain_const}' vs manifest.json='{domain_manifest}'")
            return False
        print(f"✅ Domain consistente: '{domain_manifest}'")
        
    except Exception as e:
        print(f"⚠️  Impossibile verificare consistenza domain: {e}")
    
    print()
    print("🎉 Struttura integrazione sembra corretta!")
    print()
    print("💡 Possibili cause dell'errore 'Invalid handler specified':")
    print("   1. Versione Home Assistant incompatibile con selettori moderni")
    print("   2. Errori di runtime nel config_flow (risolti rimuovendo selettori)")
    print("   3. Cache Home Assistant - riavvio necessario")
    print("   4. Permessi file o path integrazione")
    print()
    print("🔧 Passi di troubleshooting:")
    print("   1. Riavvio completo Home Assistant")
    print("   2. Cancellazione cache custom_components")
    print("   3. Verifica log Home Assistant per errori dettagliati")
    
    return True

if __name__ == "__main__":
    test_integration_structure()
