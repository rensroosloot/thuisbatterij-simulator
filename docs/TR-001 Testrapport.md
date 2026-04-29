# TR-001 - Testrapport Thuisbatterij Simulator

**Document type:** Testrapport  
**Project:** 023 Thuisbatterij  
**Versie:** 1.0  
**Datum:** 2026-04-28  
**Auteur:** Codex  
**Gebaseerd op:** TP-001 v1.1, actuele implementatie op branch `feature/datamanager`  
**Status:** Concept

---

## 1. Doel

Dit rapport vat samen:

- wat technisch en functioneel is getest;
- welke relevante bevindingen tijdens de implementatie zijn verwerkt;
- wat de huidige conclusies zijn over de betrouwbaarheid en bruikbaarheid van de tool.

---

## 2. Uitgevoerde tests

### 2.1 Geautomatiseerde tests

De huidige geautomatiseerde testset bestaat uit:

- `tests/test_data_manager.py`
- `tests/test_tariff_engine.py`
- `tests/test_sim_engine.py`
- `tests/test_result_calculator.py`
- `tests/test_capacity_sweep.py`
- `tests/test_exporter.py`
- `tests/test_scenario_runner.py`

Laatste uitgevoerde volledige testsuite:

- **Tooling:** `pytest`
- **Resultaat:** `65 passed`

Daarnaast zijn meerdere keren compile-checks uitgevoerd op onder meer:

- `src/main.py`
- `src/sim_engine.py`
- `src/result_calculator.py`
- `src/capacity_sweep.py`

Resultaat:

- **geen compile-fouten gevonden**

### 2.2 Gedekte onderdelen

De volgende onderdelen zijn aantoonbaar getest:

- inlezen en combineren van P1e-, solar- en prijsdata;
- P1e-differenties uit cumulatieve meterstanden;
- DST-afhandeling;
- solar-verdeling met energiebehoud;
- energiebalans;
- tariefberekeningen voor import en export;
- Modus 1 simulatie;
- slimme modus simulatie;
- 13:00 publicatieregel voor day-ahead prijzen;
- SoC-grenzen, laad- en ontlaadvermogen;
- financiële KPI's;
- technische KPI's;
- capaciteitssweep;
- exports naar CSV en Excel.

### 2.3 Handmatige en functionele controles

Tijdens de implementatie zijn daarnaast handmatig gecontroleerd:

- Streamlit-opstart;
- updateknopgedrag in plaats van directe rerun bij elke invoerwijziging;
- downloadgedrag zonder ongewenste reruns;
- zichtbaarheid en bruikbaarheid van grafieken;
- scenarioselectie voor `2024`, `2025` en gecombineerd;
- sweep met vaste marktopties;
- prestatie van de slimme modus.

---

## 3. Belangrijkste testbevindingen

### 3.1 Data en validatie

Bevestigd:

- de tool gebruikt niet alleen P1-data, maar ook de solar-data;
- huishoudverbruik wordt correct gereconstrueerd als:
  - `demand_kwh = import_kwh - export_kwh + solar_kwh`
- DST-gevallen en join-/kwaliteitsfouten worden gecontroleerd;
- solar-energiebehoud is afgedekt.

### 3.2 Simulatielogica

De oorspronkelijke opzet met drie modi is tijdens de implementatie aangescherpt.

Huidige werkende strategieën:

- **Modus 1**
  - alleen laden uit zonne-overschot
  - alleen ontladen naar huis
  - geen netladen
  - geen batterij-export

- **Slimme modus**
  - laden uit zonne-overschot
  - optioneel netladen voor later eigen verbruik
  - ontladen alleen naar huis
  - geen batterij-export

Bevestigd:

- de slimme modus kijkt vóór `13:00` alleen naar resterende prijzen van dezelfde dag;
- vanaf `13:00` mag de slimme modus naar de komende `24 uur` kijken;
- de slimme modus laadt niet blind vol;
- de slimme modus houdt rekening met verwachte tekorten vóór de volgende betekenisvolle zonne-laadkans;
- de slimme modus vermijdt te vroeg inkopen als later een gunstiger koopmoment beschikbaar is.

