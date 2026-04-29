"""Streamlit entrypoint for the thuisbatterij simulator."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from capacity_sweep import CapacitySweepRunner, SweepConfig
from data_manager import DataManager
from exporter import Exporter
from result_calculator import ResultCalculator, ResultConfig
from scenario_runner import (
    SCENARIO_OPTIONS,
    combine_yearly_frames,
    format_scenario_label,
    get_year_display_label,
    resolve_scenario_years,
)
from sim_engine import BatteryConfig, ModeConfig, SimEngine
from tariff_engine import TariffConfig, TariffEngine


@st.cache_data(show_spinner=False)
def load_golden_dataframe(year: int) -> pd.DataFrame:
    data_manager = DataManager()
    paths = data_manager.get_year_resource_paths(year)
    if not all(path.exists() for path in paths.values()):
        missing = [label for label, path in paths.items() if not path.exists()]
        raise FileNotFoundError(f"Missing resource(s) for {year}: {', '.join(missing)}")
    return data_manager.build_golden_dataframe(
        paths["p1e"],
        paths["prices"],
        paths["solar"],
    ).dataframe


def render_cost_chart(rows: list[dict], title: str) -> None:
    if not rows:
        return
    dataframe = pd.DataFrame(rows)
    chart_data = dataframe.melt(
        id_vars="scenario",
        value_vars=("jaarkosten_zonder_batterij_eur", "jaarkosten_met_batterij_eur"),
        var_name="kostentype",
        value_name="kosten_eur",
    )
    figure = px.bar(
        chart_data,
        x="scenario",
        y="kosten_eur",
        color="kostentype",
        barmode="group",
        title=title,
    )
    st.plotly_chart(figure, use_container_width=True)


def render_sweep_charts(sweep_result: pd.DataFrame) -> None:
    if sweep_result.empty:
        return
    saving_figure = px.line(
        sweep_result,
        x="capaciteit_kwh",
        y="jaarlijkse_besparing_eur",
        markers=True,
        title="Capaciteit versus jaarlijkse besparing",
    )
    st.plotly_chart(saving_figure, use_container_width=True)

    npv_figure = px.line(
        sweep_result,
        x="capaciteit_kwh",
        y="ncw_eur",
        markers=True,
        title="Capaciteit versus NCW",
    )
    st.plotly_chart(npv_figure, use_container_width=True)

    saving_density_figure = px.bar(
        sweep_result,
        x="capaciteit_kwh",
        y="besparing_per_capaciteit_eur_per_kwh",
        title="Jaarlijkse besparing per kWh batterijcapaciteit",
    )
    st.plotly_chart(saving_density_figure, use_container_width=True)


def render_daily_energy_chart(dataframe: pd.DataFrame, title: str) -> None:
    required = {
        "import_zonder_batterij_kwh",
        "import_met_batterij_kwh",
        "export_zonder_batterij_kwh",
        "export_met_batterij_kwh",
    }
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    daily = dataframe.resample("D").agg(
        {
            "import_zonder_batterij_kwh": "sum",
            "import_met_batterij_kwh": "sum",
            "export_zonder_batterij_kwh": "sum",
            "export_met_batterij_kwh": "sum",
        }
    )
    daily.index.name = "dag"
    chart_data = daily.reset_index().melt(
        id_vars="dag",
        var_name="energiestroom",
        value_name="kwh",
    )
    figure = px.bar(chart_data, x="dag", y="kwh", color="energiestroom", title=title)
    st.plotly_chart(figure, use_container_width=True)


def filter_detail_period(
    dataframe: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
    if dataframe.empty or "timestamp_nl" not in dataframe.columns:
        return dataframe
    start_timestamp = pd.Timestamp(start_date)
    end_timestamp = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    mask = (dataframe["timestamp_nl"] >= start_timestamp) & (
        dataframe["timestamp_nl"] <= end_timestamp
    )
    return dataframe.loc[mask].copy()


def render_net_exchange_chart(dataframe: pd.DataFrame, title: str) -> None:
    required = {
        "timestamp_nl",
        "import_zonder_batterij_kwh",
        "export_zonder_batterij_kwh",
        "import_met_batterij_kwh",
        "export_met_batterij_kwh",
    }
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    chart_frame = pd.DataFrame(
        {
            "timestamp_nl": dataframe["timestamp_nl"],
            "Net zonder batterij": (
                dataframe["import_zonder_batterij_kwh"] - dataframe["export_zonder_batterij_kwh"]
            ),
            "Net met batterij": (
                dataframe["import_met_batterij_kwh"] - dataframe["export_met_batterij_kwh"]
            ),
        }
    )
    chart_data = chart_frame.melt(
        id_vars="timestamp_nl",
        var_name="serie",
        value_name="kwh_per_15_min",
    )
    figure = px.line(
        chart_data,
        x="timestamp_nl",
        y="kwh_per_15_min",
        color="serie",
        title=title,
    )
    st.plotly_chart(figure, use_container_width=True)


def render_battery_flow_chart(dataframe: pd.DataFrame, title: str) -> None:
    required = {"timestamp_nl", "laad_kwh", "ontlaad_kwh"}
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    chart_frame = pd.DataFrame(
        {
            "timestamp_nl": dataframe["timestamp_nl"],
            "Opgenomen door batterij": dataframe["laad_kwh"],
            "Afgegeven door batterij": -dataframe["ontlaad_kwh"],
        }
    )
    chart_data = chart_frame.melt(
        id_vars="timestamp_nl",
        var_name="serie",
        value_name="kwh_per_15_min",
    )
    figure = px.line(
        chart_data,
        x="timestamp_nl",
        y="kwh_per_15_min",
        color="serie",
        title=title,
    )
    st.plotly_chart(figure, use_container_width=True)


def render_soc_chart(dataframe: pd.DataFrame, title: str) -> None:
    required = {"timestamp_nl", "soc_kwh"}
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    figure = px.line(
        dataframe,
        x="timestamp_nl",
        y="soc_kwh",
        title=title,
    )
    st.plotly_chart(figure, use_container_width=True)


def render_soc_distribution_chart(dataframe: pd.DataFrame, title: str) -> None:
    if dataframe.empty or "soc_pct" not in dataframe.columns:
        return

    figure = px.histogram(
        dataframe,
        x="soc_pct",
        nbins=20,
        title=title,
    )
    figure.update_layout(bargap=0.05)
    st.plotly_chart(figure, use_container_width=True)


def render_soc_summary(dataframe: pd.DataFrame, title: str) -> None:
    required = {"soc_kwh", "soc_pct"}
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    avg_soc_kwh = float(dataframe["soc_kwh"].mean())
    min_soc_kwh = float(dataframe["soc_kwh"].min())
    max_soc_kwh = float(dataframe["soc_kwh"].max())
    avg_soc_pct = float(dataframe["soc_pct"].mean())
    near_empty_pct = float((dataframe["soc_pct"] <= 10).mean() * 100)
    near_full_pct = float((dataframe["soc_pct"] >= 90).mean() * 100)

    st.caption(title)
    metric_columns = st.columns(5)
    metric_columns[0].metric("Gem. lading", f"{avg_soc_kwh:.2f} kWh", f"{avg_soc_pct:.1f}%")
    metric_columns[1].metric("Min. lading", f"{min_soc_kwh:.2f} kWh")
    metric_columns[2].metric("Max. lading", f"{max_soc_kwh:.2f} kWh")
    metric_columns[3].metric("Tijd <= 10%", f"{near_empty_pct:.1f}%")
    metric_columns[4].metric("Tijd >= 90%", f"{near_full_pct:.1f}%")


def render_simulation_exports(exporter: Exporter, dataframe: pd.DataFrame, prefix: str) -> None:
    export_frame = exporter.select_timeseries_columns(dataframe)
    if export_frame.empty:
        return
    st.download_button(
        f"Download {prefix} tijdreeks CSV",
        data=exporter.to_csv_bytes(export_frame),
        file_name=f"{prefix}_tijdreeks.csv",
        mime="text/csv",
        on_click="ignore",
    )


def parse_market_options(raw_text: str) -> tuple[tuple[float, float], ...]:
    options = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        normalized = stripped.replace("->", ";").replace(",", ".")
        parts = [part.strip() for part in normalized.split(";") if part.strip()]
        if len(parts) != 2:
            raise ValueError(
                "Marktopties moeten per regel als 'capaciteit;prijs' worden ingevoerd."
            )
        capacity_kwh = float(parts[0])
        price_eur = float(parts[1])
        options.append((capacity_kwh, price_eur))
    options.sort()
    return tuple(options)


def build_mode_row(
    scenario_label: str,
    simulated: pd.DataFrame,
    result_summary,
    baseline_costs,
    battery_costs,
    result_config: ResultConfig,
    year_count: int = 1,
) -> dict:
    annual_factor = 1 / year_count
    annual_baseline_costs_eur = baseline_costs.total_costs_eur * annual_factor
    annual_battery_costs_eur = battery_costs.total_costs_eur * annual_factor
    annual_saving_eur = annual_baseline_costs_eur - annual_battery_costs_eur
    payback_years = (
        result_config.purchase_price_eur / annual_saving_eur
        if annual_saving_eur > 0
        else float("inf")
    )
    net_present_value_eur = ResultCalculator.calculate_present_value_of_savings(
        annual_saving_eur,
        result_config,
    ) - result_config.purchase_price_eur
    return {
        "scenario": scenario_label,
        "jaarkosten_zonder_batterij_eur": round(annual_baseline_costs_eur, 2),
        "jaarkosten_met_batterij_eur": round(annual_battery_costs_eur, 2),
        "jaarlijkse_besparing_eur": round(annual_saving_eur, 2),
        "terugverdientijd_jr": round(payback_years, 2)
        if payback_years != float("inf")
        else None,
        "ncw_eur": round(net_present_value_eur, 2),
        "zelfvoorzienendheid_pct": round(result_summary.self_sufficiency_pct, 1),
        "zelfconsumptie_pct": round(result_summary.self_consumption_pct, 1),
        "directe_zon_zelfconsumptie_zonder_batterij_kwh": round(
            result_summary.direct_solar_self_consumption_without_battery_kwh * annual_factor,
            3,
        ),
        "totale_zon_zelfconsumptie_met_batterij_kwh": round(
            result_summary.total_solar_self_consumption_with_battery_kwh * annual_factor,
            3,
        ),
        "extra_zon_zelfconsumptie_door_batterij_kwh": round(
            result_summary.extra_solar_self_consumption_by_battery_kwh * annual_factor,
            3,
        ),
        "cycli_jaar": round(result_summary.equivalent_full_cycles * annual_factor, 2),
        "import_zonder_batterij_kwh": round(
            float(simulated["import_zonder_batterij_kwh"].sum()) * annual_factor,
            3,
        ),
        "import_met_batterij_kwh": round(
            float(simulated["import_met_batterij_kwh"].sum()) * annual_factor,
            3,
        ),
        "export_zonder_batterij_kwh": round(
            float(simulated["export_zonder_batterij_kwh"].sum()) * annual_factor,
            3,
        ),
        "export_met_batterij_kwh": round(
            float(simulated["export_met_batterij_kwh"].sum()) * annual_factor,
            3,
        ),
        "geladen_solar_kwh": round(
            float(simulated["laad_uit_solar_kwh"].sum()) * annual_factor,
            3,
        ),
        "netladen_kwh": round(float(simulated["laad_uit_net_kwh"].sum()) * annual_factor, 3),
        "ontladen_huis_kwh": round(
            float(simulated["ontlaad_naar_huis_kwh"].sum()) * annual_factor,
            3,
        ),
        "batterij_export_kwh": round(
            float(simulated["ontlaad_naar_net_kwh"].sum()) * annual_factor,
            3,
        ),
        "verlies_kwh": round(float(simulated["round_trip_loss_kwh"].sum()) * annual_factor, 3),
        "eind_soc_kwh": round(float(simulated["soc_kwh"].iloc[-1]), 3) if not simulated.empty else 0.0,
    }


def render_solar_self_consumption_summary(dataframe: pd.DataFrame, title: str) -> None:
    required = {"solar_kwh", "export_zonder_batterij_kwh", "export_met_batterij_kwh"}
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    total_solar_kwh = float(dataframe["solar_kwh"].sum())
    direct_without_battery_kwh = max(
        total_solar_kwh - float(dataframe["export_zonder_batterij_kwh"].sum()),
        0.0,
    )
    total_with_battery_kwh = max(
        total_solar_kwh - float(dataframe["export_met_batterij_kwh"].sum()),
        0.0,
    )
    extra_by_battery_kwh = max(total_with_battery_kwh - direct_without_battery_kwh, 0.0)

    st.caption(title)
    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Direct zonder batterij",
        f"{direct_without_battery_kwh:.1f} kWh",
    )
    metric_columns[1].metric(
        "Totaal met batterij",
        f"{total_with_battery_kwh:.1f} kWh",
    )
    metric_columns[2].metric(
        "Extra door batterij",
        f"{extra_by_battery_kwh:.1f} kWh",
    )


def render_battery_charge_source_summary(dataframe: pd.DataFrame, title: str) -> None:
    required = {"laad_uit_solar_kwh", "laad_uit_net_kwh", "laad_kwh"}
    if dataframe.empty or not required.issubset(dataframe.columns):
        return

    solar_charge_kwh = float(dataframe["laad_uit_solar_kwh"].sum())
    net_charge_kwh = float(dataframe["laad_uit_net_kwh"].sum())
    total_charge_kwh = float(dataframe["laad_kwh"].sum())

    st.caption(title)
    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Totaal geladen",
        f"{total_charge_kwh:.1f} kWh",
    )
    metric_columns[1].metric(
        "Geladen uit zon",
        f"{solar_charge_kwh:.1f} kWh",
        f"{(solar_charge_kwh / total_charge_kwh * 100):.1f}%"
        if total_charge_kwh > 0
        else None,
    )
    metric_columns[2].metric(
        "Geladen uit net",
        f"{net_charge_kwh:.1f} kWh",
        f"{(net_charge_kwh / total_charge_kwh * 100):.1f}%"
        if total_charge_kwh > 0
        else None,
    )


def build_monthly_baseline_cost_table(
    dataframe: pd.DataFrame,
    tariff_engine: TariffEngine,
) -> pd.DataFrame:
    if dataframe.empty:
        return pd.DataFrame()

    costed = tariff_engine.apply_baseline_costs(dataframe)
    monthly = costed.resample("MS").agg({"kosten_zonder_batterij_eur": "sum"})
    monthly["covered_days"] = costed.groupby(costed.index.to_period("M")).apply(
        lambda frame: frame.index.normalize().nunique()
    ).to_numpy()
    monthly["days_in_month"] = monthly.index.days_in_month
    monthly["coverage_ratio"] = monthly["covered_days"] / monthly["days_in_month"]
    monthly["vaste_kosten_eur_prorata"] = (
        tariff_engine.config.fixed_costs_eur_per_month * monthly["coverage_ratio"]
    )
    monthly["baseline_totaal_eur_prorata"] = (
        monthly["kosten_zonder_batterij_eur"] + monthly["vaste_kosten_eur_prorata"]
    )
    monthly["month_number"] = monthly.index.month
    return monthly.reset_index(drop=True)


def render_frank_term_sanity_check(data_manager: DataManager, tariff_engine: TariffEngine) -> None:
    paths = data_manager.get_year_resource_paths(2026)
    if not all(path.exists() for path in paths.values()):
        return

    frank_summaries = data_manager.summarize_frank_term_invoices()
    if not frank_summaries:
        return

    golden_2026 = load_golden_dataframe(2026)
    monthly_baseline = build_monthly_baseline_cost_table(golden_2026, tariff_engine)
    if monthly_baseline.empty:
        return

    invoice_by_month = {summary.month_number: summary for summary in frank_summaries}
    frank_rows = []
    for _, monthly_row in monthly_baseline.iterrows():
        invoice_summary = invoice_by_month.get(int(monthly_row["month_number"]))
        if invoice_summary is None:
            continue
        expected_prorata = (
            invoice_summary.expected_electricity_component_eur * monthly_row["coverage_ratio"]
        )
        frank_rows.append(
            {
                "maand": invoice_summary.month_name_nl,
                "dekking_dagen": int(monthly_row["covered_days"]),
                "dagen_in_maand": int(monthly_row["days_in_month"]),
                "dekkingsratio": round(float(monthly_row["coverage_ratio"]), 3),
                "frank_verwachte_stroomtermijn_eur_prorata": round(expected_prorata, 2),
                "simulatie_baseline_eur_prorata": round(
                    float(monthly_row["baseline_totaal_eur_prorata"]),
                    2,
                ),
                "verschil_eur": round(
                    float(monthly_row["baseline_totaal_eur_prorata"]) - expected_prorata,
                    2,
                ),
                "frank_notabedrag_totaal_eur": round(invoice_summary.invoice_total_eur, 2),
                "frank_gas_component_eur": round(invoice_summary.expected_gas_component_eur, 2),
            }
        )

    if not frank_rows:
        return

    st.subheader("Frank termijn sanity check 2026")
    st.caption(
        "De Frank termijn-PDF's worden hier alleen als referentie gebruikt. "
        "De vergelijking gebruikt de verwachte stroomcomponent uit de termijnfactuur; "
        "gas en eventuele correcties blijven apart zichtbaar."
    )
    st.dataframe(frank_rows, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Thuisbatterij Simulator", layout="wide")
    st.title("Thuisbatterij Simulator")
    st.caption("Feature branch: DataManager")

    data_manager = DataManager()
    exporter = Exporter()
    result_calculator = ResultCalculator()
    sim_engine = SimEngine()

    st.header("Datastatus")
    statuses = data_manager.get_resource_statuses()
    status_rows = [
        {
            "bestand": status.label,
            "aanwezig": status.exists,
            "pad": str(status.path),
            "grootte_mb": round(status.size_bytes / 1024 / 1024, 2)
            if status.size_bytes is not None
            else None,
        }
        for status in statuses
    ]
    st.dataframe(status_rows, use_container_width=True, hide_index=True)

    missing = [status for status in statuses if not status.exists]
    if missing:
        st.error(
            "Niet alle verplichte bronbestanden zijn aanwezig: "
            + ", ".join(status.label for status in missing)
        )
        return

    st.subheader("P1e samenvatting")
    with st.spinner("P1e-bestanden verwerken..."):
        summaries = data_manager.summarize_available_p1e_files()

    summary_rows = [
        {
            "bestand": summary.path.name,
            "intervallen": summary.interval_count,
            "eerste_timestamp": summary.first_timestamp,
            "laatste_timestamp": summary.last_timestamp,
            "totaal_import_kwh": round(summary.total_import_kwh, 3),
            "totaal_export_kwh": round(summary.total_export_kwh, 3),
            "meldingen": summary.issue_count,
            "melding_codes": ", ".join(summary.issue_codes),
        }
        for summary in summaries
    ]
    st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    st.subheader("Golden DataFrame samenvatting")
    with st.spinner("P1e, prijzen en solar combineren..."):
        golden_summaries = data_manager.summarize_available_golden_dataframes()

    golden_rows = [
        {
            "jaar": summary.year,
            "intervallen": summary.interval_count,
            "eerste_timestamp": summary.first_timestamp,
            "laatste_timestamp": summary.last_timestamp,
            "import_kwh": round(summary.total_import_kwh, 3),
            "export_kwh": round(summary.total_export_kwh, 3),
            "solar_kwh": round(summary.total_solar_kwh, 3),
            "verbruik_kwh": round(summary.total_demand_kwh, 3),
            "missende_prijzen": summary.missing_price_count,
            "meldingen": summary.issue_count,
            "melding_codes": ", ".join(summary.issue_codes),
        }
        for summary in golden_summaries
    ]
    st.dataframe(golden_rows, use_container_width=True, hide_index=True)

    st.subheader("Simulatieconfiguratie")
    st.info(
        "Rekenaanname: zonder salderen (2027-model). Netimport en netexport worden apart "
        "afgerekend. Historische profielen uit 2024/2025 worden doorgerekend alsof salderen "
        "niet meer bestaat. Let op: teruglevering gebruikt nu nog de gemodelleerde "
        "verkoopprijs en niet automatisch een bijna-nul vergoeding."
    )
    scenario_choice = st.selectbox("Scenario", options=SCENARIO_OPTIONS)
    scenario_years = resolve_scenario_years(scenario_choice)
    with st.form("simulation_update_form"):
        battery_capacity_kwh = st.number_input(
            "Batterijcapaciteit voorbeeld (kWh)",
            min_value=0.5,
            max_value=50.0,
            value=5.4,
            step=0.5,
        )
        battery_charge_power_kw = st.number_input(
            "Laadvermogen voorbeeld (kW)",
            min_value=0.1,
            max_value=20.0,
            value=2.4,
            step=0.1,
        )
        battery_discharge_power_kw = st.number_input(
            "Ontlaadvermogen voorbeeld (kW)",
            min_value=0.1,
            max_value=20.0,
            value=0.8,
            step=0.1,
        )
        battery_min_soc_pct = st.number_input(
            "Minimale batterijlading (%)",
            min_value=0.0,
            max_value=50.0,
            value=5.0,
            step=1.0,
            help="Ondergrens om een beschermende restlading in de batterij aan te houden.",
        )
        purchase_price_eur = st.number_input(
            "Aanschafprijs voorbeeld (EUR)",
            min_value=0.0,
            max_value=100000.0,
            value=1938.0,
            step=100.0,
        )
        economic_lifetime_years = st.number_input(
            "Economische levensduur voorbeeld (jaren)",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
        )
        use_fixed_sell_price = st.checkbox(
            "Vaste terugleververgoeding gebruiken",
            value=True,
            help="Gebruik een vaste vergoeding voor netexport in plaats van spotprijs plus opslag.",
        )
        fixed_sell_price_eur_per_kwh = st.number_input(
            "Terugleververgoeding (EUR/kWh)",
            min_value=0.0,
            max_value=2.0,
            value=0.0,
            step=0.01,
            disabled=not use_fixed_sell_price,
        )
        detail_year = st.selectbox(
            "Detailgrafiek jaar",
            options=scenario_years,
            format_func=get_year_display_label,
        )
        mode_3_min_price_spread_pct = st.number_input(
            "Slimme modus minimale prijsstijging (%)",
            min_value=0.0,
            max_value=200.0,
            value=20.0,
            step=1.0,
            help=(
                "Netladen voor later verbruik alleen als de verwachte vermeden "
                "inkoopprijs voldoende hoger ligt. Let op: de simulator gebruikt "
                "altijd minstens de economische ondergrens uit het round-trip "
                "rendement van de batterij. Met de huidige defaults is dat ongeveer "
                "10,8%, dus 0%, 5% en 10% geven hetzelfde gedrag."
            ),
        )
        sweep_enabled = st.checkbox("Capaciteitssweep uitvoeren", value=False)
        sweep_year = 2024
        sweep_mode = 1
        sweep_capacity_min_kwh = 1.0
        sweep_capacity_max_kwh = 15.0
        sweep_capacity_step_kwh = 1.0
        sweep_charge_c_rate = 2.4 / 5.4
        sweep_discharge_c_rate = 0.8 / 5.4
        sweep_min_soc_pct = battery_min_soc_pct
        sweep_purchase_base_eur = 0.0
        sweep_purchase_eur_per_kwh = 1000.0
        sweep_price_model = "Vaste marktopties"
        sweep_market_options_text = "\n".join(
            (
                "0;0",
                "2.4;1118.99",
                "5.28;1847.99",
                "8.16;2576.99",
            )
        )
        sweep_criterion_label = "Hoogste NCW"
        if sweep_enabled:
            sweep_mode = st.selectbox(
                "Sweep modus",
                options=(1, 2),
                format_func=lambda x: "Modus 1" if x == 1 else "Slimme modus",
            )
            sweep_capacity_min_kwh = st.number_input(
                "Sweep minimumcapaciteit (kWh)",
                min_value=0.5,
                max_value=100.0,
                value=1.0,
                step=0.5,
            )
            sweep_capacity_max_kwh = st.number_input(
                "Sweep maximumcapaciteit (kWh)",
                min_value=0.5,
                max_value=100.0,
                value=15.0,
                step=0.5,
            )
            sweep_capacity_step_kwh = st.number_input(
                "Sweep stapgrootte (kWh)",
                min_value=0.1,
                max_value=10.0,
                value=1.0,
                step=0.1,
            )
            sweep_charge_c_rate = st.number_input(
                "Sweep laad C-rate",
                min_value=0.1,
                max_value=5.0,
                value=2.4 / 5.4,
                step=0.01,
            )
            sweep_discharge_c_rate = st.number_input(
                "Sweep ontlaad C-rate",
                min_value=0.1,
                max_value=5.0,
                value=0.8 / 5.4,
                step=0.01,
            )
            sweep_price_model = st.selectbox(
                "Sweep prijsmodel",
                options=("Lineair prijsmodel", "Vaste marktopties"),
                index=1,
            )
            sweep_min_soc_pct = st.number_input(
                "Sweep minimale batterijlading (%)",
                min_value=0.0,
                max_value=50.0,
                value=battery_min_soc_pct,
                step=1.0,
                help="Ondergrens die in alle doorgerekende sweep-opties wordt gebruikt.",
            )
            if sweep_price_model == "Lineair prijsmodel":
                sweep_purchase_base_eur = st.number_input(
                    "Sweep basisprijs (EUR)",
                    min_value=0.0,
                    max_value=100000.0,
                    value=0.0,
                    step=100.0,
                )
                sweep_purchase_eur_per_kwh = st.number_input(
                    "Sweep prijs per kWh (EUR/kWh)",
                    min_value=0.0,
                    max_value=10000.0,
                    value=1000.0,
                    step=50.0,
                )
            else:
                sweep_market_options_text = st.text_area(
                    "Marktopties capaciteit;prijs",
                    value=sweep_market_options_text,
                    help="Een optie per regel, bijvoorbeeld '5.76;1938'. Alleen deze echte productopties worden dan doorgerekend.",
                )
            sweep_criterion_label = st.selectbox(
                "Aanbevelingscriterium",
                options=(
                    "Hoogste NCW",
                    "Kortste terugverdientijd",
                    "Hoogste jaarlijkse besparing",
                ),
            )
        st.form_submit_button("Simulaties bijwerken", type="primary")

    tariff_config = TariffConfig(
        fixed_sell_price_eur_per_kwh=(
            fixed_sell_price_eur_per_kwh if use_fixed_sell_price else None
        )
    )
    tariff_engine = TariffEngine(tariff_config)
    capacity_sweep_runner = CapacitySweepRunner(tariff_engine=tariff_engine)

    st.subheader("Baseline jaarkosten zonder batterij")
    cost_rows = []
    baseline_summaries = {}
    with st.spinner("Baselinekosten berekenen..."):
        for year in scenario_years:
            paths = data_manager.get_year_resource_paths(year)
            if not all(path.exists() for path in paths.values()):
                continue
            golden_dataframe = load_golden_dataframe(year)
            cost_summary = tariff_engine.summarize_baseline_costs(golden_dataframe)
            baseline_summaries[year] = cost_summary
            cost_rows.append(
                {
                    "scenario": get_year_display_label(year),
                    "importkosten_eur": round(cost_summary.import_costs_eur, 2),
                    "exportopbrengst_eur": round(cost_summary.export_revenue_eur, 2),
                    "intervalkosten_eur": round(cost_summary.interval_costs_eur, 2),
                    "vaste_kosten_eur": round(cost_summary.fixed_costs_eur, 2),
                    "totaal_eur": round(cost_summary.total_costs_eur, 2),
                    "missende_prijzen": cost_summary.missing_price_count,
                }
            )
        if len(baseline_summaries) > 1:
            year_count = len(baseline_summaries)
            cost_rows.append(
                {
                    "scenario": format_scenario_label(scenario_choice),
                    "importkosten_eur": round(
                        sum(summary.import_costs_eur for summary in baseline_summaries.values())
                        / year_count,
                        2,
                    ),
                    "exportopbrengst_eur": round(
                        sum(summary.export_revenue_eur for summary in baseline_summaries.values())
                        / year_count,
                        2,
                    ),
                    "intervalkosten_eur": round(
                        sum(summary.interval_costs_eur for summary in baseline_summaries.values())
                        / year_count,
                        2,
                    ),
                    "vaste_kosten_eur": round(
                        sum(summary.fixed_costs_eur for summary in baseline_summaries.values())
                        / year_count,
                        2,
                    ),
                    "totaal_eur": round(
                        sum(summary.total_costs_eur for summary in baseline_summaries.values())
                        / year_count,
                        2,
                    ),
                    "missende_prijzen": sum(
                        summary.missing_price_count for summary in baseline_summaries.values()
                    ),
                }
            )
    st.dataframe(cost_rows, use_container_width=True, hide_index=True)
    if 2026 in scenario_years:
        render_frank_term_sanity_check(data_manager, tariff_engine)

    battery_config = BatteryConfig(
        capacity_kwh=battery_capacity_kwh,
        charge_power_kw=battery_charge_power_kw,
        discharge_power_kw=battery_discharge_power_kw,
        charge_efficiency_pct=95.0,
        discharge_efficiency_pct=95.0,
        min_soc_pct=battery_min_soc_pct,
    )
    result_config = ResultConfig(
        purchase_price_eur=purchase_price_eur,
        economic_lifetime_years=economic_lifetime_years,
        battery_capacity_kwh=battery_capacity_kwh,
    )

    smart_mode_config = ModeConfig(
        min_price_spread_pct=mode_3_min_price_spread_pct,
    )

    st.subheader("Modus 1 voorbeeld: zelfconsumptie")

    mode_1_rows = []
    mode_1_detail = pd.DataFrame()
    mode_1_yearly = {}
    with st.spinner("Modus 1 voorbeeldsimulatie uitvoeren..."):
        for year in scenario_years:
            paths = data_manager.get_year_resource_paths(year)
            if not all(path.exists() for path in paths.values()):
                continue
            golden_dataframe = load_golden_dataframe(year)
            simulated = sim_engine.simulate_mode_1(golden_dataframe, battery_config)
            baseline_costs = tariff_engine.summarize_baseline_costs(simulated)
            battery_costs = tariff_engine.summarize_battery_costs(simulated)
            costed = tariff_engine.apply_battery_costs(simulated)
            mode_1_yearly[year] = costed
            if year == detail_year:
                mode_1_detail = costed
            result_summary = result_calculator.calculate(costed, result_config)
            mode_1_rows.append(
                build_mode_row(
                    get_year_display_label(year),
                    simulated,
                    result_summary,
                    baseline_costs,
                    battery_costs,
                    result_config,
                )
            )
        if len(mode_1_yearly) > 1:
            combined = combine_yearly_frames(mode_1_yearly)
            combined_result = result_calculator.calculate(combined, result_config)
            mode_1_rows.append(
                build_mode_row(
                    format_scenario_label(scenario_choice),
                    combined,
                    combined_result,
                    tariff_engine.summarize_baseline_costs(combined),
                    tariff_engine.summarize_battery_costs(combined),
                    result_config,
                    year_count=len(mode_1_yearly),
                )
            )
    st.subheader("Slimme modus: slim laden voor eigen verbruik")
    smart_rows = []
    smart_detail = pd.DataFrame()
    smart_yearly = {}

    with st.spinner("Slimme modus simulatie uitvoeren..."):
        for year in scenario_years:
            paths = data_manager.get_year_resource_paths(year)
            if not all(path.exists() for path in paths.values()):
                continue
            golden_dataframe = load_golden_dataframe(year)
            priced = tariff_engine.apply_prices(golden_dataframe)
            simulated = sim_engine.simulate_smart_mode(
                priced,
                battery_config,
                smart_mode_config,
            )
            baseline_costs = tariff_engine.summarize_baseline_costs(simulated)
            battery_costs = tariff_engine.summarize_battery_costs(simulated)
            costed = tariff_engine.apply_battery_costs(simulated)
            smart_yearly[year] = costed
            if year == detail_year:
                smart_detail = costed
            result_summary = result_calculator.calculate(costed, result_config)
            smart_rows.append(
                build_mode_row(
                    get_year_display_label(year),
                    simulated,
                    result_summary,
                    baseline_costs,
                    battery_costs,
                    result_config,
                )
            )
        if len(smart_yearly) > 1:
            combined = combine_yearly_frames(smart_yearly)
            combined_result = result_calculator.calculate(combined, result_config)
            smart_rows.append(
                build_mode_row(
                    format_scenario_label(scenario_choice),
                    combined,
                    combined_result,
                    tariff_engine.summarize_baseline_costs(combined),
                    tariff_engine.summarize_battery_costs(combined),
                    result_config,
                    year_count=len(smart_yearly),
                )
            )
    detail_period_source = next(
        (frame for frame in (mode_1_detail, smart_detail) if not frame.empty),
        pd.DataFrame(),
    )
    if not detail_period_source.empty:
        default_start = detail_period_source["timestamp_nl"].min().date()
        default_end = detail_period_source["timestamp_nl"].max().date()
        detail_period = st.date_input(
            "Detailperiode grafieken",
            value=(default_start, default_end),
            min_value=default_start,
            max_value=default_end,
            help="Deze periode wordt op alle detailgrafieken hieronder toegepast.",
        )
        if isinstance(detail_period, tuple) and len(detail_period) == 2:
            detail_start, detail_end = detail_period
        else:
            detail_start = default_start
            detail_end = default_end
    else:
        detail_start = None
        detail_end = None

    if detail_start is not None and detail_end is not None:
        mode_1_detail = filter_detail_period(mode_1_detail, detail_start, detail_end)
        smart_detail = filter_detail_period(smart_detail, detail_start, detail_end)

    st.dataframe(mode_1_rows, use_container_width=True, hide_index=True)
    render_cost_chart(mode_1_rows, "Modus 1 jaarkosten")
    render_daily_energy_chart(mode_1_detail, f"Modus 1 dagtotalen {detail_year}")
    render_net_exchange_chart(mode_1_detail, f"Modus 1 netuitwisseling {detail_year}")
    render_battery_flow_chart(mode_1_detail, f"Modus 1 batterij-opname en afgifte {detail_year}")
    render_soc_chart(mode_1_detail, f"Modus 1 batterijlading {detail_year}")
    render_solar_self_consumption_summary(mode_1_detail, "Modus 1 zonne-zelfconsumptie")
    render_battery_charge_source_summary(mode_1_detail, "Modus 1 laadbronnen batterij")
    render_soc_summary(mode_1_detail, "Modus 1 batterijgebruik")
    render_soc_distribution_chart(mode_1_detail, f"Modus 1 SoC-verdeling {detail_year}")
    render_simulation_exports(exporter, mode_1_detail, f"modus_1_{detail_year}")
    if mode_1_rows:
        mode_1_export = pd.DataFrame(mode_1_rows)
        st.download_button(
            "Download Modus 1 KPI CSV",
            data=exporter.to_csv_bytes(mode_1_export),
            file_name="modus_1_kpi.csv",
            mime="text/csv",
            on_click="ignore",
        )

    st.dataframe(smart_rows, use_container_width=True, hide_index=True)
    render_cost_chart(smart_rows, "Slimme modus jaarkosten")
    render_daily_energy_chart(smart_detail, f"Slimme modus dagtotalen {detail_year}")
    render_net_exchange_chart(smart_detail, f"Slimme modus netuitwisseling {detail_year}")
    render_battery_flow_chart(smart_detail, f"Slimme modus batterij-opname en afgifte {detail_year}")
    render_soc_chart(smart_detail, f"Slimme modus batterijlading {detail_year}")
    render_solar_self_consumption_summary(smart_detail, "Slimme modus zonne-zelfconsumptie")
    render_battery_charge_source_summary(smart_detail, "Slimme modus laadbronnen batterij")
    render_soc_summary(smart_detail, "Slimme modus batterijgebruik")
    render_soc_distribution_chart(smart_detail, f"Slimme modus SoC-verdeling {detail_year}")
    render_simulation_exports(exporter, smart_detail, f"slimme_modus_{detail_year}")
    if smart_rows:
        smart_export = pd.DataFrame(smart_rows)
        st.download_button(
            "Download Slimme modus KPI CSV",
            data=exporter.to_csv_bytes(smart_export),
            file_name="slimme_modus_kpi.csv",
            mime="text/csv",
            on_click="ignore",
        )

    st.subheader("Capaciteitssweep voorbeeld")
    if sweep_enabled:
        st.caption(
            "NCW = netto contante waarde: de huidige waarde van alle toekomstige "
            "jaarlijkse besparingen minus de aanschafprijs."
        )
        sweep_criterion = {
            "Hoogste NCW": "hoogste_ncw",
            "Kortste terugverdientijd": "kortste_terugverdientijd",
            "Hoogste jaarlijkse besparing": "hoogste_jaarlijkse_besparing",
        }[sweep_criterion_label]

        sweep_mode_config = smart_mode_config
        sweep_is_valid = True
        if sweep_mode == 2 and sweep_mode_config is None:
            st.error("Slimme modus sweep vereist geldige instellingen.")
            sweep_is_valid = False

        if sweep_is_valid:
            sweep_frames = {}
            for year in scenario_years:
                paths = data_manager.get_year_resource_paths(year)
                if not all(path.exists() for path in paths.values()):
                    st.error(f"Niet alle bronbestanden voor {year} zijn aanwezig.")
                    sweep_is_valid = False
                    break
                sweep_frames[year] = load_golden_dataframe(year)

        if sweep_enabled and sweep_is_valid:
            market_options = ()
            if sweep_price_model == "Vaste marktopties":
                try:
                    market_options = parse_market_options(sweep_market_options_text)
                except ValueError as exc:
                    st.error(str(exc))
                    sweep_is_valid = False

        if sweep_enabled and sweep_is_valid:
            with st.spinner("Capaciteitssweep uitvoeren..."):
                sweep_result = capacity_sweep_runner.run(
                    sweep_frames,
                    SweepConfig(
                        capacity_min_kwh=sweep_capacity_min_kwh,
                        capacity_max_kwh=sweep_capacity_max_kwh,
                        capacity_step_kwh=sweep_capacity_step_kwh,
                        charge_c_rate=sweep_charge_c_rate,
                        discharge_c_rate=sweep_discharge_c_rate,
                        min_soc_pct=sweep_min_soc_pct,
                        purchase_base_eur=sweep_purchase_base_eur,
                        purchase_eur_per_kwh=sweep_purchase_eur_per_kwh,
                        market_options=market_options,
                        economic_lifetime_years=economic_lifetime_years,
                        mode=sweep_mode,
                        mode_config=sweep_mode_config,
                    ),
                )
            recommendation = CapacitySweepRunner.find_recommendation(
                sweep_result,
                sweep_criterion,
            )
            st.metric(
                "Aanbevolen capaciteit",
                f"{recommendation['capaciteit_kwh']:.1f} kWh",
                f"{recommendation['jaarlijkse_besparing_eur']:.2f} EUR/jaar",
            )
            render_sweep_charts(sweep_result)
            st.dataframe(
                sweep_result.round(
                    {
                        "capaciteit_kwh": 2,
                        "laadvermogen_kw": 2,
                        "ontlaadvermogen_kw": 2,
                        "aanschafprijs_eur": 2,
                        "jaarlijkse_besparing_eur": 2,
                        "terugverdientijd_jr": 2,
                        "ncw_eur": 2,
                        "zelfvoorzienendheid_pct": 1,
                        "zelfconsumptie_pct": 1,
                        "cycli_jaar": 2,
                        "besparing_per_capaciteit_eur_per_kwh": 2,
                        "marginale_besparing_eur_per_kwh": 2,
                        "marginale_ncw_eur_per_kwh": 2,
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download sweep CSV",
                data=exporter.to_csv_bytes(sweep_result),
                file_name=f"sweep_modus_{sweep_mode}_{scenario_choice}.csv",
                mime="text/csv",
                on_click="ignore",
            )
            st.download_button(
                "Download sweep Excel",
                data=exporter.to_excel_bytes({"sweep_resultaten": sweep_result}),
                file_name=f"sweep_modus_{sweep_mode}_{scenario_choice}.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                on_click="ignore",
            )


if __name__ == "__main__":
    main()
