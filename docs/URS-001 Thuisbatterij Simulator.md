# URS-001 — Thuisbatterij Simulator

**Document type:** User Requirements Specification  
**Project:** 023 Thuisbatterij  
**Versie:** 1.6  
**Datum:** 2026-04-27  
**Auteur:** Rens Roosloot  
**Status:** Goedgekeurd

---

## 1. Doel en scope

Dit document beschrijft de gebruikerseisen voor een simulatietool waarmee beoordeeld kan worden welke thuisbatterij het beste aansluit bij het werkelijke energieprofiel van de gebruiker. De tool gebruikt historische meetdata uit 2024 en 2025 als modelinput en simuleert het effect van een thuisbatterij op financiën, zelfvoorzienendheid en terugverdientijd.

De tool is uitsluitend bedoeld voor persoonlijk gebruik en beslissingsondersteuning bij de aankoop van een thuisbatterij.

---

## 2. Context en achtergrond

### 2.1 Beschikbare databronnen

| Bestand | Inhoud | Granulariteit |
|---|---|---|
| `P1e-2024-*.csv` | Slimme meter: import/export T1+T2 (cumulatief kWh), max vermogen per fase | 15 min |
| `P1e-2025-*.csv` | Idem, jaar 2025 | 15 min |
| `jeroen_punt_nl_dynamische_stroomprijzen_jaar_2024.csv` | Dynamische spotprijzen excl. belastingen (€/kWh) | 15 min |
| `jeroen_punt_nl_dynamische_stroomprijzen_jaar_2025.csv` | Idem, jaar 2025 | 15 min |
| `history HA 2024.csv` | Home Assistant sensorhistorie: zonnepanelen (Gerardus inverter) | Uurlijks |
| `history HA 2025.csv` | Idem, jaar 2025 | Uurlijks |
| `Welkomstbrief Energie.pdf` | Huidig energiecontract (leverancier, tarieven, vaste kosten) | — |
| `SolarFlow_2400_AC__User_Manual_EN_NL.pdf` | Specificaties Zendure SolarFlow 2400 AC als referentiebatterij | — |

### 2.2 Vastgestelde jaartotalen (ter oriëntatie)

| Jaar | Import totaal | Export totaal |
|---|---|---|
| 2024 | ~2.587 kWh | ~1.953 kWh |
| 2025 | ~2.698 kWh | ~2.325 kWh |

### 2.3 Energiecontract — Frank Energie Dynamisch (ingangsdatum 28-12-2025)

Alle bedragen zijn **inclusief btw**, conform de Welkomstbrief.

**Elektriciteit — variabele componenten per kWh:**

| Component | Inkoop | Teruglevering |
|---|---|---|
| Spotprijs | EPEX Day Ahead (per kwartier) | EPEX Day Ahead (per kwartier) |
| Inkoopvergoeding | +€ 0,01815 | +€ 0,01850 |
| Energiebelasting | +€ 0,12286 | **€ 0,00** (geen teruggave na 2027) |
| **Totaal variabel** | **spotprijs + € 0,14101** | **spotprijs + € 0,01850** |

**Elektriciteit — vaste componenten per maand:**

| Component | Bedrag/maand |
|---|---|
| Vaste leveringskosten | € 4,79 |
| Netbeheerkosten (Stedin Utrecht) | € 39,48 |
| Vermindering energiebelasting | − € 52,93 |
| **Netto vaste kosten elektriciteit** | **− € 8,66** (saldo in voordeel van klant) |

**Saldering:** per 1 januari 2027 volledig afgeschaft. De simulatie modelleert **uitsluitend de situatie zonder saldering**: teruggeleverde energie wordt vergoed tegen spotprijs + € 0,01850/kWh, zonder verrekening van energiebelasting.

**Prijsdata:** de spotprijsbestanden (`jeroen_punt_nl_dynamische_stroomprijzen_jaar_*.csv`) bevatten de EPEX DA-prijs in €/kWh exclusief belastingen, op kwartierbasis — dit is precies de `spotprijs`-component in bovenstaande formule.

**T1/T2 in P1e-data:** de twee meterregisters (T1 = dag, T2 = nacht) zijn alleen relevant voor het meten van de energiebalans. Voor de prijsberekening telt uitsluitend het kwartierinterval en de bijbehorende spotprijs; T1/T2-tariefonderscheid bestaat niet bij dit dynamische contract.

