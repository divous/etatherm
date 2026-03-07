"""
Low-level wrapper kolem origin/etatherm.py.

Řeší:
- Import a patching origin knihovny (logging, bugy)
- Session management a serializaci přístupu (Lock)
- Workaroundy pro známé bugy v origin knihovně
"""

import logging
import os
import sys
import threading
from pathlib import Path

log = logging.getLogger(__name__)

# Patch logging.basicConfig PŘED importem origin knihovny.
# Origin volá logging.basicConfig(filename='/var/log/etatherm.log') v __init__,
# což na macOS/neprivilegovaném systému selže s PermissionError.
_orig_basicConfig = logging.basicConfig
_log_file = os.environ.get("ETATHERM_LOG_FILE", "/tmp/etatherm.log")


def _patched_basicConfig(**kwargs):
    if kwargs.get("filename") == "/var/log/etatherm.log":
        kwargs["filename"] = _log_file
    _orig_basicConfig(**kwargs)


logging.basicConfig = _patched_basicConfig

# Import origin knihovny
_origin_dir = str(Path(__file__).parent.parent / "origin")
if _origin_dir not in sys.path:
    sys.path.insert(0, _origin_dir)

import etatherm as _etatherm_lib  # noqa: E402

# NEREVRTOVAT patch — origin volá logging.basicConfig v __init__,
# tedy při každém vytvoření instance. Patch musí zůstat aktivní.

# Detekce třídy (origin má etatherm.etatherm, mock má etatherm.etatherm.etatherm)
_eth_class = _etatherm_lib.etatherm
if hasattr(_eth_class, "etatherm"):
    _eth_class = _eth_class.etatherm


class EtathermProtocol:
    """Thread-safe wrapper kolem origin etatherm knihovny.

    Řeší session management, serializaci přístupu a workaroundy bugů.
    """

    def __init__(self, host: str, port: int = 50001,
                 bus_high: int = 0x00, bus_low: int = 0x01):
        self._host = host
        self._port = port
        self._bus_high = bus_high
        self._bus_low = bus_low
        self._lock = threading.Lock()
        self._eth = None
        self._initialized = False

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def eth(self):
        """Vrátí origin etatherm instanci. Lazy init."""
        if self._eth is None:
            self._eth = _eth_class(
                hostname=self._host,
                port=self._port,
                addrBusH=self._bus_high,
                addrBusL=self._bus_low,
            )
        return self._eth

    def initialize(self) -> bool:
        """Inicializuje addressParameters z jednotky.

        Volat jednou po vytvoření. Řídí session sám (initAddressParameters).
        Volající MUSÍ držet self.lock.

        Returns: True pokud úspěch.
        """
        err = self.eth.initAddressParameters()
        if err:
            log.error("initAddressParameters selhalo — jednotka nedostupná?")
            self._initialized = False
            return False
        self._initialized = True
        log.info("Etatherm inicializován (%s:%d)", self._host, self._port)
        return True

    @property
    def initialized(self) -> bool:
        return self._initialized

    def refresh(self) -> bool:
        """Načte aktuální teploty a stav adres z jednotky.

        Volající MUSÍ držet self.lock.

        Returns: True pokud úspěch.
        """
        try:
            eth = self.eth
            eth.etathermSessionOpen()
            real = eth.retrieveRealTemperature()
            if real:
                eth.setAddressRealTemperature(real)
            # BUG workaround: po initAddressParameters je retrieveTargetTemperature
            # přepsán dictem (origin řádek 1604). targetTemp se načte přes
            # retrieveAddressParameters → setAddressParameters.
            addr = eth.retrieveAddressParameters()
            if addr:
                eth.setAddressParameters(addr)
            eth.etathermSessionClose()
            return True
        except Exception as e:
            log.error("Chyba refresh: %s", e)
            try:
                eth.etathermSessionClose()
            except Exception:
                pass
            return False

    def get_address_params(self, device_id: int) -> dict:
        """Vrátí addressParameters pro danou adresu.

        Volající MUSÍ držet self.lock a předtím zavolat refresh().
        """
        return self.eth.addressParameters.get(device_id, {})

    def activate_roz(self, device_id: int, temp: float, duration_hours: float) -> bool:
        """Aktivuje ROZ (operativní změnu) pro danou adresu.

        Volající MUSÍ držet self.lock.

        Args:
            device_id: ID adresy (1-16)
            temp: Cílová teplota v °C (s offsetem, tj. reálná teplota)
            duration_hours: Doba trvání v hodinách

        Returns: True pokud úspěch.
        """
        eth = self.eth
        # 1. Nastavit teplotu v paměti (opChangeTemp)
        eth.setFOCTemperature(device_id, temp)
        # 2. Nastavit délku v paměti — activateFOC čte opChangePresetLength
        #    (v 15min blocích). Uložíme vlastní hodnotu.
        blocks_15min = int(duration_hours * 4)  # 1h = 4 bloky po 15min
        eth.addressParameters[device_id]["opChangePresetLength"] = blocks_15min
        # 3. Aktivovat — přečte opChangeTemp + opChangePresetLength,
        #    spočítá start/end časy, zapíše do OZ registru. Řídí session sám.
        err = eth.activateFOC(device_id)
        if err:
            log.error("activateFOC selhalo pro adresu %d", device_id)
            return False
        log.info("ROZ aktivována: adresa %d → %.1f°C na %.1fh", device_id, temp, duration_hours)
        return True

    def cancel_roz(self, device_id: int) -> bool:
        """Zruší ROZ (operativní změnu) pro danou adresu.

        Volající MUSÍ držet self.lock.

        Returns: True pokud úspěch.
        """
        err = self.eth.deactivateFOC(device_id)
        if err:
            log.error("deactivateFOC selhalo pro adresu %d", device_id)
            return False
        log.info("ROZ zrušena: adresa %d", device_id)
        return True
