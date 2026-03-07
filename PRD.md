# PRD: Etatherm Home Assistant Integration

## Cíl

Home Assistant integrace pro regulátor Etatherm ETH1eD + WE3 s dashboardem pro zobrazení teplot a ovládání ROZ (rychlé operativní změny) pro každou místnost.

---

## Architektura

```
┌─────────────────────────────────────────────────────┐
│  Home Assistant                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │  custom_components/etatherm/                   │  │
│  │  ├── climate.py     (climate entity per room)  │  │
│  │  ├── sensor.py      (real temp sensors)        │  │
│  │  ├── binary_sensor.py (ROZ active per room)    │  │
│  │  ├── __init__.py    (setup, services)          │  │
│  │  ├── config_flow.py (UI konfigurace)           │  │
│  │  └── manifest.json                             │  │
│  └────────────────┬──────────────────────────────┘  │
│                   │                                  │
│  ┌────────────────▼──────────────────────────────┐  │
│  │  etatherm_client/        (standalone knihovna)  │  │
│  │  ├── client.py           (high-level API)      │  │
│  │  ├── protocol.py         (TCP komunikace)      │  │
│  │  └── test_client.py      (unit testy)          │  │
│  └────────────────┬──────────────────────────────┘  │
│                   │                                  │
└───────────────────┼──────────────────────────────────┘
                    │ TCP :50001
              ┌─────▼─────┐
              │  WE3/ETH1eD│
              └───────────┘
```

## Komponenty

### 1. etatherm_client/ (standalone, testovatelný bez HA)

Obaluje origin/etatherm.py, řeší:
- Workaroundy pro známé bugy (retrieveTargetTemperature, storeFOCTemperature)
- Thread-safe přístup (Lock)
- Logging patch (/var/log → configurable)
- Čistý high-level API

**API:**
```python
class EtathermClient:
    def __init__(self, host, port, bus_high=0, bus_low=1)
    def connect() -> bool
    def get_all_temperatures() -> dict[int, RoomState]
    def set_roz(device_id, temp, duration_hours) -> bool
    def cancel_roz(device_id) -> bool
    def is_connected() -> bool

@dataclass
class RoomState:
    real_temp: float       # skutečná teplota (s offsetem)
    target_temp: float     # cílová teplota z programu (s offsetem)
    roz_active: bool       # je ROZ/OZ aktivní?
    roz_temp: float | None # nastavená ROZ teplota (s offsetem)
    roz_end: datetime | None  # kdy ROZ končí
```

**Testování:** Mock TCP server nebo mock origin knihovny. Testy spustitelné bez HW i bez HA.

### 2. custom_components/etatherm/ (HA integrace)

#### Entity per místnost:

| Entita | Typ | Popis |
|--------|-----|-------|
| `climate.etatherm_{name}` | Climate | Skutečná + cílová teplota, HVAC režim |
| `sensor.etatherm_{name}_real_temp` | Sensor | Skutečná teplota (pro grafy/historii) |
| `sensor.etatherm_{name}_target_temp` | Sensor | Cílová teplota (pro grafy/historii) |
| `binary_sensor.etatherm_{name}_roz` | Binary Sensor | ROZ aktivní ano/ne |

#### Climate entita:
- `current_temperature` → skutečná teplota
- `target_temperature` → cílová teplota (programová, nebo ROZ pokud aktivní)
- `hvac_mode`: `heat` (vždy, ETH1eD je topení)
- `hvac_action`: `heating` / `idle` (podle real vs target)
- Nastavení target_temperature přes klimatizaci = nastaví ROZ

#### Služby (Services):
```yaml
etatherm.set_roz:
  description: "Nastaví rychlou operativní změnu"
  fields:
    entity_id: climate.etatherm_vasek
    temperature: 21        # °C, default 21
    duration_hours: 48     # hodiny, default 48 (2 dny)

etatherm.cancel_roz:
  description: "Zruší rychlou operativní změnu"
  fields:
    entity_id: climate.etatherm_vasek
```

#### Polling:
- Interval: 60s (odpovídá cyklu regulátoru ~1 min)
- Serializovaný přístup přes Lock (ETH1eD má pomalé CPU)

### 3. Dashboard

Lovelace dashboard s kartami pro každou místnost:

