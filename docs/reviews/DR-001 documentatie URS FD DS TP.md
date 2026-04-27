# DR-001 — Document Review: URS-001 · FD-001 · DS-001 · TP-001

**Project:** 023 Thuisbatterij  
**Documenten:** URS-001 v1.6, FD-001 v1.8, DS-001 v1.2, TP-001 v1.0  
**Datum:** 2026-04-27  
**Status:** Afgerond (alle bevindingen gesloten)

---

## Bevindingen — overzichtstabel

| ID | Agent | Prioriteit | Samenvatting | Oplosser | Hoe opgelost | Status |
|---|---|---|---|---|---|---|
| DR-001-01 | Gemini | Laag | Solar: lineaire interpolatie vs. step-down of zoncurve — v1-keuze voldoende mits energiebehoud | Claude | Gemini beoordeelde de v1-keuze zelf als veilig mits energiebehoud; energiebehoud (÷4 per kwartier) is geïmplementeerd | Niet van toepassing |
| DR-001-02 | Gemini | Laag | Degradatie: onduidelijk of toepassing tijdens of tussen jaren plaatsvindt | Claude | FD v1.8 §3.3 beschrijft expliciet "begin van jaar t" met formule `capaciteit_t = nominaal − som(verlies jaren 1..t-1)`; stepwise-tussen-jaren is helder (CHANGELOG r755) | Opgelost |
| DR-001-03 | Gemini | Medium | `start.bat`: venv aanmaken/activeren ontbreekt — globale Python kan vervuild raken | Claude | FD-001 v1.5: start.bat uitgebreid met 5-staps venv-procedure (CHANGELOG 2026-04-27 r19) | Opgelost |
| DR-001-04 | Gemini | Medium | Modus 3: `minimale_marge` ontbreekt; batterij kan cycli maken voor verwaarloosbare winst | Claude | FD-001 v1.5: `minimale_marge` conditie toegevoegd aan Modus 3 prijsconditie (CHANGELOG 2026-04-27 r19) | Opgelost |
| DR-001-05 | Copilot | Laag | Geen woordenlijst/glossarium voor niet-technische gebruikers in URS/FD | Claude | Tool is primair voor eigen gebruik (Rens); URS/FD al goedgekeurd. Kandidaat voor v2-iteratie | Uitgesteld |
| DR-001-06 | Copilot | Laag | Architectuurdiagrammen ontbreken in DS; context-diagram in FD is basic | Claude | DS al goedgekeurd; diagrammen vereisen tooling buiten markdown-scope. Kandidaat voor v2-iteratie | Uitgesteld |
| DR-001-07 | Copilot | Wens | Toekomstbestendigheid/uitbreidbaarheid niet besproken (wijzigende tarieven, nieuwe accutechniek) | Claude | Buiten v1-scope: tool is beslisondersteuning op basis van 2024/2025-data. Niet opportuun om goedgekeurde docs te heropenen | Uitgesteld |
| DR-001-08 | Copilot | Laag | Aannames niet gekwantificeerd qua risico-impact (bijv. solar datagat) | Claude | URS al goedgekeurd; risico-impact solar datagat (jan–feb 2024 = 0 kWh) is beperkt en gedekt door A-09. Kandidaat voor v2-iteratie | Uitgesteld |
| DR-001-09 | Copilot | Medium | TP-001 status nog Concept; goedkeuring ontbreekt voor V-model compliance | Claude | TP-001 v1.1 is Goedgekeurd door Rens Roosloot 2026-04-27 (CHANGELOG r40; TP §8 bevestigt status) | Opgelost |
| DR-001-10 | Copilot | Laag | FD bevat te veel implementatiedetails die thuishoren in DS | Claude | FD al goedgekeurd; herstructurering buiten v1-scope. Detail-overlap FD/DS acceptabel voor single-developer project | Uitgesteld |

---

## Review: Gemini Code Assist — 2026-04-27

**Scope:** URS-001 v1.6, FD-001 v1.8  
**Conclusie:** Positief advies voor fase DS-001

### Algemeen oordeel

De functionele architectuur is solide. De scheiding tussen de `Data Module` (preprocessing) en de `Simulatie-engine` (logica) is essentieel voor de betrouwbaarheid. Het gebruik van historische 2024/2025 data als "ground truth" i.p.v. synthetische profielen maakt de resultaten voor de eindgebruiker zeer geloofwaardig.

**Sterke punten:**
- DST-afhandeling: expliciete regels voor voor- en najaar voorkomen veelvoorkomende off-by-one errors.
- Energiebalans-verificatie (UR-17): de <1% afwijkingseis is een uitstekende kwaliteitsborging.
- Modus 2 logica: "perfect foresight" binnen de kalenderdag is een pragmatische en effectieve keuze voor historische data.
- Capaciteitssweep: marginale meeropbrengst-berekeningen maken van de tool een echt optimalisatie-instrument.

### Bevinding DR-001-01 — Prioriteit: Laag

**Samenvatting:** Solar interpolatie: lineaire aanpak vs. alternatieven  
**Sectie:** FD §3.1

Lineaire interpolatie van uur naar 15 minuten is acceptabel. Een "step-down" (waarde/4) of verdeling op basis van een zon-curve kan accurater zijn. Voor v1 is de huidige keuze veilig, mits de totale energie per uur behouden blijft.

### Bevinding DR-001-02 — Prioriteit: Laag

**Samenvatting:** Degradatie-toepassing: tijdens of tussen simulatiejaren?  
**Sectie:** FD §3.3

