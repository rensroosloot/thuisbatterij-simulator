import pandas as pd
import pytest

from src.data_manager import DataManager


def test_p1e_import_and_export_differences_sum_t1_t2():
    raw = pd.DataFrame(
        {
            "time": ["2024-01-01 00:00", "2024-01-01 00:15", "2024-01-01 00:30"],
            "Import T1 kWh": [10.0, 10.4, 10.6],
            "Import T2 kWh": [20.0, 20.1, 20.4],
            "Export T1 kWh": [1.0, 1.0, 1.2],
            "Export T2 kWh": [2.0, 2.3, 2.5],
        }
    )

    result = DataManager().preprocess_p1e(raw)

    assert result.dataframe["import_kwh"].tolist() == pytest.approx([0.5, 0.5])
    assert result.dataframe["export_kwh"].tolist() == pytest.approx([0.3, 0.4])
    assert result.report.has_issue("P1E_NO_PREVIOUS_READING")


def test_negative_p1e_difference_is_reported_and_zeroed():
    raw = pd.DataFrame(
        {
            "time": ["2024-01-01 00:00", "2024-01-01 00:15"],
            "Import T1 kWh": [10.0, 9.0],
            "Import T2 kWh": [20.0, 20.0],
            "Export T1 kWh": [1.0, 1.0],
            "Export T2 kWh": [2.0, 2.1],
        }
    )

    result = DataManager().preprocess_p1e(raw)

    assert result.report.has_issue("P1E_NEGATIVE_DIFFERENCE")
    assert result.dataframe["import_kwh"].tolist() == [0.0]


def test_duplicate_dst_fall_timestamps_are_summed_after_diff():
    raw = pd.DataFrame(
        {
            "time": [
                "2024-10-27 01:45",
                "2024-10-27 02:00",
                "2024-10-27 02:00",
                "2024-10-27 02:15",
            ],
            "Import T1 kWh": [100.0, 100.2, 100.5, 100.6],
            "Import T2 kWh": [50.0, 50.0, 50.0, 50.0],
            "Export T1 kWh": [20.0, 20.1, 20.3, 20.3],
            "Export T2 kWh": [10.0, 10.0, 10.0, 10.0],
        }
    )

    result = DataManager().preprocess_p1e(raw)

    at_0200 = result.dataframe.loc[pd.Timestamp("2024-10-27 02:00")]
    assert at_0200["import_kwh"] == pytest.approx(0.5)
    assert at_0200["export_kwh"] == pytest.approx(0.3)
    assert result.report.has_issue("P1E_DUPLICATE_LOCAL_TIMESTAMPS")


def test_spring_dst_gap_detects_92_interval_day():
    timestamps = pd.date_range("2024-03-31 00:00", periods=96, freq="15min")
    timestamps = timestamps[
        ~(
            (timestamps >= pd.Timestamp("2024-03-31 02:00"))
            & (timestamps <= pd.Timestamp("2024-03-31 02:45"))
        )
    ]

    assert DataManager().detect_spring_dst_gap(timestamps)


def test_energy_balance_columns_are_calculated():
    dataframe = pd.DataFrame(
        {
            "import_kwh": [1.0, 0.0],
            "export_kwh": [0.0, 0.5],
            "solar_kwh": [0.2, 1.0],
        }
    )

    result = DataManager().calculate_energy_balance(dataframe)

    assert result["demand_kwh"].tolist() == pytest.approx([1.2, 0.5])
    assert result["netto_baseline_kwh"].tolist() == pytest.approx([1.0, -0.5])
    assert result["import_zonder_batterij_kwh"].tolist() == pytest.approx([1.0, 0.0])
    assert result["export_zonder_batterij_kwh"].tolist() == pytest.approx([0.0, 0.5])


def test_energy_balance_tolerance_reports_deviation_above_one_percent():
    dataframe = pd.DataFrame({"import_kwh": [10.2], "export_kwh": [5.0]})

    report = DataManager().validate_energy_balance(
        dataframe,
        expected_import_kwh=10.0,
        expected_export_kwh=5.0,
        tolerance_pct=1.0,
    )

    assert report.has_issue("ENERGY_BALANCE_IMPORT_OUT_OF_TOLERANCE")
    assert not report.has_issue("ENERGY_BALANCE_EXPORT_OUT_OF_TOLERANCE")


def test_resource_statuses_report_expected_files(tmp_path):
    (tmp_path / "P1e-2024-1-1-2024-12-31.csv").write_text("x", encoding="utf-8")

    statuses = DataManager(tmp_path).get_resource_statuses()
    status_by_label = {status.label: status for status in statuses}

    assert status_by_label["P1e 2024"].exists
    assert status_by_label["P1e 2024"].size_bytes == 1
    assert not status_by_label["P1e 2025"].exists


def test_summarize_p1e_file_returns_totals(tmp_path):
    csv_path = tmp_path / "p1e.csv"
    csv_path.write_text(
        "\n".join(
            [
                "time,Import T1 kWh,Import T2 kWh,Export T1 kWh,Export T2 kWh",
                "2024-01-01 00:00,10,20,1,2",
                "2024-01-01 00:15,10.4,20.1,1,2.3",
                "2024-01-01 00:30,10.6,20.4,1.2,2.5",
            ]
        ),
        encoding="utf-8",
    )

    summary = DataManager(tmp_path).summarize_p1e_file(csv_path)

    assert summary.interval_count == 2
    assert summary.total_import_kwh == pytest.approx(1.0)
    assert summary.total_export_kwh == pytest.approx(0.7)
    assert summary.issue_codes == ("P1E_NO_PREVIOUS_READING",)
