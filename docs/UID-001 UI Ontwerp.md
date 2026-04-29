# UID-001 — UI Ontwerp: Thuisbatterij Simulator

**Project:** 023 Thuisbatterij  
**Status:** Concept  
**Datum:** 2026-04-29  
**Versie:** 1.2  
**Auteur:** Claude Code  
**Goedkeuring:** —

---

## Bevindingen — overzichtstabel

| ID | Agent | Prioriteit | Samenvatting | Oplosser | Hoe opgelost | Status |
|---|---|---|---|---|---|---|
| UID-001-01 | Codex | Hoog | §6.1 benoemt sweep-modi niet expliciet; risico op terugkeer van oude Modus 2/3-namen | Claude | §6.1 aangevuld: opties expliciet `(1, 2)` met labels `"Modus 1"` / `"Slimme modus"` | Opgelost |
| UID-001-02 | Codex | Hoog | §1 "zelfde namen/validatie" botst met §9 dat labels en help-teksten aanpast | Claude | §1 herformuleerd: logica en validatieregels blijven gelijk; widgetpresentatie valt onder §9 | Opgelost |
| UID-001-03 | Codex | Hoog | §6.1 vraagt SweepConfig-velden die §11 verbiedt te wijzigen | Claude | `fixed_charge_power_kw` / `fixed_discharge_power_kw` bestaan al in `SweepConfig`; §11 verduidelijkt | Opgelost |
| UID-001-04 | Codex | Medium | Onafhankelijke detailperiode per subtab verhoogt complexiteit en rerun-risico | Claude | §5.3.4 teruggedraaid: één gedeelde periodeselctor bóven de subtabs | Opgelost |
| UID-001-05 | Codex | Medium | Datastatus-tab met alles in expanders kan leeg ogende tab geven | Claude | §4 bijgewerkt: bestandsstatus direct zichtbaar; P1e en GDF achter expanders | Opgelost |
| UID-001-06 | Codex | Medium | Paars palet te dominant; risico op monotone UI | Claude | §7.1 en §7.5 bijgewerkt: paars alleen voor primaire lijn; secundaire series neutraal grijs/wit | Opgelost |
| UID-001-07 | Codex | Laag | Legacy variabelenaam `mode_3_min_price_spread_pct` in pseudocode §3 | Claude | §3 en §10 bijgewerkt: rename naar `smart_mode_min_price_spread_pct` als Codex-taak | Opgelost |
| UID-001-08 | Codex | Laag | "Feature branch: DataManager" caption verwijderen | Claude | Al gedekt in §2 en §9; geen aanvullende actie nodig | Niet van toepassing |
| UID-001-09 | Codex | Laag | Mogelijke encoding-vervuiling in documentweergave | Claude | Ongeldige bevinding per agents.md §5.1: consoleweergave is niet leidend; bestand had eerst als UTF-8 geverifieerd moeten worden vóór indiening | Niet van toepassing |
| UID-001-10 | Codex | Medium | KPI-kaarten verwijzen absoluut naar gecombineerde rij; single-year scenario's hebben die niet | Claude | §5.2 aangepast: gebruik gecombineerde rij indien aanwezig, anders de enige jaarrij | Opgelost |
| UID-001-11 | Codex | Medium | Voorgestelde KPI-layout (`st.columns(2)` × `st.columns(4)`) is te dicht voor Streamlit | Claude | §5.2 aangepast: modi verticaal gestapeld i.p.v. naast elkaar; `st.columns(4)` op volle breedte | Opgelost |

---

## 1. Doel en scope

Dit document beschrijft de gewenste layout, structuur en visuele stijl van de Streamlit-applicatie (`src/main.py`). Het dient als implementatiespecificatie voor Codex. De functionele logica (simulatie-engines, tariefberekeningen, data-ingestie) wijzigt niet; alleen de presentatielaag wordt herzien.

**Wat verandert:**
- Navigatiestructuur: van één verticale scroll naar tabs + sidebar
- KPI-presentatie: van ruwe tabellen naar prominente metrieken
- Detaildata: progressief zichtbaar via expanders
- Grafiekstijl: donker thema, consistente kleurcodering

