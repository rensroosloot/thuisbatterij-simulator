import math

import pandas as pd
import pytest

from src.result_calculator import ResultCalculator, ResultConfig


def _result_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "kosten_zonder_batterij_eur": [1.00, -0.10],
            "kosten_met_batterij_eur": [0.40, 0.00],
            "import_zonder_batterij_kwh": [4.0, 0.0],
            "import_met_batterij_kwh": [1.0, 0.0],
            "export_zonder_batterij_kwh": [0.0, 2.0],
            "export_met_batterij_kwh": [0.0, 0.5],
            "netladen_kwh": [0.5, 0.0],
            "batterij_export_kwh": [0.0, 0.0],
            "laad_kwh": [0.5, 1.5],
            "ontlaad_kwh": [1.0, 0.0],
            "ontlaad_naar_huis_kwh": [1.0, 0.0],
            "laad_uit_solar_kwh": [0.0, 1.5],
            "round_trip_loss_kwh": [0.1, 0.2],
            "soc_pct": [50.0, 80.0],
            "solar_kwh": [1.0, 3.0],
            "demand_kwh": [4.0, 1.0],
        }
    )


def test_result_calculator_financial_kpis():
    config = ResultConfig(purchase_price_eur=1.0, economic_lifetime_years=2)

    result = ResultCalculator().calculate(_result_frame(), config)

    assert result.total_costs_without_battery_eur == pytest.approx(0.90)
    assert result.total_costs_with_battery_eur == pytest.approx(0.40)
    assert result.annual_saving_eur == pytest.approx(0.50)
    assert result.payback_years == pytest.approx(2.0)
    assert result.break_even_purchase_price_eur == pytest.approx(1.0)
    assert result.net_present_value_eur == pytest.approx(0.0)


def test_result_calculator_payback_is_infinite_when_saving_is_not_positive():
    dataframe = _result_frame()
    dataframe["kosten_met_batterij_eur"] = dataframe["kosten_zonder_batterij_eur"]

    result = ResultCalculator().calculate(dataframe, ResultConfig(purchase_price_eur=1.0))

    assert math.isinf(result.payback_years)


def test_result_calculator_npv_uses_discount_and_indexation():
    config = ResultConfig(
        purchase_price_eur=0.0,
        economic_lifetime_years=2,
        discount_rate_pct=10.0,
        energy_price_indexation_pct=5.0,
    )

    result = ResultCalculator().calculate(_result_frame(), config)

    expected = (0.5 / 1.1) + (0.5 * 1.05 / (1.1**2))
    assert result.net_present_value_eur == pytest.approx(expected)


def test_result_calculator_technical_kpis():
    config = ResultConfig(
        battery_capacity_kwh=2.0,
        degradation_pct_per_100_cycles=2.0,
        max_cycles=6000,
    )

    result = ResultCalculator().calculate(_result_frame(), config)

    assert result.import_without_battery_kwh == pytest.approx(4.0)
    assert result.import_with_battery_kwh == pytest.approx(1.0)
    assert result.export_without_battery_kwh == pytest.approx(2.0)
    assert result.export_with_battery_kwh == pytest.approx(0.5)
    assert result.net_charging_kwh == pytest.approx(0.5)
    assert result.charged_kwh == pytest.approx(2.0)
    assert result.discharged_kwh == pytest.approx(1.0)
    assert result.round_trip_loss_kwh == pytest.approx(0.3)
    assert result.equivalent_full_cycles == pytest.approx(1.0)
    assert result.remaining_cycles == pytest.approx(5999.0)
    assert result.average_soc_pct == pytest.approx(65.0)
    assert result.max_soc_pct == pytest.approx(80.0)
    assert result.self_sufficiency_pct == pytest.approx(60.0)
    assert result.self_consumption_pct == pytest.approx(87.5)
    assert result.direct_solar_self_consumption_without_battery_kwh == pytest.approx(2.0)
    assert result.total_solar_self_consumption_with_battery_kwh == pytest.approx(3.5)
    assert result.extra_solar_self_consumption_by_battery_kwh == pytest.approx(1.5)
    assert result.capacity_loss_kwh == pytest.approx(0.0004)


def test_result_calculator_rejects_invalid_config():
    with pytest.raises(ValueError, match="Battery capacity"):
        ResultCalculator().calculate(_result_frame(), ResultConfig(battery_capacity_kwh=0.0))
