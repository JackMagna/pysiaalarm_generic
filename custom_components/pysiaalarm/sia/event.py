"""This is a class for SIA Events."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Union, Any

from .account import SIAAccount
from .utils.enums import MessageTypes, ResponseType

_LOGGER = logging.getLogger(__name__)


@dataclass
class BaseEvent(ABC):
    """Base class for Events."""

    # From Main Matcher
    full_message: str | None = None
    msg_crc: str | None = None
    length: str | None = None
    encrypted: bool | None = None
    message_type: str | MessageTypes | None = None
    receiver: str = "R0"
    line: str = "L0"
    account: str | None = None
    sequence: str | None = None

    # Content to be parsed
    content: str | None = None
    encrypted_content: str | None = None

    # From (Encrypted) Content
    ti: str | None = None
    id: str | None = None
    ri: str | None = None
    code: str | None = None
    message: str | None = None
    x_data: str | None = None
    timestamp: datetime | str | None = None

    # From ADM-CID
    event_qualifier: str | None = None
    event_type: str | None = None
    partition: str | None = None

    # Parsed fields
    calc_crc: str | None = None
    sia_account: SIAAccount | None = field(repr=False, default=None)

    @property
    def valid_message(self) -> bool:
        """Return True for valid messages."""
        return True

    @property
    def code_not_found(self) -> bool:
        """Return True if there is no Code."""
        return self.code is None

    @property
    @abstractmethod
    def response(self) -> ResponseType | None:
        """Abstract method."""

    @property
    def valid_timestamp(self) -> bool:
        """Check if the timestamp is within bounds with extended tolerance."""
        # PATCH: Tolleranza di 5 minuti per eventi SIA con timestamp skew
        if not self.sia_account:
            return True
        if self.sia_account.allowed_timeband is None:
            return True
        if self.timestamp and isinstance(self.timestamp, datetime):
            # Assicuriamoci che entrambi i datetime abbiano lo stesso timezone
            if self.timestamp.tzinfo is None:
                # Se il timestamp dell'evento non ha timezone, assumiamo UTC
                event_time = self.timestamp.replace(tzinfo=timezone.utc)
            else:
                event_time = self.timestamp
                
            current_time = datetime.now(self.sia_account.device_timezone)
            
            # TOLLERANZA ESTESA: 5 minuti (300 secondi) invece dei valori originali
            tolerance_seconds = 300  # 5 minuti di tolleranza
            current_min = current_time - timedelta(seconds=tolerance_seconds)
            current_plus = current_time + timedelta(seconds=tolerance_seconds)
            
            is_valid = current_min <= event_time <= current_plus
            
            # Log per debug quando timestamp non è valido anche con tolleranza estesa
            if not is_valid:
                _LOGGER.debug(
                    "Timestamp fuori tolleranza 5min: evento=%s, corrente=%s, diff=%s",
                    event_time, current_time, abs((event_time - current_time).total_seconds())
                )
            
            return is_valid
        return True

    @abstractmethod
    def create_response(self) -> bytes:
        """Create a response message."""


@dataclass
class SIAEvent(BaseEvent):
    """Class for SIA Events."""

    @property
    def response(self) -> ResponseType:
        """Return response type for SIA events."""
        if self.valid_message:
            return ResponseType.ACK
        return ResponseType.NAK

    def create_response(self) -> bytes:
        """Create a response for SIA events."""
        # Simplified response creation
        response_text = f'"ACK"R{self.receiver}L{self.line}#{self.account}'
        return response_text.encode('utf-8')


@dataclass  
class OHEvent(BaseEvent):
    """Class for OH Events - keep alive messages."""

    @property
    def response(self) -> ResponseType:
        """Return response type for OH events.""" 
        return ResponseType.DUH

    def create_response(self) -> bytes:
        """Create a response for OH events."""
        # Simplified OH response
        return b'"DUH"'


# Export main classes
__all__ = ["SIAEvent", "OHEvent", "BaseEvent"]