#!/usr/bin/env python3
"""
Etatherm ETH1eD + WE3 — MCP Server

Zpřístupňuje funkce etatherm regulátoru jako MCP tools:
  - list_heaters: seznam konfigurovaných topení
  - get_status: stav jednoho nebo všech topení
  - set_temperature: nastavit operativní změnu (FOC)
  - cancel_temperature: zrušit operativní změnu (FOC)

Spuštění:
  .venv/bin/python mcp_server.py                  # reálné připojení
  ETATHERM_MOCK=1 .venv/bin/python mcp_server.py  # mock režim
"""

import sys
import os
import yaml
import logging
import threading
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import etatherm knihovny (stejná logika jako app.py)
# ---------------------------------------------------------------------------
_origin_dir = os.path.join(os.path.dirname(__file__), "origin")
_use_origin = (
    os.path.isfile(os.path.join(_origin_dir, "etatherm.py"))
    and os.environ.get("ETATHERM_MOCK") != "1"
)
if _use_origin:
    sys.path.insert(0, _origin_dir)
    log.info("Používám knihovnu z origin/")
else:
    log.info("Používám mock knihovnu")

import etatherm as etatherm_lib

_eth_class = etatherm_lib.etatherm
if hasattr(_eth_class, "etatherm"):
    _eth_class = _eth_class.etatherm

# ---------------------------------------------------------------------------
# Konfigurace
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

# ---------------------------------------------------------------------------
# Etatherm klient (serializovaný přístup přes lock)
# ---------------------------------------------------------------------------
eth_lock = threading.Lock()
eth_client = None
eth_initialized = False


def get_eth():
    global eth_client, eth_initialized
    if eth_client is None:
        cfg = CFG["etatherm"]
        eth_client = _eth_class(
            hostname=cfg["host"],
            port=cfg["port"],
            addrBusH=cfg.get("bus_high", 0x00),
            addrBusL=cfg.get("bus_low", 0x01),
        )
    if not eth_initialized:
        err = eth_client.initAddressParameters()
        if err:
            log.error("Chyba initAddressParameters — jednotka nedostupná?")
        else:
            eth_initialized = True
            log.info("Etatherm inicializován")
    return eth_client


def refresh_temperatures(eth):
    """Načte aktuální a cílové teploty + stav adres. Volající MUSÍ držet eth_lock."""
    try:
        eth.etathermSessionOpen()
        real = eth.retrieveRealTemperature()
        if real:
            eth.setAddressRealTemperature(real)
        target = eth.retrieveTargetTemperature
        if callable(target):
            target = target()
        if target:
            eth.setAddressTargetTemperature(target)
        addr = eth.retrieveAddressParameters()
        if addr:
            eth.setAddressParameters(addr)
        eth.etathermSessionClose()
    except Exception as e:
        log.error(f"Chyba refresh_temperatures: {e}")
        try:
            eth.etathermSessionClose()
        except Exception:
            pass


def get_device_status(eth, device_id: int) -> dict:
    """Vrátí stav topení z addressParameters. Volat PO refresh_temperatures."""
    ap = eth.addressParameters.get(device_id, {})
    offset = ap.get("tempOffset", 5)

    real = ap.get("realTemp")
    target_val = ap.get("targetTemp")
    current_temp = (real + offset) if real is not None else None
    target_temp = (target_val + offset) if target_val is not None else None

    foc_active = False
    foc_temp = None
    try:
        foc_active = eth.isFOCActive(device_id)
    except Exception:
        pass
    if foc_active:
        oc_temp = ap.get("opChangeTemp")
        if oc_temp is not None:
            foc_temp = oc_temp + offset

    return {
        "device_id": device_id,
        "name": ap.get("name", f"Adresa {device_id}"),
        "current_temp": current_temp,
        "target_temp": target_temp,
        "foc_active": foc_active,
        "foc_temp": foc_temp,
    }


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "Etatherm",
    instructions=(
        "MCP server pro ovládání topení Etatherm ETH1eD s WiFi modulem WE3. "
        "Umožňuje číst teploty a nastavovat operativní změnu teploty (FOC/ROZ) "
        "pro jednotlivé místnosti. Jednotka má 16 adres topení."
    ),
)


@mcp.tool()
def list_heaters() -> list[dict]:
    """Vrátí seznam konfigurovaných topení (device_id a název).

    Použij pro zjištění dostupných místností a jejich device_id,
    které pak předáš do get_status nebo set_temperature.
    """
    return [
        {"device_id": h["device_id"], "name": h["name"]}
        for h in CFG.get("heaters", [])
    ]


