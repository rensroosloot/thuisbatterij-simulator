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


def _priced_frame_with_sell(
    values: list[float],
    buy_prices: list[float],
    sell_prices: list[float],
) -> pd.DataFrame:
    dataframe = _priced_frame(values, buy_prices)
    dataframe["sell_price_eur_per_kwh"] = sell_prices
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


def test_simulation_action_column_uses_category_dtype():
    dataframe = _baseline_frame([-1.0, 1.0])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )

    result = SimEngine().simulate_mode_1(dataframe, config)

    assert isinstance(result["actie"].dtype, pd.CategoricalDtype)
    assert result["actie"].tolist() == ["solar_charge", "discharge_home"]


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


def test_mode_3_requires_high_export_threshold():
    dataframe = _priced_frame_with_sell([0.0], [0.10], [0.10])
    config = BatteryConfig()
    mode_config = ModeConfig()

    with pytest.raises(ValueError, match="high threshold"):
        SimEngine().simulate_mode_3(dataframe, config, mode_config)


def test_mode_3_requires_high_export_percentile():
    dataframe = _priced_frame_with_sell([0.0], [0.10], [0.10])
    config = BatteryConfig()
    mode_config = ModeConfig(
        decision_rule="percentile",
    )

    with pytest.raises(ValueError, match="high percentile"):
        SimEngine().simulate_mode_3(dataframe, config, mode_config)


