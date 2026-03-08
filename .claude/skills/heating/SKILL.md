---
name: heating
description: >
  Ovládání topení Etatherm přes MCP server. Umožňuje zobrazit stav topení,
  nastavit teplotu (operativní změnu / ROZ) a zrušit operativní změnu.
  Použij kdykoli uživatel mluví o topení, teplotě, místnostech, ROZ, nebo
  chce nastavit/zrušit teplotu. Také když řekne věci jako "je mi zima",
  "zatop", "kolik je stupňů", "nastav 24", "vypni topení", "zpět na program",
  "stav topení", "přidej/uber" apod.
---

# Heating Skill — Etatherm ovládání

Ovládáš topení v domě přes MCP etatherm server. Komunikuj česky.

## Místnosti a device_id

| device_id | Název | Aliasy |
|-----------|-------|--------|
| 1 | Šatna | šatna |
| 2 | Maja | mája, maja, majin pokoj |
| 3 | Anka | anka, ančin pokoj |
| 4 | Vašek | vašek, vaškův pokoj |
| 5 | Tom | tom, tomův pokoj |
| 6 | Ložnice | ložnice, ložňák |
| 7 | Žlutý pokoj | žlutý, žluťák |
| 8 | Schodiště | schodiště, schody |
| 9 | R obývák | r obývák, obývák radka |
| 10 | R zimní zahrada | r zimní zahrada |
| 11 | Vstup | vstup, hala, předsíň |
| 12 | Koupelna | koupelna, koupák |
| 13 | Kuchyň | kuchyň, kuchyňka |
| 14 | Obývák | obývák, obýváček |
| 15 | Černé podlaží | čerpadlo podlahového topení — NE místnost, vynechat ze zobrazení stavu |
| 16 | Zimní zahrada R | zimní zahrada |

## Dostupné MCP nástroje

- `mcp__etatherm__list_heaters` — seznam topení
- `mcp__etatherm__get_status` — stav (device_id nebo None pro všechny)
- `mcp__etatherm__set_temperature` — nastavit ROZ (device_id, temp, volitelně duration_hours)
- `mcp__etatherm__cancel_temperature` — zrušit ROZ, vrátit na program (device_id)

## Postup

### Zobrazení stavu
1. Zavolej `get_status` s device_id (jedna místnost) nebo bez (všechny)
2. Zobraz přehledně: skutečná teplota, cílová teplota, zda je ROZ aktivní
3. Pokud ROZ aktivní, ukaž i ROZ teplotu

### Nastavení teploty
1. Identifikuj místnost z uživatelova textu → device_id
2. Identifikuj požadovanou teplotu (rozsah 6–35 °C)
3. Volitelně dobu trvání (duration_hours) — pokud neuvedeno, neposílej
4. Zavolej `set_temperature`
5. Potvrď uživateli co bylo nastaveno

### Zrušení ROZ (vrácení na program)
1. Identifikuj místnost → device_id
2. Zavolej `cancel_temperature`
3. Potvrď uživateli

### "Přidej" / "Uber"
1. Nejdřív zjisti aktuální stav (`get_status`)
2. K aktuální cílové (nebo ROZ) teplotě přidej/uber typicky 1°C
3. Nastav novou teplotu přes `set_temperature`

## Pravidla

- Pokud uživatel nespecifikuje místnost, zeptej se které místnosti se to týká
- Pokud uživatel nespecifikuje teplotu u nastavení, zeptej se
- Pro "vypni topení" / "zpět na program" / "auto" použij `cancel_temperature`
- Odpovídej stručně, česky
- Při zobrazení stavu všech místností použij tabulku
