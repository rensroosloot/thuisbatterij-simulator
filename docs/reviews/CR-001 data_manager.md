# CR-001 — Code Review: data_manager.py

**Project:** 023 Thuisbatterij  
**Bestand:** [src/data_manager.py](../../src/data_manager.py)  
**Datum:** 2026-04-27  
**Status:** Openstaand (1 bevinding open: CR-001-06)

---

## Bevindingen — overzichtstabel

| ID | Agent | Prioriteit | Samenvatting | Oplosser | Hoe opgelost | Status |
|---|---|---|---|---|---|---|
| CR-001-01 | Claude | Kritiek | Prijskoppeling uurdata → 75% NaN via directe index-join | Codex | `_join_prices_to_intervals` met `price_series.reindex(interval_index, method="ffill")` (L472-L480) | Opgelost |
| CR-001-02 | Claude | Medium | Solar kwartaalexpansie neemt exacte uurgrens aan; niet gevectoriseerd | Codex | `working["timestamp_nl"] = working["timestamp_nl"].dt.floor("h")` toegevoegd vóór kwartierexpansie (L279) | Opgelost |
| CR-001-03 | Claude | Medium | Bestandsnamen dubbel gedefinieerd in twee methoden | Codex | Module-constante `RESOURCE_FILES` ingevoerd (L22); beide methoden gebruiken deze nu als enige bron | Opgelost |
| CR-001-04 | Claude | Laag | `detect_spring_dst_gap` heuristiek kan vals positief geven bij datagat | Codex | Check beperkt tot `index.month == 3` en `index.day >= 25` (L462); willekeurige datagaten buiten maart triggeren niet meer | Opgelost |
| CR-001-05 | Claude | Laag | `summarize_available_golden_dataframes` herbouwt volledig bij elke aanroep | Codex | `@st.cache_data` decorator in `main.py:17` op `load_golden_dataframe`; herbouw alleen bij wijziging jaar-parameter | Opgelost |
| CR-001-06 | Gemini | Laag | `data_quality_flags` en `actie` kolommen: gebruik `category` dtype | Codex | TODO(codex): pas `data_quality_flags` en `actie` aan naar `pd.CategoricalDtype` in `DataManager` en `SimEngine` | Open |
| CR-001-07 | Gemini | Medium | `decimal=','` ontbreekt mogelijk in sommige `pd.read_csv` aanroepen | Codex | Prijsparser had `decimal=","` al correct; P1e- en HA-CSV's gebruiken standaard puntdecimalen — geen aanpassing nodig | Niet van toepassing |
| CR-001-08 | Gemini | Medium | Negatieve P1e-diff: clip op 0 en markeer in `data_quality_flags` i.p.v. stoppen | Codex | `_handle_negative_diffs` (L475-L485) knipt op 0 en voegt `DataQualityIssue` toe — was al geïmplementeerd bij oplevering | Niet van toepassing |
| CR-001-09 | Gemini | Laag | DST-voorjaar: join met prijsdata mag niet falen bij ontbrekende uurgrens | Codex | Gedekt door CR-001-01: `reindex(method="ffill")` geeft elk interval een prijs ongeacht DST-gat | Opgelost |

---

## Review: Claude Code — 2026-04-27

### Algemeen oordeel

De structuur is solide. De scheiding tussen dataclasses voor resultaten/kwaliteitsrapportage en de verwerkingslogica in `DataManager` is goed. DST-afhandeling voor najaar (sommen van duplicaatintervallen ná diff) en de energiebalans-formule zijn correct geïmplementeerd. Er is één kritieke correctheidsfout en twee middelzware bevindingen die vóór integratietests opgelost moeten worden.

### Bevinding CR-001-01 — Prioriteit: Kritiek

