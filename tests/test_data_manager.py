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


def test_data_quality_flags_columns_use_category_dtype():
    raw_p1e = pd.DataFrame(
        {
            "time": ["2024-01-01 00:00", "2024-01-01 00:15"],
            "Import T1 kWh": [10.0, 10.1],
            "Import T2 kWh": [20.0, 20.0],
            "Export T1 kWh": [1.0, 1.0],
            "Export T2 kWh": [2.0, 2.0],
        }
    )
    raw_solar = pd.DataFrame(
        {
            "entity_id": [
                "sensor.gerardus_total_energieopbrengst_levenslang",
                "sensor.gerardus_total_energieopbrengst_levenslang",
            ],
            "state": ["100.0", "101.0"],
            "last_changed": ["2024-01-01T09:00:00.000Z", "2024-01-01T10:00:00.000Z"],
        }
    )

    p1e_result = DataManager().preprocess_p1e(raw_p1e)
    solar_result = DataManager().preprocess_solar_lifetime(raw_solar)

    assert isinstance(p1e_result.dataframe["data_quality_flags"].dtype, pd.CategoricalDtype)
    assert isinstance(solar_result.dataframe["data_quality_flags"].dtype, pd.CategoricalDtype)


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


def test_spring_dst_gap_ignores_non_march_92_interval_day():
    timestamps = pd.date_range("2024-01-10 00:00", periods=96, freq="15min")
    timestamps = timestamps[
        ~(
            (timestamps >= pd.Timestamp("2024-01-10 02:00"))
            & (timestamps <= pd.Timestamp("2024-01-10 02:45"))
        )
    ]

    assert not DataManager().detect_spring_dst_gap(timestamps)


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


def test_price_csv_parser_handles_semicolon_and_decimal_comma(tmp_path):
    csv_path = tmp_path / "prices.csv"
    csv_path.write_text(
        "\n".join(
            [
                "datum_nl;datum_utc;prijs_excl_belastingen",
                '"2024-01-01 00:00:00";"2023-12-31 23:00:00";0,123456',
            ]
        ),
        encoding="utf-8",
    )

    prices = DataManager(tmp_path).load_price_csv(csv_path)

    assert prices.loc[pd.Timestamp("2024-01-01 00:00:00"), "spot_price_eur_per_kwh"] == (
        pytest.approx(0.123456)
    )


def test_solar_lifetime_is_distributed_to_quarters_with_energy_conservation():
    raw = pd.DataFrame(
        {
            "entity_id": [
                "sensor.gerardus_total_energieopbrengst_levenslang",
                "sensor.gerardus_total_energieopbrengst_levenslang",
            ],
            "state": ["100.0", "101.0"],
            "last_changed": ["2024-01-01T09:00:00.000Z", "2024-01-01T10:00:00.000Z"],
        }
    )

    result = DataManager().preprocess_solar_lifetime(raw)

    assert result.dataframe["solar_kwh"].sum() == pytest.approx(1.0)
    assert result.dataframe["solar_kwh"].tolist() == pytest.approx([0.25, 0.25, 0.25, 0.25])


def test_solar_lifetime_non_hour_timestamp_is_aligned_to_quarter_grid():
    raw = pd.DataFrame(
        {
            "entity_id": [
                "sensor.gerardus_total_energieopbrengst_levenslang",
                "sensor.gerardus_total_energieopbrengst_levenslang",
            ],
            "state": ["100.0", "101.0"],
            "last_changed": ["2024-01-01T09:03:00.000Z", "2024-01-01T10:03:00.000Z"],
        }
    )

    result = DataManager().preprocess_solar_lifetime(raw)

    assert result.dataframe.index.tolist() == [
        pd.Timestamp("2024-01-01 10:00:00"),
        pd.Timestamp("2024-01-01 10:15:00"),
        pd.Timestamp("2024-01-01 10:30:00"),
        pd.Timestamp("2024-01-01 10:45:00"),
    ]
    assert result.dataframe["solar_kwh"].sum() == pytest.approx(1.0)


def test_build_golden_dataframe_joins_p1e_price_and_solar(tmp_path):
    p1e_path = tmp_path / "p1e.csv"
    p1e_path.write_text(
        "\n".join(
            [
                "time,Import T1 kWh,Import T2 kWh,Export T1 kWh,Export T2 kWh",
                "2024-01-01 10:30,10,20,1,2",
                "2024-01-01 10:45,10.4,20.1,1,2.3",
            ]
        ),
        encoding="utf-8",
    )
    price_path = tmp_path / "prices.csv"
    price_path.write_text(
        "\n".join(
            [
                "datum_nl;datum_utc;prijs_excl_belastingen",
                '"2024-01-01 10:45:00";"2024-01-01 09:45:00";0,100000',
            ]
        ),
        encoding="utf-8",
    )
    solar_path = tmp_path / "solar.csv"
    solar_path.write_text(
        "\n".join(
            [
                "entity_id,state,last_changed",
                "sensor.gerardus_total_energieopbrengst_levenslang,100.0,2024-01-01T09:00:00.000Z",
                "sensor.gerardus_total_energieopbrengst_levenslang,101.0,2024-01-01T10:00:00.000Z",
            ]
        ),
        encoding="utf-8",
    )

    result = DataManager(tmp_path).build_golden_dataframe(p1e_path, price_path, solar_path)
    row = result.dataframe.loc[pd.Timestamp("2024-01-01 10:45:00")]

    assert row["import_kwh"] == pytest.approx(0.5)
    assert row["export_kwh"] == pytest.approx(0.3)
    assert row["spot_price_eur_per_kwh"] == pytest.approx(0.1)
    assert row["solar_kwh"] == pytest.approx(0.25)
    assert row["demand_kwh"] == pytest.approx(0.45)


