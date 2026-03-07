#!/usr/bin/env python3
"""
Etatherm WE3 — MODBUS register scanner
Prochází rozsah holding registrů a vypisuje nenulové hodnoty.
Pomůže najít správné adresy registrů pro vaši konfiguraci.

Použití:
  python3 scan_registers.py --host 192.168.1.100 --port 50001
  python3 scan_registers.py --host 192.168.1.100 --port 50001 --start 0 --end 500
"""

import argparse
import sys
import time

from pymodbus.client import ModbusTcpClient


def scan(host, port, unit_id, start, end, pause):
    client = ModbusTcpClient(host=host, port=port, timeout=3)
    if not client.connect():
        print(f"CHYBA: Nelze se připojit k {host}:{port}")
        sys.exit(1)

    print(f"Připojeno k {host}:{port} (unit_id={unit_id})")
    print(f"Skenuji holding registry {start}–{end}...\n")
    print(f"{'Adresa':>8}  {'Hodnota':>8}  {'Hex':>8}  Poznámka")
    print("-" * 50)

    found = 0
    for addr in range(start, end + 1):
        try:
            result = client.read_holding_registers(addr, count=1, slave=unit_id)
            if result.isError():
                continue
            val = result.registers[0]
            if val != 0:
                note = ""
                # Heuristiky pro identifikaci teplotních registrů
                if 60 <= val <= 350:
                    note = f"  ← možná teplota: {val/10:.1f} °C"
                elif val == 1:
                    note = "  ← možná bool (zapnuto)"
                elif 1 <= val <= 1440:
                    note += f"  (pokud minuty: {val/60:.1f} h)"
                print(f"{addr:>8}  {val:>8}  {val:>#8x}  {note}")
                found += 1
        except Exception as e:
            pass

        if pause > 0:
            time.sleep(pause)

    print(f"\nNalezeno {found} nenulových registrů.")
    client.close()


def main():
    parser = argparse.ArgumentParser(description="Etatherm WE3 MODBUS register scanner")
    parser.add_argument("--host", required=True, help="IP adresa WE3")
    parser.add_argument("--port", type=int, default=50001, help="MODBUS TCP port (výchozí: 50001)")
    parser.add_argument("--unit-id", type=int, default=1, help="MODBUS unit ID (výchozí: 1)")
    parser.add_argument("--start", type=int, default=0, help="Počáteční adresa (výchozí: 0)")
    parser.add_argument("--end", type=int, default=999, help="Koncová adresa (výchozí: 999)")
    parser.add_argument("--pause", type=float, default=0.05, help="Pauza mezi čteními v sekundách (výchozí: 0.05)")
    args = parser.parse_args()
    scan(args.host, args.port, args.unit_id, args.start, args.end, args.pause)


if __name__ == "__main__":
    main()
