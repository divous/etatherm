# Etatherm ETH1eD + WE3 — Ovládání operativní změny teploty

## Přehled projektu

Flask webová aplikace pro nastavení operativní změny (ROZ/FOC) teploty na topení řízeném regulátorem Etatherm ETH1eD s WiFi modulem WE3 (firmware we3-375).

Komunikuje přes proprietární Etatherm TCP protokol na portu 50001. Používá knihovnu z projektu [etatherm-ha-bridge](https://github.com/mbisak/etatherm-ha-bridge) (publikována s povolením výrobce).

## Architektura

```
Browser → Flask (app.py :8080) → TCP :50001 → WE3 modul → ETH1eD regulátor
```

Jednotka je na IP 192.168.68.75. Má 16 adres topení.

## Klíčové soubory

- `app.py` — Flask server, API endpointy, komunikace s ETH1eD
- `config.yaml` — IP adresa, seznam místností (device_id 1–16), PIN, limity teplot
- `templates/index.html` — SPA frontend (vanilla JS, dark theme, mobile-first)
- `origin/etatherm.py` — reálná komunikační knihovna (2262 řádků, proprietární protokol)
- `etatherm.py` — mock knihovna pro testování bez připojení k jednotce
- `requirements.txt` — flask, pyyaml, paho-mqtt

## Session management (kritické!)

Knihovna etatherm.py má dva typy funkcí:

**Řídí si TCP session sami** (volají etathermSessionOpen/Close interně):
- `initAddressParameters()`, `storeFOCTemperature()`, `activateFOC()`, `deactivateFOC()`

**Neřídí session** (volající MUSÍ otevřít/zavřít session):
- `retrieveRealTemperature()`, `retrieveTargetTemperature()`, `retrieveAddressParameters()`, `retrieveAddressNames()`, `retrieveFOCParameters()`

**Pouze v paměti** (žádný socket):
- `setFOCTemperature()` — nastaví teplotu v addressParameters
- `isFOCActive()` — kontroluje časy v addressParameters

Celý přístup k ETH1eD je serializován přes `threading.Lock()` — jednotka má omezený procesor.

## Vzor pro nastavení operativní změny

```python
with eth_lock:
    eth = get_eth()
    eth.setFOCTemperature(device_id, temp)    # paměť
    eth.storeFOCTemperature(device_id)         # vlastní session
    eth.activateFOC(device_id)                 # vlastní session
```

## Vzor pro čtení teplot

```python
with eth_lock:
    eth = get_eth()
    eth.etathermSessionOpen()                  # manuální session
    real = eth.retrieveRealTemperature()
    eth.setAddressRealTemperature(real)
    eth.etathermSessionClose()
```

## Teploty a offset

Všechny teploty v addressParameters jsou uloženy BEZ offsetu. Offset je typicky 5.
Zobrazovaná teplota = raw + tempOffset.

## API endpointy

- `GET /` — HTML frontend
- `GET /api/status/<device_id>` — stav jednoho topení
- `GET /api/status/all` — stav všech konfigurovaných topení
- `POST /api/oz/set` — nastavit OZ `{device_id, temp, pin}`
- `POST /api/oz/cancel` — zrušit OZ `{device_id, pin}`

## Spuštění

```bash
# Reálné připojení (na RPi ve stejné síti):
python3 app.py

# Mock režim (testování):
ETATHERM_MOCK=1 python3 app.py
```

## Místnosti (device_id → název)

1=šatna, 2=maja, 3=anka, 4=vašek, 5=tom, 6=ložnice, 7=žlutý, 8=schodiště,
9=r obývák, 10=r zimní zahrada, 11=vstup, 12=koupelna, 13=kuchyň, 14=obývák,
15=černé podlaží, 16=zimní zahrada R

## Poznámky

- `heatingMaps` v origin/etatherm.py jsou hardcodované pro autora — nepoužíváme je
- Origin knihovna importuje `paho-mqtt` na top-level — musí být nainstalován i když MQTT nepoužíváme
- Mock knihovna má vnořenou třídu `etatherm.etatherm.etatherm`, origin má `etatherm.etatherm` — app.py detekuje automaticky
- Řádek 1604 v origin/etatherm.py má bug: `self.retrieveTargetTemperature` bez `()` — targetTemp se nastaví přes `setAddressParameters()` místo toho
