# TP-001 - Testplan: Thuisbatterij Simulator

**Document type:** Testplan  
**Project:** 023 Thuisbatterij  
**Versie:** 1.1  
**Datum:** 2026-04-27  
**Auteur:** Codex  
**Gebaseerd op:** URS-001 v1.6, FD-001 v1.8, DS-001 v1.2  
**Status:** Goedgekeurd  

---

## 1. Doel

Dit testplan beschrijft hoe wordt aangetoond dat de Thuisbatterij Simulator voldoet aan de goedgekeurde URS, FD en DS.

Het testplan dekt:

- unit tests voor losse functies en modules;
- integratietests voor de volledige datastroom;
- acceptatietests voor gebruikersgedrag en beslisondersteuning;
- regressietests voor bekende risicogebieden zoals DST, P1e-differenties, batterijmodi en exports.

---

## 2. Scope

### 2.1 In scope

- Inlezen en valideren van historische data uit `resources/`.
- P1e-differenties uit cumulatieve meterstanden.
- DST-afhandeling voor voorjaars- en najaarsovergang.
- Solar-verwerking met energiebehoud.
- Tariefberekeningen inclusief negatieve prijzen en ontbrekende prijzen.
- Batterijsimulatie voor Modus 1, Modus 2 en Modus 3.
- State of Charge, rendement, degradatie en jaarovergangen.
- Financiele en technische KPI's.
- Capaciteitssweep en optimale batterijgrootte.
- Analyse-uitvoer en exports.
- Lokale opstart via `start.bat`.

### 2.2 Out of scope voor v1

- Live koppelingen met externe API's.
- Voorspellende modellen voor toekomstige productie of verbruik.
- Automatische contractvergelijking tussen energieleveranciers.
- Validatie van echte aankoopprijzen buiten de door de gebruiker ingevoerde parameters.

---

## 3. Testniveaus

| Niveau | Doel | Tooling | Eigenaar |
|---|---|---|---|
| Unit test | Losse berekeningen aantonen | `pytest` | Codex |
| Integratietest | Volledige pipeline aantonen | `pytest`, tijdelijke testdata | Codex |
| UI smoke test | Dashboard start en basisinteractie | handmatig of Playwright later | Codex |
| Acceptatietest | Gebruikersdoelen aantonen | checklist met Rens | Claude Code + Rens |

---

## 4. Testdata

### 4.1 Productiedata

De bestanden in `resources/` zijn read-only en worden alleen gebruikt voor integratie- en acceptatietests. Tests mogen deze bestanden nooit wijzigen.

### 4.2 Synthetische testdata

Unit tests gebruiken kleine synthetische DataFrames. Deze data moet expliciet en controleerbaar zijn, bijvoorbeeld:

- 4 tot 8 kwartierintervallen voor batterijlogica;
- 1 dag met bekende lage/hoge prijzen voor Modus 2 en 3;
- mini-P1e-reeks met cumulatieve T1/T2-meterstanden;
- mini-DST-reeks met dubbele timestamps in najaar;
- uur-solarreeks waarbij de som na verdeling exact gelijk blijft.

### 4.3 Golden expected values

Voor kernalgoritmes worden expected values handmatig in de tests vastgelegd. Geen test mag alleen controleren dat code "niet crasht" als er een berekenbare uitkomst bestaat.

---

## 5. Unit Test Cases

### 5.1 DataManager

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-DM-001 | P1e T1/T2 import differenties | Interval-import = diff(import_t1 + import_t2) | UR-01, DS §4.1 |
| UT-DM-002 | P1e T1/T2 export differenties | Interval-export = diff(export_t1 + export_t2) | UR-01, DS §4.1 |
| UT-DM-003 | Eerste P1e-rij | Eerste rij wordt gemarkeerd of uitgesloten als `no_previous_reading` | DS §4.1 |
| UT-DM-004 | Negatieve P1e-differentie | Negatieve diff wordt als datakwaliteitsfout gemeld | FD FR-03, DS §10 |
| UT-DM-005 | DST voorjaar | Dag met ontbrekende 02:00-02:45 heeft 92 intervallen en melding | UR-05, DS §4.2 |
| UT-DM-006 | DST najaar | Dubbele lokale timestamps worden pas na diff gesommeerd | UR-05, DS §4.2 |
| UT-DM-007 | Solar uur naar kwartier | Som kwartierwaarden = oorspronkelijke uurwaarde | URS A-09, DS §4.3 |
| UT-DM-008 | Solar ontbrekende beginperiode | Solar = 0 en kwaliteitsmelding voor bekende nul-aanname | UR-16, DS §4.3 |
| UT-DM-009 | Energiebalans | `demand_kwh = import_kwh - export_kwh + solar_kwh` | UR-06, DS §4.4 |
| UT-DM-010 | Energiebalans tolerantie | Afwijking > 1% blokkeert simulatie | UR-17, FD FR-02 |