```
┌─────────────────────────────────────────────┐
│  🏠 Topení                                   │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ Ložnice │ │  Tom    │ │  Maja   │       │
│  │  18°C   │ │  20°C   │ │  21°C   │       │
│  │ →18°C   │ │ →20°C   │ │ →21°C   │       │
│  │         │ │ ROZ 22° │ │         │       │
│  └─────────┘ └─────────┘ └─────────┘       │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ Graf: Ložnice (24h)                  │   │
│  │  22°─         ╱╲                     │   │
│  │  20°─ ───────╱  ╲───── skutečná     │   │
│  │  18°─ ─────────────── cílová        │   │
│  │  16°─                                │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ ROZ nastavení                        │   │
│  │ Místnost: [Vašek      ▾]            │   │
│  │ Teplota:  [21°C    ─●────]          │   │
│  │ Doba:     [2 dny   ─●────]          │   │
│  │ [ NASTAVIT ROZ ]  [ ZRUŠIT ROZ ]    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

**Karty:**
1. **Glance card** — přehled všech místností (teplota, ROZ indikátor)
2. **History graph card** — per místnost, skutečná + cílová teplota
3. **Thermostat card** — per místnost, interaktivní nastavení teploty
4. **Custom ROZ panel** — výběr místnosti, slider teplota/doba, tlačítka

---

## Implementační plán

### Fáze 1: etatherm_client (standalone knihovna)
1. `protocol.py` — wrapper kolem origin/etatherm.py s workaroundy
2. `client.py` — high-level API (RoomState, set_roz, cancel_roz)
3. `test_client.py` — unit testy s mock knihovnou
4. Ověření na reálném HW

### Fáze 2: HA integrace (custom_components)
5. `manifest.json` + `__init__.py` — základ integrace, config flow
6. `climate.py` — climate entity per místnost
7. `sensor.py` — teplotní senzory pro historii
8. `binary_sensor.py` — ROZ indikátor
9. Services: `set_roz`, `cancel_roz`

### Fáze 3: Dashboard
10. Lovelace YAML — glance, grafy, thermostat karty
11. ROZ ovládací panel (script/automation nebo custom card)

### Fáze 4: Dokumentace
12. README s instalací, konfigurací, použitím
13. Návod na HACS instalaci

---

## Konfigurace

### config_flow.py (UI):
```
Host: 192.168.68.75
Port: 50001
Polling interval: 60s
```

### Místnosti:
Automaticky z `retrieveAddressNames()` nebo manuální mapování v config flow.
Adresy 1-16, přeskočit speciální (15=kotel).

---

## Omezení a workaroundy

| Problém | Řešení |
|---------|--------|
| retrieveTargetTemperature bug (řádek 1604) | Nevolat po initAddressParameters, target z retrieveAddressParameters |
| storeFOCTemperature vrací vždy 1 | Přeskočit, activateFOC stačí |
| storeFOCParams typo makeFTC/makeFOC | Nevolat, použít setFOCTemperature + activateFOC |
| Teploty mají rozlišení 1°C | Zobrazit bez desetin |
| ETH1eD single-threaded | Serializovat přes Lock, polling max 1x/min |
| Adresa 15 = kotel (nesmyslné teploty) | Vyloučit z konfigurace nebo označit |
| logging do /var/log | Patch logging.basicConfig |

---

## Výstupní soubory

```
etatherm-ha/
├── etatherm_client/
│   ├── __init__.py
│   ├── client.py
│   ├── protocol.py
│   └── tests/
│       ├── test_client.py
│       └── mock_etatherm.py
├── custom_components/
│   └── etatherm/
│       ├── manifest.json
│       ├── __init__.py
│       ├── config_flow.py
│       ├── climate.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── const.py
│       ├── strings.json
│       └── translations/
│           └── en.json
├── dashboard/
│   └── lovelace.yaml
├── README.md
└── hacs.json
```

---

## ROZ flow (end-to-end)

```
Uživatel klikne "Nastavit ROZ" v dashboardu
  → HA service call: etatherm.set_roz(entity, 21°C, 48h)
    → custom_components/__init__.py handle_set_roz()
      → etatherm_client.set_roz(device_id=4, temp=21, hours=48)
        → eth.setFOCTemperature(4, 21.0)     # opChangeTemp = 16 (21-5)
        → eth.activateFOC(4)                  # start=now, end=now+48h
          → TCP :50001 → WE3 → ETH1eD
    → entity state update (ROZ active, foc_temp=21)
  → Dashboard ukazuje ROZ badge + novou cílovou teplotu
```