De formule gebruikt `totale_laadenergie_jaar_kwh / nominale_capaciteit_kwh` (standaard Equivalent Full Cycles). Verduidelijk of de degradatie *tijdens* het simulatiejaar al op de SoC-grenzen wordt toegepast, of *tussen* jaren. De huidige tekst suggereert "aan het begin van elk jaar", wat technisch eenvoudiger is en voldoende nauwkeurig voor een horizon van 10–15 jaar.

### Bevinding DR-001-03 — Prioriteit: Medium

**Samenvatting:** `start.bat` valideert geen venv  
**Sectie:** FD §3.5

Zorg dat `start.bat` niet alleen Python checkt, maar ook een venv aanmaakt of activeert. Dit voorkomt vervuiling van de globale Python-installatie en garandeert dat de juiste Streamlit-versie wordt gebruikt.

*Opmerking voor oplosser: controleer of FD v1.5 al een venv-stap beschrijft in §3.5 — mogelijk al opgelost.*

### Bevinding DR-001-04 — Prioriteit: Medium

**Samenvatting:** Modus 3 mist `minimale_marge`  
**Sectie:** FD §3.3

Bij Modus 3 (arbitrage met export) is het risico op "cycle churn" groot bij kleine prijsverschillen. De parameter `minimale_marge` uit Modus 2 zou ook in Modus 3 verplicht moeten zijn.

*Opmerking voor oplosser: controleer of FD v1.5+ `minimale_marge` al toevoegt aan Modus 3 — mogelijk al opgelost.*

### Consistentie-check

- [x] UR-01 t/m UR-19 volledig gedekt in de FD-modules
- [x] Frank Energie formules in §3.2 komen exact overeen met URS §2.3
- [x] Blokkerende foutmeldingen (FR-01, FR-02, FR-11, FR-12) garanderen robuuste gebruikerservaring

---

## Review: GitHub Copilot — 2026-04-27

**Scope:** URS-001 v1.6, FD-001 v1.8, DS-001 v1.2, TP-001 v1.0  
**Conclusie:** Sterke basis met verbeterpunten op toegankelijkheid en TP-goedkeuring

### Algemeen oordeel

De documentatie is uitgebreid, goed gestructureerd en volgt het V-model consequent, met duidelijke traceerbaarheid tussen fasen. Het gebruik van historische meetdata maakt de resultaten geloofwaardig voor de eindgebruiker.

**Sterke punten:**
- Uitgebreide scope: van data-ingestie tot geavanceerde analyse, inclusief edge cases als DST en datakwaliteit.
- Traceerbaarheid: uitgebreide kruisverwijzingen maken het eenvoudig om eisen door de ontwikkeling te volgen.
- Iteratieve verbetering: reviewhistorie in elk document toont responsieve updates.

### Cross-document consistentie

- Terminologie consistent: "Modus 1/2/3", "Golden DataFrame", "sweep".
- Kleine inconsistentie: FD v1.8 verwijst op sommige plaatsen nog naar URS v1.5 i.p.v. v1.6.
- TP gebaseerd op alle drie, maar nog als Concept — mogelijk uit sync na laatste FD/DS updates.

### Bevinding DR-001-05 — Prioriteit: Laag

**Samenvatting:** Geen woordenlijst voor niet-technische gebruikers  
**Sectie:** URS §1, FD §1

URS en FD hebben dichte technische secties. Een glossarium of vereenvoudigde samenvatting aan het begin van elk document vergroot de toegankelijkheid voor niet-technische stakeholders.

### Bevinding DR-001-06 — Prioriteit: Laag

**Samenvatting:** Architectuurdiagrammen ontbreken in DS  
**Sectie:** DS-001 algemeen

DS mist hoog-niveau architectuurdiagrammen. UML-diagrammen voor modulesrelaties en dataflows zouden de leesbaarheid verbeteren. Het context-diagram in FD is basic.

### Bevinding DR-001-07 — Prioriteit: Wens

**Samenvatting:** Toekomstbestendigheid niet besproken  
**Sectie:** URS §1

De documenten richten zich op historische data; er is weinig aandacht voor toekomstige scenario's (wijzigende tarieven, nieuwe accutechnologie). Een extensibility-sectie of roadmap in URS/FD zou dit adresseren.

### Bevinding DR-001-08 — Prioriteit: Laag

**Samenvatting:** Aannames niet gekwantificeerd qua risico-impact  
**Sectie:** URS §5

Aannames (bijv. solar datagat jan–feb 2024) zijn genoteerd maar niet gekwantificeerd in termen van impact op de simulatieresultaten. Risicobeoordelingen met mitigatiestrategieën ontbreken.

### Bevinding DR-001-09 — Prioriteit: Medium

**Samenvatting:** TP-001 nog Concept; goedkeuring vereist voor V-model compliance  
**Sectie:** TP-001 §8

TP is nog als Concept gemarkeerd, wat in het V-model betekent dat de testfase nog niet formeel kan starten. Goedkeuring door Rens Roosloot is nodig. Voeg ook geautomatiseerde testdekking-metrics en integratie met eventuele CI toe.

### Bevinding DR-001-10 — Prioriteit: Laag

**Samenvatting:** FD bevat te veel implementatiedetails  
**Sectie:** FD §3.3

Sommige FD-secties (met name de modebeschrijvingen en het algoritmische gedeelte van de sweep) zijn te gedetailleerd voor een functioneel ontwerp. Implementatie-hints horen thuis in DS.