**Wat niet verandert:**
- Berekeningslogica en validatieregels (inclusief alle `_validate_*`-methoden)
- Exportformaten en downloadinhoud
- Widgetlabels en help-teksten mogen wél worden aangepast per §9

---

## 2. Globale structuur

```
┌─────────────────────────────────────────────────────────┐
│  Thuisbatterij Simulator                                │
│  op basis van historische data 2024–2026                │
├──────────┬──────────────────────────────────────────────┤
│          │  [ Datastatus ]  [ Simulatie ]  [ Sweep ]    │
│ Sidebar  │                                              │
│ (config) │  Tab-inhoud                                  │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

- **Sidebar** (`st.sidebar`): alle configuratie-invoer + submit-knop
- **Tabs** (`st.tabs`): drie tabs voor de drie functionele gebieden
- App-titel: `st.title("Thuisbatterij Simulator")` + `st.caption("op basis van historische data 2024–2026")`
- De huidige `st.caption("Feature branch: DataManager")` wordt verwijderd

---

## 3. Sidebar — Configuratiepaneel

De sidebar bevat alle invoerparameters. Het simulatieformulier (`with st.form`) verhuist hiernaartoe. Submit-knop staat onderaan de sidebar.

```python
with st.sidebar:
    st.header("Configuratie")
    with st.form("sim_config_form"):
        # Sectie 1: Scenario
        st.subheader("Scenario")
        scenario_choice = st.selectbox(...)
        detail_year = st.selectbox(...)

        # Sectie 2: Voorbeeldbatterij
        st.subheader("Voorbeeldbatterij")
        battery_capacity_kwh = st.number_input(...)
        battery_charge_power_kw = st.number_input(...)
        battery_discharge_power_kw = st.number_input(...)
        purchase_price_eur = st.number_input(...)
        economic_lifetime_years = st.number_input(...)

        # Sectie 3: Tarief
        st.subheader("Tarief")
        use_fixed_sell_price = st.checkbox(...)
        fixed_sell_price_eur_per_kwh = st.number_input(..., disabled=not use_fixed_sell_price)

        # Sectie 4: Slimme modus
        st.subheader("Slimme modus")
        smart_mode_min_price_spread_pct = st.number_input(...)  # hernoemd van mode_3_min_price_spread_pct

        st.form_submit_button("Simulaties bijwerken", type="primary", use_container_width=True)
```

De sweep-configuratie staat **niet** in de sidebar maar in de sweep-tab zelf (zie §6).

---

## 4. Tab 1 — Datastatus

**Tab-label:** `"Datastatus"`

Inhoud bedoeld voor diagnostiek.

### 4.1 Bestandsstatus (direct zichtbaar)

Toon een `st.success("Alle bronbestanden aanwezig.")` of `st.error(...)` afhankelijk van de status, gevolgd door de bestandstabel direct zichtbaar:

`st.dataframe(status_rows, use_container_width=True, hide_index=True)`

Kolommen: `bestand | aanwezig | grootte_mb | pad`

### 4.2 P1e samenvatting

Achter `st.expander("P1e-bestandsdetails", expanded=False)`:

`st.dataframe(summary_rows, use_container_width=True, hide_index=True)`

### 4.3 Golden DataFrame samenvatting

Achter `st.expander("Golden DataFrame details", expanded=False)`:

`st.dataframe(golden_rows, use_container_width=True, hide_index=True)`

---

## 5. Tab 2 — Simulatie

**Tab-label:** `"Simulatie"`

De tab toont Modus 1 en Slimme modus. Structuur:

1. Baseline jaarkosten (compact, achter expander)
2. KPI-vergelijking: Modus 1 vs. Slimme modus naast elkaar
3. Gedeelde detailperiode-selector
4. Detail-subtabs per modus

### 5.1 Baseline jaarkosten

Achter `st.expander("Baseline jaarkosten zonder batterij", expanded=False)`:

`st.dataframe(cost_rows, use_container_width=True, hide_index=True)`

Kolommen: `scenario | importkosten_eur | exportopbrengst_eur | vaste_kosten_eur | totaal_eur | missende_prijzen`

### 5.2 KPI-vergelijking (prominent)

`st.subheader("Simulatieresultaten")`

Toon Modus 1 en Slimme modus **verticaal gestapeld** (niet naast elkaar). Elke modus krijgt een eigen subheader op volledige breedte, gevolgd door vier `st.metric()` kaarten in `st.columns(4)`. Zo heeft elke kaart een kwart van de volledige schermbreedte — voldoende ruimte in Streamlit wide-layout.

```python
st.markdown("#### Modus 1")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Jaarlijkse besparing", ...)
col2.metric("Terugverdientijd", ...)
col3.metric("NCW", ...)
col4.metric("Zelfvoorzienendheid", ...)