**Zonnepanelen:** opwekdata afgeleid uit HA-sensor `gerardus_total_uitgangsvermogen` (W, uurlijks) en `gerardus_total_energieopbrengst_levenslang` (kWh cumulatief). Wordt geïnterpoleerd naar 15-min resolutie.

**P1e-data:** cumulatieve meterstanden; intervalverbruik = differentie tussen opeenvolgende rijen. Import en export zijn som van T1+T2-registers.

---

## 3. Gebruikerseisen

### 3.1 Datainvoer en configuratie

**UR-01 — Laden van historische data**  
De tool moet de volgende acht bronbestanden uit de map `resources/` kunnen inlezen zonder handmatige bewerking:

| # | Bestandsnaam | Verplicht |
|---|---|---|
| 1 | `P1e-2024-1-1-2024-12-31.csv` | Ja |
| 2 | `P1e-2025-1-1-2025-12-31.csv` | Ja |
| 3 | `jeroen_punt_nl_dynamische_stroomprijzen_jaar_2024.csv` | Ja |
| 4 | `jeroen_punt_nl_dynamische_stroomprijzen_jaar_2025.csv` | Ja |
| 5 | `history HA 2024.csv` | Ja |
| 6 | `history HA 2025.csv` | Ja |
| 7 | `Welkomstbrief Energie.pdf` | Nee (tarieven zijn reeds vastgelegd in §2.3) |
| 8 | `SolarFlow_2400_AC__User_Manual_EN_NL.pdf` | Nee (referentie) |

Dit is de volledige verplichte inputset. De tool weigert te starten als een van de zes verplichte CSV-bestanden ontbreekt.

**UR-02 — Tariefconfiguratie**  
De tool levert de Frank Energie-tarieven als standaardwaarden (zie §2.3). De gebruiker moet deze kunnen overschrijven om alternatieve scenario's te vergelijken:
- Inkoopvergoeding inkoop (€/kWh), standaard € 0,01815
- Inkoopvergoeding teruglevering (€/kWh), standaard € 0,01850
- Energiebelasting inkoop (€/kWh), standaard € 0,12286
- Energiebelasting teruggave (€/kWh), standaard € 0,00 (post-saldering 2027-scenario)
- Vaste maandelijkse kosten elektriciteit (€/maand), standaard − € 8,66 (nettosaldo vaste componenten)
- Vaste maandelijkse kosten worden meegenomen in de jaarlijkse kostenvergelijking maar beïnvloeden de batterijbesparing niet direct

Voor de NCW-berekening (zie UR-09) zijn de volgende aanvullende parameters configureerbaar:
- Discontovoet (%), standaard 0% voor v1
- Jaarlijkse energieprijsindexatie (%), standaard 0% voor v1
- Economische horizon (jaren), standaard gelijk aan batterijlevensduur

**UR-03 — Batterijeconfiguratie**  
De gebruiker moet per simulatierun de volgende batterijparameters kunnen opgeven:
- Bruikbare capaciteit (kWh)
- Maximaal laadvermogen (kW)
- Maximaal ontlaadvermogen (kW)
- Round-trip rendement (%) of apart laad- en ontlaadrendement
- Minimale en maximale SoC (%)
- Levensduur (jaren) en cyclische degradatie (% capaciteitsverlies per 100 equivalente vollaadcycli)
- Aanschafprijs (€) inclusief installatie

**UR-04 — Bedrijfsmodus**  
De gebruiker moet per batterijconfiguratie kiezen uit de volgende drie bedrijfsmodi:
- **Modus 1 — Zelfconsumptie / nul-op-de-meter:** batterij laadt uitsluitend op zonne-overschot en ontlaadt uitsluitend bij huishoudvraag; geen netladen, geen batterij-export naar het net.
- **Modus 2 — Slim laden zonder teruglevering:** batterij laadt op zonne-overschot én op het net als een economische laadconditie dit rechtvaardigt (look-ahead binnen de kalenderdag); ontlaadt uitsluitend bij huishoudvraag; geen batterij-export.
- **Modus 3 — Slim laden met teruglevering:** batterij laadt op zonne-overschot én op het net bij lage spotprijs; ontlaadt bij huishoudvraag én exporteert naar het net bij hoge spotprijs (volledige day-ahead arbitrage).

Voor Modus 3 moet de gebruiker de laad-/exportbeslisregel kunnen kiezen en parametriseren:
- **Drempelwaarde:** laad als `spotprijs < drempel_laag` (€/kWh), exporteer als `spotprijs > drempel_hoog` (€/kWh); vereist `drempel_laag < drempel_hoog`.
- **Percentiel:** laad als spotprijs < P-laag percentiel van de dag; exporteer als spotprijs > P-hoog percentiel (configureerbaar, standaard P25/P75); vereist P-laag < P-hoog.