def test_build_golden_dataframe_forward_fills_hourly_prices_to_quarters(tmp_path):
    p1e_path = tmp_path / "p1e.csv"
    p1e_path.write_text(
        "\n".join(
            [
                "time,Import T1 kWh,Import T2 kWh,Export T1 kWh,Export T2 kWh",
                "2024-01-01 00:00,10,20,1,2",
                "2024-01-01 00:15,10.1,20,1,2",
                "2024-01-01 00:30,10.2,20,1,2",
                "2024-01-01 00:45,10.3,20,1,2",
                "2024-01-01 01:00,10.4,20,1,2",
            ]
        ),
        encoding="utf-8",
    )
    price_path = tmp_path / "prices.csv"
    price_path.write_text(
        "\n".join(
            [
                "datum_nl;datum_utc;prijs_excl_belastingen",
                '"2024-01-01 00:00:00";"2023-12-31 23:00:00";0,100000',
                '"2024-01-01 01:00:00";"2024-01-01 00:00:00";0,200000',
            ]
        ),
        encoding="utf-8",
    )
    solar_path = tmp_path / "solar.csv"
    solar_path.write_text(
        "\n".join(
            [
                "entity_id,state,last_changed",
                "sensor.gerardus_total_energieopbrengst_levenslang,100.0,2024-01-01T00:00:00.000Z",
            ]
        ),
        encoding="utf-8",
    )

    result = DataManager(tmp_path).build_golden_dataframe(p1e_path, price_path, solar_path)

    assert result.dataframe["spot_price_eur_per_kwh"].isna().sum() == 0
    assert result.dataframe.loc[pd.Timestamp("2024-01-01 00:15"), "spot_price_eur_per_kwh"] == (
        pytest.approx(0.1)
    )
    assert result.dataframe.loc[pd.Timestamp("2024-01-01 00:45"), "spot_price_eur_per_kwh"] == (
        pytest.approx(0.1)
    )
    assert result.dataframe.loc[pd.Timestamp("2024-01-01 01:00"), "spot_price_eur_per_kwh"] == (
        pytest.approx(0.2)
    )


def test_build_golden_dataframe_uses_category_dtype_for_data_quality_flags(tmp_path):
    p1e_path = tmp_path / "p1e.csv"
    p1e_path.write_text(
        "\n".join(
            [
                "time,Import T1 kWh,Import T2 kWh,Export T1 kWh,Export T2 kWh",
                "2024-01-01 00:00,10,20,1,2",
                "2024-01-01 00:15,10.1,20,1,2",
            ]
        ),
        encoding="utf-8",
    )
    price_path = tmp_path / "prices.csv"
    price_path.write_text(
        "\n".join(
            [
                "datum_nl;datum_utc;prijs_excl_belastingen",
                '"2024-01-01 00:15:00";"2023-12-31 23:15:00";0,100000',
            ]
        ),
        encoding="utf-8",
    )
    solar_path = tmp_path / "solar.csv"
    solar_path.write_text(
        "\n".join(
            [
                "entity_id,state,last_changed",
                "sensor.gerardus_total_energieopbrengst_levenslang,100.0,2024-01-01T00:00:00.000Z",
            ]
        ),
        encoding="utf-8",
    )

    result = DataManager(tmp_path).build_golden_dataframe(p1e_path, price_path, solar_path)

    assert isinstance(result.dataframe["data_quality_flags"].dtype, pd.CategoricalDtype)


def test_summarize_golden_dataframe_returns_joined_totals(tmp_path):
    p1e_path = tmp_path / "p1e.csv"
    p1e_path.write_text(
        "\n".join(
            [
                "time,Import T1 kWh,Import T2 kWh,Export T1 kWh,Export T2 kWh",
                "2024-01-01 10:30,10,20,1,2",
                "2024-01-01 10:45,10.4,20.1,1,2.3",
            ]
        ),
        encoding="utf-8",
    )
    price_path = tmp_path / "prices.csv"
    price_path.write_text(
        "\n".join(
            [
                "datum_nl;datum_utc;prijs_excl_belastingen",
                '"2024-01-01 10:45:00";"2024-01-01 09:45:00";0,100000',
            ]
        ),
        encoding="utf-8",
    )
    solar_path = tmp_path / "solar.csv"
    solar_path.write_text(
        "\n".join(
            [
                "entity_id,state,last_changed",
                "sensor.gerardus_total_energieopbrengst_levenslang,100.0,2024-01-01T09:00:00.000Z",
                "sensor.gerardus_total_energieopbrengst_levenslang,101.0,2024-01-01T10:00:00.000Z",
            ]
        ),
        encoding="utf-8",
    )

    result = DataManager(tmp_path).build_golden_dataframe(p1e_path, price_path, solar_path)
    summary = DataManager(tmp_path).summarize_golden_dataframe(2024, result)

    assert summary.year == 2024
    assert summary.interval_count == 1
    assert summary.total_import_kwh == pytest.approx(0.5)
    assert summary.total_export_kwh == pytest.approx(0.3)
    assert summary.total_solar_kwh == pytest.approx(0.25)
    assert summary.total_demand_kwh == pytest.approx(0.45)
    assert summary.missing_price_count == 0
