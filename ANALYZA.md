# Analýza přístupů k ovládání Etatherm ETH1eD + WE3

## Co jsem zjistil

WE3 modul (firmware we3-375) má dva otevřené porty:

- **Port 80** — webový server, komunikuje přes `POST /data_a`
- **Port 50001** — proprietární binární TCP protokol

Oba porty vedou ke stejné řídící jednotce ETH1eD. Webový server je v podstatě HTTP-to-serial bridge — funkce `getEth1WriteOZString()` v `jsVse.min.js` kóduje data do stejného binárního formátu, který pak WE3 přepošle na ETH1eD.

---

## Přístup A: HTTP API (POST /data_a)

**Princip:** Replikovat to, co dělá webové rozhraní — posílat HTTP POST požadavky na `/data_a`.

**Co jsem zjistil z JS kódu:**
- Funkce `zapisROZ()` staví objekt s poli: `ozu`, `ozt`, `ozzden`, `ozzmes`, `ozzrok`, `ozzhod`, `ozzmin`, `ozkden`, `ozkmes`, `ozkrok`, `ozkhod`, `ozkmin`
- Pak volá `getEth1WriteOZString()` — ta je v minifikovaném `jsVse.min.js` a kóduje data do proprietárního binárního formátu
- Výsledek jde jako POST body na `/data_a`
- Odpověď: `W=5` (OK), aktualizovaný objekt `A`

**Výhody:**
- Čistý HTTP, žádný speciální TCP klient
- Python `requests` stačí

**Nevýhody:**
- `getEth1WriteOZString()` je minifikovaná a kóduje proprietární binární formát
- Bez dekódování téhle funkce nelze tento přístup použít
- Může vyžadovat session cookies / přihlášení
- Vázáno na konkrétní firmware verzi WE3

**Náročnost:** Střední až vysoká (dekódování minifikovaného JS)

---

## Přístup B: TCP protokol (etatherm-ha-bridge knihovna)

**Princip:** Komunikovat přímo s ETH1eD přes TCP port 50001 pomocí existující Python knihovny.

**Co jsem zjistil z etatherm.py (2262 řádků):**
- Kompletní implementace proprietárního protokolu
- Frame: `[DLE(0x10), SOH(0x01), BusH, BusL, AddrB0, AddrB1, OpCode|Len, Data..., Checksum_Add, Checksum_Xor, 0xFF, 0xFF]`
- Hotové funkce pro vše co potřebujeme:
  - `retrieveRealTemperature()` — registry 0x0060
  - `retrieveTargetTemperature()` — registry 0x0070
  - `retrieveAddressNames()` — registry 0x1030
  - `setFOCTemperature(deviceID, temp)` — nastaví teplotu ROZ
  - `activateFOC(deviceID)` / `deactivateFOC(deviceID)` — zapne/vypne ROZ
  - `retrieveFOCParameters()` — stav ROZ

**Výhody:**
- Hotový, otestovaný kód (běží od 2005)
- Publikováno s povolením výrobce
- Kompletní API pro všechno co potřebujeme
- Nezávislé na webovém rozhraní / firmware WE3

**Nevýhody:**
- Hardcodované `heatingMaps` (ale ty pro ROZ nepoužíváme)
- 2262 řádků cizího kódu
- TCP socket management (ale knihovna to řeší)

**Náročnost:** Nízká (knihovna je hotová)

---

## Přístup C: Automatizace webového rozhraní (Playwright/Selenium)

**Princip:** Spustit headless prohlížeč, načíst stránku WE3, a programově klikat na ROZzap/ROZvyp.

**Výhody:**
- Nulové znalosti protokolu — prostě klikáme na tlačítka
- Funguje přesně jako ruční ovládání

**Nevýhody:**
- Těžké (Chromium/Firefox musí běžet na RPi)
- Pomalé (načítání stránek, čekání na JS)
- Křehké (každá změna HTML rozbije selektory)
- Overkill pro jedno tlačítko

**Náročnost:** Nízká, ale zbytečně těžké na zdroje

---

## Doporučení

**Přístup B (TCP + etatherm knihovna)** je nejlepší volba:

1. Kód je hotový a ověřený
2. Máme potvrzeno, že port 50001 je otevřený
3. Všechny potřebné funkce existují
4. Nezávisí na webovém rozhraní
5. Žádné reverse-engineering

Jediná úprava: v `app.py` doplnit volání `etathermSessionOpen()` / `etathermSessionClose()` před a po každém příkazu (knihovna to interně neřeší konzistentně).

HTTP přístup by byl elegantnější, ale vyžaduje dekódování `getEth1WriteOZString()` — zbytečná práce, když TCP knihovna existuje.
