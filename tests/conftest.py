"""
Configurazioni e fixture comuni per i test di pysiaalarm.

Qui definiamo una fixture ``event_loop`` per garantire la disponibilità
di un loop asyncio durante i test asincroni, utile in ambienti come Codespaces
in cui il plugin potrebbe non essere auto-caricato.
"""

from __future__ import annotations

import asyncio
import pytest


@pytest.fixture
def event_loop():
    """Crea un nuovo event loop per ogni test e lo chiude al termine."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()