def test_mode_3_grid_charges_when_next_day_deficit_price_is_high_enough():
    dataframe = _priced_frame_with_sell([0.0, 1.0], [0.10, 0.40], [0.05, 0.10])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(
        min_price_spread_pct=20.0,
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result.iloc[0]["laad_uit_net_kwh"] == pytest.approx(1.0)
    assert result.iloc[1]["ontlaad_naar_huis_kwh"] == pytest.approx(1.0)
    assert result.iloc[1]["ontlaad_naar_net_kwh"] == pytest.approx(0.0)


def test_mode_3_does_not_grid_charge_when_future_price_rise_is_too_small():
    dataframe = _priced_frame_with_sell([0.0, 1.0], [0.10, 0.11], [0.05, 0.05])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(
        min_price_spread_pct=20.0,
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result["laad_uit_net_kwh"].sum() == 0
    assert result["ontlaad_naar_net_kwh"].sum() == 0


def test_mode_3_looks_across_day_boundary_for_next_day_self_supply_gap():
    dataframe = _baseline_frame([0.0, 1.0])
    dataframe["buy_price_eur_per_kwh"] = [0.10, 0.40]
    dataframe["sell_price_eur_per_kwh"] = [0.05, 0.10]
    dataframe.index = pd.to_datetime(["2024-01-01 23:45", "2024-01-02 00:00"])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(
        min_price_spread_pct=20.0,
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result.iloc[0]["future_max_avoid_price_next_24h_eur_per_kwh"] == pytest.approx(0.40)
    assert result.iloc[0]["laad_uit_net_kwh"] == pytest.approx(1.0)


def test_mode_3_price_lookahead_before_1300_stops_at_end_of_same_day():
    index = pd.to_datetime(
        [
            "2024-01-01 12:45",
            "2024-01-01 13:00",
            "2024-01-02 00:00",
        ]
    )
    dataframe = _baseline_frame([0.0, 1.0, 1.0])
    dataframe["buy_price_eur_per_kwh"] = [0.10, 0.20, 0.60]
    dataframe["sell_price_eur_per_kwh"] = [0.05, 0.05, 0.05]
    dataframe.index = index
    mode_config = ModeConfig(
        min_price_spread_pct=20.0,
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, BatteryConfig(), mode_config)

    assert result.iloc[0]["future_max_avoid_price_next_24h_eur_per_kwh"] == pytest.approx(0.20)


def test_mode_3_price_lookahead_after_1300_includes_next_24_hours():
    index = pd.to_datetime(
        [
            "2024-01-01 13:00",
            "2024-01-02 00:00",
            "2024-01-02 12:45",
        ]
    )
    dataframe = _baseline_frame([0.0, 1.0, 1.0])
    dataframe["buy_price_eur_per_kwh"] = [0.10, 0.20, 0.60]
    dataframe["sell_price_eur_per_kwh"] = [0.05, 0.05, 0.05]
    dataframe.index = index
    mode_config = ModeConfig(
        min_price_spread_pct=20.0,
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, BatteryConfig(), mode_config)

    assert result.iloc[0]["future_max_avoid_price_next_24h_eur_per_kwh"] == pytest.approx(0.60)


def test_mode_3_reserve_stops_at_next_meaningful_solar_recharge_window():
    dataframe = _priced_frame_with_sell(
        [0.0, 1.0, -0.2, 2.0],
        [0.05, 0.40, 0.50, 0.60],
        [0.05, 0.05, 0.05, 0.05],
    )
    config = BatteryConfig(
        capacity_kwh=4.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(
        min_price_spread_pct=20.0,
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result.iloc[0]["future_required_reserve_kwh_before_next_solar_window"] == pytest.approx(
        1.0
    )
    assert result.iloc[0]["laad_uit_net_kwh"] == pytest.approx(1.0)


def test_mode_3_exports_above_household_demand_at_high_price():
    dataframe = _priced_frame_with_sell([0.25], [0.40], [0.50])
    config = BatteryConfig(
        capacity_kwh=2.0,
        discharge_power_kw=4.0,
        discharge_efficiency_pct=100.0,
        start_soc_pct=100.0,
    )
    mode_config = ModeConfig(
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result.iloc[0]["ontlaad_naar_huis_kwh"] == pytest.approx(0.25)
    assert result.iloc[0]["ontlaad_naar_net_kwh"] == pytest.approx(0.75)
    assert result.iloc[0]["import_met_batterij_kwh"] == pytest.approx(0.0)


def test_mode_3_charges_solar_before_exporting_surplus():
    dataframe = _priced_frame_with_sell([-2.0], [0.05], [0.05])
    config = BatteryConfig(
        capacity_kwh=1.0,
        charge_power_kw=4.0,
        charge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(
        threshold_high_eur_per_kwh=0.30,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result.iloc[0]["laad_uit_solar_kwh"] == pytest.approx(1.0)
    assert result.iloc[0]["laad_uit_net_kwh"] == 0
    assert result.iloc[0]["export_met_batterij_kwh"] == pytest.approx(1.0)


def test_mode_3_percentile_uses_future_high_export_price_within_same_day():
    dataframe = _priced_frame_with_sell(
        [0.0, 0.0, 0.0],
        [0.10, 0.20, 0.40],
        [0.10, 0.20, 0.60],
    )
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(
        decision_rule="percentile",
        percentile_high=75,
    )

    result = SimEngine().simulate_mode_3(dataframe, config, mode_config)

    assert result.iloc[0]["expected_export_revenue_eur_per_kwh"] == pytest.approx(0.60)


def test_smart_mode_never_exports_and_grid_charges_for_future_household_need():
    dataframe = _priced_frame([0.0, 1.0], [0.10, 0.40])
    config = BatteryConfig(
        capacity_kwh=2.0,
        charge_power_kw=4.0,
        discharge_power_kw=4.0,
        charge_efficiency_pct=100.0,
        discharge_efficiency_pct=100.0,
    )
    mode_config = ModeConfig(min_price_spread_pct=20.0)

    result = SimEngine().simulate_smart_mode(dataframe, config, mode_config)

    assert result.iloc[0]["laad_uit_net_kwh"] == pytest.approx(1.0)
    assert result.iloc[1]["ontlaad_naar_huis_kwh"] == pytest.approx(1.0)
    assert result["ontlaad_naar_net_kwh"].sum() == pytest.approx(0.0)
