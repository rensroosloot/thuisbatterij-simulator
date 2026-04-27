import pandas as pd
import pytest

from src.sim_engine import BatteryConfig, ModeConfig, SimEngine


def _baseline_frame(values: list[float]) -> pd.DataFrame:
    dataframe = pd.DataFrame({"netto_baseline_kwh": values})
    dataframe["import_zonder_batterij_kwh"] = dataframe["netto_baseline_kwh"].clip(lower=0)
    dataframe["export_zonder_batterij_kwh"] = (-dataframe["netto_baseline_kwh"]).clip(lower=0)
    return dataframe


def _priced_frame(values: list[float], prices: list[float]) -> pd.DataFrame:
    dataframe = _baseline_frame(values)
    dataframe["buy_price_eur_per_kwh"] = prices
    dataframe.index = pd.date_range("2024-01-01 00:00", periods=len(values), freq="15min")
    return dataframe


def test_mode_1_charges_from_solar_surplus_with_efficiency():
    dataframe = _baseline_frame([-1.0])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        charge_efficiency_pct=90.0,
    )

    result = SimEngine().simulate_mode_1(dataframe, config)

    assert result.loc[0, "laad_uit_solar_kwh"] == pytest.approx(1.0)
    assert result.loc[0, "laad_uit_net_kwh"] == 0
    assert result.loc[0, "soc_kwh"] == pytest.approx(0.9)
    assert result.loc[0, "round_trip_loss_kwh"] == pytest.approx(0.1)
    assert result.loc[0, "export_met_batterij_kwh"] == pytest.approx(0.0)


def test_mode_1_respects_charge_power_and_soc_maximum():
    dataframe = _baseline_frame([-2.0])
    config = BatteryConfig(
        capacity_kwh=1.0,
        charge_power_kw=2.0,
        charge_efficiency_pct=100.0,
        max_soc_pct=50.0,
    )

    result = SimEngine().simulate_mode_1(dataframe, config)

    assert result.loc[0, "laad_uit_solar_kwh"] == pytest.approx(0.5)
    assert result.loc[0, "soc_kwh"] == pytest.approx(0.5)
    assert result.loc[0, "soc_pct"] == pytest.approx(50.0)
    assert result.loc[0, "export_met_batterij_kwh"] == pytest.approx(1.5)


def test_mode_1_discharges_to_household_demand_with_efficiency():
    dataframe = _baseline_frame([1.0])
    config = BatteryConfig(
        capacity_kwh=2.0,
        discharge_power_kw=4.0,
        discharge_efficiency_pct=80.0,
        start_soc_pct=50.0,
    )

    result = SimEngine().simulate_mode_1(dataframe, config)

    assert result.loc[0, "ontlaad_naar_huis_kwh"] == pytest.approx(0.8)
    assert result.loc[0, "ontlaad_kwh"] == pytest.approx(1.0)
    assert result.loc[0, "round_trip_loss_kwh"] == pytest.approx(0.2)
    assert result.loc[0, "import_met_batterij_kwh"] == pytest.approx(0.2)
    assert result.loc[0, "soc_kwh"] == pytest.approx(0.0)


def test_mode_1_does_not_export_battery_energy_or_charge_from_grid():
    dataframe = _baseline_frame([-1.0, 1.0, 2.0])
    config = BatteryConfig(
        capacity_kwh=5.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )

    result = SimEngine().simulate_mode_1(dataframe, config)

    assert result["laad_uit_net_kwh"].sum() == 0
    assert result["ontlaad_naar_net_kwh"].sum() == 0
    assert result["batterij_export_kwh"].sum() == 0


def test_mode_1_never_violates_minimum_soc():
    dataframe = _baseline_frame([2.0])
    config = BatteryConfig(
        capacity_kwh=10.0,
        discharge_power_kw=10.0,
        discharge_efficiency_pct=100.0,
        min_soc_pct=20.0,
        start_soc_pct=30.0,
    )

    result = SimEngine().simulate_mode_1(dataframe, config)

    assert result.loc[0, "soc_kwh"] == pytest.approx(2.0)
    assert result.loc[0, "ontlaad_naar_huis_kwh"] == pytest.approx(1.0)
    assert result.loc[0, "import_met_batterij_kwh"] == pytest.approx(1.0)


def test_mode_2_future_max_lookahead_stays_within_day():
    dataframe = _priced_frame([0.0, 1.0, 0.0], [0.10, 0.30, 0.20])

    future = SimEngine().calculate_future_max_avoid_price(dataframe)

    assert future.iloc[0] == pytest.approx(0.30)
    assert pd.isna(future.iloc[1])
    assert pd.isna(future.iloc[2])


def test_mode_2_does_not_look_across_day_boundary():
    dataframe = _baseline_frame([0.0, 1.0])
    dataframe["buy_price_eur_per_kwh"] = [0.05, 0.50]
    dataframe.index = pd.to_datetime(["2024-01-01 23:45", "2024-01-02 00:00"])

    future = SimEngine().calculate_future_max_avoid_price(dataframe)

    assert pd.isna(future.iloc[0])


def test_mode_2_grid_charges_when_future_price_exceeds_loss_and_margin():
    dataframe = _priced_frame([0.0, 1.0], [0.10, 0.50])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )

    result = SimEngine().simulate_mode_2(dataframe, config, ModeConfig(min_margin_eur_per_kwh=0.0))

    assert result.iloc[0]["laad_uit_net_kwh"] == pytest.approx(1.0)
    assert result.iloc[0]["import_met_batterij_kwh"] == pytest.approx(1.0)
    assert result.iloc[1]["ontlaad_naar_huis_kwh"] == pytest.approx(1.0)
    assert result["ontlaad_naar_net_kwh"].sum() == 0


def test_mode_2_does_not_grid_charge_when_margin_is_not_met():
    dataframe = _priced_frame([0.0, 1.0], [0.10, 0.11])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )

    result = SimEngine().simulate_mode_2(dataframe, config, ModeConfig(min_margin_eur_per_kwh=0.02))

    assert result["laad_uit_net_kwh"].sum() == 0


def test_mode_2_solar_charge_has_priority_over_grid_charge():
    dataframe = _priced_frame([-1.0, 1.0], [0.10, 0.50])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )

    result = SimEngine().simulate_mode_2(dataframe, config)

    assert result.iloc[0]["laad_uit_solar_kwh"] == pytest.approx(1.0)
    assert result.iloc[0]["laad_uit_net_kwh"] == 0


def test_mode_2_never_exports_battery_energy():
    dataframe = _priced_frame([0.0, 2.0], [0.01, 1.00])
    config = BatteryConfig(
        capacity_kwh=5.0,
        charge_power_kw=10.0,
        discharge_power_kw=10.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )

    result = SimEngine().simulate_mode_2(dataframe, config)

    assert result["ontlaad_naar_net_kwh"].sum() == 0
    assert result["batterij_export_kwh"].sum() == 0
