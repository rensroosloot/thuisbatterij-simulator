import pandas as pd
import pytest

from src.tariff_engine import TariffConfig, TariffEngine


def test_apply_prices_uses_frank_energy_defaults():
    dataframe = pd.DataFrame({"spot_price_eur_per_kwh": [0.10]})

    result = TariffEngine().apply_prices(dataframe)

    assert result.loc[0, "buy_price_eur_per_kwh"] == pytest.approx(0.24101)
    assert result.loc[0, "sell_price_eur_per_kwh"] == pytest.approx(0.11850)


def test_apply_prices_allows_negative_spot_prices():
    dataframe = pd.DataFrame({"spot_price_eur_per_kwh": [-0.05]})

    result = TariffEngine().apply_prices(dataframe)

    assert result.loc[0, "buy_price_eur_per_kwh"] == pytest.approx(0.09101)
    assert result.loc[0, "sell_price_eur_per_kwh"] == pytest.approx(-0.03150)


def test_apply_prices_allows_fixed_export_compensation():
    dataframe = pd.DataFrame({"spot_price_eur_per_kwh": [0.10, -0.05]})

    result = TariffEngine(
        TariffConfig(fixed_sell_price_eur_per_kwh=0.0)
    ).apply_prices(dataframe)

    assert result["sell_price_eur_per_kwh"].tolist() == [0.0, 0.0]


def test_baseline_costs_import_minus_export_revenue():
    dataframe = pd.DataFrame(
        {
            "spot_price_eur_per_kwh": [0.10, 0.05],
            "import_zonder_batterij_kwh": [2.0, 0.0],
            "export_zonder_batterij_kwh": [0.0, 1.0],
        }
    )

    result = TariffEngine().apply_baseline_costs(dataframe)

    assert result["kosten_zonder_batterij_eur"].tolist() == pytest.approx(
        [2.0 * 0.24101, -(0.05 + 0.01850)]
    )


def test_missing_price_interval_cost_is_zero():
    dataframe = pd.DataFrame(
        {
            "spot_price_eur_per_kwh": [None],
            "import_zonder_batterij_kwh": [2.0],
            "export_zonder_batterij_kwh": [0.0],
        }
    )

    result = TariffEngine().apply_baseline_costs(dataframe)

    assert result.loc[0, "kosten_zonder_batterij_eur"] == 0.0


def test_baseline_summary_includes_fixed_costs():
    dataframe = pd.DataFrame(
        {
            "spot_price_eur_per_kwh": [0.10],
            "import_zonder_batterij_kwh": [2.0],
            "export_zonder_batterij_kwh": [0.0],
        }
    )
    engine = TariffEngine(TariffConfig(fixed_costs_eur_per_month=-8.66))

    summary = engine.summarize_baseline_costs(dataframe)

    assert summary.interval_costs_eur == pytest.approx(2.0 * 0.24101)
    assert summary.fixed_costs_eur == pytest.approx(-103.92)
    assert summary.total_costs_eur == pytest.approx((2.0 * 0.24101) - 103.92)
    assert summary.missing_price_count == 0


def test_battery_costs_use_post_battery_import_and_export():
    dataframe = pd.DataFrame(
        {
            "spot_price_eur_per_kwh": [0.10, 0.05],
            "import_zonder_batterij_kwh": [2.0, 0.0],
            "export_zonder_batterij_kwh": [0.0, 1.0],
            "import_met_batterij_kwh": [0.5, 0.0],
            "export_met_batterij_kwh": [0.0, 0.25],
        }
    )

    result = TariffEngine().apply_battery_costs(dataframe)

    baseline_costs = 2.0 * 0.24101 - (0.05 + 0.01850)
    battery_costs = 0.5 * 0.24101 - 0.25 * (0.05 + 0.01850)
    assert result["kosten_met_batterij_eur"].sum() == pytest.approx(battery_costs)
    assert result["besparing_interval_eur"].sum() == pytest.approx(
        baseline_costs - battery_costs
    )


def test_battery_summary_uses_post_battery_energy_flows():
    dataframe = pd.DataFrame(
        {
            "spot_price_eur_per_kwh": [0.10],
            "import_zonder_batterij_kwh": [2.0],
            "export_zonder_batterij_kwh": [0.0],
            "import_met_batterij_kwh": [0.5],
            "export_met_batterij_kwh": [0.0],
        }
    )

    summary = TariffEngine().summarize_battery_costs(dataframe)

    assert summary.import_costs_eur == pytest.approx(0.5 * 0.24101)
    assert summary.export_revenue_eur == 0.0
    assert summary.interval_costs_eur == pytest.approx(0.5 * 0.24101)