st.markdown("#### Slimme modus")
col1, col2, col3, col4 = st.columns(4)
col1.metric(...)
...
```

**Kaarteninhoud:**

| Kaart | Waarde | Eenheid |
|---|---|---|
| Jaarlijkse besparing | zie bronlogica hieronder | EUR/jr |
| Terugverdientijd | zie bronlogica hieronder | jaar |
| NCW | zie bronlogica hieronder | EUR |
| Zelfvoorzienendheid | zie bronlogica hieronder | % |

**Bronlogica (UID-001-10):** de gecombineerde rij bestaat alleen bij multi-jaar scenario's. Kies de bron als volgt:

```python
kpi_row = combined_row if len(mode_rows) > 1 else mode_rows[0]
```

**Opmaak terugverdientijd:** toon `"∞"` als `None` of `float("inf")`.

**Kleurcode delta (tweede argument `st.metric`):**
- besparing en NCW: groen als positief (`delta_color="normal"`)
- terugverdientijd: omgekeerd (`delta_color="inverse"`)
- geen delta-argument voor zelfvoorzienendheid (geen referentie beschikbaar)

### 5.3 Gedeelde detailperiode-selector

Één periodeselctor bóven de subtabs, van toepassing op beide modi:

```python
detail_period = st.date_input(
    "Detailperiode grafieken",
    value=(default_start, default_end),
    min_value=default_start,
    max_value=default_end,
    help="Geldt voor zowel Modus 1 als Slimme modus.",
)
```

### 5.4 Detail-subtabs

Na de gedeelde periodeselctor volgen subtabs:

```python
modus_tabs = st.tabs(["Modus 1 detail", "Slimme modus detail"])
```

Elke subtab heeft dezelfde structuur:

#### 5.4.1 Uitsplitsing per jaar (expander)

`st.expander("Uitsplitsing per jaar", expanded=False)`

`st.dataframe(mode_rows, ...)` — alle rijen inclusief per-jaar en gecombineerd

Download KPI-CSV in de expander.

#### 5.4.2 Zonne-zelfconsumptie samenvatting

`render_solar_self_consumption_summary(...)` — drie metrics naast elkaar (drie `st.columns`)

#### 5.4.3 Batterijgebruik samenvatting

`render_soc_summary(...)` — vijf metrics naast elkaar

#### 5.4.4 Grafieken (volgorde)

Toon grafieken in volgorde van globaal naar specifiek:

1. `render_daily_energy_chart(...)` — dagelijkse import/export totalen
2. `render_net_exchange_chart(...)` — netto netuitwisseling op 15-min niveau
3. `render_battery_flow_chart(...)` — batterijopname en -afgifte
4. `render_soc_chart(...)` — SoC-verloop
5. `render_soc_distribution_chart(...)` — SoC-verdeling histogram

#### 5.4.5 Tijdreeks download

`render_simulation_exports(...)` — één downloadknop voor de tijdreeks-CSV

---

## 6. Tab 3 — Capaciteitssweep

**Tab-label:** `"Capaciteitssweep"`

De sweep-configuratie staat bovenaan de tab (niet in de sidebar). De sweep wordt pas uitgevoerd na activatie via een checkbox.

### 6.1 Sweep-configuratie

```python
with st.expander("Sweep-instellingen", expanded=True):
    sweep_enabled = st.checkbox("Sweep uitvoeren", value=False)
    if sweep_enabled:
        col1, col2 = st.columns(2)
        with col1:
            sweep_mode = st.selectbox(
                "Sweep modus",
                options=(1, 2),
                format_func=lambda x: "Modus 1" if x == 1 else "Slimme modus",
            )
            sweep_price_model = st.selectbox(
                "Sweep prijsmodel",
                options=("Lineair prijsmodel", "Vaste marktopties"),
                index=1,
            )
            # marktopties of lineair model (zelfde logica als huidig)
        with col2:
            sweep_use_fixed_power = st.checkbox("Vast vermogen gebruiken", value=True)
            sweep_fixed_charge_power_kw = st.number_input(
                "Vast laadvermogen sweep (kW)", value=2.4, step=0.1,
                disabled=not sweep_use_fixed_power,
            )
            sweep_fixed_discharge_power_kw = st.number_input(
                "Vast ontlaadvermogen sweep (kW)", value=0.8, step=0.1,
                disabled=not sweep_use_fixed_power,
            )
            sweep_charge_c_rate = st.number_input(
                "Sweep laad C-rate", value=2.4 / 5.4, step=0.01,
                disabled=sweep_use_fixed_power,
            )
            sweep_discharge_c_rate = st.number_input(
                "Sweep ontlaad C-rate", value=0.8 / 5.4, step=0.01,
                disabled=sweep_use_fixed_power,
            )
        sweep_criterion_label = st.selectbox("Aanbevelingscriterium", ...)
