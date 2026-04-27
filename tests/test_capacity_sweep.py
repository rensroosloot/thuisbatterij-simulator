import pandas as pd
import pytest

from src.capacity_sweep import CapacitySweepRunner, SweepConfig


def _sweep_frame() -> pd.DataFrame:
    dataframe = pd.DataFrame(
        {
            "spot_price_eur_per_kwh": [0.10, 0.20],
            "netto_baseline_kwh": [-1.0, 1.0],
            "import_zonder_batterij_kwh": [0.0, 1.0],
            "export_zonder_batterij_kwh": [1.0, 0.0],
            "solar_kwh": [2.0, 0.0],
            "demand_kwh": [1.0, 1.0],
        }
    )
    dataframe.index = pd.date_range("2024-01-01 00:00", periods=2, freq="15min")
    return dataframe


def test_capacity_sweep_generates_expected_capacity_points():
    config = SweepConfig(capacity_min_kwh=1.0, capacity_max_kwh=2.0, capacity_step_kwh=0.5)

    capacities = CapacitySweepRunner.generate_capacities(config)

    assert capacities == [1.0, 1.5, 2.0]


def test_capacity_sweep_rejects_more_than_200_points():
    config = SweepConfig(capacity_min_kwh=1.0, capacity_max_kwh=202.0, capacity_step_kwh=1.0)

    with pytest.raises(ValueError, match="200"):
        CapacitySweepRunner.generate_capacities(config)


def test_capacity_sweep_runs_mode_1_and_calculates_marginal_columns():
    config = SweepConfig(
        capacity_min_kwh=1.0,
        capacity_max_kwh=2.0,
        capacity_step_kwh=1.0,
        charge_c_rate=4.0,
        discharge_c_rate=2.0,
        purchase_base_eur=100.0,
        purchase_eur_per_kwh=500.0,
        economic_lifetime_years=10,
        mode=1,
    )

    result = CapacitySweepRunner().run(_sweep_frame(), config)

    assert result["capaciteit_kwh"].tolist() == [1.0, 2.0]
    assert result["laadvermogen_kw"].tolist() == [4.0, 8.0]
    assert result["ontlaadvermogen_kw"].tolist() == [2.0, 4.0]
    assert result["aanschafprijs_eur"].tolist() == [600.0, 1100.0]
    assert "besparing_per_capaciteit_eur_per_kwh" in result.columns
    assert "marginale_besparing_eur_per_kwh" in result.columns
    assert pd.isna(result.loc[0, "marginale_besparing_eur_per_kwh"])


def test_capacity_sweep_recommendation_uses_selected_criterion():
    dataframe = pd.DataFrame(
        {
            "capaciteit_kwh": [1.0, 2.0],
            "jaarlijkse_besparing_eur": [50.0, 80.0],
            "terugverdientijd_jr": [12.0, 10.0],
            "ncw_eur": [100.0, 80.0],
        }
    )

    highest_saving = CapacitySweepRunner.find_recommendation(
        dataframe,
        "hoogste_jaarlijkse_besparing",
    )

    assert highest_saving["capaciteit_kwh"] == 2.0


def test_capacity_sweep_combined_scenario_annualizes_results():
    config = SweepConfig(
        capacity_min_kwh=1.0,
        capacity_max_kwh=1.0,
        capacity_step_kwh=1.0,
        charge_c_rate=4.0,
        discharge_c_rate=2.0,
        purchase_base_eur=100.0,
        purchase_eur_per_kwh=500.0,
        economic_lifetime_years=10,
        mode=1,
    )

    single_year = CapacitySweepRunner().run(_sweep_frame(), config)
    combined_years = CapacitySweepRunner().run(
        {
            2024: _sweep_frame(),
            2025: _sweep_frame().rename(lambda ts: ts + pd.DateOffset(years=1)),
        },
        config,
    )

    assert combined_years.loc[0, "jaarlijkse_besparing_eur"] == pytest.approx(
        single_year.loc[0, "jaarlijkse_besparing_eur"]
    )
    assert combined_years.loc[0, "cycli_jaar"] == pytest.approx(single_year.loc[0, "cycli_jaar"])


def test_capacity_sweep_uses_explicit_market_options():
    config = SweepConfig(
        market_options=((2.4, 1339.0), (5.76, 1938.0), (8.64, 2667.0)),
        charge_c_rate=1.0,
        discharge_c_rate=1.0,
        economic_lifetime_years=10,
        mode=1,
    )

    result = CapacitySweepRunner().run(_sweep_frame(), config)

    assert result["capaciteit_kwh"].tolist() == [2.4, 5.76, 8.64]
    assert result["aanschafprijs_eur"].tolist() == [1339.0, 1938.0, 2667.0]
