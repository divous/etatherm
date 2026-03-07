# Etatherm ETH1eD + WE3 — Operativní změna teploty

Webová aplikace pro nastavení operativní změny (ROZ/FOC) teploty na topení řízeném regulátorem Etatherm ETH1eD s modulem WE3.

Komunikuje přes proprietární Etatherm protokol (TCP port 50001) pomocí knihovny z projektu [etatherm-ha-bridge](https://github.com/mbisak/etatherm-ha-bridge).

## Požadavky

- Python 3.9+
- Raspberry Pi (nebo jiný Linux) ve stejné síti jako WE3
- WE3 firmware ≥ we3-375

## Instalace

```bash
# 1. Zkopírovat soubory na RPi
scp -r etatherm-control/ pi@raspberrypi:~/

# 2. Na RPi: nastavit prostředí
cd ~/etatherm-control
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Knihovna `etatherm.py` je již v adresáři `origin/` (stažena z GitHubu). Pokud potřebujete aktualizovat:

```bash
cd origin
wget -O etatherm.py https://raw.githubusercontent.com/mbisak/etatherm-ha-bridge/master/etatherm.py
```

## Konfigurace

Upravte `config.yaml`:

```yaml
etatherm:
  host: "192.168.68.75"   # IP adresa vašeho WE3
  port: 50001

heaters:
  - name: "Obývák"
    device_id: 14          # číslo adresy (1–16)
  # ... další místnosti

web:
  pin: "1234"              # změňte!
```

IP adresu WE3 zjistíte z routeru nebo připojením na WiFi AP mód WE3 (192.168.4.1).

Číslo `device_id` odpovídá adrese topení v systému (1–16). Zjistíte z programu Etherm nebo z webového rozhraní WE3.

## Spuštění

```bash
source venv/bin/activate
python3 app.py
```

Otevřete `http://<ip_rpi>:8080` v prohlížeči.

### Testovací režim (mock)

Pro testování bez připojení k reálné jednotce:

```bash
ETATHERM_MOCK=1 python3 app.py
```

### Systemd služba (automatický start)

```bash
sudo tee /etc/systemd/system/etatherm.service << 'EOF'
[Unit]
Description=Etatherm Operativní změna
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/etatherm-control
ExecStart=/home/pi/etatherm-control/venv/bin/python3 app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable etatherm
sudo systemctl start etatherm
```

## Ovládání

1. Vyberte místnost z rozbalovacího seznamu
2. Nastavte teplotu posuvníkem (6–35 °C)
3. Klikněte „Nastavit operativní změnu"
4. Zadejte PIN
5. Pro zrušení: „Zrušit operativní změnu" + PIN

Přehled všech místností s teplotami je v dolní části stránky.
Stav se automaticky obnovuje každých 60 sekund.

## Struktura

```
etatherm-control/
├── app.py              # Flask server + Etatherm komunikace
├── config.yaml         # Konfigurace (IP, místnosti, PIN)
├── etatherm.py         # Mock knihovna (pro testování)
├── requirements.txt
├── templates/
│   └── index.html      # Webové rozhraní
├── origin/
│   └── etatherm.py     # Reálná knihovna (etatherm-ha-bridge)
├── read_status.py      # Diagnostický skript
├── ANALYZA.md          # Analýza přístupů
└── README.md
```

## Session management

Knihovna `etatherm.py` má dva typy funkcí:

**Řídí si session sami** (volají `etathermSessionOpen`/`Close` interně):
`initAddressParameters()`, `storeFOCTemperature()`, `activateFOC()`, `deactivateFOC()`

**Neřídí session** (volající musí otevřít/zavřít):
`retrieveRealTemperature()`, `retrieveTargetTemperature()`, `retrieveAddressParameters()`, `retrieveAddressNames()`, `retrieveFOCParameters()`

**Pouze v paměti** (žádný socket):
`setFOCTemperature()`, `isFOCActive()`

`app.py` respektuje toto rozdělení a používá thread lock pro serializaci přístupu (ETH1eD má omezený procesor).

## Poznámky

- Komunikační protokol je vlastnictvím Etatherm s.r.o. Knihovna je publikována s povolením výrobce.
- ETH1eD má omezený procesor — aplikace serializuje přístupy (jeden požadavek najednou).
- `heatingMaps` v knihovně jsou hardcodované pro autora — pro operativní změnu se nepoužívají.