### 5.2 TariffEngine

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-TE-001 | Koopprijsberekening | `buy_price_eur_per_kwh` volgt FD-tariefformule | UR-02, DS §5 |
| UT-TE-002 | Verkoopprijsberekening | `sell_price_eur_per_kwh` volgt FD-tariefformule | UR-02, DS §5 |
| UT-TE-003 | Negatieve spotprijs | Negatieve prijzen worden toegestaan en correct doorgerekend | FD FR-04 |
| UT-TE-004 | Ontbrekende prijs | Energie blijft meetellen, intervalkosten = 0 en melding | FD FR-08, DS §10 |
| UT-TE-005 | Baselinekosten | Import kost geld, export verlaagt kosten | UR-09, DS §5.2 |
| UT-TE-006 | Batterijkosten | Kosten met batterij gebruiken import/export na batterij | UR-09, DS §5.2 |

### 5.3 SimEngine algemeen

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-SE-001 | SoC minimum | `soc_kwh` komt nooit onder `min_soc_kwh` | UR-06, FD FR-05 |
| UT-SE-002 | SoC maximum | `soc_kwh` komt nooit boven `max_soc_kwh` | UR-06, FD FR-05 |
| UT-SE-003 | Laadvermogen | Laden per kwartier <= `charge_power_kw * 0.25` | UR-03, DS §6.1 |
| UT-SE-004 | Ontlaadvermogen | Ontladen per kwartier <= `discharge_power_kw * 0.25` | UR-03, DS §6.1 |
| UT-SE-005 | Rendement | Laad- en ontlaadrendement worden apart toegepast | UR-03, DS §6.2 |
| UT-SE-006 | Geen gelijktijdig netladen en ontladen | Per interval is netladen en ontladen wederzijds uitsluitend | FD §3.3, DS §6.1 |
| UT-SE-007 | Jaarstart SoC | Elk simulatiejaar start met SoC 0 kWh | DS §6.3 |
| UT-SE-008 | Degradatie doorloop | Capaciteitsverlies loopt door van 2024 naar 2025 | FD §3.3, DS §6.3 |
| UT-SE-009 | Degradatie percentage | 2% per 100 cycli geeft correct verlies | UR-03, DS §6.3 |

### 5.4 SimEngine Modus 1

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-M1-001 | Laden uit solar | Zonne-overschot laadt batterij binnen grenzen | UR-04, DS §6.4 |
| UT-M1-002 | Geen netladen | `laad_uit_net_kwh = 0` voor alle intervallen | UR-04, DS §6.4 |
| UT-M1-003 | Ontladen naar huis | Ontladen is gecapt op huishoudvraag | UR-04, DS §6.4 |
| UT-M1-004 | Geen batterij-export | `ontlaad_naar_net_kwh = 0` voor alle intervallen | UR-04, DS §6.4 |

### 5.5 SimEngine Modus 2

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-M2-001 | Future max look-ahead | Hoogste toekomstige vermijdingsprijs binnen kalenderdag klopt | UR-04, DS §6.5 |
| UT-M2-002 | Geen look-ahead over daggrens | Laatste interval gebruikt geen prijs van volgende dag | DS §6.5 |
| UT-M2-003 | Netladen bij voordeel | Netladen alleen als prijsdelta groter is dan verlies + marge | UR-04, DS §6.5 |
| UT-M2-004 | Niet netladen zonder voordeel | Geen netladen als conditie niet waar is | UR-04, DS §6.5 |
| UT-M2-005 | Geen batterij-export | `ontlaad_naar_net_kwh = 0` voor alle intervallen | UR-04, DS §6.5 |
| UT-M2-006 | Solar prioriteit | Solar-lading gaat voor netlading | FD §3.3, DS §6.5 |

