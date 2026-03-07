#!/usr/bin/env python3
"""
Etatherm ETH1eD + WE3 — Operativní změna teploty
Webový server pro ovládání topení přes proprietární Etatherm protokol.
Využívá knihovnu etatherm.py z https://github.com/mbisak/etatherm-ha-bridge

Session management:
  - initAddressParameters() — řídí si session sám
  - retrieveRealTemperature(), retrieveTargetTemperature(),
    retrieveAddressParameters(), retrieveAddressNames(),
    retrieveFOCParameters() — NEŘÍDÍ session, volající musí otevřít/zavřít
  - storeFOCTemperature(), activateFOC(), deactivateFOC() — řídí si session sami
  - setFOCTemperature() — pouze nastaví hodnotu v paměti (žádný socket)
"""

import sys
import os
import yaml
import logging
import threading
import time
from pathlib import Path
from flask import Flask, render_template, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Importovat knihovnu: nejprve zkusit origin/ (reálná), pak lokální mock.
# Na RPi bude origin/etatherm.py s reálnou komunikací.
# Lokální etatherm.py je mock pro testování.
# Pořadí: origin/ má přednost (sys.path.insert na začátek).
_origin_dir = os.path.join(os.path.dirname(__file__), "origin")
_use_origin = os.path.isfile(os.path.join(_origin_dir, "etatherm.py")) and \
              os.environ.get("ETATHERM_MOCK") != "1"
if _use_origin:
    sys.path.insert(0, _origin_dir)
    log.info("Používám knihovnu z origin/")
else:
    log.info("Používám mock knihovnu (ETATHERM_MOCK=1 nebo origin/ neexistuje)")

# ---------------------------------------------------------------------------
# Konfigurace
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()

# ---------------------------------------------------------------------------
# Etatherm klient
# ---------------------------------------------------------------------------
import etatherm as etatherm_lib

# Detekce zda jde o origin (single class) nebo mock (nested class)
_eth_class = etatherm_lib.etatherm
if hasattr(_eth_class, "etatherm"):
    _eth_class = _eth_class.etatherm  # mock má etatherm.etatherm.etatherm

# Lock pro serializaci přístupu k ETH1eD (má omezené CPU)
eth_lock = threading.Lock()
eth_client = None
eth_initialized = False


def get_eth():
    """Vrátí inicializovanou instanci etatherm klienta."""
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
        # initAddressParameters() řídí session sám
        err = eth_client.initAddressParameters()
        if err:
            log.error("Chyba initAddressParameters — jednotka nedostupná?")
        else:
            eth_initialized = True
            log.info("Etatherm inicializován")
    return eth_client


def refresh_temperatures(eth):
    """Načte aktuální a cílové teploty + stav adres z jednotky.
    Volající MUSÍ držet eth_lock.
    """
    try:
        eth.etathermSessionOpen()
        real = eth.retrieveRealTemperature()
        if real:
            eth.setAddressRealTemperature(real)
        # retrieveTargetTemperature() nelze volat — bug v origin/etatherm.py řádek 1604
        # (initAddressParameters přepíše metodu dictem). targetTemp je součástí
        # retrieveAddressParameters(), takže se načte níže.
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


def get_device_status(eth, device_id):
    """Vrátí stav topení z addressParameters. Volat PO refresh_temperatures."""
    ap = eth.addressParameters.get(device_id, {})
    offset = ap.get("tempOffset", 5)

    real = ap.get("realTemp")
    target = ap.get("targetTemp")
    current_temp = (real + offset) if real is not None else None
    target_temp = (target + offset) if target is not None else None

    # FOC stav
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
        "current_temp": current_temp,
        "target_temp": target_temp,
        "foc_active": foc_active,
        "foc_temp": foc_temp,
        "name": ap.get("name", f"Adresa {device_id}"),
    }


# ---------------------------------------------------------------------------
# Flask aplikace
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/")
def index():
    heaters = CFG.get("heaters", [])
    defaults = CFG["defaults"]
    pin = CFG["web"]["pin"]
    return render_template("index.html", heaters=heaters, defaults=defaults, pin=pin)


