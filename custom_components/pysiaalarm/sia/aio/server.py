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
    r'"(?P<msg_type>SIA-DCS|ADM-CID|OH)"\s*(?P<line>L\d+)?\s*(?P<receiver>R\d+)?\s*#(?P<account>\w+).*'
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
            match = SIA_REGEX.match(message.strip())
            if not match:
                _LOGGER.debug("Message doesn't match SIA format: %s", message)
                return None

            groups = match.groupdict()
            msg_type = groups.get('msg_type', '')
            account_id = groups.get('account', '').upper()
            line = groups.get('line', 'L0')
            receiver = groups.get('receiver', 'R0')

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
                return SIAEvent(
                    full_message=message,
                    message_type=msg_type,
                    account=account_id,
                    line=line,
                    receiver=receiver,
                    timestamp=datetime.now(),
                    sia_account=account,
                    code="999",  # Generic code for simplified parser
                    message="SIA Event received",
                )

        except Exception as e:
            _LOGGER.error("Error parsing message '%s': %s", message, e)
            return None