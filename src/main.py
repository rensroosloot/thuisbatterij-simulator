"""Streamlit entrypoint for the thuisbatterij simulator."""

from __future__ import annotations

import streamlit as st

from data_manager import DataManager


def main() -> None:
    st.set_page_config(page_title="Thuisbatterij Simulator", layout="wide")
    st.title("Thuisbatterij Simulator")
    st.caption("Feature branch: DataManager")

    data_manager = DataManager()

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


if __name__ == "__main__":
    main()
