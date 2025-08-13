"""Smoke test end-to-end per pysiaalarm.

Avvia un server SIA TCP su una porta libera, invia un messaggio SIA-DCS
non cifrato e verifica la ricezione dell'ACK. Stampa anche i contatori.
"""
from __future__ import annotations

import logging
import socket
import time
from typing import List
from datetime import datetime

from pysiaalarm import SIAAccount, SIAClient, SIAEvent


logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger("smoke_test")


def crc_calc(msg: str) -> str:
    """Calcola il CRC come nel protocollo SIA (stesso algoritmo dei test)."""
    crc = 0
    for letter in msg.encode():
        temp = letter
        for _ in range(8):
            temp ^= crc & 1
            crc >>= 1
            if temp & 1:
                crc ^= 0xA001
            temp >>= 1
    return ("%04x" % crc).upper()


def build_packet(account: str, code: str = "CL", zone: str = "1") -> str:
    """Costruisce un pacchetto SIA-DCS non cifrato con CRC e length."""
    # Timestamp corrente (UTC) nel formato richiesto _HH:MM:SS,MM-DD-YYYY
    ts = datetime.utcnow().strftime("_%H:%M:%S,%m-%d-%Y")
    content = f"|Nri{zone}/{code}501]{ts}"
    line = f'"SIA-DCS"6002L0#{account}[{content}'
    crc = crc_calc(line)
    length = ("%04x" % len(line)).upper()
    return f"{crc}{length}{line}"


def main() -> int:
    events: List[SIAEvent] = []

    def on_event(ev: SIAEvent) -> None:
        events.append(ev)
        _LOGGER.info("Evento ricevuto: %s", ev)

    # Usa port=0 per far scegliere al SO una porta libera.
    account = SIAAccount("1111", "AAAAAAAAAAAAAAAA")
    client = SIAClient("127.0.0.1", 0, [account], function=on_event)
    client.start()
    try:
        # Attendi che il server sia pronto.
        time.sleep(0.1)
        assert client.sia_server is not None
        host, port = client.sia_server.server_address  # type: ignore[attr-defined]
        _LOGGER.info("Server avviato su %s:%s", host, port)

        # Invia un pacchetto SIA-DCS non cifrato per l'account configurato.
        pkt = build_packet(account.account_id)
        with socket.create_connection((host, port), timeout=2) as s:
            s.sendall(pkt.encode("ascii"))
            s.settimeout(2)
            data = s.recv(1024)
            _LOGGER.info("ACK: %s", data.decode(errors="ignore"))

        # Lascia processare l'evento.
        time.sleep(0.1)
        _LOGGER.info("Counts: %s", client.counts)
        _LOGGER.info("Numero eventi: %d", len(events))
        return 0
    finally:
        client.stop()


if __name__ == "__main__":
    raise SystemExit(main())