@app.route("/api/status/<int:device_id>")
def api_status(device_id):
    """Vrátí aktuální stav jednoho topení."""
    with eth_lock:
        try:
            eth = get_eth()
            refresh_temperatures(eth)
            result = get_device_status(eth, device_id)
        except Exception as e:
            log.error(f"Chyba čtení stavu: {e}")
            return jsonify({"error": str(e)}), 503
    return jsonify({"device_id": device_id, **result})


@app.route("/api/status/all")
def api_status_all():
    """Vrátí stav všech konfigurovaných topení najednou."""
    heaters = CFG.get("heaters", [])
    device_ids = [h["device_id"] for h in heaters]

    with eth_lock:
        try:
            eth = get_eth()
            refresh_temperatures(eth)
            results = {}
            for did in device_ids:
                results[did] = get_device_status(eth, did)
        except Exception as e:
            log.error(f"Chyba čtení stavu: {e}")
            return jsonify({"error": str(e)}), 503
    return jsonify(results)


@app.route("/api/oz/set", methods=["POST"])
def api_oz_set():
    """Nastaví operativní změnu (FOC) teploty."""
    data = request.json
    device_id = data.get("device_id", 1)
    temp = data.get("temp")
    pin = data.get("pin", "")

    cfg_pin = CFG["web"]["pin"]
    if cfg_pin and pin != cfg_pin:
        return jsonify({"error": "Nesprávný PIN"}), 403

    if temp is None:
        return jsonify({"error": "Chybí parametr temp"}), 400

    temp = float(temp)
    if temp < CFG["defaults"]["temp_min"] or temp > CFG["defaults"]["temp_max"]:
        return jsonify({"error": f"Teplota musí být {CFG['defaults']['temp_min']}–{CFG['defaults']['temp_max']} °C"}), 400

    with eth_lock:
        try:
            eth = get_eth()
            # 1. Nastavit teplotu v paměti (žádný socket)
            eth.setFOCTemperature(device_id, temp)
            # 2. Aktivovat OZ — přečte opChangeTemp z paměti + preset délku z ROZ,
            #    spočítá start/end časy a zapíše vše do OZ registru.
            #    storeFOCTemperature je redundantní (activateFOC přepíše stejný registr)
            #    a navíc má bug (vrací 1 i při úspěchu).
            err = eth.activateFOC(device_id)
            if err:
                log.warning(f"activateFOC vrátil chybu pro zařízení {device_id}")
                return jsonify({"error": "Chyba aktivace operativní změny"}), 500
            log.info(f"OZ nastavena: zařízení {device_id} → {temp} °C")
            # Refresh stavu po změně
            time.sleep(0.5)
            refresh_temperatures(eth)
        except Exception as e:
            log.error(f"Chyba nastavení FOC: {e}")
            return jsonify({"error": f"Chyba komunikace: {e}"}), 500

    return jsonify({"ok": True, "message": f"Operativní změna: {temp} °C"})


@app.route("/api/oz/cancel", methods=["POST"])
def api_oz_cancel():
    """Zruší operativní změnu (FOC)."""
    data = request.json
    device_id = data.get("device_id", 1)
    pin = data.get("pin", "")

    cfg_pin = CFG["web"]["pin"]
    if cfg_pin and pin != cfg_pin:
        return jsonify({"error": "Nesprávný PIN"}), 403

    with eth_lock:
        try:
            eth = get_eth()
            # deactivateFOC řídí si session sám
            err = eth.deactivateFOC(device_id)
            if err:
                return jsonify({"error": "Chyba deaktivace"}), 500
            log.info(f"FOC zrušena: zařízení {device_id}")
            time.sleep(0.5)
            refresh_temperatures(eth)
        except Exception as e:
            log.error(f"Chyba rušení FOC: {e}")
            return jsonify({"error": f"Chyba komunikace: {e}"}), 500

    return jsonify({"ok": True, "message": "Operativní změna zrušena"})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    web = CFG["web"]
    log.info(f"Server: http://{web['host']}:{web['port']}")
    log.info(f"Etatherm: {CFG['etatherm']['host']}:{CFG['etatherm']['port']}")
    # Předem inicializovat klienta
    with eth_lock:
        try:
            get_eth()
        except Exception as e:
            log.error(f"Inicializace selhala: {e}")
    app.run(host=web["host"], port=web["port"], debug=False)
