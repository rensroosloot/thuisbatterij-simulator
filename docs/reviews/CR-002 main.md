# CR-002 — Code Review: main.py

**Project:** 023 Thuisbatterij  
**Bestand:** [src/main.py](../../src/main.py)  
**Datum:** 2026-04-28  
**Status:** Openstaand (2 bevindingen open: CR-002-01, CR-002-02)

---

## Bevindingen — overzichtstabel

| ID | Agent | Prioriteit | Samenvatting | Oplosser | Hoe opgelost | Status |
|---|---|---|---|---|---|---|
| CR-002-01 | Claude | Medium | Sweep gebruikt altijd C-rate; geen UI-invoer voor vast vermogen → foute vermogens voor 2.4 kWh en 8.16 kWh batteries | Codex | TODO(codex): voeg `fixed_charge_power_kw`/`fixed_discharge_power_kw` invoervelden toe en geef ze door aan `SweepConfig` | Open |
| CR-002-02 | Claude | Laag | Dode variabele `sweep_year = 2024` en verouderde caption "Feature branch: DataManager" | Codex | TODO(codex): verwijder `sweep_year = 2024` (L525) en vervang de caption (L386) | Open |
| CR-002-03 | Claude | Laag | Slimme modus roept `apply_prices` 4× aan: 1× expliciet + 3× intern via tariefmethoden | — | Niet fout, enkel overbodig rekenwerk; acceptabel voor v1 | Niet van toepassing |

---

## Review: Claude Code — 2026-04-28

### Algemeen oordeel

De structuur is solide. UI-flow, caching, export en chart-rendering zijn goed opgezet. De multi-jaar normalisatie via `year_count`, de `@st.cache_data`-decorator en de `parse_market_options`-parser zijn correct geïmplementeerd. Er is één bug met meetbare impact op de sweep-nauwkeurigheid en twee kleine schoonmaakpunten.

### Bevinding CR-002-01 — Prioriteit: Medium

**Samenvatting:** Sweep gebruikt altijd C-rate; geen UI-invoer voor vast vermogen  
**Locatie:** [src/main.py:570-583](../../src/main.py#L570-L583) en [src/main.py:901-916](../../src/main.py#L901-L916)

De UI heeft sliders voor `sweep_charge_c_rate` en `sweep_discharge_c_rate` (defaults `2.4/5.4 ≈ 0.444C` en `0.8/5.4 ≈ 0.148C`), maar geen invoervelden voor vast vermogen. De `SweepConfig` krijgt nooit `fixed_charge_power_kw` / `fixed_discharge_power_kw` mee. Hierdoor worden vermogens per capaciteit geschaald, wat alleen correct is voor batteries van ~5.28 kWh:

| Batterij | C-rate geeft | Werkelijk (vast) |
|---|---|---|
| 2.40 kWh | 1.07 kW laden / 0.36 kW ontladen | 2.4 kW / 0.8 kW |
| 5.28 kWh | 2.34 kW / 0.78 kW ≈ ✓ | 2.4 kW / 0.8 kW |
| 8.16 kWh | 3.62 kW / 1.21 kW | 2.4 kW / 0.8 kW |

De 2.4 kWh-optie wordt te traag doorgerekend (onderschat besparing); de 8.16 kWh te snel (overschat). Dit is ook de verklaring voor de afwijking in de eerder opgeslagen testresultaten (`sweep_modus_1_2024.xlsx`, `sweep_modus_2_2024.xlsx`).

**Aanbevolen fix:**

Voeg in het sweep-formuliergedeelte twee optionele invoervelden toe:

```python
sweep_use_fixed_power = st.checkbox("Vast vermogen gebruiken i.p.v. C-rate", value=True)
sweep_fixed_charge_power_kw = st.number_input(
    "Vast laadvermogen sweep (kW)", value=2.4, step=0.1,
    disabled=not sweep_use_fixed_power,
)
sweep_fixed_discharge_power_kw = st.number_input(
    "Vast ontlaadvermogen sweep (kW)", value=0.8, step=0.1,
    disabled=not sweep_use_fixed_power,
)
```

En geef ze door aan `SweepConfig(...)`:

```python
fixed_charge_power_kw=sweep_fixed_charge_power_kw if sweep_use_fixed_power else None,
fixed_discharge_power_kw=sweep_fixed_discharge_power_kw if sweep_use_fixed_power else None,
```

### Bevinding CR-002-02 — Prioriteit: Laag

**Samenvatting:** Dode variabele en verouderde caption  
**Locaties:** [src/main.py:525](../../src/main.py#L525) en [src/main.py:386](../../src/main.py#L386)

- `sweep_year = 2024` (L525) wordt nergens gebruikt — de sweep gebruikt `scenario_years`.
- `st.caption("Feature branch: DataManager")` (L386) is een verouderd ontwikkelnotitie dat niet in productie thuishoort.

### Bevinding CR-002-03 — Prioriteit: Laag (Niet van toepassing)

**Samenvatting:** Overbodige `apply_prices`-aanroepen voor slimme modus  
**Locatie:** [src/main.py:758](../../src/main.py#L758)

De slimme modus roept `tariff_engine.apply_prices(golden_dataframe)` expliciet aan (vereist zodat `simulate_smart_mode` bij de prijskolommen kan). Daarna roepen `summarize_baseline_costs`, `summarize_battery_costs` en `apply_battery_costs` `apply_prices` intern ook aan — dus wordt de berekening 4× uitgevoerd. Mode 1 doet dit correct: geen expliciete aanroep, de tariefmethoden regelen het intern. Niet fout voor v1; de overhead is verwaarloosbaar op jaardata.

### Correcte implementaties

| Aspect | Locatie | Status |
|---|---|---|
| `@st.cache_data` op `load_golden_dataframe` | L18 | ✓ CR-001-05 opgelost |
| `tariff_engine.apply_prices` intern in alle tariefmethoden | tariff_engine L64, L96 | ✓ geen bug in Mode 1-pad |
| Multi-jaar normalisatie via `year_count` | L280, L744 | ✓ correct |
| `parse_market_options` met `;`-scheiding en komma→punt normalisatie | L252-268 | ✓ robuust |
| Detail-periode filter end-of-day berekening via microseconds | L119 | ✓ correct voor 15-min resolutie |
| `fixed_sell_price_eur_per_kwh = 0.0` als standaard (post-2027 model) | L507-513 | ✓ correct |