@mcp.tool()
def get_status(device_id: int | None = None) -> dict | list[dict]:
    """Vrátí aktuální stav topení — skutečnou teplotu, cílovou teplotu a stav operativní změny.

    Args:
        device_id: Číslo adresy topení (1–16). Pokud None, vrátí stav všech konfigurovaných topení.

    Vrací pro každé topení:
        - current_temp: skutečná teplota (°C)
        - target_temp: cílová teplota dle programu (°C)
        - foc_active: zda je aktivní operativní změna
        - foc_temp: teplota operativní změny (°C), pokud je aktivní
    """
    heaters = CFG.get("heaters", [])
    if device_id is not None:
        device_ids = [device_id]
    else:
        device_ids = [h["device_id"] for h in heaters]

    with eth_lock:
        eth = get_eth()
        refresh_temperatures(eth)
        results = [get_device_status(eth, did) for did in device_ids]

    if device_id is not None:
        return results[0]
    return results


@mcp.tool()
def set_temperature(device_id: int, temp: float, duration_hours: float | None = None) -> str:
    """Nastaví operativní změnu (FOC) teploty pro dané topení.

    Teplota se nastaví okamžitě a platí po zadanou dobu (nebo dle presetu v regulátoru).
    Po uplynutí se topení vrátí k automatickému programu.

    Args:
        device_id: Číslo adresy topení (1–16).
        temp: Požadovaná teplota v °C (rozsah dle konfigurace, typicky 6–35).
        duration_hours: Volitelná doba trvání v hodinách. Pokud nezadáno, použije se preset z regulátoru (typicky 120 min).
    """
    temp_min = CFG["defaults"]["temp_min"]
    temp_max = CFG["defaults"]["temp_max"]
    if temp < temp_min or temp > temp_max:
        return f"Chyba: teplota musí být {temp_min}–{temp_max} °C"

    with eth_lock:
        eth = get_eth()
        offset = eth.addressParameters.get(device_id, {}).get("tempOffset", 5)

        if duration_hours is not None:
            blocks = int(duration_hours * 4)  # bloky po 15 minutách
        else:
            blocks = eth.addressParameters[device_id].get("opChangePresetLength", 8)

        # 1. Zapsat ROZ preset do registru 0x10B0 (volitelné, pokud selže, pokračujeme)
        try:
            eth.etathermSessionOpen()
            err = eth.storeFOCParams(device_id, "fastchange", int(temp), blocks)
            eth.etathermSessionClose()
            if err:
                log.warning("storeFOCParams selhalo pro adresu %d, pokračuji", device_id)
            else:
                log.info("ROZ preset zapsán do 0x10B0: adresa=%d, temp=%d°C, bloky=%d", device_id, int(temp), blocks)
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
            return f"Chyba aktivace operativní změny pro zařízení {device_id}"
        time.sleep(1)
        refresh_temperatures(eth)

    duration_info = f" na {duration_hours}h" if duration_hours else ""
    return f"Operativní změna nastavena: zařízení {device_id} → {temp} °C{duration_info}"


@mcp.tool()
def cancel_temperature(device_id: int) -> str:
    """Zruší operativní změnu (FOC) a vrátí topení na automatický program.

    Args:
        device_id: Číslo adresy topení (1–16).
    """
    with eth_lock:
        eth = get_eth()
        log.info("cancel_temperature: volám deactivateFOC pro adresu %d", device_id)
        err = eth.deactivateFOC(device_id)
        log.info("cancel_temperature: deactivateFOC vrátilo %s", err)
        if err:
            return f"Chyba deaktivace operativní změny pro zařízení {device_id}"
        time.sleep(1)
        refresh_temperatures(eth)

    return f"Operativní změna zrušena pro zařízení {device_id}, topení zpět na program"


if __name__ == "__main__":
    log.info(f"Etatherm MCP server — {'origin' if _use_origin else 'mock'} knihovna")
    log.info(f"Etatherm: {CFG['etatherm']['host']}:{CFG['etatherm']['port']}")
    with eth_lock:
        try:
            get_eth()
            log.info("Eager init úspěšný")
        except Exception as e:
            log.warning(f"Init při startu selhal: {e} — zkusím znovu při prvním požadavku")
    mcp.run()
