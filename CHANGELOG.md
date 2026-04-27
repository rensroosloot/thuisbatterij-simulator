2026-04-27 | claude  | setup  | agents.md aangemaakt: samenwerkingsregels Claude/Codex vastgelegd (rolverdeling, V-model, communicatietags, codeconventies)
2026-04-27 | claude  | URS    | URS-001 v1.0 aangemaakt: 19 eisen vastgelegd op basis van databronverkenning
2026-04-27 | claude  | URS    | URS-001 v1.1: Frank Energie tarieven verwerkt vanuit Welkomstbrief; aannames A-02/A-03/A-04/A-07/A-08 bevestigd
2026-04-27 | codex   | URS    | URS-001 reviewcommentaar toegevoegd (7 bevindingen)
2026-04-27 | claude  | URS    | URS-001 v1.2: alle 7 Codex-bevindingen verwerkt; reviewhistorie sectie 7 toegevoegd
2026-04-27 | codex   | URS    | URS-001 herreview: 2 aanvullende bevindingen (DST-voorjaar, datagat feb 2024)
2026-04-27 | claude  | URS    | URS-001 v1.3: 2 herreviewbevindingen verwerkt; UR-05 DST gecorrigeerd; A-09 uitgebreid naar 4 perioden
2026-04-27 | codex   | URS    | URS-001 v1.3 herbeoordeeld; geen open Codex-bevindingen
2026-04-27 | claude  | setup  | agents.md bijgewerkt: CHANGELOG-verplichting aangescherpt (direct na elke stap, niet aan het eind)
2026-04-27 | claude  | URS    | URS-001 v1.3 goedgekeurd door Rens Roosloot (09:28); status bijgewerkt naar Goedgekeurd
2026-04-27 | claude  | URS    | Goedkeuringstabel: kolom "Handtekening" hernoemd naar "Status"
2026-04-27 | claude  | FD     | FD-001 v1.0 aangemaakt: 6 modules, 5 schermen, 10 functionele gedragsregels, volledige URS-traceerbaarheid
2026-04-27 | claude  | FD     | FD-001 v1.0 aangevuld: opstartlauncher (start.bat) toegevoegd voor gebruik door niet-coders
2026-04-27 | codex   | FD     | FD-001 v1.0 reviewcommentaar toegevoegd (5 bevindingen)
2026-04-27 | claude  | FD     | FD-001 v1.1: alle 5 Codex-bevindingen verwerkt (teruglevering-formule, bron/sink-regels, degradatie, FR-08, UR-19 ruwe data tabblad)
2026-04-27 | claude  | FD     | FD-001 v1.2: strategieën vervangen door 3 expliciete bedrijfsmodi (Modus 1/2/3) met harde bron/sink-grenzen; dashboard Paneel B bijgewerkt
2026-04-27 | claude  | FD     | FD-001 v1.3: economische laadconditie Modus 2 (verwachte_vermijdingsprijs-formule, optimalisatieperiode kalenderdag, minimale_marge parameter); Paneel B bijgewerkt
2026-04-27 | claude  | FD     | FD-001 v1.4: capaciteitsoptimalisatie toegevoegd (sweep, C-rate, lineair/handmatig prijsmodel, marginale meeropbrengst, optimumcriteria, sweepgrafiek, sweepexport, FR-11/FR-12)
2026-04-27 | claude  | FD     | FD-001 v1.5: 5 review-bevindingen verwerkt (Modus 2 prioriteitsregel, Modus 3 marge, FR-13 drempel/percentiel-validatie, start.bat venv, solar energiebehoud)
2026-04-27 | claude  | URS    | URS-001 v1.4: UR-20 capaciteitsoptimalisatie toegevoegd; status → Concept (hergoedkeuring vereist)
2026-04-27 | codex   | FD     | FD-001 v1.4 reviewcommentaar toegevoegd (2 bevindingen)
2026-04-27 | codex   | FD     | Gemini-review verwerkt tot 3 aanvullende FD-reviewpunten
2026-04-27 | codex   | FD     | FD-001 v1.5 herreview: Modus 3 margeformule reviewpunt toegevoegd
2026-04-27 | codex   | FD     | FD-001 v1.6 analyse- en beslisondersteuning toegevoegd als v1-scope
2026-04-27 | claude  | FD     | FD-001 v1.6: visuele stijl vastgelegd (dark mode standaard + toggle, paars/indigo accent, KPI-kaarten met delta, Plotly dark + kleurenschema per config)
2026-04-27 | claude  | URS    | URS-001 v1.5: UR-03 eenheid gecorrigeerd, UR-04 herschreven naar 3 bedrijfsmodi, UR-21 analyse/beslisondersteuning toegevoegd; 3 Codex-issues gesloten
2026-04-27 | claude  | FD     | FD-001 v1.7: Modus 3 margeformule gecorrigeerd (verwachte_exportopbrengst × RTR − laadprijs); basisreferentie → URS-001 v1.5; 3 open V-model bevindingen gesloten
2026-04-27 | codex   | URS/FD | Laatste review: 4 open V-model bevindingen toegevoegd
2026-04-27 | gemini  | review | URS-001 v1.6 en FD-001 v1.8: Reviewronde Gemini afgerond; inconsistentie in sweep-parameters Modus 3 hersteld
2026-04-27 | gemini  | DS     | DS-001 v1.0 aangemaakt: Architectuur, "Golden DataFrame" definitie en vectorisatie-strategie vastgelegd
2026-04-27 | gemini  | DS     | DS-001 v1.1: 9 reviewpunten Codex verwerkt (Golden DataFrame uitgebreid, look-ahead logica, DST-volgorde, degradatieformule, start.bat pip-check)
2026-04-27 | gemini  | review | DS-001 v1.2: Reviewronde Gemini afgerond; positief advies voor implementatie.
2026-04-27 | gemini  | review | datamenagercodereview.md: Code review van de DataManager implementatie uitgevoerd; focus op P1e logica en memory efficiency.
2026-04-27 | codex   | URS/FD | URS-001 v1.6 en FD-001 v1.8 door Rens goedgekeurd; status bijgewerkt
2026-04-27 | codex   | DS     | DS-001 v1.2 uitgewerkt tot implementatiegericht detailed design met datacontracten, algoritmes, validatie en teststrategie
2026-04-27 | codex   | DS     | DS-001 traceerbaarheid uitgebreid met FD-verwijzingen; Gemini-reviewpunten expliciet afgevinkt in reviewhistorie
2026-04-27 | codex   | DS     | DS-001 Gemini-observaties verwerkt: Modus 3 percentielopbrengst verduidelijkt en start.bat pause conditioneel gemaakt
2026-04-27 | codex   | test   | TP-001 v1.0 aangemaakt met unit-, integratie-, UI- en acceptatietests plus URS-traceerbaarheid
2026-04-27 | codex   | test   | Chatreview verwerkt: TP-001 v1.1 uitgebreid met performance- en stresstests plus traceerbaarheid
2026-04-27 | codex   | review | Documentatiefase afgerond: URS-001 v1.6, FD-001 v1.8, DS-001 v1.2 en TP-001 v1.1 door Rens goedgekeurd
2026-04-27 | codex   | impl   | Projectstructuur gestart: DataManager, eerste unit tests, requirements.txt en start.bat toegevoegd
2026-04-27 | codex   | impl   | Minimale Streamlit-entrypoint toegevoegd en DataManager-tests robuuster gemaakt voor floatvergelijkingen
2026-04-27 | codex   | test   | Unit tests nog niet uitvoerbaar in huidige shell: Python-runtime ontbreekt volgens py.exe launcher
2026-04-27 | codex   | impl   | DataManager uitgebreid met resource-status en P1e-samenvatting; Streamlit datastatusscherm aangesloten
2026-04-27 | codex   | test   | DataManager-tests opnieuw geprobeerd via venv; geblokkeerd door Access denied op Python313 executable
2026-04-27 | codex   | test   | DataManager unit tests succesvol uitgevoerd buiten sandbox: 8 tests groen
2026-04-27 | codex   | impl   | DataManager uitgebreid met prijsparser, HA solar lifetime-verwerking en eerste Golden DataFrame builder
2026-04-27 | codex   | test   | Nieuwe DataManager-tests nog niet uitgevoerd: buiten-sandbox pytest-aanvraag geweigerd door usage/approval-limiet
2026-04-27 | codex   | test   | pytest.ini toegevoegd zodat tests ook buiten projectroot `src` kunnen importeren
2026-04-27 | codex   | test   | DataManager unit tests succesvol uitgevoerd: 11 tests groen
2026-04-27 | codex   | impl   | Golden DataFrame samenvatting toegevoegd aan DataManager en Streamlit datastatus
2026-04-27 | codex   | test   | DataManager unit tests succesvol uitgevoerd: 12 tests groen
2026-04-27 | codex   | impl   | TariffEngine toegevoegd met Frank Energie defaults, baselinekosten en Streamlit jaarkostentabel
2026-04-27 | codex   | test   | DataManager en TariffEngine unit tests succesvol uitgevoerd: 17 tests groen
2026-04-27 | codex   | impl   | SimEngine Modus 1 toegevoegd met SoC, rendement, vermogensgrenzen en Streamlit voorbeeldsimulatie
2026-04-27 | codex   | test   | DataManager, TariffEngine en SimEngine Modus 1 unit tests succesvol uitgevoerd: 22 tests groen
2026-04-27 | codex   | impl   | SimEngine Modus 2 toegevoegd met day-ahead look-ahead, netladen zonder export en margeconditie
2026-04-27 | codex   | impl   | Streamlit uitgebreid met Modus 2 voorbeeldsimulatie en minimale marge-invoer
2026-04-27 | codex   | test   | DataManager, TariffEngine en SimEngine Modus 1/2 unit tests succesvol uitgevoerd: 28 tests groen
2026-04-27 | codex   | setup  | GitHub-publicatie voorbereid: README.md en .gitignore toegevoegd; resources uitgesloten
2026-04-27 | codex   | impl   | SimEngine Modus 3 toegevoegd met drempel/percentielgestuurd netladen, margeconditie en batterij-export
2026-04-27 | codex   | test   | DataManager, TariffEngine en SimEngine Modus 1/2/3 unit tests succesvol uitgevoerd: 35 tests groen
2026-04-27 | codex   | impl   | TariffEngine uitgebreid met kosten mét batterij en Streamlit toont jaarkosten/besparing per modus
2026-04-27 | codex   | test   | Kostenberekening met batterij toegevoegd; volledige unit test suite succesvol uitgevoerd: 37 tests groen
2026-04-27 | codex   | impl   | ResultCalculator toegevoegd met financiele en technische KPI's voor simulaties
2026-04-27 | codex   | test   | ResultCalculator unit tests toegevoegd; volledige unit test suite succesvol uitgevoerd: 42 tests groen
2026-04-27 | codex   | impl   | Capaciteitssweep toegevoegd met C-rate, lineair prijsmodel, marginale opbrengst en aanbevelingscriterium
2026-04-27 | codex   | test   | Capaciteitssweep unit tests toegevoegd; volledige unit test suite succesvol uitgevoerd: 46 tests groen
2026-04-27 | codex   | impl   | Exporter toegevoegd met CSV/Excel exports voor KPI- en sweepresultaten in Streamlit
2026-04-27 | codex   | test   | Exporter unit tests toegevoegd; volledige unit test suite succesvol uitgevoerd: 48 tests groen
2026-04-27 | codex   | impl   | Oude browsertool als referentie gebruikt: Streamlit caching, Plotly kostengrafieken, dagaggregaties en tijdreeks-CSV toegevoegd
2026-04-27 | codex   | test   | Exporter tijdreekskolommen getest; volledige unit test suite succesvol uitgevoerd: 49 tests groen
2026-04-27 | codex   | impl   | Laadvermogen en ontlaadvermogen gesplitst in Streamlit en capaciteitssweep
2026-04-27 | codex   | test   | Gescheiden laad/ontlaad C-rate in sweep getest; volledige unit test suite succesvol uitgevoerd: 49 tests groen
2026-04-27 | codex   | impl   | Streamlit simulatie-invoer in updateformulier gezet zodat parameterwijzigingen pas na knopdruk doorrekenen
2026-04-27 | codex   | test   | Streamlit entrypoint compileert; volledige unit test suite succesvol uitgevoerd: 49 tests groen
2026-04-27 | codex   | impl   | Downloadknoppen aangepast met on_click=ignore zodat CSV/Excel downloads geen simulatie-rerun starten
2026-04-27 | codex   | test   | Streamlit entrypoint compileert; volledige unit test suite succesvol uitgevoerd: 49 tests groen
2026-04-27 | claude  | setup  | docs/reviews/ aangemaakt; CR-001 en DR-001 opgesteld; losse reviewbestanden geconsolideerd; agents.md §7 reviewconventies toegevoegd
2026-04-27 | claude  | review | CR-001 bijgewerkt: 8 van 9 bevindingen afgedaan o.b.v. CHANGELOG + codecheck; CR-001-06 (category dtype) nog open. DR-001-03/04 opgelost via FD v1.5
2026-04-27 | claude  | review | DR-001 volledig afgerond: 4 opgelost, 1 n.v.t., 5 uitgesteld. CR-001-06 TODO(codex) toegevoegd; CR-001 status: 1 open bevinding
2026-04-27 | codex   | impl   | Scenarioselectie toegevoegd voor 2024, 2025 en gecombineerd; KPI's en sweep rekenen gecombineerde scenario's nu als jaargemiddelde
2026-04-27 | codex   | impl   | CR-001-06 opgelost: data_quality_flags en actie gebruiken nu category dtype in DataManager en SimEngine
2026-04-27 | codex   | impl   | Simulatie-UX verbeterd: scenarioselectie buiten formulier, defaults aangepast, NCW-toelichting toegevoegd en sweepgrafiek toont nu besparing per kWh batterijcapaciteit
2026-04-27 | codex   | impl   | Capaciteitssweep ondersteunt nu vaste marktopties met echte capaciteit/prijs-combinaties naast lineair prijsmodel
2026-04-27 | codex   | impl   | Terugleververgoeding configureerbaar gemaakt; simulaties en sweep kunnen nu met vaste lage of nulvergoeding rekenen voor 2027
2026-04-27 | codex   | impl   | Modus 3 netladen kijkt nu 24 uur vooruit naar verwacht tekort voor zelfvoorziening en vereist configureerbare minimale prijsstijging boven rendementsverlies
2026-04-27 | codex   | impl   | Modus 3 vereenvoudigd: netladen gebruikt alleen 24u tekort plus minimale prijsstijging; export blijft gestuurd via exportdrempel of exportpercentiel
2026-04-27 | codex   | impl   | UI en sweep vereenvoudigd naar twee strategieen: Modus 1 en Slimme modus; slimme modus gebruikt de 24u tekortlogica voor eigen verbruik
2026-04-27 | codex   | impl   | Slimme modus laad nu alleen bij verwacht 24u tekort en wanneer huidig interval ook een lokaal gunstig koopmoment is; overagressief vroeg inkopen voorkomen
2026-04-27 | codex   | impl   | Slimme modus reserve verfijnd tot tekort voor de volgende betekenisvolle zonne-laadkans; voorkomt onnodig laden voor tekorten die overdag door zon kunnen worden opgevangen
2026-04-27 | codex   | test   | Slimme modus prijskijkvenster afgedekt met tests: voor 13:00 alleen resterende dagprijzen, na 13:00 komende 24 uur
2026-04-27 | codex   | impl   | Slimme modus losgetrokken van oude exportmodus; UI en sweep rekenen nu met een aparte niet-exporterende simulate_smart_mode
2026-04-27 | codex   | impl   | Slimme modus sterk versneld: publicatie-afhankelijke prijslookahead gevectoriseerd, simulatietijd van ~32s naar ~0.6s per jaar
2026-04-27 | codex   | docs   | URS, FD, DS en TP bijgewerkt naar twee modi, geen batterij-export, 13:00-prijspublicatie en actuele slimme-modus tests