### 5.6 SimEngine Modus 3

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-M3-001 | Drempelvalidatie | `threshold_low >= threshold_high` blokkeert simulatie | FD FR-13, DS §10 |
| UT-M3-002 | Percentielvalidatie | `percentile_low >= percentile_high` blokkeert simulatie | FD FR-13, DS §10 |
| UT-M3-003 | Laden bij lage prijs | Netladen alleen als prijs- en margeconditie waar zijn | UR-04, DS §6.6 |
| UT-M3-004 | Margeformule | `expected_export_revenue * RTR - buy_price >= margin` wordt gebruikt | FD §3.3, DS §6.6 |
| UT-M3-005 | Export bij hoge prijs | Ontladen mag boven huishoudvraag uit naar netexport | UR-04, DS §6.6 |
| UT-M3-006 | Percentiel-exportopbrengst | Verwachte opbrengst gebruikt hoge-prijsintervallen binnen dezelfde dag | DS §6.6 |
| UT-M3-007 | Geen churn bij kleine marge | Batterij maakt geen cyclus als marge onvoldoende is | FD review, DS §6.6 |

### 5.7 ResultCalculator

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-RC-001 | Jaarlijkse besparing | Som intervalbesparingen klopt | UR-09, DS §7.1 |
| UT-RC-002 | Terugverdientijd | Aanschafprijs / jaarlijkse besparing klopt, inclusief nul/negatief geval | UR-09, DS §7.1 |
| UT-RC-003 | NCW | NCW volgt ingestelde horizon, discontovoet en indexatie | UR-09, DS §7.1 |
| UT-RC-004 | Technische KPI's | Import, export, cycles, losses en SoC-statistieken kloppen | UR-10, DS §7.2 |
| UT-RC-005 | Besparingsdecompositie | Componenten en eventuele restpost worden gerapporteerd | UR-21, DS §7.3 |
| UT-RC-006 | Sweep puntentelling | `floor((max-min)/step)+1` wordt gebruikt | UR-20, DS §7.4 |
| UT-RC-007 | Sweep max 200 | Meer dan 200 punten blokkeert simulatie | FD FR-11 |
| UT-RC-008 | Sweep handmatige prijstabel | Verkeerde lengte blokkeert simulatie | FD FR-12 |
| UT-RC-009 | Marginale meeropbrengst | Delta besparing per extra kWh klopt | UR-20, DS §7.4 |
| UT-RC-010 | Optimumcriteria | Aanbevolen capaciteit klopt per criterium | UR-20, DS §7.4 |
| UT-RC-011 | Gevoeligheidsanalyse | Varianten voor prijs, rendement, vergoeding en marge worden berekend | UR-21, DS §7.5 |

### 5.8 Exporter

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UT-EX-001 | Configuratie-CSV kolommen | Alle verplichte tijdreekskolommen aanwezig | UR-12, DS §9.1 |
| UT-EX-002 | KPI-export | KPI's en configuratieparameters aanwezig | UR-12, DS §9.2 |
| UT-EX-003 | Sweep-export | Sweepkolommen en aanbevolen-capaciteit-indicator aanwezig | UR-20, DS §9.3 |
| UT-EX-004 | Analyse-export | Excel bevat de afgesproken tabbladen | UR-21, DS §9.4 |
| UT-EX-005 | Reproduceerbaarheid | Export bevat modus, parameters en scenariojaar | UR-18, DS §9 |

---

