"""
High-level klient pro Etatherm ETH1eD.

Poskytuje čistý API pro čtení teplot a ovládání ROZ.
Veškerá komunikace s HW je delegována na EtathermProtocol.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from etatherm_client.protocol import EtathermProtocol

log = logging.getLogger(__name__)

DEFAULT_ROZ_TEMP = 21.0
DEFAULT_ROZ_HOURS = 48.0


@dataclass
class RoomState:
    """Stav jedné místnosti."""
    device_id: int
    name: str
    real_temp: Optional[float]       # skutečná teplota °C
    target_temp: Optional[float]     # cílová teplota z programu °C
    roz_active: bool                 # je ROZ/OZ aktivní?
    roz_temp: Optional[float]        # ROZ cílová teplota °C
    roz_end: Optional[datetime]      # kdy ROZ končí


class EtathermClient:
    """High-level klient pro Etatherm ETH1eD.

    Thread-safe. Serializuje přístup k jednotce přes interní Lock.

    Použití:
        client = EtathermClient("192.168.68.75")
        if client.connect():
            rooms = client.get_all_rooms()
            for room in rooms.values():
                print(f"{room.name}: {room.real_temp}°C")
            client.set_roz(4, 22.0, 48)  # Vašek, 22°C, 2 dny
    """

    def __init__(self, host: str, port: int = 50001,
                 bus_high: int = 0x00, bus_low: int = 0x01,
                 room_names: Optional[dict[int, str]] = None,
                 exclude_ids: Optional[set[int]] = None):
        """
        Args:
            host: IP adresa WE3 modulu
            port: TCP port (default 50001)
            bus_high, bus_low: Adresa sběrnice
            room_names: Volitelné mapování device_id → název místnosti.
                        Pokud None, použijí se názvy z jednotky.
            exclude_ids: ID adres k přeskočení (např. {15} pro kotel)
        """
        self._proto = EtathermProtocol(host, port, bus_high, bus_low)
        self._room_names = room_names or {}
        self._exclude_ids = exclude_ids or set()

    @property
    def connected(self) -> bool:
        return self._proto.initialized

    def connect(self) -> bool:
        """Připojí se k jednotce a načte počáteční data.

        Returns: True pokud úspěch.
        """
        with self._proto.lock:
            if not self._proto.initialized:
                if not self._proto.initialize():
                    return False
            return self._proto.refresh()

    def get_all_rooms(self) -> dict[int, RoomState]:
        """Načte aktuální stav všech místností.

        Provede refresh dat z jednotky.

        Returns: Slovník device_id → RoomState
        """
        with self._proto.lock:
            if not self._proto.initialized:
                if not self._proto.initialize():
                    return {}
            self._proto.refresh()
            rooms = {}
            for did in range(1, 17):
                if did in self._exclude_ids:
                    continue
                room = self._read_room_state(did)
                if room is not None:
                    rooms[did] = room
            return rooms

    def get_room(self, device_id: int) -> Optional[RoomState]:
        """Načte stav jedné místnosti.

        Provede refresh dat z jednotky.
        """
        with self._proto.lock:
            if not self._proto.initialized:
                if not self._proto.initialize():
                    return None
            self._proto.refresh()
            return self._read_room_state(device_id)

    def set_roz(self, device_id: int,
                temp: float = DEFAULT_ROZ_TEMP,
                duration_hours: float = DEFAULT_ROZ_HOURS) -> bool:
        """Nastaví ROZ (rychlou operativní změnu) pro místnost.

        Args:
            device_id: ID adresy (1-16)
            temp: Cílová teplota °C (default 21)
            duration_hours: Doba trvání v hodinách (default 48)

        Returns: True pokud úspěch.
        """
        with self._proto.lock:
            if not self._proto.initialized:
                if not self._proto.initialize():
                    return False
            return self._proto.activate_roz(device_id, temp, duration_hours)

    def cancel_roz(self, device_id: int) -> bool:
        """Zruší ROZ pro místnost.

        Returns: True pokud úspěch.
        """
        with self._proto.lock:
            if not self._proto.initialized:
                if not self._proto.initialize():
                    return False
            return self._proto.cancel_roz(device_id)

    def _read_room_state(self, device_id: int) -> Optional[RoomState]:
        """Přečte stav místnosti z addressParameters.

        Volající MUSÍ držet lock a předtím zavolat refresh().
        """
        ap = self._proto.get_address_params(device_id)
        if not ap:
            return None

        offset = ap.get("tempOffset", 5)
        real = ap.get("realTemp")
        target = ap.get("targetTemp")

        real_temp = (real + offset) if real is not None else None
        target_temp = (target + offset) if target is not None else None

        # ROZ stav
        eth = self._proto.eth
        roz_active = False
        roz_temp = None
        roz_end = None
        try:
            roz_active = eth.isFOCActive(device_id)
        except Exception:
            pass
        if roz_active:
            oc_temp = ap.get("opChangeTemp")
            if oc_temp is not None:
                roz_temp = oc_temp + offset
            roz_end = ap.get("opChangeEndTime")
            if isinstance(roz_end, str):
                try:
                    roz_end = datetime.strptime(roz_end, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    roz_end = None

        # Název: preferuj room_names, pak z jednotky, pak default
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
