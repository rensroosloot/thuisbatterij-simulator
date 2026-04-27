"""Export helpers for dashboard tables."""

from __future__ import annotations

from io import BytesIO

import pandas as pd


class Exporter:
    """Create download payloads for tabular results."""

    DEFAULT_TIMESERIES_COLUMNS = (
        "timestamp_nl",
        "solar_kwh",
        "demand_kwh",
        "import_zonder_batterij_kwh",
        "export_zonder_batterij_kwh",
        "soc_kwh",
        "soc_pct",
        "laad_kwh",
        "ontlaad_kwh",
        "import_met_batterij_kwh",
        "export_met_batterij_kwh",
        "spot_price_eur_per_kwh",
        "buy_price_eur_per_kwh",
        "sell_price_eur_per_kwh",
        "kosten_zonder_batterij_eur",
        "kosten_met_batterij_eur",
        "besparing_interval_eur",
        "actie",
    )

    @staticmethod
    def to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
        return dataframe.to_csv(index=False).encode("utf-8-sig")

    @staticmethod
    def to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
        if not sheets:
            raise ValueError("At least one sheet is required for Excel export.")

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for sheet_name, dataframe in sheets.items():
                safe_name = Exporter._safe_sheet_name(sheet_name)
                dataframe.to_excel(writer, sheet_name=safe_name, index=False)
        return output.getvalue()

    @staticmethod
    def _safe_sheet_name(sheet_name: str) -> str:
        invalid_characters = ("\\", "/", "*", "[", "]", ":", "?")
        safe_name = sheet_name
        for character in invalid_characters:
            safe_name = safe_name.replace(character, "_")
        return safe_name[:31] or "Sheet"

    @staticmethod
    def select_timeseries_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
        columns = [
            column for column in Exporter.DEFAULT_TIMESERIES_COLUMNS if column in dataframe.columns
        ]
        return dataframe[columns].copy()