## 6. Integratietests

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| IT-001 | Volledige pipeline 2024 | Data inlezen, simuleren en KPI's berekenen zonder onverwachte fout | UR-01 t/m UR-21 |
| IT-002 | Volledige pipeline 2025 | Data inlezen, simuleren en KPI's berekenen zonder onverwachte fout | UR-01 t/m UR-21 |
| IT-003 | Gecombineerde run 2024+2025 | Degradatie loopt door, SoC reset per jaar | DS §6.3 |
| IT-004 | Vier handmatige configuraties | Vier configuraties worden naast elkaar berekend en weergegeven | UR-07 |
| IT-005 | Modusvergelijking | Modus 1, 2 en 3 geven verschillende traceerbare energiestromen | UR-04 |
| IT-006 | Sweep kleine set | Sweep met 3 punten geeft correcte tabel en grafiekdata | UR-20 |
| IT-007 | Sweep 200 punten | Maximaal toegestane sweep blijft binnen acceptabele runtime | UR-20, FD FR-11 |
| IT-008 | Ontbrekende prijs | Energiebalans blijft intact, kosteninterval = 0, melding zichtbaar | FD FR-08 |
| IT-009 | Bekende nul-solarperiode | Solar = 0 in bekende periode en melding zichtbaar | URS A-09, FD FR-10 |
| IT-010 | Export na volledige run | CSV/Excel exports zijn te openen en bevatten data | UR-12 |

---

## 7. UI en Smoke Tests

| ID | Test | Acceptatiecriterium | Trace |
|---|---|---|---|
| UI-001 | `start.bat` zonder venv | Venv wordt aangemaakt, requirements geinstalleerd, Streamlit start | UR-14, DS §11 |
| UI-002 | `start.bat` met bestaande venv | Requirements worden opnieuw gecontroleerd/geinstalleerd | DS §11 |
| UI-003 | Datastatusscherm | Bestanden, DST-meldingen en datakwaliteit worden getoond | UR-16 |
| UI-004 | Modusafhankelijke velden | Modus 2/3 tonen alleen relevante velden | UR-15 |
| UI-005 | Simuleerknop | Simulatie start alleen met geldige configuratie | FD §5 |
| UI-006 | Resultatentabs | KPI's, grafieken, analyse en exports zijn bereikbaar | UR-11, UR-21 |
| UI-007 | Dark mode | Dashboard opent standaard in vastgelegde visuele stijl | FD §3.5 |

---

## 8. Acceptatietests met gebruiker

| ID | Scenario | Acceptatiecriterium |
|---|---|---|
| AT-001 | Rens laadt de standaard 2024/2025 data | Tool meldt dat data is ingelezen en toont datakwaliteit begrijpelijk |
| AT-002 | Rens simuleert Modus 1 met voorbeeldbatterij | Resultaat toont effect van zonne-overschot opslaan zonder netladen |
| AT-003 | Rens simuleert Modus 2 | Resultaat toont slim netladen zonder batterij-export |
| AT-004 | Rens simuleert Modus 3 | Resultaat toont arbitrage inclusief batterij-export |
| AT-005 | Rens vergelijkt meerdere batterijen | Dashboard maakt verschil in kosten, besparing en technische KPI's zichtbaar |
| AT-006 | Rens zoekt optimale batterijgrootte | Sweep toont aanbevolen capaciteit en marginale meeropbrengst |
| AT-007 | Rens exporteert resultaten | CSV/Excel kan buiten de tool worden gebruikt voor eigen analyse |
| AT-008 | Rens kan aankoopbeslissing onderbouwen | Tool toont terugverdientijd, NCW, break-even prijs en gevoeligheid |

---

## 9. Performance- en stresstests

De review op `chatreview.md` noemt terecht dat TP-001 v1.0 nog geen expliciete performancebenchmarks had. Onderstaande tests zijn meetpunten voor de implementatiefase. Als een grens niet wordt gehaald, is dat geen automatische functionele afkeur, maar wel een optimalisatie- of scopebesluit vóór acceptatie.

| ID | Test | Richtwaarde | Trace |
|---|---|---:|---|
| PT-001 | Volledige simulatie 1 jaar, 1 configuratie, zonder sweep | <= 10 seconden op laptop van gebruiker | UR-08, DS §6 |
| PT-002 | Volledige simulatie 2 jaar, 4 configuraties, zonder sweep | <= 30 seconden op laptop van gebruiker | UR-07, UR-08 |
| PT-003 | Sweep met 50 capaciteitspunten voor 2 jaar | <= 60 seconden op laptop van gebruiker | UR-20, DS §7.4 |
| PT-004 | Sweep met maximaal 200 capaciteitspunten voor 2 jaar | Meetbaar afronden zonder crash; runtime wordt gerapporteerd | UR-20, FD FR-11 |
| PT-005 | Export volledige tijdreeks voor 4 configuraties | CSV/Excel wordt gegenereerd zonder geheugenfout | UR-12, DS §9 |
| PT-006 | Dashboardrespons na parameterwijziging | UI blijft bruikbaar; lange run toont voortgangsindicator | UR-15, FD §3.5 |

