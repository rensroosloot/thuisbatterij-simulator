# FD-001 — Thuisbatterij Simulator

**Document type:** Functional Design  
**Project:** 023 Thuisbatterij  
**Versie:** 1.8  
**Datum:** 2026-04-27  
**Auteur:** Rens Roosloot  
**Gebaseerd op:** URS-001 v1.6 (goedgekeurd 2026-04-27)  
**Status:** Goedgekeurd

---

## 1. Doel en scope

Dit document beschrijft de functionele opbouw van de thuisbatterij-simulatietool. Het legt vast *wat* elke module doet, hoe de gebruiker de tool bedient, en welke functionele regels gelden voor berekeningen, foutafhandeling en uitvoer. De technische uitwerking (klassen, algoritmen, datastructuren) volgt in DS-001.

---

## 2. Systeemoverzicht

### 2.1 Contextdiagram

```
┌─────────────────────────────────────────────────────┐
│                    resources/                        │
│  P1e-CSV  │  Prijzen-CSV  │  HA-CSV  │  (PDF-ref)  │
└─────────────────────┬───────────────────────────────┘
                      │ inlezen bij opstart
                      ▼
             ┌────────────────┐
             │  Data Module   │  validatie, preprocessing,
             │                │  DST-afhandeling, solar-afleiding
             └───────┬────────┘
                     │ verwerkt tijdreeks (DataFrame)
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
 ┌────────────────┐   ┌──────────────────────┐
 │ Tariefmodule   │   │  Simulatie-engine     │
 │                │   │  (per strategie,      │
 │ kosten/opbrengst│  │   per configuratie)   │
 │ per interval   │   └──────────┬───────────┘
 └────────┬───────┘              │
          └──────────┬───────────┘
                     │ gesimuleerde tijdreeks + financiën
                     ▼
          ┌──────────────────┐
          │ Resultatenmodule │  KPI's, aggregaties
          └────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐    ┌────────────────┐
│   Dashboard   │    │ Exportmodule   │
│  (Streamlit)  │    │  (CSV/Excel)   │
│  lokaal       │    └────────────────┘
│  webbrowser   │
└───────────────┘
        ▲
        │ bediening
  [Gebruiker]
```

### 2.2 Moduloverzicht

| Module | Verantwoordelijkheid | URS-eisen |
|---|---|---|
| Data Module | Inlezen, valideren, preprocessen van alle bronbestanden | UR-01, UR-05, UR-16, UR-17 |
| Tariefmodule | Berekenen van inkoop- en terugleverkosten per interval | UR-02, UR-06 |
| Simulatie-engine | Uitvoeren van de batterijsimulatie per strategie en configuratie | UR-03, UR-04, UR-05, UR-06, UR-07, UR-08 |
| Resultatenmodule | Berekenen van financiële en technische KPI's | UR-09, UR-10, UR-17, UR-18 |
| Dashboard | Interactieve gebruikersinterface (configuratie + visualisaties) | UR-11, UR-13, UR-14, UR-15, UR-19 |
| Exportmodule | Exporteren van resultaten naar CSV/Excel | UR-12 |

---

## 3. Functionele modules

### 3.1 Data Module

**Doel:** alle bronbestanden inlezen, valideren en omzetten naar één samengestelde tijdreeks op 15-minuten-basis.

**Functie: Inlezen en valideren**
- Controleert aanwezigheid van de zes verplichte CSV-bestanden in `resources/`. Bij ontbreken: foutmelding met bestandsnaam, geen opstart.
- Parseert kolomkoppen en datatypes; bij afwijkend formaat: foutmelding met bestandsnaam en regelnummer.
- Detecteert gaten in de tijdreeks (ontbrekende kwartierintervals); registreert deze voor de datakwaliteitsmelding.

**Functie: P1e-verwerking**
- Leest cumulatieve meterstanden (`Import T1`, `Import T2`, `Export T1`, `Export T2`).
- Berekent per interval: `Δimport_kwh = (Import T1[t] + Import T2[t]) − (Import T1[t-1] + Import T2[t-1])` en analoog voor export. Negatieve differenties (meterrollover of datacorruptie) worden gemarkeerd als datakwaliteitswaarschuwing.
- DST-najaar: duplicaat-tijdstempels worden gedetecteerd, de twee energiedifferenties worden gesommeerd tot één interval.
- DST-voorjaar: ontbrekende 02:00–02:45-intervallen worden geregistreerd; de dag telt 92 meetpunten.

**Functie: Prijsdata-verwerking**
- Leest `datum_nl` en `prijs_excl_belastingen` (decimaalkomma → punt conversie).
- Join met P1e-data op `datum_nl` (Nederlandse lokale tijd).
- DST-voorjaar: geen actie vereist (beide datasets missen dezelfde intervallen).

**Functie: HA-solar-verwerking**
- Leest `sensor.gerardus_total_energieopbrengst_levenslang` (kWh cumulatief, uurlijks) voor 2024 en 2025.
- Berekent uurlijkse opwek als differentie van opeenvolgende waarden; negatieve waarden (reset of fout) worden op nul gezet en gemarkeerd.
- Interpoleert lineair van uur naar 15 minuten (elk uurinterval verdeeld in 4 gelijke kwartieren). Energiebehoud is gegarandeerd: de som van de vier kwartierwaarden is exact gelijk aan de afgeleide uurlijkse opwek (`kwartierwaarde = uurwaarde / 4` bij gelijke verdeling).
- **Periode 2024-01-01 00:00 t/m 2024-02-14 13:45:** zonopwek = 0,000 kWh per interval (geen cumulatieve beginmeterstand beschikbaar; winterperiode met verwaarloosbare productie). Wordt gemeld als datakwaliteitsmelding.
- Overige perioden: afgeleid uit cumulatieve sensor zoals hierboven.

**Functie: Samenstellen samengestelde tijdreeks**
- Combineert P1e-intervaldata, spotprijs en zonopwek in één tijdreeks per kwartier.
- Berekent huishoudverbruik per interval: `verbruik_kwh = import_kwh − export_kwh + solar_kwh`.
- Output: één DataFrame per jaar (of gecombineerd), geïndexeerd op Nederlandse lokale tijd.

**Functie: Verificatie energiebalans (UR-17)**
- Vergelijkt gesommeerde intervalwaarden met P1e-eindmeterstanden voor vier grootheden: totaal import, totaal export, cumulatief T1, cumulatief T2.
- Afwijking > 1% per grootheid: blokkerende foutmelding vóór simulatie.