**Samenvatting:** Prijskoppeling uurdata → 75% NaN via directe index-join  
**Locatie:** [src/data_manager.py:326](../../src/data_manager.py#L326)

```python
golden = p1e_result.dataframe.join(prices[["spot_price_eur_per_kwh"]], how="left")
```

Als de jeroen_punt-CSV uurlijkse prijzen bevat (tijdstempels 00:00, 01:00, ...), dan matcht een directe index-join alleen de `:00`-intervallen in het 15-minuten P1e-raster. De `:15`, `:30` en `:45` intervallen krijgen `NaN`. Dit raakt 75% van alle intervallen. `TariffEngine` slaat NaN-prijsintervallen over (kosten = 0), waardoor alle financiële KPI's structureel te laag uitvallen.

**Aanbevolen fix:**
```python
golden = p1e_result.dataframe.join(prices[["spot_price_eur_per_kwh"]], how="left")
golden["spot_price_eur_per_kwh"] = golden["spot_price_eur_per_kwh"].ffill()
```

Of via `merge_asof` voor een expliciete "meest recente uurprijs per kwartierinterval"-koppeling. Voeg een unittest toe die na `build_golden_dataframe` controleert dat het NaN-aantal ≤ werkelijk ontbrekende uren.

### Bevinding CR-001-02 — Prioriteit: Medium

**Samenvatting:** Solar kwartaalexpansie neemt exacte uurgrens aan; niet gevectoriseerd  
**Locatie:** [src/data_manager.py:293-311](../../src/data_manager.py#L293-L311)

*Subprobleem a — uurgrens-aanname:* `interval_start = timestamp_nl − 1 uur` veronderstelt dat de HA-sensor exact op de uurgrens logt. Als de sensor op bijv. 10:03 logt, worden de kwartier-tijdstempels 09:03, 09:18, 09:33, 09:48 — niet uitgelijnd op het P1e-raster. Na de groupby vallen deze waarden weg bij de join.

**Fix:** Rond `timestamp_nl` af naar het dichtstbijzijnde uur vóór de kwartierexpansie:
```python
working["timestamp_nl"] = working["timestamp_nl"].dt.floor("h")
```

*Subprobleem b — performance:* De dubbele Python-lus produceert ~35.040 dict-operaties per jaar. Niet blokkerend voor v1, maar relevant voor de 200-punts sweep (400 simulaties). Gevectoriseerde aanpak met `np.repeat` verdient voorkeur.

### Bevinding CR-001-03 — Prioriteit: Medium

**Samenvatting:** Bestandsnamen dubbel gedefinieerd  
**Locatie:** [src/data_manager.py:119-126](../../src/data_manager.py#L119-L126) en [src/data_manager.py:186-196](../../src/data_manager.py#L186-L196)

Dezelfde CSV-bestandsnamen staan hardcoded in zowel `get_resource_statuses` als `get_year_resource_paths`. Samenvoegen naar één module-constante:

```python
_RESOURCE_FILES = {
    2024: {"p1e": "P1e-2024-1-1-2024-12-31.csv", "prices": "...", "solar": "..."},
    2025: {"p1e": "P1e-2025-1-1-2025-12-31.csv", "prices": "...", "solar": "..."},
}
```

### Bevinding CR-001-04 — Prioriteit: Laag

**Samenvatting:** `detect_spring_dst_gap` heuristiek kan vals positief geven  
**Locatie:** [src/data_manager.py:448-449](../../src/data_manager.py#L448-L449)

`(counts == 92).any()` triggert ook op een niet-DST-dag met een toevallig datagat van precies 4 intervallen. Robuster: beperk de check tot het verwachte DST-datumbereik (25–31 maart).

### Bevinding CR-001-05 — Prioriteit: Laag

**Samenvatting:** `summarize_available_golden_dataframes` herbouwt volledig bij elke aanroep  
**Locatie:** [src/data_manager.py:171-182](../../src/data_manager.py#L171-L182)

In Streamlit triggert elke UI-interactie een herberekening. Gebruik `@st.cache_data` in de Streamlit-laag of sla het resultaat op als sessie-attribuut. Dit is een integratiezorg voor `main.py`, niet voor `DataManager` zelf.

### Correcte implementaties

| Aspect | Locatie | Status |
|---|---|---|
| Energiebalans `demand = import − export + solar` | L409 | ✓ Correct per FD §3.1 |
| Najaar-DST: diff vóór groupby, daarna sum | L368-L396 | ✓ Correct per UR-05 |
| Solar datagat 2024 → `fillna(0.0)` | L328 | ✓ Correct per A-09 |
| Negatieve diff-waarden → 0 met rapportage | L282-L290 | ✓ Correct |
| Eerste P1e-rij uitgesloten | L371-L378 | ✓ Correct |
| Bevroren dataclasses voor resultaten | diverse | ✓ Goede keuze |

---

## Review: Gemini Code Assist — 2026-04-27

### Algemeen oordeel

De `DataManager` implementatie volgt nauwgezet de richtlijnen uit DS-001 v1.2. De keuze om eerst differentiële waarden te berekenen op de P1e-registers en pas daarna de aggregatie voor de najaars-DST uit te voeren, getuigt van een diep begrip van de onderliggende datastructuur en voorkomt significante fouten in de energiebalans.

### Bevinding CR-001-06 — Prioriteit: Laag

**Samenvatting:** `category` dtype voor `data_quality_flags` en `actie` kolommen  

Met 2 jaar aan kwartierdata bevat het Golden DataFrame ~70.000 rijen. Door voor `data_quality_flags` en `actie` het `category` dtype te gebruiken i.p.v. strings, wordt geheugengebruik beperkt en worden UI-filters in Streamlit versneld.

### Bevinding CR-001-07 — Prioriteit: Medium

**Samenvatting:** `decimal=','` ontbreekt mogelijk in sommige `pd.read_csv` aanroepen  

In de `resources/` bestanden komt soms de Nederlandse decimaalkomma voor (met name in de prijsdata). Controleer alle `pd.read_csv` aanroepen op `decimal=','` om typecasting-fouten naar `object`/`string` te voorkomen. De prijsparser heeft dit (`sep=";"`, `decimal=","`); controleer of de overige loaders dit ook correct afhandelen.

### Bevinding CR-001-08 — Prioriteit: Medium

**Samenvatting:** Negatieve P1e-diff: clip op 0 en markeer i.p.v. stoppen  

Bij de detectie van negatieve P1e-differenties (bijv. door metervervanging) moet de tool doorgaan met de rest van het jaar, niet stoppen. Voeg een clip-op-nul mechanisme toe en markeer de betrokken intervallen in `data_quality_flags`.

*Opmerking voor oplosser: controleer of `_handle_negative_diffs` (L475-L485) dit al implementeert — mogelijk al opgelost.*

### Bevinding CR-001-09 — Prioriteit: Laag

**Samenvatting:** DST-voorjaar: join met prijsdata mag niet falen bij ontbrekende uurgrens  

De logica laat een gat vallen van 02:00 tot 03:00 in het voorjaar. Zorg dat de join met de prijsdata hierop niet faalt. Een `left join` van de P1e-index op de prijs-index is de veiligste methode zodat energie meetelt maar prijs = 0 of NaN geregistreerd wordt (conform FR-08).

*Zie ook CR-001-01 — de prijskoppeling via ffill lost dit impliciet op.*