Minimaal te loggen bij performance-tests:

- gebruikte datasetjaren;
- aantal configuraties;
- sweep aan/uit en aantal punten;
- runtime in seconden;
- piekgeheugen indien eenvoudig meetbaar;
- laptop/omgeving waarop is getest.

---

## 10. Regressierisico's

Deze gebieden krijgen bij elke betekenisvolle wijziging opnieuw tests:

- P1e-differenties en energiebalans.
- DST-voorjaar en DST-najaar.
- Modus 2 look-ahead.
- Modus 3 minimale marge en exportlogica.
- SoC-grenzen.
- Degradatie tussen jaren.
- Sweep puntentelling en optimumselectie.
- Exportkolommen.

---

## 11. Traceerbaarheid URS naar test

| URS | Testdekking |
|---|---|
| UR-01 | UT-DM-001 t/m UT-DM-004, IT-001, IT-002 |
| UR-02 | UT-TE-001 t/m UT-TE-006 |
| UR-03 | UT-SE-001 t/m UT-SE-009 |
| UR-04 | UT-M1-001 t/m UT-M3-007, IT-005 |
| UR-05 | UT-DM-005, UT-DM-006 |
| UR-06 | UT-DM-009, UT-SE-001 t/m UT-SE-006 |
| UR-07 | IT-004, AT-005, PT-002 |
| UR-08 | IT-001, IT-002, IT-003, PT-001, PT-002 |
| UR-09 | UT-RC-001 t/m UT-RC-003 |
| UR-10 | UT-RC-004 |
| UR-11 | UI-006 |
| UR-12 | UT-EX-001 t/m UT-EX-005, IT-010, AT-007, PT-005 |
| UR-13 | UI-001, UI-002 |
| UR-14 | UI-001, UI-002 |
| UR-15 | UI-003 t/m UI-006, PT-006 |
| UR-16 | UT-DM-004, UT-DM-008, IT-008, IT-009, UI-003 |
| UR-17 | UT-DM-010, IT-001, IT-002 |
| UR-18 | UT-EX-005 |
| UR-19 | UT-EX-001, UI-006 |
| UR-20 | UT-RC-006 t/m UT-RC-010, IT-006, IT-007, AT-006, PT-003, PT-004 |
| UR-21 | UT-RC-005, UT-RC-011, UT-EX-004, AT-008 |

---

## 12. Exitcriteria implementatiefase

Implementatie mag naar integratietest als:

- alle unit tests groen zijn;
- er geen bekende blocker in `DataManager`, `TariffEngine`, `SimEngine` of `ResultCalculator` open staat;
- testdata geen bestanden in `resources/` wijzigt;
- elke module minimaal de testgevallen uit dit plan heeft;
- alle bekende validatiefouten een duidelijke foutmelding hebben.

Integratietest mag naar acceptatietest als:

- IT-001 t/m IT-010 groen zijn;
- PT-001 t/m PT-006 zijn uitgevoerd en eventuele overschrijdingen zijn gedocumenteerd;
- exports handmatig geopend zijn;
- `start.bat` op een schone omgeving is getest;
- de belangrijkste KPI's plausibel zijn gecontroleerd tegen handmatige berekeningen op kleine datasets.

---

## 13. Goedkeuring

| Rol | Naam | Datum | Status |
|---|---|---|---|
| Opdrachtgever / Gebruiker | Rens Roosloot | 2026-04-27 | Goedgekeurd (v1.1) |
| Testontwerp | Codex | 2026-04-27 | Goedgekeurd (v1.1) |
| Acceptatiecriteria | Claude Code | 2026-04-27 | Goedgekeurd voor acceptatiefase |
