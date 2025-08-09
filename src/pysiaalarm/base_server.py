"""This is the base class with the handling logic for both sia_servers.

Adds optional logging of raw incoming SIA lines to a file (rotating).
This helps external systems (e.g., Home Assistant) analyze the inbound
messages and derive a mapping to virtual sensors.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from abc import ABC
from collections.abc import Awaitable, Callable

from .account import SIAAccount
from .const import (
    COUNTER_ACCOUNT,
    COUNTER_CODE,
    COUNTER_CRC,
    COUNTER_EVENTS,
    COUNTER_FORMAT,
    COUNTER_TIMESTAMP,
    COUNTER_USER_CODE,
)
from .errors import EventFormatError, NoAccountError
from .event import NAKEvent, OHEvent, SIAEvent, EventsType
from .utils import Counter, ResponseType

_LOGGER = logging.getLogger(__name__)


class BaseSIAServer(ABC):
    """Base class for SIA Server."""

    def __init__(
        self,
        accounts: dict[str, SIAAccount],
        counts: Counter,
        func: Callable[[SIAEvent], None] | None = None,
        async_func: Callable[[SIAEvent], Awaitable[None]] | None = None,
        raw_message_log_path: str | None = None,
        raw_message_log_rotate_bytes: int = 1024 * 1024,
        raw_message_log_backup_count: int = 3,
    ):
        """Create a SIA Server.

        Arguments:
            accounts Dict[str, SIAAccount] -- accounts as dict with account_id as key, SIAAccount object as value.  # pylint: disable=line-too-long
            func Callable[[SIAEvent], None] -- Function called for each valid SIA event, that can be matched to a account.  # pylint: disable=line-too-long
            counts Counter -- counter kept by client to give insights in how many errorous EventsType were discarded of each type.  # pylint: disable=line-too-long
            raw_message_log_path str | None -- If provided, all incoming raw SIA lines will be appended to this file via a rotating file handler. No effect when None.
            raw_message_log_rotate_bytes int -- Max size in bytes before rotating the raw message log. Default 1 MiB.
            raw_message_log_backup_count int -- Number of rotated backup files to keep. Default 3.
        """
        self.accounts = accounts
        self.func = func
        self.async_func = async_func
        self.counts = counts
        self.shutdown_flag = False
        # Optional raw message logger (thread-safe via logging's own lock)
        self._raw_logger: logging.Logger | None = None
        if raw_message_log_path:
            try:
                raw_logger = logging.getLogger(f"{__name__}.raw")
                raw_logger.setLevel(logging.INFO)
                # Avoid duplicate handlers if multiple servers are created.
                # Reuse existing handler if already configured for same path.
                handler_found = False
                for h in raw_logger.handlers:
                    if isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == raw_message_log_path:
                        handler_found = True
                        break
                if not handler_found:
                    handler = RotatingFileHandler(
                        raw_message_log_path,
                        maxBytes=raw_message_log_rotate_bytes,
                        backupCount=raw_message_log_backup_count,
                        encoding="utf-8",
                    )
                    formatter = logging.Formatter(
                        fmt="%(asctime)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                    )
                    handler.setFormatter(formatter)
                    raw_logger.addHandler(handler)
                # Do not propagate to root to avoid duplicating output.
                raw_logger.propagate = False
                self._raw_logger = raw_logger
            except Exception as exp:  # pragma: no cover
                _LOGGER.error("Failed to configure raw message logger: %s", exp)

    def parse_and_check_event(self, data: bytes) -> EventsType | None:
        """Parse and check the line and create the event, check the account and define the response.

        Args:
            line (str): Line to parse

        Returns:
            SIAEvent: The SIAEvent type of the parsed line.
            ResponseType: The response to send to the alarm.

        """
        line = str.strip(data.decode("ascii", errors="ignore"))
        if not line:
            return None
        # Optionally log raw incoming line for external consumption (e.g., HA download)
        if self._raw_logger is not None:
            try:
                self._raw_logger.info("%s", line)
            except Exception:  # pragma: no cover
                pass
        self.log_and_count(COUNTER_EVENTS, line=line)
        try:
            event = SIAEvent.from_line(line, self.accounts)
        except NoAccountError as exc:
            self.log_and_count(COUNTER_ACCOUNT, line, exception=exc)
            return NAKEvent()
        except EventFormatError as exc:
            self.log_and_count(COUNTER_FORMAT, line, exception=exc)
            return NAKEvent()

        if isinstance(event, OHEvent):
            return event  # pragma: no cover
        if not event.valid_message:
            self.log_and_count(COUNTER_CRC, event=event)
        elif not event.sia_account:
            self.log_and_count(COUNTER_ACCOUNT, event=event)
        elif event.code_not_found:
            self.log_and_count(COUNTER_CODE, event=event)
        elif not event.valid_timestamp:
            self.log_and_count(COUNTER_TIMESTAMP, event=event)
        return event

    async def async_func_wrap(self, event: EventsType | None) -> None:
        """Wrap the user function in a try."""
        if (
            event is None
            or not (isinstance(event, SIAEvent))
            or event.response != ResponseType.ACK
        ):
            return
        self.counts.increment_valid_events()
        try:
            assert self.async_func is not None
            await self.async_func(event)  # type: ignore
        except Exception as exp:  # pylint: disable=broad-except
            self.log_and_count(COUNTER_USER_CODE, event=event, exception=exp)

    def func_wrap(self, event: EventsType | None) -> None:
        """Wrap the user function in a try."""
        if (
            event is None
            or not (isinstance(event, SIAEvent))
            or event.response != ResponseType.ACK
        ):
            return
        self.counts.increment_valid_events()
        try:
            assert self.func is not None
            self.func(event)
        except Exception as exp:  # pylint: disable=broad-except
            self.log_and_count(COUNTER_USER_CODE, event=event, exception=exp)

    def log_and_count(
        self,
        counter: str,
        line: str | None = None,
        event: SIAEvent | None = None,
        exception: Exception | None = None,
    ) -> None:
        """Log the appropriate line and increment the right counter."""
        if counter == COUNTER_ACCOUNT and exception is not None:
            _LOGGER.warning(
                "There is no account for a encrypted line, line was: %s",
                line,
            )
        if counter == COUNTER_ACCOUNT and event:
            _LOGGER.warning(
                "Unknown or non-existing account (%s) was used by the event: %s",
                event.account,
                event,
            )
        if counter == COUNTER_FORMAT and exception:
            _LOGGER.warning(
                "Last line could not be parsed succesfully. Error message: %s. Line: %s",
                exception.args[0],
                line,
            )
        if counter == COUNTER_USER_CODE and event and exception:
            _LOGGER.warning(
                "Last event: %s, gave error in user function: %s.", event, exception
            )
        if counter == COUNTER_CRC and event:
            _LOGGER.warning(
                "CRC mismatch, ignoring message. Sent CRC: %s, Calculated CRC: %s. Line was %s",
                event.msg_crc,
                event.calc_crc,
                event.full_message,
            )
        if counter == COUNTER_CODE and event:
            _LOGGER.warning(
                "Code not found, replying with DUH to account: %s", event.account
            )
        if counter == COUNTER_TIMESTAMP and event:
            _LOGGER.warning("Event timestamp is no longer valid: %s", event.timestamp)
        if counter == COUNTER_EVENTS and line:
            _LOGGER.debug("Incoming line: %s", line)
        self.counts.increment(counter)