### 3.3 Kostenmodel

Bevestigd:

- de tool rekent zonder saldering;
- import en export worden apart afgerekend;
- terugleververgoeding is configureerbaar, inclusief `0.00 EUR/kWh`;
- dit maakt een 2027-achtig model zonder saldering mogelijk.

### 3.4 Analyse en KPI's

Toegevoegd en getest:

- jaarkosten zonder batterij;
- jaarkosten met batterij;
- jaarlijkse besparing;
- terugverdientijd;
- NCW;
- zelfvoorzienendheid;
- zelfconsumptie;
- cycli;
- SoC-statistieken;
- zonne-zelfconsumptie uitgesplitst naar:
  - direct zonder batterij
  - totaal met batterij
  - extra door batterij

### 3.5 Capaciteitssweep

Bevestigd:

- de sweep ondersteunt vaste marktopties;
- de sweep gebruikt nu standaard de actuele drie ingevoerde batterijopties:
  - `2.4 kWh`
  - `5.28 kWh`
  - `8.16 kWh`
- laad- en ontlaad-C-rate zijn gescheiden;
- de sweep toont jaarlijkse besparing per kWh batterijcapaciteit;
- aanbeveling werkt op:
  - hoogste NCW
  - kortste terugverdientijd
  - hoogste jaarlijkse besparing

### 3.6 Performance

De grootste prestatiebevinding was de slimme modus.

Eerdere situatie:

- slimme modus duurde ongeveer `32s` per jaar

Na optimalisatie:

- slimme modus duurt ongeveer `0.6s` per jaar

Conclusie:

- de tool is na optimalisatie snel genoeg voor normaal interactief gebruik in Streamlit

---

## 4. Inhoudelijke conclusies

### 4.0 Resultaten uit de huidige simulaties

De onderstaande uitkomsten zijn bepaald met de huidige standaardinstellingen van de tool:

- terugleververgoeding: `0.00 EUR/kWh`
- strategieën:
  - `Modus 1`
  - `Slimme modus`
- voorbeeldbatterij:
  - capaciteit `5.4 kWh`
  - laadvermogen `2.4 kW`
  - ontlaadvermogen `0.8 kW`
- slimme modus:
  - minimale prijsstijging `20%`

#### Resultaat 2024

**Modus 1**
- kosten met batterij: `362.35 EUR`
- jaarlijkse besparing: `223.54 EUR`
- zelfvoorzienendheid: `53.8%`
- zelfconsumptie: `70.2%`
- netladen: `0.0 kWh`

**Slimme modus**
- kosten met batterij: `351.92 EUR`
- jaarlijkse besparing: `233.96 EUR`
- zelfvoorzienendheid: `62.6%`
- zelfconsumptie: `70.2%`
- netladen: `326.53 kWh`

**Conclusie 2024**
- de slimme modus presteert beter dan Modus 1;
- het extra voordeel komt vooral uit minder netimport, niet uit extra zonne-zelfconsumptie;
- de winst is aanwezig, maar niet extreem groot.

#### Resultaat 2025

**Modus 1**
- kosten met batterij: `382.19 EUR`
- jaarlijkse besparing: `260.97 EUR`
- zelfvoorzienendheid: `58.2%`
- zelfconsumptie: `68.1%`
- netladen: `0.0 kWh`

**Slimme modus**
- kosten met batterij: `374.98 EUR`
- jaarlijkse besparing: `268.18 EUR`
- zelfvoorzienendheid: `64.4%`
- zelfconsumptie: `68.1%`
- netladen: `257.30 kWh`

**Conclusie 2025**
- ook in 2025 is de slimme modus beter dan Modus 1;
- het verschil blijft beperkt;
- de meerwaarde van slim netladen zit vooral in kostenreductie en hogere zelfvoorzienendheid, niet in een sterk hogere zonne-zelfconsumptie.

#### Zonne-zelfconsumptie

De tool laat nu expliciet zien:

