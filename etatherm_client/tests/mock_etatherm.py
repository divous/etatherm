"""
Mock Etatherm knihovna pro testování bez HW.

Simuluje chování origin/etatherm.py včetně addressParameters,
session managementu a FOC operací.
"""

import datetime


class MockEtatherm:
    """Mock origin etatherm knihovny pro unit testy."""

    def __init__(self, hostname="127.0.0.1", port=50001,
                 addrBusH=0x00, addrBusL=0x01):
        self.etathermHostname = hostname
        self.etathermPort = port
        self.addressParameters = {}
        self._session_open = False
        self._init_called = False

        # Předvyplnit 16 adres s defaultními hodnotami
        for i in range(1, 17):
            self.addressParameters[i] = {
                "name": f"Room {i}",
                "deviceName": f"Room {i}",
                "tempOffset": 5,
                "realTemp": 15 + i,  # 16-31 bez offsetu → 21-36 s offsetem
                "targetTemp": 13,    # 13 + 5 = 18°C
                "opChangeTemp": 0,
                "opChangeAll": 0,
                "opChangeHoldActive": 0,
                "opChangeEndNextYear": 0,
                "opChangeStartNextYear": 0,
                "opChangeStartByteHigh": 0,
                "opChangeStartByteLow": 0,
                "opChangeEndByteHigh": 0,
                "opChangeEndByteLow": 0,
                "opChangeStartTime": "2025-01-01 00:00:00",
                "opChangeEndTime": "2025-01-01 00:00:00",
                "opChangePresetTemp": 15,   # 15 + 5 = 20°C
                "opChangePresetType": "fastchange",
                "opChangePresetLength": 1536,  # 16 dnů v 15min blocích
                "deviceType": 0,
                "serviceTime": 0,
                "controlsSwitch1": 0,
                "controlsSwitch2": 0,
                "devicePass": 0,
            }

    def initAddressParameters(self):
        self._init_called = True
        return 0  # success

    def etathermSessionOpen(self):
        self._session_open = True
        return 0

    def etathermSessionClose(self):
        self._session_open = False

    def retrieveRealTemperature(self):
        return {i: self.addressParameters[i]["realTemp"] for i in range(1, 17)}

    def setAddressRealTemperature(self, real_temp):
        if real_temp:
            for j in range(1, 17):
                if j in real_temp:
                    self.addressParameters[j]["realTemp"] = real_temp[j]

    def retrieveAddressParameters(self):
        return {i: dict(self.addressParameters[i]) for i in range(1, 17)}

    def setAddressParameters(self, addr):
        if addr:
            for j in range(1, 17):
                if j in addr:
                    self.addressParameters[j].update(addr[j])

    def setFOCTemperature(self, deviceID, temperature):
        offset = self.addressParameters[deviceID]["tempOffset"]
        self.addressParameters[deviceID]["opChangeTemp"] = int(temperature) - offset

    def activateFOC(self, deviceID):
        length = self.addressParameters[deviceID]["opChangePresetLength"] * 15
        start = datetime.datetime.now()
        end = start + datetime.timedelta(minutes=length)
        self.addressParameters[deviceID]["opChangeStartTime"] = start.strftime("%Y-%m-%d %H:%M:%S")
        self.addressParameters[deviceID]["opChangeEndTime"] = end.strftime("%Y-%m-%d %H:%M:%S")
        return 0  # success

    def deactivateFOC(self, deviceID):
        year = datetime.date.today().year
        past = f"{year}-01-01 00:00:00"
        self.addressParameters[deviceID]["opChangeStartTime"] = past
        self.addressParameters[deviceID]["opChangeEndTime"] = past
        return 0  # success

    def isFOCActive(self, deviceID):
        end_str = self.addressParameters[deviceID].get("opChangeEndTime", "")
        if not end_str:
            return False
        try:
            end = datetime.datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
            return end > datetime.datetime.now()
        except (ValueError, TypeError):
            return False
