"""
High-level klient pro Etatherm ETH1eD — verze pro HA custom component.

Kopie etatherm_client/client.py + protocol.py sloučené do jednoho souboru
pro jednoduchou distribuci v custom_components.
"""

import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DEFAULT_ROZ_TEMP = 21.0
DEFAULT_ROZ_HOURS = 48.0

# ---------------------------------------------------------------------------
# Logging patch — origin knihovna volá logging.basicConfig(filename='/var/log/etatherm.log')
# v __init__, což na HA OS selže s PermissionError.
# ---------------------------------------------------------------------------
_orig_basicConfig = logging.basicConfig
_log_file = os.environ.get("ETATHERM_LOG_FILE", "/tmp/etatherm.log")


def _patched_basicConfig(**kwargs):
    if kwargs.get("filename") == "/var/log/etatherm.log":
        kwargs["filename"] = _log_file
    _orig_basicConfig(**kwargs)


logging.basicConfig = _patched_basicConfig

# ---------------------------------------------------------------------------
# Import origin knihovny — hledáme ji v etatherm_lib/ podadresáři
# ---------------------------------------------------------------------------
_lib_dir = str(Path(__file__).parent / "etatherm_lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

try:
    import etatherm as _etatherm_lib
    _eth_class = _etatherm_lib.etatherm
    if hasattr(_eth_class, "etatherm"):
        _eth_class = _eth_class.etatherm
    _LIB_AVAILABLE = True
except ImportError:
    _LIB_AVAILABLE = False
    _eth_class = None
    log.error("Etatherm knihovna nenalezena v %s", _lib_dir)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class RoomState:
    """Stav jedné místnosti."""
    device_id: int
    name: str
    real_temp: Optional[float]
    target_temp: Optional[float]
    roz_active: bool
    roz_temp: Optional[float]
    roz_end: Optional[datetime]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class EtathermClient:
    """Thread-safe klient pro Etatherm ETH1eD."""

    def __init__(self, host: str, port: int = 50001,
                 bus_high: int = 0x00, bus_low: int = 0x01,
                 room_names: Optional[dict[int, str]] = None,
                 exclude_ids: Optional[set[int]] = None):
        self._host = host
        self._port = port
        self._bus_high = bus_high
        self._bus_low = bus_low
        self._room_names = room_names or {}
        self._exclude_ids = exclude_ids or set()
        self._lock = threading.Lock()
        self._eth = None
        self._initialized = False

    @property
    def connected(self) -> bool:
        return self._initialized

    def _get_eth(self):
        if self._eth is None:
            if not _LIB_AVAILABLE:
                raise RuntimeError("Etatherm knihovna není dostupná")
            self._eth = _eth_class(
                hostname=self._host,
                port=self._port,
                addrBusH=self._bus_high,
                addrBusL=self._bus_low,
            )
        return self._eth

    def connect(self) -> bool:
        with self._lock:
            try:
                eth = self._get_eth()
                err = eth.initAddressParameters()
                if err:
                    log.error("initAddressParameters selhalo")
                    return False
                self._initialized = True
                log.info("Etatherm připojen (%s:%d)", self._host, self._port)
                return self._refresh_locked()
            except Exception as e:
                log.error("Chyba připojení: %s", e)
                return False

    def _refresh_locked(self) -> bool:
        """Refresh dat — volající MUSÍ držet self._lock."""
        try:
            eth = self._get_eth()
            eth.etathermSessionOpen()
            real = eth.retrieveRealTemperature()
            if real:
                eth.setAddressRealTemperature(real)
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

    def get_all_rooms(self) -> dict[int, RoomState]:
        with self._lock:
            if not self._initialized:
                try:
                    eth = self._get_eth()
                    err = eth.initAddressParameters()
                    if err:
                        return {}
                    self._initialized = True
                except Exception:
                    return {}
            self._refresh_locked()
            rooms = {}
            for did in range(1, 17):
                if did in self._exclude_ids:
                    continue
                room = self._read_room(did)
                if room is not None:
                    rooms[did] = room
            return rooms

    def get_room(self, device_id: int) -> Optional[RoomState]:
        with self._lock:
            if not self._initialized:
                return None
            self._refresh_locked()
            return self._read_room(device_id)

    def set_roz(self, device_id: int,
                temp: float = DEFAULT_ROZ_TEMP,
                duration_hours: float = DEFAULT_ROZ_HOURS) -> bool:
        """Nastaví ROZ preset (0x10B0) a aktivuje ho (0x1100)."""
        with self._lock:
            if not self._initialized:
                log.error("set_roz: klient není inicializován")
                return False
            try:
                eth = self._get_eth()
                offset = eth.addressParameters.get(device_id, {}).get("tempOffset", 5)
                blocks = int(duration_hours * 4)
                log.info("set_roz: adresa=%d, temp=%.1f°C (raw=%d), bloky=%d",
                         device_id, temp, int(temp) - offset, blocks)

                # 1. Zapsat ROZ preset do 0x10B0 (volitelné, pokud selže, pokračujeme)
                try:
                    eth.etathermSessionOpen()
                    err = eth.storeFOCParams(device_id, "fastchange", int(temp), blocks)
                    eth.etathermSessionClose()
                    if err:
                        log.warning("storeFOCParams selhalo pro adresu %d, pokračuji s activateFOC", device_id)
                    else:
                        log.info("ROZ preset zapsán do 0x10B0")
                except Exception as e:
                    log.warning("storeFOCParams výjimka: %s, pokračuji", e)
                    try:
                        eth.etathermSessionClose()
                    except Exception:
                        pass

                # 2. Nastavit teplotu v paměti a aktivovat
                eth.setFOCTemperature(device_id, temp)
                eth.addressParameters[device_id]["opChangePresetLength"] = blocks
                err = eth.activateFOC(device_id)
                if err:
                    log.error("activateFOC selhalo pro adresu %d", device_id)
                    return False
                time.sleep(1)
                log.info("ROZ aktivována: adresa %d → %.1f°C na %.0fh", device_id, temp, duration_hours)
                return True
            except Exception as e:
                log.error("Chyba set_roz pro adresu %d: %s", device_id, e, exc_info=True)
                return False

    def store_roz(self, device_id: int,
                  temp: float = DEFAULT_ROZ_TEMP,
                  duration_hours: float = DEFAULT_ROZ_HOURS) -> bool:
        """Zapíše ROZ preset do registru 0x10B0 a aktivuje ho."""
        with self._lock:
            if not self._initialized:
                log.error("store_roz: klient není inicializován")
                return False
            try:
                eth = self._get_eth()
                blocks = int(duration_hours * 4)  # 15min bloky
                foc_type = "fastchange"
                offset = eth.addressParameters.get(device_id, {}).get("tempOffset", 5)
                log.info("store_roz: adresa=%d, temp=%.1f°C (raw=%d), bloky=%d, typ=%s",
                         device_id, temp, int(temp) - offset, blocks, foc_type)
                # 1. Zapsat ROZ preset do 0x10B0
                eth.etathermSessionOpen()
                err = eth.storeFOCParams(device_id, foc_type, int(temp), blocks)
                eth.etathermSessionClose()
                if err:
                    log.error("storeFOCParams selhalo pro adresu %d", device_id)
                    return False
                # 2. Aktivovat ROZ → zapíše se do OZ registru 0x1100
                eth.setFOCTemperature(device_id, temp)
                err = eth.activateFOC(device_id)
                if err:
                    log.error("activateFOC selhalo pro adresu %d", device_id)
                    return False
                time.sleep(1)
                log.info("ROZ aktivována: adresa %d → %.1f°C na %.0fh", device_id, temp, duration_hours)
                return True
            except Exception as e:
                log.error("Chyba store_roz pro adresu %d: %s", device_id, e, exc_info=True)
                try:
                    eth.etathermSessionClose()
                except Exception:
                    pass
                return False

    def cancel_roz(self, device_id: int) -> bool:
        with self._lock:
            if not self._initialized:
                log.error("cancel_roz: klient není inicializován")
                return False
            try:
                err = self._get_eth().deactivateFOC(device_id)
                if err:
                    log.error("deactivateFOC selhalo pro adresu %d (vrátilo %s)", device_id, err)
                    return False
                time.sleep(1)
                log.info("ROZ zrušena: adresa %d", device_id)
                return True
            except Exception as e:
                log.error("Chyba cancel_roz pro adresu %d: %s", device_id, e, exc_info=True)
                return False

    def _read_room(self, device_id: int) -> Optional[RoomState]:
        eth = self._get_eth()
        ap = eth.addressParameters.get(device_id, {})
        if not ap:
            return None

        offset = ap.get("tempOffset", 5)
        real = ap.get("realTemp")
        target = ap.get("targetTemp")
        real_temp = (real + offset) if real is not None else None
        target_temp = (target + offset) if target is not None else None

        roz_active = False
        roz_temp = None
        roz_end = None
        try:
            roz_active = eth.isFOCActive(device_id)
        except Exception:
            pass
        if roz_active:
            oc = ap.get("opChangeTemp")
            if oc is not None:
                roz_temp = oc + offset
            end_str = ap.get("opChangeEndTime")
            if isinstance(end_str, str):
                try:
                    roz_end = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

        name = self._room_names.get(device_id)
        if not name:
            name = ap.get("name") or ap.get("deviceName") or f"Adresa {device_id}"

        return RoomState(
            device_id=device_id,
            name=name,
            real_temp=real_temp,
            target_temp=target_temp,
            roz_active=roz_active,
            roz_temp=roz_temp,
            roz_end=roz_end,
        )
