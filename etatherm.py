"""
Mock etatherm knihovna pro lokální testování.
Při deployi na RPi: tato verze se NEPOUŽÍVÁ — app.py importuje z origin/.

Pokud origin/ neexistuje, app.py použije tuto mock verzi.
Mock simuluje chování reálné knihovny včetně addressParameters struktury.
"""

import logging
import random
import datetime

log = logging.getLogger(__name__)

# Výjimky kompatibilní s reálnou knihovnou
class etathermOpenSessionError(Exception):
    pass

class etathermSendReceiveError(Exception):
    pass


class etatherm:
    class etatherm:
        FOC_TYPE_OFF = "off"
        FOC_TYPE_HOLD = "hold"
        FOC_TYPE_OPCHANGE = "fastchange"

        DEVICE_TYPE_NOTUSED = "notused"
        DEVICE_TYPE_REGULATION = "regulation"
        DEVICE_TYPE_HEATER = "heater"

        MOCK_NAMES = {
            1: "satna", 2: "maja", 3: "anka", 4: "vasek",
            5: "tom", 6: "lozni", 7: "zluty", 8: "schod",
            9: "r oby", 10: "r zim", 11: "vstup", 12: "koup",
            13: "kuch", 14: "oby", 15: "cer.podl", 16: "z.zahr.R",
        }

        def __init__(self, hostname="localhost", port=50001, addrBusH=0x00, addrBusL=0x01):
            self.etathermHostname = hostname
            self.etathermPort = port
            self.reqAddrBusH = addrBusH
            self.reqAddrBusL = addrBusL
            self.addressParameters = {}
            self._mock = True
            log.info(f"[MOCK] Etatherm klient: {hostname}:{port}")

        def initAddressParameters(self):
            """Inicializuje addressParameters pro všech 16 adres."""
            log.info("[MOCK] initAddressParameters")
            now = datetime.datetime.now()
            past = datetime.datetime(now.year, 1, 1, 0, 0)

            for i in range(1, 17):
                offset = 5
                real_raw = random.randint(13, 20)  # 18–25 °C se zobrazí
                target_raw = 16  # 21 °C
                self.addressParameters[i] = {
                    "name": self.MOCK_NAMES.get(i, f"Adresa {i}"),
                    "deviceType": self.DEVICE_TYPE_HEATER,
                    "serviceTime": 0,
                    "controlsSwitch1": 0,
                    "controlsSwitch2": 0,
                    "devicePass": 0,
                    "tempOffset": offset,
                    "realTemp": real_raw,
                    "targetTemp": target_raw,
                    "opChangeAll": 0,
                    "opChangeTemp": 0,
                    "opChangeHoldActive": 0,
                    "opChangeEndNextYear": 0,
                    "opChangeStartNextYear": 0,
                    "opChangeStartByteHigh": 0,
                    "opChangeStartByteLow": 0,
                    "opChangeEndByteHigh": 0,
                    "opChangeEndByteLow": 0,
                    "opChangeStartTime": past.strftime("%Y-%m-%d %H:%M:%S"),
                    "opChangeEndTime": past.strftime("%Y-%m-%d %H:%M:%S"),
                    "opChangePresetType": self.FOC_TYPE_OPCHANGE,
                    "opChangePresetTemp": 17,
                    "opChangePresetLength": 96,  # 24 hodin (96*15min)
                    "opChangePresetLengthHighByte": 0,
                    "opChangePresetLengthLowByte": 96,
                    "activeHeatingMap": [1, 1, 1, 1, 1, 1, 1, 1],
                }
            return 0  # 0 = OK

        def etathermSessionOpen(self):
            log.debug("[MOCK] Session opened")

        def etathermSessionClose(self):
            log.debug("[MOCK] Session closed")

        def retrieveRealTemperature(self):
            """Vrátí raw teploty bez offsetu."""
            return {i: self.addressParameters[i]["realTemp"] for i in range(1, 17)}

        def retrieveTargetTemperature(self):
            """Vrátí raw cílové teploty bez offsetu."""
            return {i: self.addressParameters[i]["targetTemp"] for i in range(1, 17)}

        def retrieveAddressParameters(self):
            """Vrátí kopii address parametrů."""
            result = {}
            for i in range(1, 17):
                ap = self.addressParameters[i]
                result[i] = {
                    "deviceType": ap["deviceType"],
                    "serviceTime": ap["serviceTime"],
                    "controlsSwitch1": ap["controlsSwitch1"],
                    "controlsSwitch2": ap["controlsSwitch2"],
                    "devicePass": ap["devicePass"],
                    "tempOffset": ap["tempOffset"],
                    "opChangeAll": ap["opChangeAll"],
                    "opChangeTemp": ap["opChangeTemp"],
                    "opChangeHoldActive": ap["opChangeHoldActive"],
                    "opChangeEndNextYear": ap["opChangeEndNextYear"],
                    "opChangeStartNextYear": ap["opChangeStartNextYear"],
                    "opChangeStartByteHigh": ap["opChangeStartByteHigh"],
                    "opChangeStartByteLow": ap["opChangeStartByteLow"],
                    "opChangeEndByteHigh": ap["opChangeEndByteHigh"],
                    "opChangeEndByteLow": ap["opChangeEndByteLow"],
                    "activeHeatingMap": ap["activeHeatingMap"],
                }
            return result

        def setAddressRealTemperature(self, realTemp):
            if realTemp:
                for j in range(1, 17):
                    if j in realTemp:
                        self.addressParameters[j]["realTemp"] = realTemp[j]
                return 0
            return 1

        def setAddressTargetTemperature(self, targetTemp):
            if targetTemp:
                for j in range(1, 17):
                    if j in targetTemp:
                        self.addressParameters[j]["targetTemp"] = targetTemp[j]
                return 0
            return 1

        def setAddressParameters(self, addr):
            if addr:
                for j in range(1, 17):
                    if j in addr:
                        # Simulace: převést start/end bytes na časy
                        now = datetime.datetime.now()
                        past = datetime.datetime(now.year, 1, 1, 0, 0)
                        self.addressParameters[j].update({
                            "opChangeTemp": addr[j].get("opChangeTemp", 0),
                            "opChangeHoldActive": addr[j].get("opChangeHoldActive", 0),
                            "opChangeEndNextYear": addr[j].get("opChangeEndNextYear", 0),
                            "opChangeStartNextYear": addr[j].get("opChangeStartNextYear", 0),
                        })
                return 0
            return 1

        def retrieveFOCParameters(self):
            """Vrátí raw FOC data (4 byty na adresu)."""
            result = {}
            for i in range(1, 17):
                result[i] = [0, 0, 0, 0]
            return result

        def retrieveAddressNames(self):
            return {i: self.addressParameters[i]["name"] for i in range(1, 17)}

        def isFOCActive(self, deviceID):
            """Kontroluje, zda je OZ aktivní na základě časů."""
            ap = self.addressParameters.get(deviceID, {})
            now = datetime.datetime.now()
            try:
                start = datetime.datetime.strptime(ap["opChangeStartTime"], "%Y-%m-%d %H:%M:%S")
                end = datetime.datetime.strptime(ap["opChangeEndTime"], "%Y-%m-%d %H:%M:%S")
                if (now >= start and now <= end) or ap.get("opChangeHoldActive") == 1:
                    return True
            except (KeyError, ValueError):
                pass
            return False

        def setFOCTemperature(self, deviceID, temperature):
            """Nastaví teplotu OZ v paměti (bez socketu)."""
            log.info(f"[MOCK] setFOCTemperature: device={deviceID}, temp={temperature}")
            offset = self.addressParameters[deviceID]["tempOffset"]
            self.addressParameters[deviceID]["opChangeTemp"] = int(temperature) - offset
            return 1

        def storeFOCTemperature(self, deviceID):
            """Uloží teplotu OZ do jednotky (mock: nic nedělá)."""
            log.info(f"[MOCK] storeFOCTemperature: device={deviceID}")
            return 0  # 0 = OK

        def activateFOC(self, deviceID):
            """Aktivuje OZ — nastaví start/end časy."""
            log.info(f"[MOCK] activateFOC: device={deviceID}")
            length = self.addressParameters[deviceID]["opChangePresetLength"] * 15
            start = datetime.datetime.now()
            end = start + datetime.timedelta(minutes=length)
            self.addressParameters[deviceID]["opChangeStartTime"] = start.strftime("%Y-%m-%d %H:%M:%S")
            self.addressParameters[deviceID]["opChangeEndTime"] = end.strftime("%Y-%m-%d %H:%M:%S")
            return 0  # 0 = OK

        def deactivateFOC(self, deviceID):
            """Deaktivuje OZ — nastaví časy do minulosti."""
            log.info(f"[MOCK] deactivateFOC: device={deviceID}")
            past = datetime.datetime(datetime.date.today().year, 1, 1, 0, 0)
            self.addressParameters[deviceID]["opChangeStartTime"] = past.strftime("%Y-%m-%d %H:%M:%S")
            self.addressParameters[deviceID]["opChangeEndTime"] = past.strftime("%Y-%m-%d %H:%M:%S")
            self.addressParameters[deviceID]["opChangeHoldActive"] = 0
            return 0  # 0 = OK

        def enqueueCmd(self, cmd):
            """Mock: ignoruje příkazy ve frontě."""
            pass