Aanvullend voor Modus 2 en 3: een configureerbare minimale marge (€/kWh, standaard 0,00) garandeert dat netladen pas plaatsvindt als het verwachte financiële voordeel de round-trip verliezen overtreft.

De gekozen modus, beslisregel en parameterwaarden worden meegenomen in de simulatie-output zodat resultaten reproduceerbaar zijn (UR-18).

---

### 3.2 Simulatie

**UR-05 — Tijdstapresolutie en tijdzone**  
De simulatie moet draaien op 15-minuten-intervallen, in lijn met de P1e- en prijsdata.

Tijdzone-afhandeling:
- Alle tijdstempels worden intern verwerkt als **Nederlandse lokale tijd** (`datum_nl` uit de prijsbestanden; kolomnaam `time` uit de P1e-bestanden).
- Bij het samenvoegen van P1e-data en prijsdata wordt op `datum_nl` gejoint.
- **Zomertijdovergang voorjaar** (klok gaat 1 uur vooruit, 02:00 → 03:00): de lokale tijdstempels 02:00–02:45 bestaan niet. Zowel P1e als prijsdata bevatten die rijen niet; er is geen mismatch. De betreffende dag telt 92 in plaats van 96 intervallen. De simulatie slaat deze intervallen stilzwijgend over; energie en kosten voor die dag zijn op basis van de 92 aanwezige meetpunten.
- **Zomertijdovergang najaar** (klok gaat 1 uur terug, 03:00 → 02:00): de lokale tijdstempels 02:00–02:45 komen tweemaal voor in de P1e-data. De twee energiedifferenties per duplicaat-tijdstempel worden gesommeerd tot één interval; de spotprijs van het eerste optreden wordt gebruikt.
- De tool rapporteert de afgehandelde DST-dag(en) als onderdeel van de datakwaliteitsmelding (zie UR-16).

**UR-06 — Energiebalans per interval**  
Per tijdstap moet de tool de volgende grootheden berekenen:
- Zonopwek (kWh) — afgeleid uit HA-data
- Huishoudverbruik (kWh) — afgeleid als: import − export + zonopwek
- Nettouitwisseling met het net zonder batterij
- Batterij SoC (kWh en %) na het interval
- Netto laad- of ontlaadvermogen batterij (kW)
- Nettouitwisseling met het net mét batterij
- Financieel effect per interval (€)

**UR-07 — Meerdere configuraties vergelijken**  
De tool moet minimaal vier batterijconfiguraties tegelijk kunnen simuleren op dezelfde dataset, zodat de gebruiker direct kan vergelijken.

**UR-08 — Scenariojaren**  
De tool moet het mogelijk maken om te simuleren over:
- Jaar 2024 afzonderlijk
- Jaar 2025 afzonderlijk
- 2024 + 2025 gecombineerd (als tweejarig gemiddelde)

---

### 3.3 Resultaten en visualisatie

**UR-09 — Financiële KPI's**  
De tool moet per simulatie de volgende resultaten tonen:
- Jaarlijkse energiekosten zonder batterij (€)
- Jaarlijkse energiekosten met batterij (€)
- Jaarlijkse besparing (€)
- Terugverdientijd (jaren), inclusief degradatie en financieringskosten indien gewenst
- Netto contante waarde (NCW) over de levensduur van de batterij

**UR-10 — Technische KPI's**  
De tool moet per simulatie de volgende technische resultaten tonen:
- Zelfvoorzienendheidsgraad (%) — aandeel verbruik gedekt door eigen opwek + batterij
- Zelfconsumptiegraad (%) — aandeel eigen opwek dat zelf gebruikt wordt
- Aantal equivalente vollaadcycli per jaar
- Geschat resterende levensduur in cycli aan het eind van de simulatieperiode

**UR-11 — Grafische weergave**  
De tool moet ten minste de volgende visualisaties bieden:
- Dagprofiel (gemiddeld of specifieke dag): verbruik, opwek, batterij-SoC, netimport
- Maandoverzicht: import, export, batterijgebruik per maand (gestapeld staafdiagram)
- Prijsheatmap: spotprijs per uur van de dag per maand
- Vergelijkingsgrafiek: financieel resultaat van meerdere batterijconfiguraties naast elkaar
- Terugverdientijdcurve: cumulatieve besparing vs. investering over de jaren