```

**SweepConfig-aanroep:** `fixed_charge_power_kw` en `fixed_discharge_power_kw` bestaan al als optionele velden in `SweepConfig`. Geef ze mee als `sweep_use_fixed_power=True`, anders `None`:

```python
SweepConfig(
    ...
    fixed_charge_power_kw=sweep_fixed_charge_power_kw if sweep_use_fixed_power else None,
    fixed_discharge_power_kw=sweep_fixed_discharge_power_kw if sweep_use_fixed_power else None,
    charge_c_rate=sweep_charge_c_rate,
    discharge_c_rate=sweep_discharge_c_rate,
    ...
)
```

`SweepConfig` zelf hoeft **niet** gewijzigd te worden (CR-002-01).

### 6.2 Sweep-resultaten

Als sweep is uitgevoerd:

#### Aanbeveling (prominent)

```python
st.success(
    f"Aanbevolen: {recommendation['capaciteit_kwh']:.1f} kWh — "
    f"NCW €{recommendation['ncw_eur']:.0f} | "
    f"besparing €{recommendation['jaarlijkse_besparing_eur']:.0f}/jr"
)
```

Gevolgd door drie `st.metric()` kaarten in `st.columns(3)`:

| Kaart | Waarde |
|---|---|
| Aanbevolen batterij | `{x:.1f} kWh` |
| NCW | `€{x:.0f}` |
| Jaarlijkse besparing | `€{x:.0f}/jr` |

#### Grafieken

`render_sweep_charts(sweep_result)` — bestaande drie grafieken (besparing, NCW, besparing per kWh)

#### Sweeptabel

`st.dataframe(sweep_result.round(...), ...)` — bestaande afrondingen

#### Downloads

Twee knoppen naast elkaar via `st.columns(2)`:

```python
col1, col2 = st.columns(2)
col1.download_button("Download CSV", ...)
col2.download_button("Download Excel", ...)
```

---

## 7. Grafiekstijl

Alle Plotly-figuren krijgen een consistent donker thema.

### 7.1 Kleurpalet

| Element | Kleurcode | Gebruik |
|---|---|---|
| Primaire lijn / accent | `#7C3AED` (paars) | Eerste dataserie, sweep NCW |
| Importkosten | `#EF4444` (rood) | Import, kosten |
| Besparing | `#22C55E` (groen) | Besparing, export |
| SoC-lijn | `#F59E0B` (amber) | Batterijlading |
| Secundaire serie | `#94A3B8` (grijs) | Vergelijkingsserie (bijv. "zonder batterij") |

Paars wordt uitsluitend gebruikt voor de primaire dataserie en de sweep-NCW-lijn. Overige series krijgen functionele kleuren (rood/groen/amber) of neutraal grijs — geen extra paarsschakeringen.

### 7.2 Plotly-template

Gebruik `template="plotly_dark"` als basistemplate voor alle figuren:

```python
figure = px.line(..., template="plotly_dark")
figure.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=13),
)
```

