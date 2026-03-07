#!/usr/bin/env python3
"""Jednorázový skript: načte všechna dostupná data z ETH1eD a vypíše tabulku."""

import sys
import os
import logging

# Nastavit logging PŘED importem origin knihovny (ta chce /var/log/etatherm.log)
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

# Import knihovny (stejná logika jako app.py)
_origin_dir = os.path.join(os.path.dirname(__file__), "origin")
_use_origin = os.path.isfile(os.path.join(_origin_dir, "etatherm.py")) and \
              os.environ.get("ETATHERM_MOCK") != "1"
if _use_origin:
    sys.path.insert(0, _origin_dir)

import yaml
import etatherm as etatherm_lib

_eth_class = etatherm_lib.etatherm
if hasattr(_eth_class, "etatherm"):
    _eth_class = _eth_class.etatherm

with open(os.path.join(os.path.dirname(__file__), "config.yaml"), encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

cfg = CFG["etatherm"]
eth = _eth_class(hostname=cfg["host"], port=cfg["port"],
                 addrBusH=cfg.get("bus_high", 0), addrBusL=cfg.get("bus_low", 1))

# Inicializace (řídí si session sám)
err = eth.initAddressParameters()
if err:
    print("CHYBA: initAddressParameters selhalo — jednotka nedostupná?")
    sys.exit(1)

# Načíst vše v jedné session
eth.etathermSessionOpen()

real_temps = eth.retrieveRealTemperature() or {}
eth.setAddressRealTemperature(real_temps)

addr_params = eth.retrieveAddressParameters() or {}
eth.setAddressParameters(addr_params)

addr_names = eth.retrieveAddressNames() or {}

try:
    foc_params = eth.retrieveFOCParameters() or {}
except AttributeError:
    foc_params = {}

try:
    goc_params = eth.retrieveGOCParameters() or {}
except AttributeError:
    goc_params = {}

try:
    all_programs = eth.retrieveAllActiveHeatingPrograms() or []
except AttributeError:
    all_programs = []

eth.etathermSessionClose()

# Sestavit tabulku
heaters = {h["device_id"]: h["name"] for h in CFG.get("heaters", [])}
programs_by_id = {}
for p in all_programs:
    programs_by_id[p["DeviceID"]] = p

DEVICE_TYPES = {0: "nepoužito", 1: "regulace", 2: "přímotop", 3: "spínač1", 4: "spínač2", 99: "?"}
DAYS = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne", "Sv"]
day_keys = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Holiday"]

print()
print("=" * 120)
print(f"{'ETATHERM ETH1eD — KOMPLETNÍ VÝPIS VŠECH MÍSTNOSTÍ':^120}")
print("=" * 120)

for did in range(1, 17):
    ap = eth.addressParameters.get(did, {})
    offset = ap.get("tempOffset", 5)
    real = ap.get("realTemp")
    target = ap.get("targetTemp")
    name_cfg = heaters.get(did, "—")
    name_eth = addr_names.get(did, "—")
    dev_type = ap.get("deviceType", 99)
    dev_type_str = DEVICE_TYPES.get(dev_type, f"? ({dev_type})")

    real_disp = f"{real + offset:.1f} °C" if real is not None else "—"
    target_disp = f"{target + offset:.1f} °C" if target is not None else "—"

    # FOC
    foc_active = False
    try:
        foc_active = eth.isFOCActive(did)
    except Exception:
        pass
    oc_temp = ap.get("opChangeTemp")
    foc_temp_disp = f"{oc_temp + offset:.1f} °C" if oc_temp is not None else "—"
    foc_hold = ap.get("opChangeHoldActive", 0)
    foc_end_ny = ap.get("opChangeEndNextYear", 0)
    foc_start_ny = ap.get("opChangeStartNextYear", 0)
    foc_start_h = ap.get("opChangeStartByteHigh", 0)
    foc_start_l = ap.get("opChangeStartByteLow", 0)
    foc_end_h = ap.get("opChangeEndByteHigh", 0)
    foc_end_l = ap.get("opChangeEndByteLow", 0)

    # FOC raw params
    foc_raw = foc_params.get(did, [0, 0, 0, 0])

    # GOC
    goc_val = goc_params.get(did, 0)

    # Program
    prog = programs_by_id.get(did, {})
    prog_str = "  ".join(f"{DAYS[i]}={prog.get(day_keys[i], '?')}" for i in range(8)) if prog else "—"

    # Flags
    svc = ap.get("serviceTime", 0)
    sw1 = ap.get("controlsSwitch1", 0)
    sw2 = ap.get("controlsSwitch2", 0)
    passwd = ap.get("devicePass", 0)

    print()
    print(f"─── [{did:2d}] {name_cfg} (ETH název: \"{name_eth}\") ───")
    print(f"  Typ:             {dev_type_str}")
    print(f"  Skutečná tepl.:  {real_disp}")
    print(f"  Cílová tepl.:    {target_disp}")
    print(f"  Offset:          {offset}")
    print(f"  OZ aktivní:      {'ANO' if foc_active else 'ne'}")
    print(f"  OZ teplota:      {foc_temp_disp}")
    print(f"  OZ hold:         {foc_hold}  endNextYear: {foc_end_ny}  startNextYear: {foc_start_ny}")
    print(f"  OZ start:        0x{foc_start_h:02X}{foc_start_l:02X}  end: 0x{foc_end_h:02X}{foc_end_l:02X}")
    print(f"  FOC raw:         {[hex(x) for x in foc_raw]}")
    print(f"  GOC:             {goc_val}")
    print(f"  Program:         {prog_str}")
    print(f"  ServiceTime:     {svc}  Switch1: {sw1}  Switch2: {sw2}  Pass: {passwd}")

print()
print("=" * 120)
