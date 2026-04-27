"""Tariff calculations for the thuisbatterij simulator."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TariffConfig:
    """Configurable electricity tariff parameters.

    Defaults follow URS-001 §2.3 for Frank Energie dynamic electricity in the
    post-saldering 2027 scenario. Amounts are EUR/kWh unless stated otherwise.
    """

    buy_markup_eur_per_kwh: float = 0.01815
    sell_markup_eur_per_kwh: float = 0.01850
    energy_tax_buy_eur_per_kwh: float = 0.12286
    energy_tax_sell_eur_per_kwh: float = 0.0
    fixed_costs_eur_per_month: float = -8.66
    fixed_sell_price_eur_per_kwh: float | None = None


@dataclass(frozen=True)
class BaselineCostSummary:
    """Yearly baseline cost summary without battery."""

    interval_costs_eur: float
    fixed_costs_eur: float
    total_costs_eur: float
    import_costs_eur: float
    export_revenue_eur: float
    missing_price_count: int


class TariffEngine:
    """Apply tariffs and baseline cost calculations to a Golden DataFrame."""

    def __init__(self, config: TariffConfig | None = None) -> None:
        self.config = config or TariffConfig()

    def apply_prices(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        self._validate_columns(dataframe, ("spot_price_eur_per_kwh",))

        result = dataframe.copy()
        result["buy_price_eur_per_kwh"] = (
            result["spot_price_eur_per_kwh"]
            + self.config.buy_markup_eur_per_kwh
            + self.config.energy_tax_buy_eur_per_kwh
        )
        if self.config.fixed_sell_price_eur_per_kwh is None:
            result["sell_price_eur_per_kwh"] = (
                result["spot_price_eur_per_kwh"]
                + self.config.sell_markup_eur_per_kwh
                + self.config.energy_tax_sell_eur_per_kwh
            )
        else:
            result["sell_price_eur_per_kwh"] = self.config.fixed_sell_price_eur_per_kwh
        return result

    def apply_baseline_costs(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        result = self.apply_prices(dataframe)
        self._validate_columns(
            result,
            (
                "import_zonder_batterij_kwh",
                "export_zonder_batterij_kwh",
                "buy_price_eur_per_kwh",
                "sell_price_eur_per_kwh",
            ),
        )

        has_price = result["spot_price_eur_per_kwh"].notna()
        result["kosten_zonder_batterij_eur"] = 0.0
        if has_price.any():
            result.loc[has_price, "kosten_zonder_batterij_eur"] = (
                result.loc[has_price, "import_zonder_batterij_kwh"]
                * result.loc[has_price, "buy_price_eur_per_kwh"]
                - result.loc[has_price, "export_zonder_batterij_kwh"]
                * result.loc[has_price, "sell_price_eur_per_kwh"]
            )
        return result

    def summarize_baseline_costs(self, dataframe: pd.DataFrame) -> BaselineCostSummary:
        costed = self.apply_baseline_costs(dataframe)
        return self.summarize_costed_dataframe(
            costed,
            cost_column="kosten_zonder_batterij_eur",
            import_column="import_zonder_batterij_kwh",
            export_column="export_zonder_batterij_kwh",
        )

    def apply_battery_costs(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        result = self.apply_prices(dataframe)
        self._validate_columns(
            result,
            (
                "import_met_batterij_kwh",
                "export_met_batterij_kwh",
                "import_zonder_batterij_kwh",
                "export_zonder_batterij_kwh",
                "buy_price_eur_per_kwh",
                "sell_price_eur_per_kwh",
            ),
        )

        has_price = result["spot_price_eur_per_kwh"].notna()
        result["kosten_zonder_batterij_eur"] = 0.0
        result["kosten_met_batterij_eur"] = 0.0
        result["besparing_interval_eur"] = 0.0
        if has_price.any():
            result.loc[has_price, "kosten_zonder_batterij_eur"] = (
                result.loc[has_price, "import_zonder_batterij_kwh"]
                * result.loc[has_price, "buy_price_eur_per_kwh"]
                - result.loc[has_price, "export_zonder_batterij_kwh"]
                * result.loc[has_price, "sell_price_eur_per_kwh"]
            )
            result.loc[has_price, "kosten_met_batterij_eur"] = (
                result.loc[has_price, "import_met_batterij_kwh"]
                * result.loc[has_price, "buy_price_eur_per_kwh"]
                - result.loc[has_price, "export_met_batterij_kwh"]
                * result.loc[has_price, "sell_price_eur_per_kwh"]
            )
            result.loc[has_price, "besparing_interval_eur"] = (
                result.loc[has_price, "kosten_zonder_batterij_eur"]
                - result.loc[has_price, "kosten_met_batterij_eur"]
            )
        return result

    def summarize_battery_costs(self, dataframe: pd.DataFrame) -> BaselineCostSummary:
        costed = self.apply_battery_costs(dataframe)
        return self.summarize_costed_dataframe(
            costed,
            cost_column="kosten_met_batterij_eur",
            import_column="import_met_batterij_kwh",
            export_column="export_met_batterij_kwh",
        )

    def summarize_costed_dataframe(
        self,
        dataframe: pd.DataFrame,
        cost_column: str,
        import_column: str,
        export_column: str,
    ) -> BaselineCostSummary:
        self._validate_columns(
            dataframe,
            (
                "spot_price_eur_per_kwh",
                import_column,
                export_column,
                "buy_price_eur_per_kwh",
                "sell_price_eur_per_kwh",
                cost_column,
            ),
        )
        has_price = dataframe["spot_price_eur_per_kwh"].notna()

        import_costs_eur = float(
            (
                dataframe.loc[has_price, import_column]
                * dataframe.loc[has_price, "buy_price_eur_per_kwh"]
            ).sum()
        )
        export_revenue_eur = float(
            (
                dataframe.loc[has_price, export_column]
                * dataframe.loc[has_price, "sell_price_eur_per_kwh"]
            ).sum()
        )
        interval_costs_eur = float(dataframe[cost_column].sum())
        fixed_costs_eur = self.config.fixed_costs_eur_per_month * 12

        return BaselineCostSummary(
            interval_costs_eur=interval_costs_eur,
            fixed_costs_eur=fixed_costs_eur,
            total_costs_eur=interval_costs_eur + fixed_costs_eur,
            import_costs_eur=import_costs_eur,
            export_revenue_eur=export_revenue_eur,
            missing_price_count=int(dataframe["spot_price_eur_per_kwh"].isna().sum()),
        )

    @staticmethod
    def _validate_columns(dataframe: pd.DataFrame, required: tuple[str, ...]) -> None:
        missing = [column for column in required if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")
