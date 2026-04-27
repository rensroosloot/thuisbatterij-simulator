# Review Gemini: URS-001 & FD-001

**Project:** 023 Thuisbatterij  
**Reviewer:** Gemini Code Assist  
**Datum:** 2026-04-27  
**Status:** Positief advies voor fase DS-001

---

## 1. Algemene Indruk
De functionele architectuur is solide. De scheiding tussen de `Data Module` (preprocessing) en de `Simulatie-engine` (logica) is essentieel voor de betrouwbaarheid. Het gebruik van historische 2024/2025 data als "ground truth" i.p.v. synthetische profielen maakt de resultaten voor de eindgebruiker zeer geloofwaardig.

## 2. Sterke Punten
- **DST-afhandeling:** De expliciete regels voor de overgang in voor- en najaar voorkomen veelvoorkomende off-by-one errors in tijdreeksen.
- **Energiebalans-verificatie (UR-17):** De <1% afwijkingseis is een uitstekende kwaliteitsborging die fouten in de differentiatie-logica direct afvangt.
- **Modus 2 Logica:** De "perfect foresight" binnen de kalenderdag is een pragmatische en effectieve keuze voor een simulatietool op historische data.
- **Capaciteitssweep:** De toevoeging van marginale meeropbrengst-berekeningen maakt de tool van een simulator tot een echt optimalisatie-instrument.

## 3. Observaties en Verfijningen (voor DS-fase)

### 3.1 Data Interpolatie (Solar)
In §3.1 wordt lineaire interpolatie van uur naar 15 minuten voorgesteld voor solar-data. 
*   *Advies:* Hoewel lineair acceptabel is, kan een "step-down" (waarde/4) of een verdeling op basis van een standaard zon-curve (indien tijdstip bekend) accurater zijn. Voor v1 is de huidige keuze echter veilig, mits de totale energie behouden blijft.

### 3.2 Degradatie-berekening
De formule in §3.3 gebruikt `totale_laadenergie_jaar_kwh / nominale_capaciteit_kwh`.
*   *Aandachtspunt:* Dit is de standaard methode voor "Equivalent Full Cycles". Houd er in het DS rekening mee of de degradatie *tijdens* het simulatiejaar al wordt toegepast op de SoC-grenzen, of dat dit pas *tussen* de jaren gebeurt. De huidige tekst suggereert aan het begin van elk jaar, wat technisch eenvoudiger is en voldoende nauwkeurig voor een horizon van 10-15 jaar.

### 3.3 Dashboard Launch (start.bat)
*   *Advies:* Zorg dat de `start.bat` niet alleen Python checkt, maar ook een `venv` (virtual environment) aanmaakt of activeert. Dit voorkomt vervuiling van de globale Python-installatie bij de gebruiker en garandeert dat de juiste Streamlit-versie wordt gebruikt.

### 3.4 Modus 3: Arbitrage
Bij Modus 3 (arbitrage met export) is het risico op "cycle churn" groot bij kleine prijsverschillen.
*   *Advies:* De parameter `minimale_marge` uit Modus 2 zou ook in Modus 3 verplicht moeten zijn om te voorkomen dat de batterij slijt voor een winst van €0,0001.

## 4. Consistentie-check
- [x] **URS-01 t/m UR-19** zijn volledig gedekt in de FD-modules.
- [x] **Tarieven:** De Frank Energie formules in §3.2 komen exact overeen met URS §2.3.
- [x] **Validatie:** De blokkerende foutmeldingen (FR-01, FR-02, FR-11, FR-12) garanderen een robuuste gebruikerservaring.

## 5. Conclusie
Het ontwerp is klaar voor de technische uitwerking (Detailed Design). De logica is deterministisch en de scope is scherp afgebakend. 

**Advies:** Start met **DS-001**, waarbij de nadruk ligt op de datastructuur van het centrale DataFrame en de vectorisatie van de simulatie-engine (voor performance bij de 200-punts sweep).

---
*Review uitgevoerd door Gemini Code Assist.*
<!--
[PROMPT_SUGGESTION]Stel op basis van de FD v1.4 een opzet voor DS-001 (Detailed Design) op, met focus op de klassenstructuur en de simulatie-loop.[/PROMPT_SUGGESTION]
[PROMPT_SUGGESTION]Maak een concept voor de start.bat die robuust omgaat met venv en package installatie.[/PROMPT_SUGGESTION]
-->