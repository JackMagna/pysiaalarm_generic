"""Simplified SIA Client for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ..account import SIAAccount
from ..event import SIAEvent
from ..utils.enums import CommunicationsProtocol
from .server import SIAServerTCP

_LOGGER = logging.getLogger(__name__)


class SIAClient:
    """Simplified SIA Client for Home Assistant integration."""

    def __init__(
        self,
        host: str,
        port: int,
        accounts: list[SIAAccount],
        function: Callable[[SIAEvent], Awaitable[None]],
        protocol: CommunicationsProtocol = CommunicationsProtocol.TCP,
    ):
        """Create the SIA Client.

        Arguments:
            host: Host to run the server on
            port: The port the server listens to
            accounts: List of SIA Accounts
            function: The async function that gets called for each event
            protocol: Protocol to use (TCP only for simplicity)
        """
        if not asyncio.iscoroutinefunction(function):
            raise TypeError("Function should be a coroutine, create with async def.")
        
        self._host = host
        self._port = port
        self._func = function
        self._accounts = {a.account_id: a for a in accounts}
        self._protocol = protocol
        
        self.task: asyncio.Task | None = None
        self._server: SIAServerTCP | None = None

    async def start(self, **kwargs: Any) -> None:
        """Start the SIA client."""
        _LOGGER.debug("Starting SIA client on %s:%s", self._host, self._port)
        
        # Create the server
        self._server = SIAServerTCP(self._accounts, self._func)
        
        # Start the asyncio server
        coro = asyncio.start_server(
            self._server.handle_line, self._host, self._port, **kwargs
        )
        self.task = asyncio.create_task(coro)
        _LOGGER.info("SIA client started and listening")

    async def stop(self) -> None:
        """Stop the SIA client."""
        _LOGGER.debug("Stopping SIA client")
        
        if self._server:
            self._server.shutdown_flag = True
            
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        _LOGGER.info("SIA client stopped")

    @property
    def accounts(self) -> list[SIAAccount]:
        """Return accounts list."""
        return list(self._accounts.values())

    @accounts.setter 
    def accounts(self, accounts: list[SIAAccount]) -> None:
        """Set the accounts to monitor."""
        self._accounts = {a.account_id: a for a in accounts}
        if self._server:
            self._server.accounts = self._accounts