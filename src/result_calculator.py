"""KPI calculations for simulated battery scenarios."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ResultConfig:
    """Financial and technical KPI configuration."""

    purchase_price_eur: float = 0.0
    economic_lifetime_years: int = 10
    discount_rate_pct: float = 0.0
    energy_price_indexation_pct: float = 0.0
    battery_capacity_kwh: float = 5.0
    degradation_pct_per_100_cycles: float = 0.0
    max_cycles: float | None = None

    @property
    def discount_rate(self) -> float:
        return self.discount_rate_pct / 100

    @property
    def energy_price_indexation(self) -> float:
        return self.energy_price_indexation_pct / 100


@dataclass(frozen=True)
class ResultSummary:
    """Aggregated KPIs for one simulated scenario."""

    total_costs_without_battery_eur: float
    total_costs_with_battery_eur: float
    annual_saving_eur: float
    purchase_price_eur: float
    payback_years: float
    net_present_value_eur: float
    break_even_purchase_price_eur: float
    import_without_battery_kwh: float
    import_with_battery_kwh: float
    export_without_battery_kwh: float
    export_with_battery_kwh: float
    net_charging_kwh: float
    battery_export_kwh: float
    charged_kwh: float
    discharged_kwh: float
    round_trip_loss_kwh: float
    equivalent_full_cycles: float
    remaining_cycles: float | None
    average_soc_pct: float
    max_soc_pct: float
    self_sufficiency_pct: float
    self_consumption_pct: float
    direct_solar_self_consumption_without_battery_kwh: float
    total_solar_self_consumption_with_battery_kwh: float
    extra_solar_self_consumption_by_battery_kwh: float
    capacity_loss_kwh: float


class ResultCalculator:
    """Calculate financial and technical KPIs from a costed simulation frame."""

    def calculate(self, dataframe: pd.DataFrame, config: ResultConfig) -> ResultSummary:
        self._validate_config(config)
        self._validate_columns(
            dataframe,
            (
                "kosten_zonder_batterij_eur",
                "kosten_met_batterij_eur",
                "import_zonder_batterij_kwh",
                "import_met_batterij_kwh",
                "export_zonder_batterij_kwh",
                "export_met_batterij_kwh",
                "netladen_kwh",
                "batterij_export_kwh",
                "laad_kwh",
                "ontlaad_kwh",
                "ontlaad_naar_huis_kwh",
                "laad_uit_solar_kwh",
                "round_trip_loss_kwh",
                "soc_pct",
            ),
        )

        total_costs_without_battery_eur = float(dataframe["kosten_zonder_batterij_eur"].sum())
        total_costs_with_battery_eur = float(dataframe["kosten_met_batterij_eur"].sum())
        annual_saving_eur = total_costs_without_battery_eur - total_costs_with_battery_eur
        break_even_purchase_price_eur = self.calculate_present_value_of_savings(
            annual_saving_eur,
            config,
        )
        payback_years = (
            config.purchase_price_eur / annual_saving_eur
            if annual_saving_eur > 0
            else math.inf
        )
        net_present_value_eur = break_even_purchase_price_eur - config.purchase_price_eur

        charged_kwh = float(dataframe["laad_kwh"].sum())
        equivalent_full_cycles = charged_kwh / config.battery_capacity_kwh
        remaining_cycles = (
            config.max_cycles - equivalent_full_cycles if config.max_cycles is not None else None
        )
        capacity_loss_kwh = (
            equivalent_full_cycles
            * (config.degradation_pct_per_100_cycles / 100)
            * config.battery_capacity_kwh
            / 100
        )

        total_demand_kwh = self._get_total_demand_kwh(dataframe)
        total_solar_kwh = float(dataframe["solar_kwh"].sum()) if "solar_kwh" in dataframe else 0.0
        direct_solar_to_home_kwh = self._calculate_direct_solar_to_home(dataframe)
        direct_solar_self_consumption_without_battery_kwh = max(
            total_solar_kwh - float(dataframe["export_zonder_batterij_kwh"].sum()),
            0.0,
        )
        total_solar_self_consumption_with_battery_kwh = max(
            total_solar_kwh - float(dataframe["export_met_batterij_kwh"].sum()),
            0.0,
        )
        extra_solar_self_consumption_by_battery_kwh = max(
            total_solar_self_consumption_with_battery_kwh
            - direct_solar_self_consumption_without_battery_kwh,
            0.0,
        )
        self_sufficiency_pct = self._percentage(
            direct_solar_to_home_kwh + float(dataframe["ontlaad_naar_huis_kwh"].sum()),
            total_demand_kwh,
        )
        self_consumption_pct = self._percentage(
            direct_solar_to_home_kwh + float(dataframe["laad_uit_solar_kwh"].sum()),
            total_solar_kwh,
        )

        return ResultSummary(
            total_costs_without_battery_eur=total_costs_without_battery_eur,
            total_costs_with_battery_eur=total_costs_with_battery_eur,
            annual_saving_eur=annual_saving_eur,
            purchase_price_eur=config.purchase_price_eur,
            payback_years=payback_years,
            net_present_value_eur=net_present_value_eur,
            break_even_purchase_price_eur=break_even_purchase_price_eur,
            import_without_battery_kwh=float(dataframe["import_zonder_batterij_kwh"].sum()),
            import_with_battery_kwh=float(dataframe["import_met_batterij_kwh"].sum()),
            export_without_battery_kwh=float(dataframe["export_zonder_batterij_kwh"].sum()),
            export_with_battery_kwh=float(dataframe["export_met_batterij_kwh"].sum()),
            net_charging_kwh=float(dataframe["netladen_kwh"].sum()),
            battery_export_kwh=float(dataframe["batterij_export_kwh"].sum()),
            charged_kwh=charged_kwh,
            discharged_kwh=float(dataframe["ontlaad_kwh"].sum()),
            round_trip_loss_kwh=float(dataframe["round_trip_loss_kwh"].sum()),
            equivalent_full_cycles=equivalent_full_cycles,
            remaining_cycles=remaining_cycles,
            average_soc_pct=float(dataframe["soc_pct"].mean()) if not dataframe.empty else 0.0,
            max_soc_pct=float(dataframe["soc_pct"].max()) if not dataframe.empty else 0.0,
            self_sufficiency_pct=min(self_sufficiency_pct, 100.0),
            self_consumption_pct=min(self_consumption_pct, 100.0),
            direct_solar_self_consumption_without_battery_kwh=(
                direct_solar_self_consumption_without_battery_kwh
            ),
            total_solar_self_consumption_with_battery_kwh=(
                total_solar_self_consumption_with_battery_kwh
            ),
            extra_solar_self_consumption_by_battery_kwh=(
                extra_solar_self_consumption_by_battery_kwh
            ),
            capacity_loss_kwh=capacity_loss_kwh,
        )

    @staticmethod
    def calculate_present_value_of_savings(
        annual_saving_eur: float,
        config: ResultConfig,
    ) -> float:
        present_value_eur = 0.0
        for year in range(1, config.economic_lifetime_years + 1):
            indexed_saving_eur = annual_saving_eur * (
                (1 + config.energy_price_indexation) ** (year - 1)
            )
            present_value_eur += indexed_saving_eur / ((1 + config.discount_rate) ** year)
        return present_value_eur

    @staticmethod
    def _calculate_direct_solar_to_home(dataframe: pd.DataFrame) -> float:
        if "solar_kwh" not in dataframe or "demand_kwh" not in dataframe:
            return 0.0
        return float(dataframe[["solar_kwh", "demand_kwh"]].min(axis=1).sum())

    @staticmethod
    def _get_total_demand_kwh(dataframe: pd.DataFrame) -> float:
        if "demand_kwh" in dataframe:
            return float(dataframe["demand_kwh"].sum())
        return float(dataframe["import_zonder_batterij_kwh"].sum())

    @staticmethod
    def _percentage(numerator: float, denominator: float) -> float:
        return (numerator / denominator * 100) if denominator > 0 else 0.0

    @staticmethod
    def _validate_config(config: ResultConfig) -> None:
        if config.purchase_price_eur < 0:
            raise ValueError("Purchase price must be non-negative.")
        if config.economic_lifetime_years <= 0:
            raise ValueError("Economic lifetime must be greater than 0.")
        if config.battery_capacity_kwh <= 0:
            raise ValueError("Battery capacity must be greater than 0 kWh.")
        if config.discount_rate <= -1:
            raise ValueError("Discount rate must be greater than -100%.")

    @staticmethod
    def _validate_columns(dataframe: pd.DataFrame, required: tuple[str, ...]) -> None:
        missing = [column for column in required if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")
