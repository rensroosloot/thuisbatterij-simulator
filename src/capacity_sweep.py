"""Capacity sweep support for battery size comparison."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

try:
    from .result_calculator import ResultCalculator, ResultConfig
    from .sim_engine import BatteryConfig, ModeConfig, SimEngine
    from .tariff_engine import TariffEngine
except ImportError:
    from result_calculator import ResultCalculator, ResultConfig
    from sim_engine import BatteryConfig, ModeConfig, SimEngine
    from tariff_engine import TariffEngine


@dataclass(frozen=True)
class SweepConfig:
    """Configuration for a battery capacity sweep."""

    capacity_min_kwh: float = 1.0
    capacity_max_kwh: float = 10.0
    capacity_step_kwh: float = 1.0
    charge_c_rate: float = 0.5
    discharge_c_rate: float = 0.5
    fixed_charge_power_kw: float | None = None
    fixed_discharge_power_kw: float | None = None
    purchase_base_eur: float = 0.0
    purchase_eur_per_kwh: float = 1000.0
    market_options: tuple[tuple[float, float], ...] = ()
    economic_lifetime_years: int = 10
    discount_rate_pct: float = 0.0
    energy_price_indexation_pct: float = 0.0
    degradation_pct_per_100_cycles: float = 0.0
    mode: int = 1
    mode_config: ModeConfig | None = None
    max_points: int = 200


class CapacitySweepRunner:
    """Run battery simulations for a configured capacity range."""

    def __init__(
        self,
        sim_engine: SimEngine | None = None,
        tariff_engine: TariffEngine | None = None,
        result_calculator: ResultCalculator | None = None,
    ) -> None:
        self.sim_engine = sim_engine or SimEngine()
        self.tariff_engine = tariff_engine or TariffEngine()
        self.result_calculator = result_calculator or ResultCalculator()

    def run(
        self,
        dataframe: pd.DataFrame | dict[int, pd.DataFrame],
        config: SweepConfig,
    ) -> pd.DataFrame:
        self._validate_config(config)
        scenario_frames = self._normalize_scenario_frames(dataframe)
        year_count = len(scenario_frames)
        rows = []
        for capacity_kwh in self.generate_capacities(config):
            charge_power_kw = config.fixed_charge_power_kw or capacity_kwh * config.charge_c_rate
            discharge_power_kw = (
                config.fixed_discharge_power_kw or capacity_kwh * config.discharge_c_rate
            )
            battery_config = BatteryConfig(
                capacity_kwh=capacity_kwh,
                charge_power_kw=charge_power_kw,
                discharge_power_kw=discharge_power_kw,
                charge_efficiency_pct=95.0,
                discharge_efficiency_pct=95.0,
            )
            yearly_costed_frames = []
            for yearly_frame in scenario_frames.values():
                simulated = self._simulate(yearly_frame, battery_config, config)
                yearly_costed_frames.append(self.tariff_engine.apply_battery_costs(simulated))
            costed = pd.concat(yearly_costed_frames, axis=0).sort_index()
            purchase_price_eur = self.resolve_purchase_price_eur(capacity_kwh, config)
            result = self.result_calculator.calculate(
                costed,
                ResultConfig(
                    purchase_price_eur=purchase_price_eur,
                    economic_lifetime_years=config.economic_lifetime_years,
                    discount_rate_pct=config.discount_rate_pct,
                    energy_price_indexation_pct=config.energy_price_indexation_pct,
                    battery_capacity_kwh=capacity_kwh,
                    degradation_pct_per_100_cycles=config.degradation_pct_per_100_cycles,
                ),
            )
            annual_saving_eur = result.annual_saving_eur / year_count
            payback_years = (
                purchase_price_eur / annual_saving_eur if annual_saving_eur > 0 else float("inf")
            )
            net_present_value_eur = self.result_calculator.calculate_present_value_of_savings(
                annual_saving_eur,
                ResultConfig(
                    purchase_price_eur=purchase_price_eur,
                    economic_lifetime_years=config.economic_lifetime_years,
                    discount_rate_pct=config.discount_rate_pct,
                    energy_price_indexation_pct=config.energy_price_indexation_pct,
                    battery_capacity_kwh=capacity_kwh,
                    degradation_pct_per_100_cycles=config.degradation_pct_per_100_cycles,
                ),
            ) - purchase_price_eur
            rows.append(
                {
                    "capaciteit_kwh": capacity_kwh,
                    "laadvermogen_kw": charge_power_kw,
                    "ontlaadvermogen_kw": discharge_power_kw,
                    "aanschafprijs_eur": purchase_price_eur,
                    "jaarlijkse_besparing_eur": annual_saving_eur,
                    "terugverdientijd_jr": payback_years,
                    "ncw_eur": net_present_value_eur,
                    "zelfvoorzienendheid_pct": result.self_sufficiency_pct,
                    "zelfconsumptie_pct": result.self_consumption_pct,
                    "cycli_jaar": result.equivalent_full_cycles / year_count,
                    "netladen_kwh": result.net_charging_kwh / year_count,
                    "batterij_export_kwh": result.battery_export_kwh / year_count,
                }
            )

        result_frame = pd.DataFrame(rows)
        return self.add_marginal_columns(result_frame)

    def _simulate(
        self,
        dataframe: pd.DataFrame,
        battery_config: BatteryConfig,
        config: SweepConfig,
    ) -> pd.DataFrame:
        priced = self.tariff_engine.apply_prices(dataframe)
        if config.mode == 1:
            return self.sim_engine.simulate_mode_1(priced, battery_config)
        if config.mode == 2:
            if config.mode_config is None:
                raise ValueError("Smart mode sweep requires mode_config.")
            return self.sim_engine.simulate_smart_mode(
                priced,
                battery_config,
                config.mode_config,
            )
        raise ValueError("Sweep mode must be 1 or 2.")

    @staticmethod
    def _normalize_scenario_frames(
        dataframe: pd.DataFrame | dict[int, pd.DataFrame],
    ) -> dict[int, pd.DataFrame]:
        if isinstance(dataframe, pd.DataFrame):
            return {0: dataframe}
        if not dataframe:
            raise ValueError("Sweep requires at least one scenario dataframe.")
        return dict(sorted(dataframe.items()))

    @staticmethod
    def add_marginal_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
        result = dataframe.copy()
        result["besparing_per_capaciteit_eur_per_kwh"] = (
            result["jaarlijkse_besparing_eur"] / result["capaciteit_kwh"]
        )
        result["marginale_besparing_eur_per_kwh"] = result[
            "jaarlijkse_besparing_eur"
        ].diff() / result["capaciteit_kwh"].diff()
        result["marginale_ncw_eur_per_kwh"] = result["ncw_eur"].diff() / result[
            "capaciteit_kwh"
        ].diff()
        return result

    @staticmethod
    def generate_capacities(config: SweepConfig) -> list[float]:
        CapacitySweepRunner._validate_config(config)
        if config.market_options:
            return [capacity_kwh for capacity_kwh, _ in config.market_options]
        count = int((config.capacity_max_kwh - config.capacity_min_kwh) // config.capacity_step_kwh)
        capacities = [
            round(config.capacity_min_kwh + index * config.capacity_step_kwh, 10)
            for index in range(count + 1)
        ]
        if capacities[-1] < config.capacity_max_kwh:
            capacities.append(round(config.capacity_max_kwh, 10))
        return capacities

    @staticmethod
    def find_recommendation(dataframe: pd.DataFrame, criterion: str) -> pd.Series:
        if dataframe.empty:
            raise ValueError("Sweep result is empty.")
        if criterion == "hoogste_ncw":
            return dataframe.loc[dataframe["ncw_eur"].idxmax()]
        if criterion == "kortste_terugverdientijd":
            finite = dataframe[dataframe["terugverdientijd_jr"] < float("inf")]
            if finite.empty:
                return dataframe.iloc[0]
            return finite.loc[finite["terugverdientijd_jr"].idxmin()]
        if criterion == "hoogste_jaarlijkse_besparing":
            return dataframe.loc[dataframe["jaarlijkse_besparing_eur"].idxmax()]
        raise ValueError("Unknown recommendation criterion.")

    @staticmethod
    def resolve_purchase_price_eur(capacity_kwh: float, config: SweepConfig) -> float:
        if config.market_options:
            market_price_by_capacity = dict(config.market_options)
            return market_price_by_capacity[capacity_kwh]
        return config.purchase_base_eur + (config.purchase_eur_per_kwh * capacity_kwh)

    @staticmethod
    def _validate_config(config: SweepConfig) -> None:
        if config.market_options:
            if len(config.market_options) > config.max_points:
                raise ValueError("Sweep may contain at most 200 market options.")
            capacities = [capacity_kwh for capacity_kwh, _ in config.market_options]
            if any(capacity_kwh <= 0 for capacity_kwh in capacities):
                raise ValueError("Market option capacity must be greater than 0 kWh.")
            if any(price_eur < 0 for _, price_eur in config.market_options):
                raise ValueError("Market option purchase price must be non-negative.")
            if capacities != sorted(set(capacities)):
                raise ValueError("Market option capacities must be unique and sorted ascending.")
            return
        if config.capacity_min_kwh <= 0:
            raise ValueError("Sweep minimum capacity must be greater than 0 kWh.")
        if config.capacity_max_kwh < config.capacity_min_kwh:
            raise ValueError("Sweep maximum capacity must be at least the minimum capacity.")
        if config.capacity_step_kwh <= 0:
            raise ValueError("Sweep capacity step must be greater than 0 kWh.")
        n_points = (
            int((config.capacity_max_kwh - config.capacity_min_kwh) // config.capacity_step_kwh)
            + 1
        )
        if config.capacity_min_kwh + (n_points - 1) * config.capacity_step_kwh < (
            config.capacity_max_kwh
        ):
            n_points += 1
        if n_points > config.max_points:
            raise ValueError("Sweep may contain at most 200 capacity points.")
        if config.fixed_charge_power_kw is not None and config.fixed_charge_power_kw <= 0:
            raise ValueError("Sweep fixed charge power must be greater than 0 kW.")
        if (
            config.fixed_discharge_power_kw is not None
            and config.fixed_discharge_power_kw <= 0
        ):
            raise ValueError("Sweep fixed discharge power must be greater than 0 kW.")
        if config.fixed_charge_power_kw is None and config.charge_c_rate <= 0:
            raise ValueError("Sweep charge C-rate must be greater than 0.")
        if config.fixed_discharge_power_kw is None and config.discharge_c_rate <= 0:
            raise ValueError("Sweep discharge C-rate must be greater than 0.")
