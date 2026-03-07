"""Unit testy pro EtathermClient."""

import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

from etatherm_client.client import EtathermClient, RoomState, DEFAULT_ROZ_TEMP, DEFAULT_ROZ_HOURS
from etatherm_client.tests.mock_etatherm import MockEtatherm


def _make_client(**kwargs) -> tuple[EtathermClient, MockEtatherm]:
    """Vytvoří klienta s mock protokolem."""
    mock = MockEtatherm()
    client = EtathermClient("127.0.0.1", **kwargs)
    # Injektovat mock místo reálné origin knihovny
    client._proto._eth = mock
    return client, mock


class TestConnect(unittest.TestCase):

    def test_connect_success(self):
        client, mock = _make_client()
        self.assertTrue(client.connect())
        self.assertTrue(client.connected)

    def test_connect_failure(self):
        client, mock = _make_client()
        mock.initAddressParameters = lambda: 1  # simuluj chybu
        self.assertFalse(client.connect())
        self.assertFalse(client.connected)


class TestGetRooms(unittest.TestCase):

    def test_get_all_rooms_returns_16(self):
        client, mock = _make_client()
        rooms = client.get_all_rooms()
        self.assertEqual(len(rooms), 16)

    def test_get_all_rooms_excludes_ids(self):
        client, mock = _make_client(exclude_ids={15, 16})
        rooms = client.get_all_rooms()
        self.assertEqual(len(rooms), 14)
        self.assertNotIn(15, rooms)
        self.assertNotIn(16, rooms)

    def test_room_state_temperatures(self):
        client, mock = _make_client()
        rooms = client.get_all_rooms()
        room1 = rooms[1]
        # realTemp=16, offset=5 → 21°C
        self.assertEqual(room1.real_temp, 21)
        # targetTemp=13, offset=5 → 18°C
        self.assertEqual(room1.target_temp, 18)

    def test_room_state_no_roz(self):
        client, mock = _make_client()
        rooms = client.get_all_rooms()
        room1 = rooms[1]
        self.assertFalse(room1.roz_active)
        self.assertIsNone(room1.roz_temp)
        self.assertIsNone(room1.roz_end)

    def test_custom_room_names(self):
        names = {1: "Šatna", 4: "Vašek"}
        client, mock = _make_client(room_names=names)
        rooms = client.get_all_rooms()
        self.assertEqual(rooms[1].name, "Šatna")
        self.assertEqual(rooms[4].name, "Vašek")
        # Bez custom názvu → z mocku
        self.assertEqual(rooms[2].name, "Room 2")

    def test_get_single_room(self):
        client, mock = _make_client()
        room = client.get_room(4)
        self.assertIsNotNone(room)
        self.assertEqual(room.device_id, 4)


class TestROZ(unittest.TestCase):

    def test_set_roz_activates(self):
        client, mock = _make_client()
        client.connect()
        ok = client.set_roz(4, temp=22.0, duration_hours=48)
        self.assertTrue(ok)
        # Ověřit stav
        room = client.get_room(4)
        self.assertTrue(room.roz_active)
        self.assertEqual(room.roz_temp, 22)

    def test_set_roz_default_values(self):
        client, mock = _make_client()
        client.connect()
        ok = client.set_roz(4)
        self.assertTrue(ok)
        room = client.get_room(4)
        self.assertTrue(room.roz_active)
        self.assertEqual(room.roz_temp, DEFAULT_ROZ_TEMP)

    def test_set_roz_duration(self):
        client, mock = _make_client()
        client.connect()
        client.set_roz(4, temp=22.0, duration_hours=24)
        room = client.get_room(4)
        self.assertTrue(room.roz_active)
        # roz_end by měl být ~24h od teď
        self.assertIsNotNone(room.roz_end)
        expected_end = datetime.now() + timedelta(hours=24)
        diff = abs((room.roz_end - expected_end).total_seconds())
        self.assertLess(diff, 120)  # tolerance 2 minuty

    def test_cancel_roz(self):
        client, mock = _make_client()
        client.connect()
        client.set_roz(4, temp=22.0, duration_hours=48)
        # Ověřit aktivní
        room = client.get_room(4)
        self.assertTrue(room.roz_active)
        # Zrušit
        ok = client.cancel_roz(4)
        self.assertTrue(ok)
        room = client.get_room(4)
        self.assertFalse(room.roz_active)

    def test_set_roz_stores_temperature(self):
        client, mock = _make_client()
        client.connect()
        client.set_roz(4, temp=25.0, duration_hours=12)
        # opChangeTemp = 25 - 5(offset) = 20
        self.assertEqual(mock.addressParameters[4]["opChangeTemp"], 20)

    def test_set_roz_stores_duration(self):
        client, mock = _make_client()
        client.connect()
        client.set_roz(4, temp=22.0, duration_hours=6)
        # 6h = 24 bloků po 15min
        self.assertEqual(mock.addressParameters[4]["opChangePresetLength"], 24)


class TestEdgeCases(unittest.TestCase):

    def test_get_rooms_without_connect(self):
        """get_all_rooms auto-connects."""
        client, mock = _make_client()
        rooms = client.get_all_rooms()
        self.assertEqual(len(rooms), 16)
        self.assertTrue(client.connected)

    def test_set_roz_without_connect(self):
        """set_roz auto-connects."""
        client, mock = _make_client()
        ok = client.set_roz(4, temp=22.0)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