**UR-12 — Exportfunctie**  
De gebruiker moet de simulatieresultaten kunnen exporteren als CSV en/of Excel voor verdere analyse.

---

### 3.4 Bruikbaarheid

**UR-13 — Lokale uitvoering**  
De tool moet volledig lokaal draaien, zonder externe services of internetverbinding vereist voor de simulatie zelf.

**UR-14 — Opstartdrempel**  
De tool moet starten via een enkelvoudig commando (bijv. `python simulate.py` of een dashboard-opstart) zonder complexe installatieprocedure.

**UR-15 — Interactief dashboard**  
De resultaten worden bij voorkeur gepresenteerd in een interactief webdashboard (lokaal) zodat parameters live aangepast kunnen worden en resultaten direct bijwerken.

**UR-16 — Foutmeldingen bij ontbrekende data**  
Als invoerdata ontbreekt of ongeldig is (bijv. gaten in de meetreeks), meldt de tool dit expliciet met de betreffende tijdspanne en een keuze hoe daarmee om te gaan (overslaan, interpoleren of stoppen).

---

### 3.5 Betrouwbaarheid en validatie

**UR-17 — Verificatie energiebalans**  
De tool moet de gesimuleerde energiebalans vergelijken met de werkelijke P1e-eindmeterstanden als sanity check. De verificatie geldt voor vier grootheden afzonderlijk:
- Totaal import (kWh) = som van alle positieve netto-intervalwaarden
- Totaal export (kWh) = som van alle negatieve netto-intervalwaarden (absoluut)
- Import T1 cumulatief (laatste meterstand minus eerste meterstand)
- Import T2 cumulatief (idem)

De toegestane afwijking voor elk van de vier grootheden is **< 1%** ten opzichte van de overeenkomstige P1e-eindmeterstand. Grotere afwijkingen blokkeren de simulatie met een expliciete foutmelding.

**UR-18 — Reproduceerbaarheid**  
Dezelfde invoerdata en parameters moeten altijd exact hetzelfde resultaat opleveren (deterministisch).

**UR-19 — Transparantie berekeningen**  
De gebruiker moet per tijdstap de ruwe berekende waarden kunnen inzien (debug-uitvoer of inspecteerbare tabel) ter controle van de simulatielogica.

**UR-21 — Analyse- en beslisondersteuning**  
De tool biedt analyse-uitvoer die de gebruiker helpt simulatieresultaten te interpreteren en een aankoopbeslissing te nemen:
- **Besparingsdecompositie** per configuratie: opsplitsing van de totale besparing naar component (opslag zonne-overschot, slim laden, batterij-export, round-trip verlies, degradatie-effect).
- **Batterijbenutting** per configuratie: percentage dagen dat max/min SoC wordt bereikt, gemiste zonne-opslag en gemiste vraagdekking.
- **Maand- en seizoensanalyse:** kernmetrieken per kalendermaand (import, export, laadenergie, besparing, cycli, zelfvoorzienendheid).
- **Beperkte gevoeligheidsanalyse:** effect van ±25% batterijprijs, ±25% energieprijsniveau, ±5%-punt rendement en ±25% terugleververgoeding op besparing, terugverdientijd en NCW.
- **Break-even analyse:** maximale aanschafprijs waarbij NCW ≥ 0 en break-even terugverdientijd.
- **Aanbevelingsuitleg** bij capaciteitsoptimalisatie: tekstuele toelichting bij de aanbevolen capaciteit met onderbouwing en vergelijking met naastgelegen capaciteitswaarden.
- Alle analyse-uitvoer is exporteerbaar (UR-12).

**UR-20 — Capaciteitsoptimalisatie**  
De tool moet de gebruiker ondersteunen bij het bepalen van de optimale batterijgrootte door een geautomatiseerde sweep uit te voeren over een configureerbaar capaciteitsbereik (minimale capaciteit, maximale capaciteit, stapgrootte in kWh; maximaal 200 punten). Voor elk capaciteitspunt worden alle financiële KPI's (UR-09) en technische KPI's (UR-10) berekend. De tool berekent tevens de marginale meeropbrengst per extra kWh capaciteit en markeert de optimale capaciteit op basis van een door de gebruiker gekozen criterium (hoogste NCW, kortste terugverdientijd, hoogste jaarlijkse besparing, of marginale drempel). Laad- en ontlaadvermogen kunnen meeschalen via een configureerbare C-rate of als vaste waarde worden opgegeven. De aanschafprijs wordt berekend via een lineair kostenmodel (`basisprijs + prijs_per_kwh × capaciteit`) of handmatig per capaciteitspunt ingevoerd. De sweepresultaten zijn exporteerbaar via UR-12.