**Functie: Datakwaliteitsrapport**
- Geeft een overzicht van: ontbrekende bestanden (geblokkeerd), DST-intervallen afgehandeld, nul-opwekperioden, gemarkeerde anomalieën. Dit rapport verschijnt bij opstart vóór de configuratiepagina.

---

### 3.2 Tariefmodule

**Doel:** bereken voor elk kwartierinterval de werkelijke inkoopkosten en terugleveropbrengst op basis van de geconfigureerde tarieven.

**Functie: Inkoop per interval**

```
kosten_inkoop = import_kwh × (spotprijs + inkoopvergoeding_inkoop + energiebelasting_inkoop)
```

**Functie: Teruglevering per interval**

```
opbrengst_teruglevering = export_kwh × (spotprijs + inkoopvergoeding_teruglevering + energiebelasting_teruggave)
```

Standaard is `energiebelasting_teruggave = 0,00 €/kWh` (post-2027-scenario zonder saldering). Door deze parameter op een positieve waarde in te stellen kunnen pre-2027-scenario's worden gesimuleerd.

**Functie: Netto intervalkosten (zonder batterij)**

```
netto_kosten = kosten_inkoop − opbrengst_teruglevering
```

**Functie: Vaste maandkosten**
- Worden eenmalig per maand opgeteld bij de jaarlijkse kostentotalen.
- Beïnvloeden de absolute jaarkosten maar niet de batterijbesparing (die is gebaseerd op de verandering in netto intervalkosten).

**Configureerbare parameters** (standaardwaarden uit URS §2.3, alle overschrijfbaar):

| Parameter | Standaard | Eenheid |
|---|---|---|
| Inkoopvergoeding inkoop | 0,01815 | €/kWh |
| Inkoopvergoeding teruglevering | 0,01850 | €/kWh |
| Energiebelasting inkoop | 0,12286 | €/kWh |
| Energiebelasting teruggave | 0,00000 | €/kWh |
| Vaste maandkosten (netto) | −8,66 | €/maand |
| Discontovoet (NCW) | 0,0 | % |
| Energieprijsindexatie (NCW) | 0,0 | % |
| Economische horizon | = batterijlevensduur | jaren |

---

### 3.3 Simulatie-engine

**Doel:** simuleer het gedrag van een thuisbatterij op de samengestelde tijdreeks voor een gegeven strategie en configuratie, en produceer een gesimuleerde tijdreeks met batterij-SoC en gecorrigeerde netuitwisseling.

**Configureerbare parameters per batterijconfiguratie (UR-03):**

| Parameter | Eenheid |
|---|---|
| Naam (label) | tekst |
| Bruikbare capaciteit | kWh |
| Maximaal laadvermogen | kW |
| Maximaal ontlaadvermogen | kW |
| Laadrendement | % |
| Ontlaadrendement | % |
| Minimum SoC | % van capaciteit |
| Maximum SoC | % van capaciteit |
| Levensduur | jaren |
| Cyclische degradatie | % capaciteitsverlies per 100 equivalente vollaadcycli (invoer in %, bijv. 2,0 voor 2%/100 cycli) |
| Aanschafprijs | € |

Tot vier configuraties kunnen gelijktijdig worden gesimuleerd op dezelfde dataset.

**Algemene regels (gelden voor alle modi)**

- Per interval is de batterij in precies één toestand: laden, ontladen of inactief. Gelijktijdig laden én ontladen is niet toegestaan.
- Solar heeft prioriteit als laadenergie-bron: indien solar-overschot beschikbaar is én de modus laden toestaat, laadt de batterij daar eerst uit.
- Na afhandeling van alle batterijacties:
  - `import_met_batterij_kwh = max(0, netto_na_solar − ontlaad_effectief_kwh + laad_uit_net_kwh)`
  - `export_met_batterij_kwh = max(0, overschot_na_solar − laad_uit_solar_kwh + ontlaad_surplus_kwh)`

---

**Modus 1 — Zelfconsumptie / nul-op-de-meter**

| Eigenschap | Waarde |
|---|---|
| Laadenergie-bron | Uitsluitend zonne-overschot |
| Netladen | Niet toegestaan |
| Ontlaad-sink | Uitsluitend huishoudvraag |
| Batterij-export naar net | Niet toegestaan |
| Doel | Export minimaliseren; dure import later vermijden |

Logica per kwartierinterval:
1. `netto = verbruik_kwh − solar_kwh`
2. `netto < 0` (zonne-overschot): laad batterij met `min(|netto|, max_laadvermogen_kwh, vrije_capaciteit_kwh / laadrendement)` — bron = solar.
3. `netto > 0` (huishoudvraag): ontlaad batterij met `min(netto, max_ontlaadvermogen_kwh, beschikbare_energie_kwh × ontlaadrendement)` — ontlading gecapt op netto; geen export vanuit batterij.
4. Resterende netto na batterijafhandeling → import of export van solar-overschot naar net.

---

**Slimme modus — Slim laden voor eigen verbruik**

| Eigenschap | Waarde |
|---|---|
| Laadenergie-bron | Zonne-overschot én net bij vervulde economische laadconditie |
| Netladen | Toegestaan als economische laadconditie vervuld (zie hieronder) |
| Ontlaad-sink | Uitsluitend huishoudvraag |
| Batterij-export naar net | Niet toegestaan |
| Doel | Goedkopere energie opslaan voor later eigen verbruik; dure import vermijden |

**Optimalisatieperiode**

De eenheid voor planningsbeslissingen is een **publicatie-afhankelijk look-ahead venster**. Dit sluit aan op de day-ahead marktstructuur waarin de prijzen voor de volgende 24 uur om 13:00 beschikbaar komen.

- Vóór 13:00 lokale tijd mag de simulatie alleen gebruikmaken van prijzen voor de resterende intervallen van dezelfde kalenderdag.
- Vanaf 13:00 lokale tijd mag de simulatie gebruikmaken van de komende 24 uur.

**Economische laadconditie voor netladen**

Netladen vanuit het net is in interval *t* uitsluitend toegestaan als aan **alle** onderstaande voorwaarden is voldaan:

*Voorwaarde 1 — Verwachte eigen vraag aanwezig vóór de volgende betekenisvolle zonne-laadkans:*
Er bestaat ten minste één later interval *t'* binnen het toegestane publicatievenster waarvoor geldt:
```
netto_baseline[t'] > 0
```
waarbij `netto_baseline = verbruik_kwh − solar_kwh` op basis van de ongewijzigde invoerdata (zonder enig batterij-effect). De benodigde reserve wordt begrensd tot het tekort vóór de volgende betekenisvolle zonne-laadkans; de batterij laadt dus niet alvast voor tekorten die dezelfde dag nog door solar kunnen worden opgevangen.

*Voorwaarde 2 — Economische rentabiliteit via prijsratio:*
```
verwachte_vermijdingsprijs >= laadprijs × max(1 / round_trip_rendement, 1 + minimale_prijsstijging_pct / 100)
```

*Voorwaarde 3 — Huidig interval is lokaal gunstig koopmoment:*
De huidige `laadprijs[t]` mag niet hoger zijn dan een later gepubliceerde koopprijs binnen hetzelfde look-ahead venster.

Waarbij:
- `laadprijs [€/kWh]` = spotprijs[t] + inkoopvergoeding_inkoop + energiebelasting_inkoop
- `verwachte_vermijdingsprijs [€/kWh]` = max(laadprijs[t']) over alle gepubliceerde toekomstige *t'* waarvoor `netto_baseline[t'] > 0` en *t'* > *t*
- `round_trip_rendement` = laadrendement × ontlaadrendement (als fractionele waarde, bijv. 0,90 × 0,92 = 0,828)
- `minimale_prijsstijging_pct` = configureerbaar, standaard 20%

De voorwaarde garandeert dat elke kWh die nu wordt ingeladen, later ook financieel voordeel oplevert voor eigen verbruik na correctie voor round-trip verlies en de ingestelde minimale prijsstijging.

**Configureerbare parameter (Slimme modus):**

| Parameter | Standaard | Eenheid |
|---|---|---|
| Minimale prijsstijging | 20 | % |

**Logica per kwartierinterval:**

1. `netto = verbruik_kwh − solar_kwh`
2. `netto < 0` (zonne-overschot): laad batterij vanuit solar (zie Modus 1, stap 2).
3. `netto ≥ 0` én SoC < max SoC: evalueer de economische laadconditie.
   - Bepaal `verwachte_vermijdingsprijs` = max(laadprijs) over gepubliceerde toekomstige intervallen met `netto_baseline > 0`.
   - Controleer de prijsratio en het lokale koopmoment.
   - Bij vervulling: laad vanuit net met `min(max_laadvermogen_kwh, vrije_capaciteit_kwh / laadrendement)`. De batterij ontlaadt **niet** in dit interval (laden en ontladen zijn wederzijds uitsluitend; zie algemene regels).
4. Laadconditie stap 3 **niet** vervuld én SoC > min SoC én netto > 0: ontlaad batterij met `min(netto, max_ontlaadvermogen_kwh, beschikbare_energie_kwh × ontlaadrendement)` — ontlading gecapt op netto; geen export.
5. Resterende netto → import of solar-export naar net.

**SoC-tracking:**
- SoC wordt bijgehouden in kWh (niet alleen %). Min/max SoC-grenzen worden afgedwongen per interval.
- Begin-SoC bij aanvang van elk simulatiejaar: 0 kWh (lege batterij).

**Degradatie:**
- Invoerparameter: `degradatie_pct_per_100_cycli` (bijv. 2,0 = 2% per 100 cycli).
- Equivalente vollaadcycli per jaar: `cycli_jaar = totale_laadenergie_jaar_kwh / nominale_capaciteit_kwh`
- Capaciteitsverlies per jaar: `verlies_kwh = cycli_jaar × (degradatie_pct_per_100_cycli / 100) × nominale_capaciteit_kwh / 100`
- De effectieve capaciteit aan het begin van jaar t: `capaciteit_t = nominale_capaciteit − som(verlies_kwh jaren 1..t-1)`
- Minimale resterende capaciteit: 0 kWh (batterij buiten gebruik als capaciteit ≤ 0).

---

**Capaciteitsoptimalisatie-modus**

De simulatie-engine ondersteunt naast de maximaal vier handmatige configuraties een geautomatiseerde **capaciteitssweep**: de engine voert de simulatie uit voor elke capaciteit in een door de gebruiker opgegeven bereik. Elke capaciteitswaarde wordt als één afzonderlijke configuratie gesimuleerd; de modus (1, 2 of 3) en alle tariefparameters zijn gelijk voor alle sweeppunten.

**Sweep-parameters:**

| Parameter | Eenheid | Beschrijving |
|---|---|---|
| Minimale capaciteit | kWh | Beginwaarde van het bereik |
| Maximale capaciteit | kWh | Eindwaarde van het bereik |
| Stapgrootte | kWh | Interval tussen opeenvolgende sweeppunten |
| Modus | 1 / 2 / 3 | Bedrijfsmodus, gelijknamig aan §3.3 |
| Minimale marge (bij Modus 2 en 3) | €/kWh | Idem Modus 2/3 configureerbare parameter |
| Beslisregel (bij Modus 3) | Drempel / Percentiel | Idem Modus 3 configureerbare parameter |

Aantal sweeppunten: `N = floor((cap_max − cap_min) / cap_stap) + 1`. Maximaal 200 sweeppunten (FR-11).

**Vermogensschaling per sweeppunt:**

Keuze uit twee methoden:

- **Vast vermogen:** `max_laadvermogen_kw` en `max_ontlaadvermogen_kw` zijn absolute waarden, onafhankelijk van capaciteit.
- **C-rate:** `max_laadvermogen_kw = C_laad × capaciteit_kwh`; `max_ontlaadvermogen_kw = C_ontlaad × capaciteit_kwh`. C-rate-waarden worden ingevoerd als positieve ratiowaarde (bijv. 0,5 voor 0,5C = volladen in 2 uur).

Overige parameters (rendementen, min/max SoC, levensduur, degradatie) zijn gemeenschappelijk voor alle sweeppunten.

**Aanschafprijsmodel:**

| Model | Formule | Invoer |
|---|---|---|
| Lineair | `aanschafprijs_eur = basisprijs_eur + prijs_per_kwh_eur × capaciteit_kwh` | Basisprijs (€) en prijs per kWh capaciteit (€/kWh) |
| Handmatig | Vaste prijs per sweeppunt | Tabel met één prijs per capaciteitswaarde (FR-12) |

---

### 3.4 Resultatenmodule

**Doel:** bereken alle KPI's uit de gesimuleerde tijdreeks en produceer de invoer voor het dashboard en de exportmodule.

**Financiële KPI's (UR-09):**

| KPI | Berekening |
|---|---|
| Jaarkosten zonder batterij | Som netto intervalkosten + vaste maandkosten × 12 |
| Jaarkosten met batterij | Som gecorrigeerde netto intervalkosten + vaste maandkosten × 12 |
| Jaarlijkse besparing | Jaarkosten zonder − Jaarkosten met batterij |
| Terugverdientijd | Aanschafprijs / jaarlijkse besparing (simpel); of via NCW-berekening |
| NCW | Som van (jaarlijkse besparing_jaar_t / (1 + discontovoet)^t) − aanschafprijs, over economische horizon |

**Technische KPI's (UR-10):**

| KPI | Berekening |
|---|---|
| Zelfvoorzienendheidsgraad | (verbruik gedekt door solar + batterij) / totaal verbruik × 100% |
| Zelfconsumptiegraad | (solar gebruikt in huis of batterij) / totale solar × 100% |
| Equivalente vollaadcycli/jaar | totale laadenergie / nominale capaciteit |
| Resterende levensduur (cycli) | maximale cycli uit specs − gecumuleerde cycli |

**Aggregaties beschikbaar voor dashboard:**
- Per kwartier (ruwe simulatie-output)
- Per dag
- Per maand
- Per jaar

**Sweepresultaten (bij capaciteitsoptimalisatie):**

Na de capaciteitssweep wordt voor elk sweeppunt de volledige KPI-set berekend. De resultatenmodule levert een tabel met per sweeppunt:

`capaciteit_kwh`, `aanschafprijs_eur`, `jaarlijkse_besparing_eur`, `terugverdientijd_jr`, `ncw_eur`, `zelfvoorzienendheid_pct`, `zelfconsumptie_pct`, `cycli_jaar`

**Marginale meeropbrengst per extra kWh capaciteit:**

Voor elk aangrenzend paar sweeppunten (i, i+1) met stapgrootte `cap_stap`:

```
marginale_ncw_eur_per_kwh       = (ncw[i+1] − ncw[i]) / cap_stap
marginale_besparing_eur_per_kwh = (jaarlijkse_besparing[i+1] − jaarlijkse_besparing[i]) / cap_stap
```

De marginale meeropbrengst maakt zichtbaar hoeveel extra NCW of besparing elke extra kWh capaciteit oplevert. Waar deze sterk daalt, is groter kopen nauwelijks meer rendabel.

**Optimale capaciteit per criterium:**

| Criterium | Definitie |
|---|---|
| Hoogste NCW | capaciteit met `max(ncw_eur)` |
| Kortste terugverdientijd | capaciteit met `min(terugverdientijd_jr)` |
| Hoogste jaarlijkse besparing | capaciteit met `max(jaarlijkse_besparing_eur)` |
| Marginale drempel | kleinste capaciteit waarvoor `marginale_ncw_eur_per_kwh < drempelwaarde`; de drempelwaarde is configureerbaar (€/kWh extra capaciteit, standaard 50,00) |

De aanbevolen capaciteit wordt in het dashboard gemarkeerd met het bijbehorende criterium en de bijbehorende KPI-waarden.

**Analyse- en beslisondersteuning (v1):**

De resultatenmodule levert naast KPI's ook analyse-uitvoer die verklaart waarom een configuratie
financieel en technisch goed of slecht scoort.

**Besparingsdecompositie per configuratie:**

| Component | Betekenis |
|---|---|
| Minder netimport door zonne-opslag | Besparing doordat zonne-overschot later eigen verbruik dekt |
| Slim laden voor eigen verbruik | Besparing doordat goedkoop geladen netstroom dure latere import voorkomt |
| Batterij-export | Opbrengst doordat batterij-energie aan het net wordt geleverd |
| Round-trip verlies | Kosten/effect van laad- en ontlaadverlies in kWh en euro |
| Degradatie-effect | Vermindering van besparing door lagere effectieve capaciteit over de horizon |
| Netto totaalbesparing | Som van bovenstaande componenten |

**Batterijbenutting per configuratie:**

| Metric | Betekenis |
|---|---|
| Dagen max SoC bereikt | Percentage dagen waarop batterij vol raakt |
| Dagen min SoC bereikt | Percentage dagen waarop batterij leeg/minimum bereikt |
| Gemiddelde SoC per maand | Gemiddelde batterijvulling per kalendermaand |
| Ongebruikte capaciteit | Gemiddelde vrije capaciteit tijdens zonne-overschot |
| Gemiste zonne-opslag | Zonne-energie die niet kon worden opgeslagen door volle batterij of laadvermogenslimiet |
| Gemiste vraagdekking | Huishoudvraag die niet kon worden gedekt door lege batterij of ontlaadvermogenslimiet |

**Maand- en seizoensanalyse per configuratie:**

Per maand worden minimaal berekend:
`import_zonder_batterij_kwh`, `import_met_batterij_kwh`, `export_zonder_batterij_kwh`,
`export_met_batterij_kwh`, `netladen_kwh`, `batterij_export_kwh`,
`batterij_laadenergie_kwh`, `batterij_ontlaadenergie_kwh`, `besparing_eur`,
`cycli`, `zelfvoorzienendheid_pct`, `zelfconsumptie_pct`.

**Beperkte gevoeligheidsanalyse:**

Voor een gekozen handmatige configuratie of voor de aanbevolen capaciteit uit de sweep kan de tool
vaste scenario's doorrekenen:

| Parameter | Scenario's |
|---|---|
| Batterijprijs | -25%, basis, +25% |
| Energieprijsniveau | -25%, basis, +25% |
| Rendement | -5 procentpunt, basis, +5 procentpunt |
| Terugleververgoeding | -25%, basis, +25% |
| Minimale marge | basis, basis + 0,02 €/kWh |

Output per scenario: `jaarlijkse_besparing_eur`, `terugverdientijd_jr`, `ncw_eur` en, indien
capaciteitssweep actief is, of de aanbevolen capaciteit gelijk blijft of verschuift.

**Break-even analyse:**

Per handmatige configuratie en per sweeppunt berekent de tool:
- maximale aanschafprijs waarbij `NCW >= 0`
- verschil tussen opgegeven aanschafprijs en break-even aanschafprijs
- break-even terugverdientijd indien jaarlijkse besparing > 0

**Uitleg bij aanbevolen capaciteit:**

Bij capaciteitsoptimalisatie toont de tool een tekstuele verklaring met:
- gekozen optimalisatiecriterium
- aanbevolen capaciteit
- belangrijkste KPI's
- marginale meeropbrengst bij de eerstvolgende grotere capaciteit
- korte reden waarom groter of kleiner minder gunstig is

---

### 3.5 Dashboard

**Doel:** interactieve lokale webapplicatie (Streamlit) waarmee de gebruiker de simulatie configureert, uitvoert en resultaten bekijkt.

**Opstarten voor niet-coders**

De applicatie wordt geleverd met een dubbelklikbaar opstartbestand (`start.bat` op Windows) dat:
1. Controleert of Python aanwezig is; bij ontbreken: foutmelding met downloadinstructie.
2. Maakt een project-lokale virtual environment aan in `venv/` (indien nog niet aanwezig) en activeert deze; packages worden daarmee geïsoleerd van de globale Python-installatie.
3. Installeert of verifieert de vereiste packages uit `requirements.txt`; ontbrekende packages worden automatisch geïnstalleerd.
4. Start de Streamlit-server lokaal.
5. Opent automatisch de browser op de applicatiepagina.

De gebruiker hoeft geen terminal te openen of commando's te typen. Alle interactie verloopt via de webbrowser.

---

**Visuele stijl en UX**

*Thema*
- Standaard: dark mode. Toggle beschikbaar in de sidebar om te wisselen naar light mode.
- Technische implementatie: `.streamlit/config.toml` met `base = "dark"`; accentkleur paars/indigo (primaire kleur ~`#6C63FF`).
- Light mode gebruikt dezelfde accentkleur op witte/lichtgrijze achtergrond.

*KPI-kaarten (Scherm 3)*
- Elke kaart heeft een donkere achtergrond met een subtiele indigo-rand of -tint.
- Lay-out per kaart: klein label bovenaan → groot vet getal als centrale waarde → delta t.o.v. "Zonder batterij" onderin.
- Delta-kleurcodering:
  - Positief (besparing, hogere zelfvoorzienendheid): groen, pijl omhoog (▲)
  - Negatief (hogere kosten, negatieve NCW): rood, pijl omlaag (▼)
  - Neutraal / niet van toepassing: grijs

*Grafieken (Plotly)*
- Donkere plotachtergrond consistent met app-thema.
- Kleurenschema per configuratie: Config 1 = indigo, Config 2 = teal, Config 3 = oranje, Config 4 = geel; sweep-lijn = lichtgrijs of wit.
- Subtiele gridlijnen; geen overbodige decoratie; tooltips volledig ingeschakeld.

*Algemene UX*
- Sidebar voor navigatie tussen schermen en thema-toggle.
- Ruime padding tussen secties; invoervelden altijd vooringevuld met standaardwaarden.
- Foutmeldingen: rood tekstblok met klare omschrijving — geen technische stacktraces zichtbaar voor de gebruiker.

---

**Scherm 1 — Datakwaliteitsrapport (automatisch bij opstart)**

Toont bij elke opstart:
- Groen vinkje per verplicht bestand dat aanwezig en geldig is; rood kruis bij ontbrekend of ongeldig bestand (opstart geblokkeerd).
- Tabel met datakwaliteitsmeldingen: type melding, periode, beschrijving.
- DST-meldingen: welke dag(en) zijn afgehandeld en hoe.
- Energiebalanscheck: afwijking per grootheid ten opzichte van P1e-eindmeterstand; blokkering als > 1%.
- Knop "Doorgaan naar configuratie" (alleen actief als alle verplichte bestanden geldig zijn en energiebalanscheck geslaagd is).

**Scherm 2 — Configuratie**

Vier panelen naast elkaar of in tabbladen:

*Paneel A — Scenario*
- Keuze scenariojaar: 2024 / 2025 / 2024+2025 gecombineerd
- Tarieven (alle velden met standaardwaarden vooringevuld, overschrijfbaar)
- NCW-parameters

*Paneel B — Batterijconfiguraties*
- Vier configuratie-slots (Config 1 t/m 4); elke slot heeft een aan/uit-schakelaar
- Per slot: alle UR-03-parameters, met een naamveld (bijv. "SolarFlow 5 kWh")
- Moduskeuze per slot (keuzelijst met twee opties):
  - **Modus 1 — Zelfconsumptie / nul-op-de-meter**
  - **Slimme modus — Slim laden voor eigen verbruik**
- Bij **Slimme modus**: aanvullende invoeroptie verschijnt:
  - Invoerveld "Minimale prijsstijging (%)" (standaard 20) — de slimme modus gebruikt geen batterij-exportregels
  - Invoerveld "Minimale marge arbitrage" (€/kWh, standaard 0,00) — geldt voor beide beslisregels

*Paneel C — Capaciteitsoptimalisatie (optioneel)*
- Schakelaar "Capaciteitsoptimalisatie inschakelen"
- Bij ingeschakeld:
  - Invoervelden: minimale capaciteit (kWh), maximale capaciteit (kWh), stapgrootte (kWh)
  - Moduskeuze (Modus 1 / 2 / 3); aanvullende velden per modus overeenkomstig Paneel B
  - Vermogensschaling: keuzelijst "Vast vermogen" of "C-rate"
    - Vast vermogen: invoerveld maximaal laadvermogen (kW) en maximaal ontlaadvermogen (kW)
    - C-rate: invoerveld C_laad en C_ontlaad (bijv. 0,5)
  - Gemeenschappelijke parameters voor alle sweeppunten: laadrendement (%), ontlaadrendement (%), minimum SoC (%), maximum SoC (%), levensduur (jaren), degradatie (% per 100 cycli)
  - Aanschafprijsmodel: keuzelijst "Lineair" of "Handmatig"
    - Lineair: invoerveld basisprijs (€) en prijs per kWh capaciteit (€/kWh)
    - Handmatig: tabel met capaciteitspunten (automatisch gegenereerd) en prijs per punt (€)
  - Optimalisatiecriterium: keuzelijst
    - Hoogste NCW
    - Kortste terugverdientijd
    - Hoogste jaarlijkse besparing
    - Marginale drempel
    - Bij "Marginale drempel": invoerveld drempelwaarde (€/kWh extra capaciteit, standaard 50,00)

*Paneel D — Uitvoeren*
- Knop "Simuleer"; voortgangsindicator tijdens berekening (handmatige configuraties en sweep worden in één run uitgevoerd)
- Na afloop: automatisch doorsturen naar Scherm 3

**Scherm 3 — Resultaten**

Bovenaan: KPI-kaarten per actieve configuratie (en "Zonder batterij" als referentie):
- Jaarkosten, Jaarlijkse besparing, Terugverdientijd, NCW, Zelfvoorzienendheid%, Zelfconsumptie%, Cycli/jaar

Daaronder: tabbladen voor de vijf verplichte grafieken (UR-11):

| Tabblad | Grafiek | Interactiviteit |
|---|---|---|
| Dagprofiel | Verbruik, opwek, SoC, netimport op tijdas (15 min) | Datumkiezer; keuze gemiddelde dag of specifieke dag |
| Maandoverzicht | Gestapeld staafdiagram: import, export, batterijgebruik per maand | Toggle per configuratie |
| Prijsheatmap | Spotprijs per uur van de dag × maand (kleurschaal) | Jaarkeuze |
| Vergelijking | Besparing per configuratie naast elkaar (staafdiagram) | Sorteervolgorde |
| Terugverdientijd | Cumulatieve besparing vs. investering over tijd (lijndiagram) | Horizon-slider |
| Ruwe data | Pagineerbare tabel met alle UR-06-velden per kwartierinterval (UR-19) | Datumfilter, configuratiekeuze, zoekbalk op tijdstempel |
| Capaciteitsoptimalisatie | Dubbel diagram: (1) lijndiagram capaciteit (x-as) × gekozen KPI (y-as: NCW / jaarlijkse besparing / terugverdientijd, wisselbaar); (2) staafdiagram marginale meeropbrengst per extra kWh; verticale markering van aanbevolen capaciteit per gekozen criterium; KPI-kaart voor de aanbevolen capaciteit. Tabblad zichtbaar alleen als sweep ingeschakeld is. | Y-as-keuze per grafiek; criteriumkeuze voor markering; drempelwaarde marginale meeropbrengst als horizontale referentielijn |

Aanvullende analyse-tabbladen:

| Tabblad | Inhoud | Interactiviteit |
|---|---|---|
| Beslisanalyse | Besparingsdecompositie, batterijbenutting, maandanalyse, break-even resultaten en tekstuele uitleg bij aanbevolen capaciteit | Configuratiekeuze; maandfilter; componenten aan/uit |
| Gevoeligheid | Tabel met beperkte gevoeligheidsanalyse voor batterijprijs, energieprijsniveau, rendement, terugleververgoeding en minimale marge | Keuze handmatige configuratie of aanbevolen sweep-capaciteit |

**Scherm 4 — Export**
- Knop "Download CSV": per actieve handmatige configuratie een CSV met de volledige gesimuleerde tijdreeks (alle UR-06-velden per kwartier).
- Knop "Download Excel": één werkboek met tabbladen per handmatige configuratie + KPI-overzichtstabblad.
- Knop "Download KPI-samenvatting CSV": alleen de KPI-tabel van de handmatige configuraties.
- Knop "Download sweep CSV" (alleen zichtbaar als sweep ingeschakeld): tabel met per sweeppunt alle KPI's + marginale meeropbrengst.
- Knop "Download sweep Excel" (alleen zichtbaar als sweep ingeschakeld): werkboek met één tabblad "Capaciteitsoptimalisatie" met dezelfde kolommen als de sweep CSV.
- Knop "Download analyse Excel": werkboek met besparingsdecompositie, batterijbenutting, maandanalyse, gevoeligheidsanalyse, break-even resultaten en aanbevelingsuitleg.

---

### 3.6 Exportmodule

**Doel:** genereer downloadbare bestanden vanuit de gesimuleerde tijdreeks en resultaten.

**CSV per configuratie** bevat per rij (kwartierinterval):
`timestamp_nl`, `solar_kwh`, `verbruik_kwh`, `import_zonder_batterij_kwh`, `export_zonder_batterij_kwh`, `soc_kwh`, `soc_pct`, `laad_kwh`, `ontlaad_kwh`, `import_met_batterij_kwh`, `export_met_batterij_kwh`, `spotprijs_eur_kwh`, `kosten_interval_eur`, `besparing_interval_eur`

**Excel** bevat dezelfde kolommen per configuratie in een apart tabblad, plus een `KPI`-tabblad met de resultatenmodule-output.

**Capaciteitssweep-export (bij ingeschakelde sweep):**

CSV-bestand `sweep_resultaten.csv` bevat per rij (sweeppunt):
`capaciteit_kwh`, `aanschafprijs_eur`, `jaarlijkse_besparing_eur`, `terugverdientijd_jr`, `ncw_eur`, `zelfvoorzienendheid_pct`, `zelfconsumptie_pct`, `cycli_jaar`, `marginale_ncw_eur_per_kwh`, `marginale_besparing_eur_per_kwh`

Excel-tabblad `Capaciteitsoptimalisatie` bevat dezelfde kolommen. Het aanbevolen capaciteitspunt (per gekozen criterium) is gemarkeerd in een aparte kolom `aanbevolen`.

**Analyse-export:**

Excel-bestand `analyse_resultaten.xlsx` bevat minimaal de volgende tabbladen:
- `Besparingsdecompositie`
- `Batterijbenutting`
- `Maandanalyse`
- `Gevoeligheidsanalyse`
- `BreakEven`
- `Aanbeveling`

Alle analyse-tabbladen bevatten configuratienaam, modus, scenariojaar en relevante parameterwaarden
zodat de export zelfstandig interpreteerbaar is.

---

## 4. Gebruikersinteractieflow

```
Opstart
  │
  ▼
[Datakwaliteitsrapport]
  │ alle checks OK?
  ├─ Nee ──► Foutmelding; geen verdere actie mogelijk
  └─ Ja ───► [Configuratiescherm]
                │
                │ gebruiker stelt in en klikt "Simuleer"
                ▼
             [Simulatie draait] ── voortgangsindicator
                │
                ▼
             [Resultatenscherm]
                │
                ├──► grafieken bekijken (tabbladen)
                ├──► parameters aanpassen → terug naar Configuratie
                └──► [Exportscherm] ── download knop(pen)
```

---

## 5. Functionele gedragsregels

| Regel | Situatie | Gedrag |
|---|---|---|
| FR-01 | Verplicht CSV-bestand ontbreekt | Opstart geblokkeerd; foutmelding met bestandsnaam |
| FR-02 | Energiebalansafwijking > 1% | Simulatie geblokkeerd; foutmelding met afwijkingspercentage per grootheid |
| FR-03 | Negatieve P1e-differentie | Waarschuwing in datakwaliteitsrapport; interval op 0 kWh gezet |
| FR-04 | Spotprijs ≤ 0 (negatieve prijzen) | Toegestaan; de formules werken correct met negatieve waarden (terugleveren levert kosten op, inkopen genereert opbrengst) |
| FR-05 | Batterij-SoC bereikt min/max grens | Laden/ontladen wordt begrensd; geen over- of onderschrijding |
| FR-06 | Batterijcapaciteit na degradatie ≤ 0 | Batterij wordt als buiten gebruik beschouwd; resterende jaren: geen batterijeffect |
| FR-07 | Geen enkele batterijconfiguratie actief | Simulatie draait "zonder batterij"-scenario als referentie; geen vergelijkingsgrafieken |
| FR-08 | Spotprijs ontbreekt voor een interval (join-miss) | Energievolumes (import, export, solar) worden wél volledig meegeteld in energiebalans en UR-17-verificatie. Alleen de kosten voor dat interval worden op € 0,00 gezet. Gemeld in datakwaliteitsrapport met tijdstempel en aantal getroffen intervallen. |
| FR-09 | Dezelfde parameters, zelfde data | Identieke uitvoer (deterministisch; UR-18) |
| FR-10 | Nul-opwekperiode (A-09) | Verwerkt als solar = 0 kWh; gemeld in datakwaliteitsrapport |
| FR-11 | Capaciteitssweep overschrijdt 200 sweeppunten | Foutmelding vóór simulatie met berekend aantal punten; simulatie geblokkeerd tot stapgrootte wordt vergroot |
| FR-12 | Handmatig prijsmodel sweep: aantal rijen in prijstabel ≠ N sweeppunten | Foutmelding; simulatie geblokkeerd tot tabel is aangevuld of aanschafprijsmodel is gewijzigd naar Lineair |
| FR-13 | Modus 3 drempelwaarde: `drempel_laag ≥ drempel_hoog`; of percentiel: `P_laag ≥ P_hoog` | Foutmelding bij configuratie-invoer; simulatie geblokkeerd — laad- en exportconditie mogen niet gelijktijdig actief zijn in hetzelfde interval |

---

## 6. Traceerbaarheid URS → FD

| URS-eis | FD-sectie |
|---|---|
| UR-01 | §3.1 Inlezen en valideren |
| UR-02 | §3.2 Tariefmodule, Configureerbare parameters |
| UR-03 | §3.3 Configureerbare parameters per batterijconfiguratie |
| UR-04 | §3.3 Modus 1 (Zelfconsumptie), Modus 2 (Slim laden zonder teruglevering), Modus 3 (Slim laden met teruglevering) |
| UR-05 | §3.1 DST-afhandeling |
| UR-06 | §3.3 SoC-tracking; §3.4 Financiële KPI's |
| UR-07 | §3.3 "Tot vier configuraties" |
| UR-08 | §3.5 Scherm 2 Paneel A — Scenariokeuze |
| UR-09 | §3.4 Financiële KPI's |
| UR-10 | §3.4 Technische KPI's |
| UR-11 | §3.5 Scherm 3 — vijf grafiek-tabbladen |
| UR-12 | §3.6 Exportmodule |
| UR-13 | §2.1 Contextdiagram (lokale Streamlit-app) |
| UR-14 | §3.5 Dashboard (enkelvoudig opstart-commando) |
| UR-15 | §3.5 Dashboard (interactief; parameters live aanpasbaar) |
| UR-16 | §3.1 Datakwaliteitsrapport; §3.5 Scherm 1 |
| UR-17 | §3.1 Verificatie energiebalans |
| UR-18 | §5 FR-09 |
| UR-19 | §3.5 Scherm 3 — tabblad "Ruwe data" (pagineerbare tabel per kwartierinterval) |

**Uitbreidingen buiten URS-001 v1.4 (FD v1.6):**

De onderstaande analyse- en beslisondersteunende functies zijn op verzoek van de gebruiker toegevoegd tijdens de FD-fase. Aanbevolen actie: UR-21 toevoegen aan URS-001 voordat DS start.

| FD-sectie | Beschrijving |
|---|---|
| §3.3 Capaciteitsoptimalisatie-modus | Sweep, vermogensschaling, aanschafprijsmodel |
| §3.4 Sweepresultaten, marginale meeropbrengst, optimale capaciteit | KPI-tabel sweep + marginale berekening + criteriumselectie |
| §3.5 Paneel C, tabblad Capaciteitsoptimalisatie | Dashboard-invoer en -visualisatie sweep |
| §3.6 Capaciteitssweep-export | CSV/Excel-export sweep |
| §5 FR-11, FR-12 | Validatieregels sweep |
| §3.4 Analyse- en beslisondersteuning | Besparingsdecompositie, batterijbenutting, maandanalyse, gevoeligheid, break-even, aanbevelingsuitleg |
| §3.5 Tabbladen Beslisanalyse en Gevoeligheid | Dashboardweergave analyse-uitvoer |
| §3.6 Analyse-export | Excel-export van alle analysegegevens |

---

## 7. Reviewhistorie

| Reviewdatum | Reviewer | Bevinding | Verwerkt in | Actie |
|---|---|---|---|---|
| 2026-04-27 | Codex | `energiebelasting_teruggave` niet in teruglevering-formule opgenomen | v1.1 | Formule uitgebreid: opbrengst = export × (spotprijs + inkoopverg_teruglev + eb_teruggave) |
| 2026-04-27 | Codex | Bron/sink-regels arbitrage/gecombineerd ontbreken; import/export niet testbaar | v1.1 | Expliciete bron/sink-sectie toegevoegd vóór strategiebeschrijvingen |
| 2026-04-27 | Rens | Strategieën vervangen door 3 expliciete bedrijfsmodi met harde bron/sink-grenzen per modus | v1.2 | §3.3 volledig herschreven (Modus 1/2/3); dashboard Paneel B bijgewerkt; traceerbaarheid UR-04 bijgewerkt |
| 2026-04-27 | Codex | Degradatie-eenheid inconsistent ("per cyclus" vs "per 100 cycli") | v1.1 | Invoer gestandaardiseerd op % per 100 cycli; degradatieformule volledig uitgeschreven |
| 2026-04-27 | Codex | FR-08: overslaan interval verbreekt UR-17-energiebalans | v1.1 | FR-08 herschreven: energie altijd meegeteld, alleen kosten = € 0,00 bij ontbrekende prijs |
| 2026-04-27 | Codex | UR-19 getraceerd naar export, niet naar dashboard-tabel | v1.1 | Tabblad "Ruwe data" toegevoegd aan Scherm 3; traceerbaarheid bijgewerkt |
| 2026-04-27 | Rens | Modus 2 vereist economische laadconditie i.p.v. drempel/percentiel: look-ahead binnen kalenderdag, nieuw parameter minimale_marge_eur_per_kwh | v1.3 | §3.3 Modus 2 volledig herschreven (optimalisatieperiode, Voorwaarde 1/2, verwachte_vermijdingsprijs-formule); Paneel B bijgewerkt (alleen minimale_marge voor Modus 2) |
| 2026-04-27 | Rens | Capaciteitsoptimalisatie toegevoegd: geautomatiseerde sweep over capaciteitsbereik met C-rate/vast-vermogen-schaling, lineair/handmatig prijsmodel, marginale meeropbrengst en optimumkeuze per criterium | v1.4 | §3.3 sweep-sectie; §3.4 sweepresultaten + marginale berekening + optimumcriteria; §3.5 Paneel C (nieuw) + tabblad Capaciteitsoptimalisatie + Scherm 4 sweep-export; §3.6 sweep CSV/Excel; §5 FR-11/FR-12; §6 uitbreidingsnoot (UR-20 aanbevolen) |
| 2026-04-27 | Claude | 5 openstaande reviewpunten (Codex + Gemini) verwerkt: Modus 2 prioriteitsregel, Modus 3 minimale marge, FR-13 drempel/percentiel-validatie, start.bat venv, solar energiebehoud; UR-20 vastgelegd in URS-001 v1.4 | v1.5 | §3.1 solar energiebehoud; §3.3 Modus 2 stap 3/4 wederzijdse uitsluiting; §3.3 Modus 3 marge-conditie + parameter; §3.5 Paneel B Modus 3 + start.bat; §5 FR-13 |
| 2026-04-27 | Claude | 3 open V-model bevindingen Codex verwerkt: Modus 3 margeformule gecorrigeerd, basisreferentie bijgewerkt naar URS v1.5, UR-21 vastgelegd in URS; URS UR-03/UR-04/UR-21 gesynchroniseerd met FD | v1.7 | §3.3 Modus 3 margeformule: `verwachte_exportopbrengst × RTR − laadprijs ≥ marge`; §1 basisreferentie → URS-001 v1.5 |
| 2026-04-27 | Rens/Codex | Analyse- en beslisondersteuning als v1-scope toegevoegd: besparingsdecompositie, batterijbenutting, maandanalyse, beperkte gevoeligheidsanalyse, break-even aankoopprijs, aanbevelingsuitleg en analyse-export | v1.6 | §3.4 analyse-uitvoer; §3.5 tabbladen Beslisanalyse en Gevoeligheid; §3.6 analyse-export; §6 UR-21 aanbevolen |
| 2026-04-27 | Codex | ISSUE(urs): Analyse- en beslisondersteuning (FD v1.6) ontbreekt als URS-eis | v1.7 | UR-21 toegevoegd aan URS-001 v1.5 |
| 2026-04-27 | Gemini | REVIEW(gemini): Minimale marge in sweep-tabel was alleen voor Modus 2 vermeld; degradatie-toepassing verduidelijkt als stepwise per jaar | v1.8 | §3.3 Sweep-parameters tabel bijgewerkt voor Modus 3; §3.3 degradatie-tekst verduidelijkt |

| 2026-04-27 | Codex | ISSUE(urs): Capaciteitsoptimalisatie staat nog niet in URS-001 v1.3; UR-20 vereist vóór DS-start | v1.5 | UR-20 toegevoegd aan URS-001 v1.4; URS-status gezet naar Concept — wacht op goedkeuring Rens |
| 2026-04-27 | Codex | REVIEW(codex): Modus 2 kan in hetzelfde interval laden én ontladen — strijdig met algemene "precies één toestand"-regel; ook drempel/percentiel-overlap Modus 3 vereist validatie | v1.5 | §3.3 Modus 2 stap 3: laadconditie sluit ontladen in dat interval expliciet uit; stap 4: ontladen alleen als laadconditie stap 3 niet vervuld; §5 FR-13 toegevoegd voor drempel/percentiel-overlap Modus 3 |
| 2026-04-27 | Gemini/Codex | REVIEW(codex): Modus 3 mist een economische minimale marge; batterij kan cycli maken voor verwaarloosbaar klein prijsverschil | v1.5 | §3.3 Modus 3: minimale marge-conditie toegevoegd aan prijscondities (verwachte_ontlaadprijs − laadprijs) × RTR ≥ marge; nieuw configureerbaar parameter (standaard 0,00 €/kWh); Paneel B Modus 3 bijgewerkt |
| 2026-04-27 | Gemini/Codex | REVIEW(codex): `start.bat` specificeert geen venv; globale Python-installatie kan vervuild raken | v1.5 | §3.5 start.bat uitgebreid: stap 1 Python-check, stap 2 venv aanmaken/activeren, stap 3 requirements.txt installeren, stap 4/5 server starten en browser openen |
| 2026-04-27 | Gemini/Codex | REVIEW(codex): Solar-interpolatie energiebehoud niet gegarandeerd in FD | v1.5 | §3.1 HA-solar-verwerking: energiebehoud expliciet vastgelegd — som vier kwartierwaarden = afgeleide uurlijkse opwek |
| 2026-04-27 | Codex | REVIEW(codex): Modus 3 minimale marge-formule financieel onjuist: `(verwachte_ontlaadprijs − laadprijs) × RTR` onderschat laadkosten | v1.7 | Formule gecorrigeerd naar `verwachte_exportopbrengst × RTR − laadprijs ≥ minimale_marge`; `verwachte_exportopbrengst` uitgewerkt per beslisregel (drempel/percentiel) incl. inkoopvergoeding en energiebelasting teruglevering |
| 2026-04-27 | Codex | ISSUE(urs): FD v1.6 gebaseerd op URS v1.3 terwijl het UR-20/21-functionaliteit gebruikt | v1.7 | "Gebaseerd op" bijgewerkt naar URS-001 v1.5 |

---

## 8. Goedkeuring

| Rol | Naam | Datum | Status |
|---|---|---|---|
| Opdrachtgever / Gebruiker | Rens Roosloot | 2026-04-27 | Goedgekeurd (v1.8) |
