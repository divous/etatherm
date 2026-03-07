# Instalace Etatherm integrace do Home Assistant

## Požadavky

- Home Assistant OS na Raspberry Pi (testováno na RPi 5, Core 2026.3.0)
- Etatherm ETH1eD + WE3 modul ve stejné síti
- SSH přístup k HA (addon: Advanced SSH & Web Terminal)

## Krok 1: Zkopírovat integraci

### Varianta A: Přes SSH

```bash
# Na Macu — zabalí komponentu
cd /Users/tomas.divila/git/etherm
tar czf etatherm-ha.tar.gz custom_components/etatherm/

# Přenést na RPi
scp etatherm-ha.tar.gz root@<HA_IP>:/root/

# Na RPi přes SSH addon
cd /config
tar xzf /root/etatherm-ha.tar.gz
```

### Varianta B: Přes Samba share

1. Nainstaluj addon **Samba share** v HA
2. Připoj se na `\\<HA_IP>\config\` z počítače
3. Vytvoř složku `custom_components/etatherm/`
4. Zkopíruj obsah `custom_components/etatherm/` z tohoto repozitáře

### Varianta C: Přes File Editor addon

1. Nainstaluj addon **File editor**
2. Ručně vytvoř soubory — nepraktické, doporučujeme A nebo B

## Krok 2: Restart Home Assistant

```
Settings → System → Restart
```

Nebo přes SSH:
```bash
ha core restart
```

## Krok 3: Přidat integraci

1. **Settings → Devices & Services → Add Integration**
2. Vyhledej **"Etatherm"**
3. Zadej:
   - IP adresa: `192.168.68.75`
   - Port: `50001`
4. Klikni **Submit**

Integrace vytvoří:
- **15 climate entit** (jedna per místnost, bez kotle)
- **30 teplotních senzorů** (skutečná + cílová per místnost)
- **15 binary senzorů** (ROZ stav per místnost)

## Krok 4: Dashboard

1. **Settings → Dashboards → Add Dashboard**
   - Název: `Topení`
   - Ikona: `mdi:radiator`
2. Otevři nový dashboard
3. Klikni **⋮** (tři tečky) → **Edit dashboard** → **Raw configuration editor**
4. Vlož obsah souboru `custom_components/etatherm/dashboard.yaml`
5. Ulož

## Použití

### Změna teploty (ROZ)

- Na **termostatové kartě** otočte kolečkem na požadovanou teplotu
- Automaticky aktivuje ROZ na **48 hodin** (default)
- Režim se změní z AUTO na HEAT

### Zrušení ROZ

- Na termostatové kartě přepněte režim zpět na **AUTO**
- Nebo zavolejte službu `etatherm.cancel_roz`

### Služby pro pokročilé ovládání

```yaml
# Nastavit ROZ s vlastní dobou trvání
service: etatherm.set_roz
data:
  device_id: 4          # Vašek
  temperature: 22        # °C
  duration_hours: 72     # 3 dny

# Zrušit ROZ
service: etatherm.cancel_roz
data:
  device_id: 4
```

### Automatizace — příklad

```yaml
# Zapnout topení v koupelně ráno
automation:
  - alias: "Koupelna ráno"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: etatherm.set_roz
        data:
          device_id: 12     # Koupelna
          temperature: 24
          duration_hours: 2
```

## Entity ID formát

| Typ | Formát | Příklad |
|-----|--------|---------|
| Climate | `climate.etatherm_{name}` | `climate.etatherm_vasek` |
| Skutečná teplota | `sensor.etatherm_{name}_teplota` | `sensor.etatherm_vasek_teplota` |
| Cílová teplota | `sensor.etatherm_{name}_cil` | `sensor.etatherm_vasek_cil` |
| ROZ stav | `binary_sensor.etatherm_{name}_roz` | `binary_sensor.etatherm_vasek_roz` |

> **Poznámka:** Přesný formát entity ID závisí na tom, jak HA normalizuje české názvy.
> Po instalaci ověřte v Settings → Entities.

## Řešení problémů

### "Cannot connect to Etatherm unit"
- Ověřte, že RPi je ve stejné síti jako WE3 modul
- Zkuste `ping 192.168.68.75` z HA SSH terminálu
- Port 50001 musí být dostupný (žádný firewall)

### Entity se nezobrazují
- Počkejte 60s (polling interval)
- Zkontrolujte logy: Settings → System → Logs, filtr "etatherm"

### Timeouty v logu
- ETH1eD má pomalý procesor, občasné timeouty jsou normální
- Knihovna automaticky opakuje požadavky (až 10×)