---

## 4. Niet in scope

- Aansturing van een echte batterij of koppeling met een home-automation systeem
- Optimalisatie via machine learning of voorspellende algoritmen
- Weersvoorspelling of toekomstige productie-inschatting
- Netbeheerderstarief (congestiekosten, terugleverheffing) — wordt als PM gemarkeerd indien relevant

---

## 5. Aannames en open punten

| Nr | Punt | Status |
|---|---|---|
| A-01 | Zonnepaneel-vermogensprofiel afgeleid uit HA `uitgangsvermogen` (W, uurlijks), geïnterpoleerd naar 15 min | **Aanname — bevestigd** |
| A-02 | T1/T2-onderscheid niet relevant voor prijsberekening bij Frank Energie dynamisch contract; T1+T2 worden gesommeerd voor energiebalans | **Bevestigd** (gebruiker + contract) |
| A-03 | Simulatie modelleert post-2027 situatie: **geen saldering**, energiebelasting niet verrekend bij teruglevering | **Bevestigd** (gebruiker) |
| A-04 | Prijsdata `jeroen_punt_nl` = EPEX DA in €/kWh excl. belastingen; overeenkomend met Frank Energie-contractdefinitie | **Bevestigd** (contract §2.3) |
| A-05 | Degradatiemodel batterij: lineair over cycli | Aanname — te verfijnen in DS |
| A-06 | Installatie- en aansluitkosten zijn onderdeel van opgegeven aanschafprijs | Aanname |
| A-07 | Tarieven Frank Energie (§2.3) worden als standaardwaarden gebruikt voor de simulatie; gebruiker kan overschrijven | **Bevestigd** (Welkomstbrief 14-12-2025) |
| A-08 | De spotprijsdata 2024/2025 wordt gebruikt alsof het toen al een dynamisch contract betrof (retroactieve projectie) | **Bevestigd** (gebruiker) |
| A-09 | HA-opwekdata is niet volledig: `energieopbrengst_levenslang` 2024 start op 14-02-2024 14:00 (geen beginwaarde beschikbaar vóór die datum); `uitgangsvermogen` is voor heel 2024 `unavailable` en voor 2025 beschikbaar vanaf 17-03-2025. Afhandeling per periode: (1) **2024-01-01 t/m 2024-02-14 13:59** → zonopwek = 0 kWh; interpolatie is onmogelijk zonder beginmeterstand; de periode valt in diepe winter (NL-productie verwaarloosbaar); (2) **2024-02-14 t/m 2024-12-31** → interval-opwek afgeleid als differentie van opeenvolgende `energieopbrengst_levenslang`-waarden, geïnterpoleerd van uur naar 15 min; (3) **2025-01-01 t/m 2025-03-17** → idem op basis van `energieopbrengst_levenslang` 2025 (sensor wél beschikbaar); (4) **2025-03-18 t/m 2025-12-31** → idem, aangevuld met `uitgangsvermogen` als verificatie. Alle perioden met nul-aanname worden meldplichtig via UR-16. | **Aanname — gedocumenteerd** |
| OP-02 | Maximaal aansluitvermogen / groepsgrootte woning onbekend | Open — niet kritisch voor simulatie, wel relevant voor batterijakkoord |

---

## 6. Traceerbaarheid

| Eis | Afgeleid van |
|---|---|
| UR-01 t/m UR-04 | Beschikbare databronnen (§2.1) |
| UR-05 t/m UR-08 | Gewenste simulatienauwkeurigheid |
| UR-09 t/m UR-12 | Beslissingsondersteuning aankoop |
| UR-13 t/m UR-16 | Bruikbaarheidswensen gebruiker |
| UR-17 t/m UR-19 | Betrouwbaarheid en testeisen (V-model) |
| UR-20 | Primaire gebruikersvraag: welke batterijgrootte is optimaal om te kopen (FD v1.4 uitbreiding) |
| UR-21 | Beslissingsondersteuning: simulatieresultaten begrijpelijk en interpreteerbaar maken voor aankoopbeslissing (FD v1.6 uitbreiding) |

---

## 7. Reviewhistorie

