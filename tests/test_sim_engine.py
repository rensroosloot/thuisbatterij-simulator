import pandas as pd
import pytest

from src.sim_engine import BatteryConfig, SimEngine


def _baseline_frame(values: list[float]) -> pd.DataFrame:
    dataframe = pd.DataFrame({"netto_baseline_kwh": values})
    dataframe["import_zonder_batterij_kwh"] = dataframe["netto_baseline_kwh"].clip(lower=0)
    dataframe["export_zonder_batterij_kwh"] = (-dataframe["netto_baseline_kwh"]).clip(lower=0)
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

