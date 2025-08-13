import sys

if sys.version_info[:2] >= (3, 8):
    # TODO: Import directly (no need for conditional) when `python_requires = >= 3.8`
    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
else:
    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

__author__ = "E.A. van Valkenburg"
__copyright__ = "E.A. van Valkenburg"
__license__ = "mit"

from .account import SIAAccount
from .sync.client import SIAClient
from .errors import (
    InvalidAccountFormatError,
    InvalidAccountLengthError,
    InvalidKeyFormatError,
    InvalidKeyLengthError,
)
from .event import SIAEvent, OHEvent
from .utils import CommunicationsProtocol

# Default logging: abilita DEBUG su tutto il namespace 'pysiaalarm'
# e aggiunge un semplice StreamHandler, a meno che non sia disabilitato
# tramite variabile d'ambiente PYSIA_DISABLE_DEFAULT_LOGGING=1.
# Questo aiuta in ambienti come Home Assistant a vedere i log
# senza configurazioni aggiuntive, pur evitando duplicazioni se
# l'applicazione configura già i logger.
import logging
import os

_pkg_logger = logging.getLogger(__name__.split(".")[0])  # 'pysiaalarm'
if os.environ.get("PYSIA_DISABLE_DEFAULT_LOGGING") != "1":
    if not _pkg_logger.handlers:
        _pkg_logger.setLevel(logging.DEBUG)
        _handler = logging.StreamHandler()
        _handler.setLevel(logging.DEBUG)
        _handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        _pkg_logger.addHandler(_handler)
        # Evita propagazione al root per non duplicare output se
        # l'applicazione aggiunge i propri handler.
        _pkg_logger.propagate = False