### 7.3 Aslijnen en rasterlijnen

```python
figure.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
figure.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
```

### 7.4 Legenda-positie

`legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)`

### 7.5 Kleursequentie per grafiektype

| Grafiek | Kleurvolgorde |
|---|---|
| Net exchange (zonder/met batterij) | `["#94A3B8", "#7C3AED"]` |
| Batterijstroom (laden/ontladen) | `["#22C55E", "#F59E0B"]` |
| Dagelijkse energie (4 series) | `["#EF4444", "#22C55E", "#94A3B8", "#7C3AED"]` |
| SoC-lijn | `["#F59E0B"]` |
| Sweep-lijn (besparing) | `["#22C55E"]` |
| Sweep-lijn (NCW) | `["#7C3AED"]` |

Stel de kleurvolgorde in via `color_discrete_sequence=[...]` op de `px.*`-aanroep.

### 7.6 SoC-histogram — referentielijn

Voeg twee verticale referentielijnen toe aan `render_soc_distribution_chart`:

```python
figure.add_vline(x=20, line_dash="dash", line_color="#EF4444",
                 annotation_text="Min SoC (20%)")
figure.add_vline(x=80, line_dash="dash", line_color="#22C55E",
                 annotation_text="Optimaal (80%)")
```

### 7.7 Dagelijkse energie-grafiek — nettolijn

Voeg een nettolijn (import − export, met batterij) toe als overlay aan `render_daily_energy_chart`. Gebruik een aparte trace over het gestapelde diagram:

```python
daily["net_met_batterij_kwh"] = (
    daily["import_met_batterij_kwh"] - daily["export_met_batterij_kwh"]
)
# Voeg toe als scatter-trace na de bar-figuur
```

---

## 8. Streamlit-themaconfiguratie

Maak `.streamlit/config.toml` aan (of breid het uit als het al bestaat):

```toml
[theme]
base = "dark"
primaryColor = "#7C3AED"
backgroundColor = "#0F0F1A"
secondaryBackgroundColor = "#1A1A2E"
textColor = "#F1F5F9"
font = "sans serif"
```

---

## 9. Kleine tekstwijzigingen

| Locatie | Huidig | Nieuw |
|---|---|---|
| `st.caption` onder titel | `"Feature branch: DataManager"` | `"op basis van historische data 2024–2026"` |
| `st.info(...)` in simulatieconfiguratie | Lange technische toelichting | Verplaats naar `help=`-parameter van `use_fixed_sell_price`-checkbox; verwijder de `st.info` |
| Sweep-marktopties help-tekst | `"Alleen deze echte productopties worden dan doorgerekend."` | `"Voer per regel: capaciteit kWh;aanschafprijs EUR — bijv. '5.28;1847.99'"` |
| Sweep `st.metric` label | `"Aanbevolen capaciteit"` | `"Aanbevolen batterij"` |

---

## 10. Variabelen die verdwijnen of hernoemd worden

| Variabele | Locatie | Actie |
|---|---|---|
| `sweep_year = 2024` | `main.py:525` | Verwijderen — nooit gebruikt (CR-002-02) |
| `mode_3_min_price_spread_pct` | `main.py` | Hernomen naar `smart_mode_min_price_spread_pct` — legacy naam uit oude 3-modi-fase |

---

## 11. Niet te wijzigen

- Berekeningslogica buiten `main.py` (alle engines, calculators)
- Kolomnamen in output-DataFrames
- `SweepConfig`, `BatteryConfig`, `ModeConfig`, `ResultConfig` dataclasses (velden bestaan al)
- `parse_market_options` functie
- `build_mode_row` functie (alleen de aanroepvolgorde wijzigt)
- Exportformaten (CSV/Excel)

---

## 12. Review: Codex — 2026-04-29

### Algemeen oordeel

Het ontwerp is implementeerbaar en sluit goed aan op de bestaande code. Drie implementatieconflicten zijn opgelost (§13 bevindingen verwerkt in v1.1). De keuze voor tabs + sidebar verbetert de navigatie significant ten opzichte van de huidige verticale scroll. Het kleurpalet is aangescherpt zodat paars niet overheerst.

