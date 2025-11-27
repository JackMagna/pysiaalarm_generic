"""Simplified SIA Server for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from ..account import SIAAccount
from ..event import SIAEvent, OHEvent

_LOGGER = logging.getLogger(__name__)

# Simplified SIA message parser
SIA_REGEX = re.compile(
    # Find the quoted message type and the account id (preceded by '#') anywhere in the message.
    # The message coming from some panels can include binary/hex prefixes or numbers between
    # the quoted type and the line/receiver markers, so we'll extract line/receiver separately.
    r'"(?P<msg_type>SIA-DCS|ADM-CID|OH)".*?#(?P<account>\w+)',
    re.DOTALL,
)


class SIAServerTCP:
    """Simplified SIA TCP Server for Home Assistant."""

    def __init__(
        self,
        accounts: dict[str, SIAAccount],
        func: Callable[[SIAEvent], Awaitable[None]],
    ):
        """Create a SIA TCP Server.

        Arguments:
            accounts: Dict with account_id as key, SIAAccount object as value
            func: Function called for each valid SIA event
        """
        self.accounts = accounts
        self.async_func = func
        self.shutdown_flag = False

    async def handle_line(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle line for SIA Events. This supports TCP connections.

        Arguments:
            reader: StreamReader with new data
            writer: StreamWriter to respond
        """
        while not self.shutdown_flag:
            try:
                data = await reader.read(1000)
                if not data or reader.at_eof():
                    break
                    
                message = data.decode('utf-8', errors='ignore')
                _LOGGER.debug("Received message: %s", message)
                
                event = self._parse_message(message)
                if event:
                    # Send response
                    response = event.create_response()
                    writer.write(response)
                    await writer.drain()
                    
                    # Call the user function
                    await self.async_func(event)
                
            except ConnectionResetError:
                break
            except Exception as e:
                _LOGGER.error("Error handling SIA message: %s", e)
                break

        writer.close()

    def _parse_message(self, message: str) -> SIAEvent | OHEvent | None:
        """Parse incoming SIA message into event object."""
        try:
            message = message.strip()
            match = SIA_REGEX.search(message)
            if not match:
                _LOGGER.debug("Message doesn't match SIA format: %s", message)
                return None

            groups = match.groupdict()
            msg_type = groups.get('msg_type', '')
            account_id = groups.get('account', '').upper()

            # Some panels include numeric prefixes or other tokens before the L.. and R.. markers
            # (for example: 6925L0 or binary/hex prefixes). Extract L and R markers separately.
            line_search = re.search(r'L\d+', message)
            receiver_search = re.search(r'R\d+', message)

            line = line_search.group(0) if line_search else 'L0'
            receiver = receiver_search.group(0) if receiver_search else 'R0'

            # Check if account is configured
            if account_id not in self.accounts:
                _LOGGER.debug("Unknown account: %s", account_id)
                return None

            account = self.accounts[account_id]

            if msg_type == 'OH':
                # Keep-alive message
                return OHEvent(
                    full_message=message,
                    message_type=msg_type,
                    account=account_id,
                    line=line,
                    receiver=receiver,
                    timestamp=datetime.now(),
                    sia_account=account,
                )
            else:
                # Regular SIA event
                ev = SIAEvent(
                    full_message=message,
                    message_type=msg_type,
                    account=account_id,
                    line=line,
                    receiver=receiver,
                    timestamp=datetime.now(),
                    sia_account=account,
                    code="999",  # Generic fallback code for simplified parser
                    message="SIA Event received",
                )

                # Try to extract more useful info from content between [] to help mapping
                # e.g. '[#005544|Nri1UX12^C. F.SINGOLA    CASA            ^]'
                try:
                    bracket = re.search(r"\[(.*?)\]", message)
                    if bracket:
                        content = bracket.group(1)
                        # try to find a 3-digit numeric code
                        code_search = re.search(r"\b(\d{3})\b", content)
                        if code_search:
                            ev.code = code_search.group(1)

                        # Special handling for Nri<part><Code><Zone> format (e.g. Nri1UX12)
                        # This overrides the generic 3-digit code search if found
                        special_match = re.search(r"Nri(\d+)([A-Z]{2})(\d+)", content)
                        if special_match:
                            # partition = special_match.group(1)
                            code_str = special_match.group(2)
                            zone_str = special_match.group(3)
                            # Construct a unique code for this sensor
                            ev.code = f"{code_str}-{zone_str}"
                            # Use zone as RI for consistency
                            ev.ri = zone_str 
                            try:
                                setattr(ev, 'zone', int(zone_str))
                            except Exception:
                                pass

                        # try to find 'ri' zone pattern (e.g. 'Nri1' -> zone 1)
                        ri_search = re.search(r"[Rr]?i(\d+)", content)
                        if ri_search:
                            ev.ri = ri_search.group(1)
                            # also set 'zone' attribute for sensors expecting it
                            try:
                                setattr(ev, 'zone', int(ev.ri))
                            except Exception:
                                setattr(ev, 'zone', ev.ri)
                except Exception as err:  # pragma: no cover - defensive
                    _LOGGER.debug("Non è stato possibile estrarre codice/zone dal messaggio: %s", err)

                return ev

        except Exception as e:
            _LOGGER.error("Error parsing message '%s': %s", message, e)
            return None