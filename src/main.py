"""Streamlit entrypoint for the thuisbatterij simulator."""

from __future__ import annotations

import streamlit as st

from data_manager import DataManager
from sim_engine import BatteryConfig, SimEngine
from tariff_engine import TariffEngine


def main() -> None:
    st.set_page_config(page_title="Thuisbatterij Simulator", layout="wide")
    st.title("Thuisbatterij Simulator")
    st.caption("Feature branch: DataManager")

    data_manager = DataManager()
    sim_engine = SimEngine()
    tariff_engine = TariffEngine()

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

    st.subheader("Baseline jaarkosten zonder batterij")
    cost_rows = []
    with st.spinner("Baselinekosten berekenen..."):
        for year in (2024, 2025):
            paths = data_manager.get_year_resource_paths(year)
            if not all(path.exists() for path in paths.values()):
                continue
            golden = data_manager.build_golden_dataframe(
                paths["p1e"],
                paths["prices"],
                paths["solar"],
            )
            cost_summary = tariff_engine.summarize_baseline_costs(golden.dataframe)
            cost_rows.append(
                {
                    "jaar": year,
                    "importkosten_eur": round(cost_summary.import_costs_eur, 2),
                    "exportopbrengst_eur": round(cost_summary.export_revenue_eur, 2),
                    "intervalkosten_eur": round(cost_summary.interval_costs_eur, 2),
                    "vaste_kosten_eur": round(cost_summary.fixed_costs_eur, 2),
                    "totaal_eur": round(cost_summary.total_costs_eur, 2),
                    "missende_prijzen": cost_summary.missing_price_count,
                }
            )
    st.dataframe(cost_rows, use_container_width=True, hide_index=True)

    st.subheader("Modus 1 voorbeeld: zelfconsumptie")
    battery_capacity_kwh = st.number_input(
        "Batterijcapaciteit voorbeeld (kWh)",
        min_value=0.5,
        max_value=50.0,
        value=5.0,
        step=0.5,
    )
    battery_power_kw = st.number_input(
        "Laad-/ontlaadvermogen voorbeeld (kW)",
        min_value=0.1,
        max_value=20.0,
        value=2.4,
        step=0.1,
    )
    battery_config = BatteryConfig(
        capacity_kwh=battery_capacity_kwh,
        charge_power_kw=battery_power_kw,
        discharge_power_kw=battery_power_kw,
        charge_efficiency_pct=95.0,
        discharge_efficiency_pct=95.0,
    )

    mode_1_rows = []
    with st.spinner("Modus 1 voorbeeldsimulatie uitvoeren..."):
        for year in (2024, 2025):
            paths = data_manager.get_year_resource_paths(year)
            if not all(path.exists() for path in paths.values()):
                continue
            golden = data_manager.build_golden_dataframe(
                paths["p1e"],
                paths["prices"],
                paths["solar"],
            )
            simulated = sim_engine.simulate_mode_1(golden.dataframe, battery_config)
            mode_1_rows.append(
                {
                    "jaar": year,
                    "import_zonder_batterij_kwh": round(
                        float(simulated["import_zonder_batterij_kwh"].sum()), 3
                    ),
                    "import_met_batterij_kwh": round(
                        float(simulated["import_met_batterij_kwh"].sum()), 3
                    ),
                    "export_zonder_batterij_kwh": round(
                        float(simulated["export_zonder_batterij_kwh"].sum()), 3
                    ),
                    "export_met_batterij_kwh": round(
                        float(simulated["export_met_batterij_kwh"].sum()), 3
                    ),
                    "geladen_solar_kwh": round(float(simulated["laad_uit_solar_kwh"].sum()), 3),
                    "ontladen_huis_kwh": round(
                        float(simulated["ontlaad_naar_huis_kwh"].sum()), 3
                    ),
                    "verlies_kwh": round(float(simulated["round_trip_loss_kwh"].sum()), 3),
                    "eind_soc_kwh": round(float(simulated["soc_kwh"].iloc[-1]), 3)
                    if not simulated.empty
                    else 0.0,
                }
            )
    st.dataframe(mode_1_rows, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