**2024**
- directe zonne-zelfconsumptie zonder batterij: `836.5 kWh`
- extra zonne-zelfconsumptie door batterij:
  - Modus 1: `1075.4 kWh`
  - Slimme modus: `1074.1 kWh`

**2025**
- directe zonne-zelfconsumptie zonder batterij: `1105.6 kWh`
- extra zonne-zelfconsumptie door batterij:
  - Modus 1: `1180.6 kWh`
  - Slimme modus: `1180.4 kWh`

**Conclusie zonne-zelfconsumptie**
- bijna alle extra winst van de slimme modus komt niet uit extra benutting van zonne-energie;
- de slimme modus gebruikt vooral netladen om duurdere latere import te vermijden.

#### Capaciteitssweep met vaste marktopties

Doorgerekende opties:

| Capaciteit | Prijs | Jaarlijkse besparing | Terugverdientijd | NCW | Zelfvoorzienendheid | Zelfconsumptie |
|---|---:|---:|---:|---:|---:|---:|
| `2.4 kWh` | `1118.99 EUR` | `154.66 EUR` | `7.24 jaar` | `427.58 EUR` | `49.5%` | `54.7%` |
| `5.28 kWh` | `1847.99 EUR` | `248.72 EUR` | `7.43 jaar` | `639.24 EUR` | `63.2%` | `68.7%` |
| `8.16 kWh` | `2576.99 EUR` | `288.39 EUR` | `8.94 jaar` | `306.89 EUR` | `69.7%` | `74.4%` |

**Conclusie sweep**
- `5.28 kWh` is in het huidige model de sterkste middenweg;
- `8.16 kWh` levert nog extra besparing, maar tegen duidelijk meer investering;
- `8.16 kWh` heeft in deze simulatie een slechtere terugverdientijd en lagere NCW dan `5.28 kWh`;
- `2.4 kWh` is financieel verdedigbaar, maar laat technisch en energetisch meer waarde liggen.

### 4.1 Betrouwbaarheid van de tool

De huidige conclusie is:

- de tool is technisch stabiel genoeg om scenarioanalyses uit te voeren;
- de kernlogica voor data, kosten, simulatie en sweep is aantoonbaar getest;
- de huidige implementatie sluit redelijk goed aan op het gewenste 2027-gebruiksscenario zonder saldering.

### 4.2 Grenzen van het model

De huidige tool is een **conservatief beslismodel** en geen perfecte voorspeller.

Niet of beperkt gemodelleerd:

- leveranciersspecifieke HEMS-optimalisatie;
- realtime externe sturing;
- extra slimme aansturing van andere verbruikers zoals EV of warmtepomp;
- toekomstige afwijkingen van historische prijs- of verbruiksprofielen.

Daarom geldt:

- de tool is goed bruikbaar voor vergelijking en orde van grootte;
- de tool is minder geschikt om kleine verschillen als absolute waarheid te behandelen.

### 4.3 Conclusie voor batterijvergelijking

Op basis van de huidige simulaties en aannames:

- de middenvariant is financieel doorgaans de veiligere keuze;
- een grotere batterij kan verdedigbaar zijn als extra waarde wordt verwacht uit betere praktijksturing of HEMS-optimalisatie;
- het model ondersteunt dus een onderbouwde keuze, maar geen definitieve garantie op werkelijke opbrengst.

---

## 5. Open aandachtspunten

De belangrijkste resterende aandachtspunten zijn:

1. verdere verfijning van analysevisualisaties;
2. optioneel uploaden van eigen data in plaats van alleen `resources/`;
3. scenario's voor optimistischer of pessimistischer 2027-aannames;
4. eventueel explicieter modelleren van externe HEMS-meerwaarde.

---

## 6. Eindoordeel

**Eindoordeel huidige stand:**

- de tool is functioneel bruikbaar;
- de technische kern is goed getest;
- de huidige resultaten zijn geschikt voor verkennende investeringsanalyse;
- voor definitieve aankoopbeslissingen blijft interpretatie nodig, vooral waar leverancierssoftware in de praktijk beter kan sturen dan het huidige model.