### Bevinding UID-001-01 — Prioriteit: Hoog (Opgelost in v1.1)

Sweep-modus opties waren generiek omschreven; risico op verwarring met verouderde Modus 2/3-benaming. Opgelost door expliciete `options=(1, 2)` met `format_func` in §6.1.

### Bevinding UID-001-02 — Prioriteit: Hoog (Opgelost in v1.1)

§1 stelde "zelfde namen/validatie" maar §9 paste labels en help-teksten aan. §1 is aangescherpt: logica en validatieregels blijven gelijk; widgetpresentatie valt onder §9.

### Bevinding UID-001-03 — Prioriteit: Hoog (Opgelost in v1.1)

§6.1 vroeg `SweepConfig`-velden die §11 verbood te wijzigen. Opgelost: `fixed_charge_power_kw` en `fixed_discharge_power_kw` bestaan al als optionele velden; §11 verduidelijkt dat de dataclass zelf niet hoeft te veranderen.

### Bevinding UID-001-04 — Prioriteit: Medium (Opgelost in v1.1)

Onafhankelijke detailperiode per subtab verhoogde complexiteit en rerun-risico. §5.3.4 teruggedraaid naar één gedeelde selector (nu §5.3).

### Bevinding UID-001-05 — Prioriteit: Medium (Opgelost in v1.1)

Datastatus-tab met alles in expanders zou leeg ogen. §4 bijgewerkt: bestandsstatus direct zichtbaar, P1e en Golden DataFrame achter expanders.

### Bevinding UID-001-06 — Prioriteit: Medium (Opgelost in v1.1)

Paars palet te dominant. §7.1 en §7.5 aangepast: paars uitsluitend voor primaire lijn en sweep-NCW; overige series krijgen functionele kleuren of neutraal grijs.

### Bevinding UID-001-07 — Prioriteit: Laag (Opgelost in v1.1)

Legacy variabelenaam `mode_3_min_price_spread_pct` in pseudocode. §3 en §10 bijgewerkt met hernoeming naar `smart_mode_min_price_spread_pct`.

### Bevinding UID-001-08 — Prioriteit: Laag (Niet van toepassing)

Caption "Feature branch: DataManager" verwijderen. Al gedekt in §2 en §9.

### Bevinding UID-001-09 — Prioriteit: Laag (Niet van toepassing)

Ongeldige bevinding per **agents.md §5.1**: terminal- en consoleweergave zijn niet leidend voor encodingbeoordeling. Codex had het bestand als UTF-8 moeten verifiëren vóór indiening. Het bestand is correct UTF-8 en bevat geen onjuiste bytes.

### Bevinding UID-001-10 — Prioriteit: Medium (Opgelost in v1.2)

KPI-kaarten in §5.2 verwezen absoluut naar de gecombineerde (multi-jaar) rij. Bij een enkel geselecteerd jaar bestaat die rij niet — de code zou crashen of een lege kaart tonen. Opgelost in §5.2 met expliciete bronlogica: gebruik `combined_row` als `len(mode_rows) > 1`, anders `mode_rows[0]`.

### Bevinding UID-001-11 — Prioriteit: Medium (Opgelost in v1.2)

De oorspronkelijke layout plaatste twee modi naast elkaar via `st.columns(2)` met daarbinnen elk vier kaarten via `st.columns(4)`. In Streamlit wide-layout levert dat geneste halveerde kolommen van ~200px per kaart — te krap voor leesbare getallen en labels. Opgelost door modi verticaal te stapelen zodat `st.columns(4)` op de volledige schermbreedte werkt.

---

## 13. Versiebeheer

| Versie | Datum | Wijziging |
|---|---|---|
| 1.0 | 2026-04-29 | Initiële versie |
| 1.1 | 2026-04-29 | 9 Codex-bevindingen verwerkt: sweep-modus expliciet, §1 aangescherpt, SweepConfig-conflict opgelost, gedeelde periodeselctor, datastatus direct zichtbaar, kleurpalet ontpaarst, variabelenaam hernoemd |
| 1.2 | 2026-04-29 | UID-001-10/11 verwerkt: KPI-bronlogica conditioneel op scenariotype; KPI-layout van naast-elkaar naar verticaal gestapeld |
