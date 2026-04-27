from io import BytesIO

import pandas as pd

from src.exporter import Exporter


def test_exporter_creates_utf8_csv_bytes():
    dataframe = pd.DataFrame({"jaar": [2024], "besparing_eur": [12.34]})

    result = Exporter.to_csv_bytes(dataframe)

    assert result.startswith(b"\xef\xbb\xbf")
    assert b"jaar,besparing_eur" in result
    assert b"2024,12.34" in result


def test_exporter_creates_excel_workbook_with_safe_sheet_names():
    dataframe = pd.DataFrame({"capaciteit_kwh": [5.0]})

    result = Exporter.to_excel_bytes({"Sweep/Resultaat:2024": dataframe})

    workbook = pd.read_excel(BytesIO(result), sheet_name=None)
    assert "Sweep_Resultaat_2024" in workbook
    assert workbook["Sweep_Resultaat_2024"].loc[0, "capaciteit_kwh"] == 5.0


def test_exporter_selects_available_timeseries_columns_in_stable_order():
    dataframe = pd.DataFrame(
        {
            "actie": ["idle"],
            "unknown": [1],
            "soc_kwh": [2.0],
            "timestamp_nl": ["2024-01-01 00:00"],
        }
    )

    result = Exporter.select_timeseries_columns(dataframe)

    assert result.columns.tolist() == ["timestamp_nl", "soc_kwh", "actie"]
