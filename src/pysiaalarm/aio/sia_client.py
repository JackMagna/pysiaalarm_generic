"""This is a the main class for the SIA Client."""
import asyncio
import logging
from typing import Callable
from typing import List

from .. import __author__
from .. import __copyright__
from .. import __license__
from .. import __version__
from ..base_sia_client import BaseSIAClient
from ..sia_account import SIAAccount
from ..sia_event import SIAEvent
from .sia_server import SIAServer

logging.getLogger(__name__)


class SIAClient(BaseSIAClient):
    def __init__(
        self,
        host: str,
        port: int,
        accounts: List[SIAAccount],
        function: Callable[[SIAEvent], None],
    ):
        """Create the asynchronous SIA Client object.

        Arguments:
            host {str} -- Host to run the server on, usually would be ""
            port {int} -- The port the server listens to.
            accounts {List[SIAAccount]} -- List of SIA Accounts to add.
            function {Callable[[SIAEvent], None]} -- The function that gets called for each event.

        """
        BaseSIAClient.__init__(self, host, port, accounts, function)

    def start(self):
        """Start the asynchronous SIA server."""
        logging.debug("Starting SIA.")
        loop = asyncio.get_event_loop()
        self.sia_server = SIAServer(self._accounts, self._func, self._counts)
        self.coro = asyncio.start_server(
            self.sia_server.handle_line, self._host, self._port, loop=loop
        )
        self.task = loop.create_task(self.coro)

    async def stop(self):
        """Stop the asynchronous SIA server."""
        logging.info("Stopping SIA.")
        self.sia_server.shutdown_flag = True
        await self.task
