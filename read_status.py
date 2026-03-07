#!/usr/bin/env python3
"""
Etatherm ETH1eD — čtení stavu jednotky
Spusťte ve stejném adresáři jako etatherm.py (pravá knihovna, ne mock).

Použití:
  python3 read_status.py
  python3 read_status.py --host 192.168.68.75 --port 50001
"""

import argparse
import sys
import os

# Přidat origin/ do cesty pro import knihovny
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "origin"))

import etatherm as etatherm_lib


def main():
    parser = argparse.ArgumentParser(description="Čtení stavu Etatherm ETH1eD")
    parser.add_argument("--host", default="192.168.68.75", help="IP adresa WE3")
    parser.add_argument("--port", type=int, default=50001, help="TCP port (výchozí: 50001)")
    args = parser.parse_args()

    print(f"Připojuji se k {args.host}:{args.port}...")

    try:
        eth = etatherm_lib.etatherm.etatherm(
            hostname=args.host,
            port=args.port,
            addrBusH=0x00,
            addrBusL=0x01,
        )
    except Exception as e:
        print(f"Chyba vytváření klienta: {e}")
        sys.exit(1)

    # Načtení parametrů
    print("Načítám parametry adres...")
    try:
        eth.etathermSessionOpen()
        err = eth.initAddressParameters()
        if err:
            print(f"Chyba initAddressParameters: {err}")
            sys.exit(1)
    except Exception as e:
        print(f"Chyba připojení: {e}")
        print("Zkontrolujte, zda je WE3 dostupné a port správný.")
        sys.exit(1)

    # Názvy místností
    print("Načítám názvy adres...")
    try:
        eth.etathermSessionOpen()
        names = eth.retrieveAddressNames()
        eth.etathermSessionClose()
    except Exception as e:
        names = {}
        print(f"Varování: nelze načíst názvy ({e})")

    # Aktuální teploty
    print("Načítám aktuální teploty...")
    try:
        eth.etathermSessionOpen()
        real_temps = eth.retrieveRealTemperature()
        eth.etathermSessionClose()
    except Exception as e:
        real_temps = {}
        print(f"Varování: nelze načíst aktuální teploty ({e})")

    # Cílové teploty
    print("Načítám cílové teploty...")
    try:
        eth.etathermSessionOpen()
        target_temps = eth.retrieveTargetTemperature()
        eth.etathermSessionClose()
    except Exception as e:
        target_temps = {}
        print(f"Varování: nelze načíst cílové teploty ({e})")

    # FOC parametry
    print("Načítám stav operativních změn...")
    try:
        eth.etathermSessionOpen()
        foc = eth.retrieveFOCParameters()
        eth.etathermSessionClose()
    except Exception as e:
        foc = {}
        print(f"Varování: nelze načíst FOC ({e})")

    # Výpis tabulky
    print()
    print("=" * 75)
    print(f"  ETATHERM ETH1eD — {args.host}:{args.port}")
    print("=" * 75)
    print(f"{'ID':>3}  {'Název':<16}  {'Aktuální':>8}  {'Cílová':>8}  {'OZ':>12}")
    print("-" * 75)

    for i in range(1, 17):
        name = names.get(i, "—")
        if not name or name.strip() == "":
            continue  # přeskočit prázdné adresy

        real_t = real_temps.get(i)
        target_t = target_temps.get(i)
        real_str = f"{real_t} °C" if real_t is not None else "—"
        target_str = f"{target_t} °C" if target_t is not None else "—"

        # FOC stav
        foc_str = "—"
        if i in foc:
            foc_info = foc[i]
            if isinstance(foc_info, dict) and foc_info.get("active"):
                foc_temp = foc_info.get("temperature", "?")
                foc_str = f"aktivní {foc_temp}°C"
            elif isinstance(foc_info, dict):
                foc_str = "neaktivní"

        print(f"{i:>3}  {name:<16}  {real_str:>8}  {target_str:>8}  {foc_str:>12}")

    print("-" * 75)
    print()

    # Výpis jako JSON pro strojové zpracování
    print("--- RAW DATA (JSON) ---")
    import json
    data = {
        "names": {str(k): v for k, v in names.items()},
        "real_temps": {str(k): v for k, v in real_temps.items()},
        "target_temps": {str(k): v for k, v in target_temps.items()},
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
