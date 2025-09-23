"""Libreria SIA integrata per Home Assistant."""
from __future__ import annotations

import logging

from .account import SIAAccount
from .errors import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
)
from .event import SIAEvent, OHEvent
from .utils import CommunicationsProtocol

__version__ = "1.0.0"
__author__ = "E.A. van Valkenburg"
__license__ = "mit"

# Configura il logging per il modulo SIA
_LOGGER = logging.getLogger(__name__)

__all__ = [
    "SIAAccount",
    "SIAEvent", 
    "OHEvent",
    "CommunicationsProtocol",
    "InvalidAccountFormatError",
    "InvalidAccountLengthError", 
    "InvalidKeyFormatError",
    "InvalidKeyLengthError",
]