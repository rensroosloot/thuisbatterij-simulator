# agents.md — Samenwerkingsregels Claude Code & Codex

**Project:** 023 Thuisbatterij  
**Datum:** 2026-04-27

Dit document legt vast hoe Claude Code en Codex samenwerken in dit project. Beide agents houden zich aan deze regels. Bij twijfel heeft dit document voorrang op eigen aannames.

---

## 1. Rolverdeling

| Verantwoordelijkheid | Claude Code | Codex |
|---|---|---|
| URS opstellen en bewaken | Primair | Reviewt |
| FD en DS schrijven | Primair | Reviewt |
| Implementatie (Python/data) | Reviewt | Primair |
| Testcases schrijven | Schrijft acceptatiecriteria | Implementeert unittests |
| Datavalidatie en sanity checks | Ontwerpt logica | Implementeert |
| Refactoring | Accordeert | Voert uit |
| Documentatie in code | Accordeert stijl | Schrijft |

**Vuistregel:** Claude Code bewaakt het *wat* en *waarom* (eisen, ontwerp, architectuur). Codex bewaakt het *hoe* (implementatie, tests, uitvoerbaarheid).

---

## 2. V-model werkwijze

Beide agents volgen de V-model volgorde strikt. Geen agent begint aan een fase zonder dat de vorige fase is afgerond en door de gebruiker (Rens) is goedgekeurd.

```
URS  →  FD  →  DS  →  Implementatie  →  Unittests  →  Integratietest  →  Acceptatietest
(Claude)  (Claude)  (samen)  (Codex)    (Codex)        (samen)           (Claude, met gebruiker)
```

- Een agent die een fout ontdekt in een hogere fase (bijv. een DS-probleem terwijl je implementeert) **stopt**, markeert het issue als `ISSUE(fase):` in het betreffende document, en meldt dit aan de gebruiker vóór verdergaan.
- Geen agent past een document van een hogere fase aan zonder expliciete opdracht van de gebruiker.

---

## 3. Bestandseigenaarschap

| Map / bestand | Eigenaar | Andere agent mag |
|---|---|---|
| `docs/URS-*.md` | Claude Code | Lezen, reviewcommentaar toevoegen |
| `docs/FD-*.md` | Claude Code | Lezen, reviewcommentaar toevoegen |
| `docs/DS-*.md` | Gedeeld | Lezen, schrijven na accordering |
| `docs/reviews/CR-*.md` | Gedeeld | Eigen sectie toevoegen; oplosser vult afdoeningskolommen in |
| `docs/reviews/DR-*.md` | Gedeeld | Eigen sectie toevoegen; oplosser vult afdoeningskolommen in |
| `src/**` | Codex | Lezen, reviewopmerkingen plaatsen |
| `tests/**` | Codex | Lezen, acceptatiecriteria toevoegen |
| `agents.md` | Gedeeld | Beide mogen wijzigingen voorstellen; gebruiker keurt goed |
| `resources/**` | Geen van beide | Alleen lezen — brondata wordt nooit gewijzigd |

---

## 4. Communicatie tussen agents

Omdat agents niet direct communiceren, verloopt alle communicatie via bestanden in de repository.

### 4.1 Taakmarkering in code en documenten

Gebruik de volgende gestandaardiseerde tags:

```
TODO(claude):  <omschrijving>    — actie voor Claude Code
TODO(codex):   <omschrijving>    — actie voor Codex
ISSUE(urs):    <omschrijving>    — probleem gevonden in URS
ISSUE(fd):     <omschrijving>    — probleem gevonden in FD
ISSUE(ds):     <omschrijving>    — probleem gevonden in DS
REVIEW(claude): <omschrijving>   — Claude Code moet dit beoordelen
REVIEW(codex):  <omschrijving>   — Codex moet dit beoordelen
```

### 4.2 Handoff-procedure

Wanneer een agent zijn deel afrondt:
1. Alle `TODO` voor de andere agent zijn correct geplaatst.
2. Een korte samenvatting wordt toegevoegd aan `CHANGELOG.md` (zie §7).
3. De gebruiker wordt geïnformeerd dat de volgende agent aan zet is.

---

## 5. Codeconventies

Beide agents houden zich aan de volgende conventies, zodat elkaars code leesbaar en onderhoudbaar blijft.

- **Taal:** Python 3.11+
- **Stijl:** PEP 8; regellengte max. 100 tekens
- **Commentaar:** Alleen als het *waarom* niet vanzelfsprekend is — geen beschrijving van wat de code doet
- **Bestandsnamen:** `snake_case.py`
- **Functies:** korte, enkelvoudige verantwoordelijkheid; max. ~40 regels per functie
- **Geen globale state** buiten configuratie-objecten
- **Alle invoerpaden** zijn configureerbaar (geen hardcoded paths)
- **Eenheden** worden altijd expliciet benoemd in variabelenamen: `energy_kwh`, `power_kw`, `price_eur_per_kwh`