| Reviewdatum | Reviewer | Bevinding | Verwerkt in | Actie |
|---|---|---|---|---|
| 2026-04-27 | Codex | Status "open punten gesloten" klopt niet: OP-02 nog open | v1.2 | Status gecorrigeerd |
| 2026-04-27 | Codex | UR-01: onduidelijk over volledige inputset; verkeerde PDF-bestandsnaam | v1.2 | UR-01 herschreven met expliciete bestandstabel; bestandsnaam gecorrigeerd |
| 2026-04-27 | Codex | HA-opwekdata heeft gaten: 2024 start op 14-02, 2025 `uitgangsvermogen` start op 17-03 | v1.2 | A-09 toegevoegd met afhandelingsstrategie per gat |
| 2026-04-27 | Codex | UR-05/UR-16: tijdzone en zomertijdbehandeling niet gespecificeerd; rijentelling P1e vs. prijsdata wijkt af | v1.2 | UR-05 uitgebreid met tijdzone-paragraaf en DST-afhandeling |
| 2026-04-27 | Codex | UR-04: arbitrage "laag/hoog" niet gedefinieerd; niet testbaar | v1.2 | UR-04 uitgebreid met keuze drempelwaarde vs. percentiel |
| 2026-04-27 | Codex | UR-09/UR-02: discontovoet, indexatie en horizon ontbreken voor NCW | v1.2 | UR-02 uitgebreid met NCW-parameters (standaard 0% voor v1) |
| 2026-04-27 | Codex | UR-17: "< 1%" geldt voor welke grootheid? | v1.2 | UR-17 herschreven: vier grootheden elk afzonderlijk gedefinieerd |
| 2026-04-27 | Codex | UR-05: voorjaar-DST was fout beschreven — beide datasets missen 02:00–02:45 gelijkelijk; geen mismatch. Alleen najaar-DST geeft P1e-duplicaten. | v1.3 | UR-05 herschreven: voorjaar = 92 intervallen overgeslagen, najaar = P1e-duplicaten gesommeerd |
| 2026-04-27 | Codex | A-09: datagat loopt t/m 2024-02-14 13:59, niet alleen januari; zonder beginmeterstand is interpolatie onmogelijk voor die periode. | v1.3 | A-09 herschreven: vier perioden expliciet benoemd; 2024-01-01–2024-02-14 = 0 kWh (onderbouwd); overige perioden via cumulatieve differentiatie |
| 2026-04-27 | Claude | UR-20 toegevoegd: capaciteitsoptimalisatie (sweep, marginale meeropbrengst, optimumkeuze, C-rate, lineair prijsmodel) — uitbreiding op basis van FD v1.4-bevinding Codex | v1.4 | §3.5 UR-20 toegevoegd; §6 traceerbaarheid bijgewerkt; status Goedgekeurd → Concept (hergoedkeuring vereist) |

| 2026-04-27 | Codex | ISSUE(urs): UR-04 beschrijft nog de oude strategieën (Zelfconsumptie / Prijsarbitrage / Gecombineerd), terwijl FD-001 werkt met drie expliciete bedrijfsmodi | v1.5 | UR-04 volledig herschreven: drie bedrijfsmodi (Modus 1/2/3) met harde bron/sink-definitie, beslisregel voor Modus 3, minimale marge voor Modus 2/3 |
| 2026-04-27 | Codex | ISSUE(urs): UR-03 noemt degradatie als percentage per volledig laadcyclus; FD rekent in % per 100 equivalente vollaadcycli | v1.5 | UR-03 eenheid gecorrigeerd: % capaciteitsverlies per 100 equivalente vollaadcycli |
| 2026-04-27 | Codex | ISSUE(urs): Analyse- en beslisondersteuning (FD v1.6) heeft geen URS-eis; UR-21 vereist | v1.5 | UR-21 toegevoegd: besparingsdecompositie, batterijbenutting, maandanalyse, gevoeligheidsanalyse, break-even, aanbevelingsuitleg, analyse-export; §6 bijgewerkt |
| 2026-04-27 | Claude | UR-03/04/21 verwerkt; URS v1.5 gereed voor hergoedkeuring | v1.5 | zie bovenstaande acties |
| 2026-04-27 | Gemini | REVIEW(gemini): Consistentie-check met FD v1.8 uitgevoerd; UR-20 marginale marge impliciet via UR-04 akkoord bevonden | v1.6 | Reviewhistorie bijgewerkt |

---

## 8. Goedkeuring

| Rol | Naam | Datum | Status |
|---|---|---|---|
| Opdrachtgever / Gebruiker | Rens Roosloot | 2026-04-27 | Goedgekeurd (v1.6) |