---

## 6. Wat agents nooit mogen doen

- **Brondata aanpassen** — bestanden in `resources/` zijn read-only
- **Een hogere V-model fase wijzigen** zonder gebruikerstoestemming
- **Bestaande, goedgekeurde code verwijderen** zonder eerst een `REVIEW`-tag te plaatsen
- **Aannames doen over tarieven of contract** — altijd verwijzen naar URS §5 open punten
- **Externe services aanroepen** tijdens simulatie (tool draait lokaal, zie UR-13)
- **Committen of pushen** zonder expliciete opdracht van de gebruiker

---

## 7. Reviewdocumenten (`docs/reviews/`)

Alle code- en documentreviews worden opgeslagen in `docs/reviews/` met een vaste naamgeving en structuur.

### 7.1 Naamgeving

| Prefix | Betekenis | Voorbeeld |
|---|---|---|
| `CR-NNN` | Code Review — één bronbestand of module | `CR-001 data_manager.md` |
| `DR-NNN` | Document Review — één of meer specificatiedocumenten | `DR-001 documentatie URS FD DS TP.md` |

### 7.2 Documentstructuur

Elk reviewdocument heeft:

1. **Koptabel met metadata** — document-ID, betrokken bestanden, datum, status.
2. **Bevindingen — overzichtstabel** — alle bevindingen van alle reviewers in één tabel:

   | ID | Agent | Prioriteit | Samenvatting | Oplosser | Hoe opgelost | Status |
   |---|---|---|---|---|---|---|
   | CR-001-01 | Claude | Kritiek | korte omschrijving | — | — | Open |

   - **ID:** `CR-NNN-NN` of `DR-NNN-NN` — uniek per bevinding.
   - **Oplosser:** de agent of persoon die de bevinding afhandelt (invullen bij afdoening).
   - **Hoe opgelost:** korte beschrijving van de toegepaste fix of onderbouwing voor "Niet van toepassing".
   - **Status:** `Open` | `Opgelost` | `Niet van toepassing` | `Uitgesteld`

3. **Reviewsecties per agent** — elke reviewer heeft een eigen `## Review: [Agent] — [datum]` sectie met gedetailleerde bevindingen gelinkt aan de ID's uit de overzichtstabel.

### 7.3 Werkwijze afdoening

- De **oplosser** (meestal Codex voor code, Claude voor docs) werkt de overzichtstabel bij zodra een bevinding is verwerkt.
- Een bevinding mag alleen `Opgelost` worden als de fix aantoonbaar aanwezig is in de code of het document.
- `Niet van toepassing` vereist een korte onderbouwing in de kolom "Hoe opgelost".
- Na afdoening van alle open bevindingen wordt de documentstatus van `Open` naar `Afgerond` gezet.

---

## 8. CHANGELOG.md

Elke agent voegt **direct na elke stap** een regel toe aan `CHANGELOG.md` — niet pas aan het eind van een sessie. Geen uitzondering.

Formaat:
```
YYYY-MM-DD | <agent> | <fase> | <korte omschrijving>
```

Toegestane fasen: `setup`, `URS`, `FD`, `DS`, `impl`, `test`, `review`

Voorbeelden:
```
2026-04-27 | claude  | URS    | URS-001 v1.0 aangemaakt, 19 eisen vastgelegd
2026-04-27 | claude  | setup  | agents.md aangemaakt
2026-04-27 | codex   | impl   | Data-inleesmodule P1e CSV gereed, unittests groen
```

Een agent die vergeet de CHANGELOG bij te houden heeft zijn handoff-procedure niet volledig uitgevoerd (zie §4.2).

---

## 9. Conflictresolutie

Als agents het oneens zijn over een ontwerpkeuze of implementatie:
1. De afwijkende agent plaatst een `REVIEW`-tag met zijn bezwaar en onderbouwing.
2. Beide agents schrijven hun positie kort op in `docs/DECISIONS.md` onder een nieuw genummerd besluit.
3. De gebruiker beslist; de beslissing wordt vastgelegd in `DECISIONS.md` en is daarna bindend.

Geen agent overschrijft de ander zonder dat de gebruiker heeft beslist.

---

## 10. Sessieopstart-checklist

Elke agent voert bij de start van een nieuwe werksessie het volgende uit:

- [ ] `agents.md` gelezen en akkoord
- [ ] Laatste regels van `CHANGELOG.md` bekeken
- [ ] Open `TODO(eigen-naam):`-tags in de codebase opgezocht
- [ ] Huidige V-model fase vastgesteld
- [ ] Geen wijzigingen in `resources/` aangebracht
