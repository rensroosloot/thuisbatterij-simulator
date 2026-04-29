"""Battery simulation engine."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ACTION_VALUES = (
    "idle",
    "solar_charge",
    "grid_charge",
    "discharge_home",
    "discharge_export",
)
ACTION_DTYPE = pd.CategoricalDtype(categories=ACTION_VALUES)
SOLAR_RECHARGE_SURPLUS_KWH_THRESHOLD = 0.05


@dataclass(frozen=True)
class BatteryConfig:
    """Battery configuration with explicit units."""

    capacity_kwh: float = 5.0
    charge_power_kw: float = 2.4
    discharge_power_kw: float = 2.4
    charge_efficiency_pct: float = 95.0
    discharge_efficiency_pct: float = 95.0
    min_soc_pct: float = 0.0
    max_soc_pct: float = 100.0
    start_soc_pct: float = 0.0

    @property
    def charge_efficiency(self) -> float:
        return self.charge_efficiency_pct / 100

    @property
    def discharge_efficiency(self) -> float:
        return self.discharge_efficiency_pct / 100

    @property
    def min_soc_kwh(self) -> float:
        return self.capacity_kwh * self.min_soc_pct / 100

    @property
    def max_soc_kwh(self) -> float:
        return self.capacity_kwh * self.max_soc_pct / 100

    @property
    def start_soc_kwh(self) -> float:
        return self.capacity_kwh * self.start_soc_pct / 100


@dataclass(frozen=True)
class ModeConfig:
    """Operating mode configuration."""

    min_margin_eur_per_kwh: float = 0.0
    min_price_spread_pct: float = 20.0
    decision_rule: str = "threshold"
    threshold_high_eur_per_kwh: float | None = None
    percentile_high: float | None = None


class SimEngine:
    """Stateful battery simulation."""

    def simulate_mode_1(self, dataframe: pd.DataFrame, config: BatteryConfig) -> pd.DataFrame:
        """Simulate self-consumption mode.

        Mode 1 charges only from solar surplus and discharges only to household
        demand. It never charges from the grid and never exports battery energy.
        """

        self._validate_config(config)
        self._validate_columns(dataframe, ("netto_baseline_kwh",))

        result = dataframe.copy()

        soc_kwh = min(max(config.start_soc_kwh, config.min_soc_kwh), config.max_soc_kwh)
        charge_limit_kwh = config.charge_power_kw * 0.25
        discharge_limit_kwh = config.discharge_power_kw * 0.25
        arrays = self._initialise_result_arrays(result)
        netto_values = result["netto_baseline_kwh"].to_numpy(dtype=float)

        for row_number, netto_baseline_kwh in enumerate(netto_values):
            arrays["actie"][row_number] = "idle"

            if netto_baseline_kwh < 0:
                surplus_kwh = -netto_baseline_kwh
                storage_room_kwh = max(config.max_soc_kwh - soc_kwh, 0.0)
                max_input_by_room_kwh = storage_room_kwh / config.charge_efficiency
                charge_input_kwh = min(surplus_kwh, charge_limit_kwh, max_input_by_room_kwh)
                soc_increase_kwh = charge_input_kwh * config.charge_efficiency
                soc_kwh += soc_increase_kwh

                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_solar_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] = charge_input_kwh - soc_increase_kwh
                arrays["export_met_batterij_kwh"][row_number] = surplus_kwh - charge_input_kwh
                if charge_input_kwh > 0:
                    arrays["actie"][row_number] = "solar_charge"

            elif netto_baseline_kwh > 0:
                demand_kwh = netto_baseline_kwh
                available_soc_kwh = max(soc_kwh - config.min_soc_kwh, 0.0)
                max_delivered_by_soc_kwh = available_soc_kwh * config.discharge_efficiency
                delivered_kwh = min(demand_kwh, discharge_limit_kwh, max_delivered_by_soc_kwh)
                discharge_from_soc_kwh = delivered_kwh / config.discharge_efficiency
                soc_kwh -= discharge_from_soc_kwh

                arrays["ontlaad_kwh"][row_number] = discharge_from_soc_kwh
                arrays["ontlaad_naar_huis_kwh"][row_number] = delivered_kwh
                arrays["round_trip_loss_kwh"][row_number] = discharge_from_soc_kwh - delivered_kwh
                arrays["import_met_batterij_kwh"][row_number] = demand_kwh - delivered_kwh
                if delivered_kwh > 0:
                    arrays["actie"][row_number] = "discharge_home"

            arrays["soc_kwh"][row_number] = soc_kwh
            arrays["soc_pct"][row_number] = (
                soc_kwh / config.capacity_kwh * 100 if config.capacity_kwh else 0.0
            )

        self._apply_result_arrays(result, arrays)
        return result

    def simulate_mode_2(
        self,
        dataframe: pd.DataFrame,
        battery_config: BatteryConfig,
        mode_config: ModeConfig | None = None,
    ) -> pd.DataFrame:
        """Simulate smart charging without export to the grid."""

        mode_config = mode_config or ModeConfig()
        self._validate_config(battery_config)
        self._validate_columns(dataframe, ("netto_baseline_kwh", "buy_price_eur_per_kwh"))

        result = dataframe.copy()
        result["future_max_avoid_price_eur_per_kwh"] = self.calculate_future_max_avoid_price(
            result
        )
        arrays = self._initialise_result_arrays(result)

        soc_kwh = min(
            max(battery_config.start_soc_kwh, battery_config.min_soc_kwh),
            battery_config.max_soc_kwh,
        )
        charge_limit_kwh = battery_config.charge_power_kw * 0.25
        discharge_limit_kwh = battery_config.discharge_power_kw * 0.25
        round_trip_efficiency = (
            battery_config.charge_efficiency * battery_config.discharge_efficiency
        )
        netto_values = result["netto_baseline_kwh"].to_numpy(dtype=float)
        buy_prices = result["buy_price_eur_per_kwh"].to_numpy(dtype=float)
        future_prices = result["future_max_avoid_price_eur_per_kwh"].to_numpy(dtype=float)

        for row_number, netto_baseline_kwh in enumerate(netto_values):
            arrays["actie"][row_number] = "idle"
            charged_this_interval = False

            if netto_baseline_kwh < 0:
                surplus_kwh = -netto_baseline_kwh
                charge_input_kwh, soc_increase_kwh = self._calculate_charge(
                    available_input_kwh=surplus_kwh,
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += soc_increase_kwh
                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_solar_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] += charge_input_kwh - soc_increase_kwh
                arrays["export_met_batterij_kwh"][row_number] = surplus_kwh - charge_input_kwh
                charged_this_interval = charge_input_kwh > 0
                if charged_this_interval:
                    arrays["actie"][row_number] = "solar_charge"

            if netto_baseline_kwh >= 0 and self._should_grid_charge_prices(
                buy_price=buy_prices[row_number],
                future_price=future_prices[row_number],
                round_trip_efficiency=round_trip_efficiency,
                min_margin_eur_per_kwh=mode_config.min_margin_eur_per_kwh,
            ):
                charge_input_kwh, soc_increase_kwh = self._calculate_charge(
                    available_input_kwh=charge_limit_kwh,
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += soc_increase_kwh
                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_net_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] += charge_input_kwh - soc_increase_kwh
                arrays["import_met_batterij_kwh"][row_number] = (
                    max(netto_baseline_kwh, 0.0) + charge_input_kwh
                )
                charged_this_interval = charge_input_kwh > 0
                if charged_this_interval:
                    arrays["actie"][row_number] = "grid_charge"

            if netto_baseline_kwh > 0 and not charged_this_interval:
                delivered_kwh, discharge_from_soc_kwh = self._calculate_discharge_to_home(
                    demand_kwh=netto_baseline_kwh,
                    discharge_limit_kwh=discharge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh -= discharge_from_soc_kwh
                arrays["ontlaad_kwh"][row_number] = discharge_from_soc_kwh
                arrays["ontlaad_naar_huis_kwh"][row_number] = delivered_kwh
                arrays["round_trip_loss_kwh"][row_number] += discharge_from_soc_kwh - delivered_kwh
                arrays["import_met_batterij_kwh"][row_number] = netto_baseline_kwh - delivered_kwh
                if delivered_kwh > 0:
                    arrays["actie"][row_number] = "discharge_home"

            arrays["soc_kwh"][row_number] = soc_kwh
            arrays["soc_pct"][row_number] = (
                soc_kwh / battery_config.capacity_kwh * 100
                if battery_config.capacity_kwh
                else 0.0
            )

        self._apply_result_arrays(result, arrays)
        return result

    def simulate_mode_3(
        self,
        dataframe: pd.DataFrame,
        battery_config: BatteryConfig,
        mode_config: ModeConfig,
    ) -> pd.DataFrame:
        """Simulate smart charging with export to the grid.

        Mode 3 charges from solar surplus and can charge from the grid when the
        low-price and margin conditions are met. It can discharge to household
        demand and, at high-price intervals, export remaining discharge capacity.
        """

        self._validate_config(battery_config)
        self._validate_columns(
            dataframe,
            ("netto_baseline_kwh", "buy_price_eur_per_kwh", "sell_price_eur_per_kwh"),
        )
        self._validate_mode_3_config(mode_config)

        result = dataframe.copy()
        self._add_mode_3_decision_columns(result, mode_config)
        arrays = self._initialise_result_arrays(result)

        soc_kwh = min(
            max(battery_config.start_soc_kwh, battery_config.min_soc_kwh),
            battery_config.max_soc_kwh,
        )
        charge_limit_kwh = battery_config.charge_power_kw * 0.25
        discharge_limit_kwh = battery_config.discharge_power_kw * 0.25
        round_trip_efficiency = (
            battery_config.charge_efficiency * battery_config.discharge_efficiency
        )
        netto_values = result["netto_baseline_kwh"].to_numpy(dtype=float)
        buy_prices = result["buy_price_eur_per_kwh"].to_numpy(dtype=float)
        sell_prices = result["sell_price_eur_per_kwh"].to_numpy(dtype=float)
        high_thresholds = result["mode_3_high_threshold_eur_per_kwh"].to_numpy(dtype=float)
        future_avoid_prices = result["future_max_avoid_price_next_24h_eur_per_kwh"].to_numpy(
            dtype=float
        )
        future_required_reserves = result[
            "future_required_reserve_kwh_before_next_solar_window"
        ].to_numpy(dtype=float)
        future_min_buy_prices = result["future_min_buy_price_next_24h_eur_per_kwh"].to_numpy(
            dtype=float
        )

        for row_number, netto_baseline_kwh in enumerate(netto_values):
            arrays["actie"][row_number] = "idle"
            charged_this_interval = False

            if netto_baseline_kwh < 0:
                surplus_kwh = -netto_baseline_kwh
                charge_input_kwh, soc_increase_kwh = self._calculate_charge(
                    available_input_kwh=surplus_kwh,
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += soc_increase_kwh
                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_solar_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] += charge_input_kwh - soc_increase_kwh
                arrays["export_met_batterij_kwh"][row_number] = surplus_kwh - charge_input_kwh
                charged_this_interval = charge_input_kwh > 0
                if charged_this_interval:
                    arrays["actie"][row_number] = "solar_charge"

            if netto_baseline_kwh >= 0 and self._should_grid_charge_mode_3_values(
                buy_price=buy_prices[row_number],
                future_avoid_buy_price_eur_per_kwh=future_avoid_prices[row_number],
                future_required_reserve_kwh=future_required_reserves[row_number],
                future_min_buy_price_eur_per_kwh=future_min_buy_prices[row_number],
                current_soc_kwh=soc_kwh,
                mode_config=mode_config,
                round_trip_efficiency=round_trip_efficiency,
            ):
                required_charge_input_kwh = max(
                    future_required_reserves[row_number] - soc_kwh,
                    0.0,
                ) / battery_config.charge_efficiency
                charge_input_kwh, soc_increase_kwh = self._calculate_charge(
                    available_input_kwh=min(charge_limit_kwh, required_charge_input_kwh),
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += soc_increase_kwh
                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_net_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] += charge_input_kwh - soc_increase_kwh
                arrays["import_met_batterij_kwh"][row_number] = (
                    max(netto_baseline_kwh, 0.0) + charge_input_kwh
                )
                charged_this_interval = charge_input_kwh > 0
                if charged_this_interval:
                    arrays["actie"][row_number] = "grid_charge"

            if (
                not charged_this_interval
                and not np.isnan(sell_prices[row_number])
                and not np.isnan(high_thresholds[row_number])
                and sell_prices[row_number] >= high_thresholds[row_number]
            ):
                delivered_home_kwh, delivered_net_kwh, discharge_from_soc_kwh = (
                    self._calculate_discharge_to_home_and_grid(
                        demand_kwh=max(netto_baseline_kwh, 0.0),
                        discharge_limit_kwh=discharge_limit_kwh,
                        soc_kwh=soc_kwh,
                        config=battery_config,
                    )
                )
                soc_kwh -= discharge_from_soc_kwh
                arrays["ontlaad_kwh"][row_number] = discharge_from_soc_kwh
                arrays["ontlaad_naar_huis_kwh"][row_number] = delivered_home_kwh
                arrays["ontlaad_naar_net_kwh"][row_number] = delivered_net_kwh
                arrays["round_trip_loss_kwh"][row_number] += (
                    discharge_from_soc_kwh - delivered_home_kwh - delivered_net_kwh
                )
                arrays["import_met_batterij_kwh"][row_number] = (
                    max(netto_baseline_kwh, 0.0) - delivered_home_kwh
                )
                arrays["export_met_batterij_kwh"][row_number] += delivered_net_kwh
                if delivered_net_kwh > 0:
                    arrays["actie"][row_number] = "discharge_export"
                elif delivered_home_kwh > 0:
                    arrays["actie"][row_number] = "discharge_home"

            elif netto_baseline_kwh > 0 and not charged_this_interval:
                delivered_kwh, discharge_from_soc_kwh = self._calculate_discharge_to_home(
                    demand_kwh=netto_baseline_kwh,
                    discharge_limit_kwh=discharge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh -= discharge_from_soc_kwh
                arrays["ontlaad_kwh"][row_number] = discharge_from_soc_kwh
                arrays["ontlaad_naar_huis_kwh"][row_number] = delivered_kwh
                arrays["round_trip_loss_kwh"][row_number] += discharge_from_soc_kwh - delivered_kwh
                arrays["import_met_batterij_kwh"][row_number] = netto_baseline_kwh - delivered_kwh
                if delivered_kwh > 0:
                    arrays["actie"][row_number] = "discharge_home"

            arrays["soc_kwh"][row_number] = soc_kwh
            arrays["soc_pct"][row_number] = (
                soc_kwh / battery_config.capacity_kwh * 100
                if battery_config.capacity_kwh
                else 0.0
            )

        self._apply_result_arrays(result, arrays)
        return result

    def simulate_smart_mode(
        self,
        dataframe: pd.DataFrame,
        battery_config: BatteryConfig,
        mode_config: ModeConfig,
    ) -> pd.DataFrame:
        """Simulate smart charging for household demand only.

        Smart mode charges from solar surplus and may charge from the grid when
        there is an expected household deficit before the next meaningful solar
        recharge window and the published future price spread is large enough.
        It never intentionally exports battery energy to the grid.
        """

        self._validate_config(battery_config)
        self._validate_columns(dataframe, ("netto_baseline_kwh", "buy_price_eur_per_kwh"))

        result = dataframe.copy()
        result["future_max_avoid_price_next_24h_eur_per_kwh"] = (
            self.calculate_future_max_avoid_price_next_24h(result)
        )
        result["future_required_reserve_kwh_before_next_solar_window"] = (
            self.calculate_future_required_reserve_kwh_before_next_solar_window(result)
        )
        result["future_min_buy_price_next_24h_eur_per_kwh"] = (
            self.calculate_future_min_buy_price_next_24h(result)
        )
        arrays = self._initialise_result_arrays(result)

        soc_kwh = min(
            max(battery_config.start_soc_kwh, battery_config.min_soc_kwh),
            battery_config.max_soc_kwh,
        )
        charge_limit_kwh = battery_config.charge_power_kw * 0.25
        discharge_limit_kwh = battery_config.discharge_power_kw * 0.25
        round_trip_efficiency = (
            battery_config.charge_efficiency * battery_config.discharge_efficiency
        )
        netto_values = result["netto_baseline_kwh"].to_numpy(dtype=float)
        buy_prices = result["buy_price_eur_per_kwh"].to_numpy(dtype=float)
        future_avoid_prices = result["future_max_avoid_price_next_24h_eur_per_kwh"].to_numpy(
            dtype=float
        )
        future_required_reserves = result[
            "future_required_reserve_kwh_before_next_solar_window"
        ].to_numpy(dtype=float)
        future_min_buy_prices = result["future_min_buy_price_next_24h_eur_per_kwh"].to_numpy(
            dtype=float
        )

        for row_number, netto_baseline_kwh in enumerate(netto_values):
            arrays["actie"][row_number] = "idle"
            charged_this_interval = False

            if netto_baseline_kwh < 0:
                surplus_kwh = -netto_baseline_kwh
                charge_input_kwh, soc_increase_kwh = self._calculate_charge(
                    available_input_kwh=surplus_kwh,
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += soc_increase_kwh
                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_solar_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] += charge_input_kwh - soc_increase_kwh
                arrays["export_met_batterij_kwh"][row_number] = surplus_kwh - charge_input_kwh
                charged_this_interval = charge_input_kwh > 0
                if charged_this_interval:
                    arrays["actie"][row_number] = "solar_charge"

            if netto_baseline_kwh >= 0 and self._should_grid_charge_mode_3_values(
                buy_price=buy_prices[row_number],
                future_avoid_buy_price_eur_per_kwh=future_avoid_prices[row_number],
                future_required_reserve_kwh=future_required_reserves[row_number],
                future_min_buy_price_eur_per_kwh=future_min_buy_prices[row_number],
                current_soc_kwh=soc_kwh,
                mode_config=mode_config,
                round_trip_efficiency=round_trip_efficiency,
            ):
                required_charge_input_kwh = max(
                    future_required_reserves[row_number] - soc_kwh,
                    0.0,
                ) / battery_config.charge_efficiency
                charge_input_kwh, soc_increase_kwh = self._calculate_charge(
                    available_input_kwh=min(charge_limit_kwh, required_charge_input_kwh),
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += soc_increase_kwh
                arrays["laad_kwh"][row_number] = charge_input_kwh
                arrays["laad_uit_net_kwh"][row_number] = charge_input_kwh
                arrays["round_trip_loss_kwh"][row_number] += charge_input_kwh - soc_increase_kwh
                arrays["import_met_batterij_kwh"][row_number] = (
                    max(netto_baseline_kwh, 0.0) + charge_input_kwh
                )
                charged_this_interval = charge_input_kwh > 0
                if charged_this_interval:
                    arrays["actie"][row_number] = "grid_charge"

            if netto_baseline_kwh > 0 and not charged_this_interval:
                delivered_kwh, discharge_from_soc_kwh = self._calculate_discharge_to_home(
                    demand_kwh=netto_baseline_kwh,
                    discharge_limit_kwh=discharge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh -= discharge_from_soc_kwh
                arrays["ontlaad_kwh"][row_number] = discharge_from_soc_kwh
                arrays["ontlaad_naar_huis_kwh"][row_number] = delivered_kwh
                arrays["round_trip_loss_kwh"][row_number] += discharge_from_soc_kwh - delivered_kwh
                arrays["import_met_batterij_kwh"][row_number] = netto_baseline_kwh - delivered_kwh
                if delivered_kwh > 0:
                    arrays["actie"][row_number] = "discharge_home"

            arrays["soc_kwh"][row_number] = soc_kwh
            arrays["soc_pct"][row_number] = (
                soc_kwh / battery_config.capacity_kwh * 100
                if battery_config.capacity_kwh
                else 0.0
            )

        self._apply_result_arrays(result, arrays)
        return result

    def calculate_future_max_avoid_price(self, dataframe: pd.DataFrame) -> pd.Series:
        self._validate_columns(dataframe, ("netto_baseline_kwh", "buy_price_eur_per_kwh"))

        candidate_price = dataframe["buy_price_eur_per_kwh"].where(
            dataframe["netto_baseline_kwh"] > 0
        )
        grouped = candidate_price.groupby(dataframe.index.normalize(), group_keys=False)
        return grouped.transform(
            lambda series: series.iloc[::-1].cummax().iloc[::-1].shift(-1)
        )

    def calculate_future_max_avoid_price_next_24h(self, dataframe: pd.DataFrame) -> pd.Series:
        self._validate_columns(dataframe, ("netto_baseline_kwh", "buy_price_eur_per_kwh"))

        candidate_values = dataframe["buy_price_eur_per_kwh"].where(
            dataframe["netto_baseline_kwh"] > 0
        )
        return self._calculate_future_window_max_with_publication(
            candidate_values,
            dataframe.index,
            horizon_intervals=96,
        )

    def calculate_future_min_buy_price_next_24h(self, dataframe: pd.DataFrame) -> pd.Series:
        self._validate_columns(dataframe, ("buy_price_eur_per_kwh",))

        return self._calculate_future_window_min_with_publication(
            dataframe["buy_price_eur_per_kwh"],
            dataframe.index,
            horizon_intervals=96,
        )

    def calculate_future_required_reserve_kwh_before_next_solar_window(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.Series:
        self._validate_columns(dataframe, ("netto_baseline_kwh",))

        net_values = dataframe["netto_baseline_kwh"].to_numpy(dtype=float)
        required = np.zeros(len(net_values))
        horizon_intervals = 96

        for row_number in range(len(net_values)):
            running_balance_kwh = 0.0
            max_required_kwh = 0.0
            upper_bound = min(row_number + 1 + horizon_intervals, len(net_values))
            for future_row in range(row_number + 1, upper_bound):
                if net_values[future_row] < -SOLAR_RECHARGE_SURPLUS_KWH_THRESHOLD:
                    break
                running_balance_kwh += net_values[future_row]
                if running_balance_kwh > max_required_kwh:
                    max_required_kwh = running_balance_kwh
            required[row_number] = max_required_kwh

        return pd.Series(required, index=dataframe.index)

    def calculate_future_high_export_price(
        self,
        sell_prices: pd.Series,
        high_thresholds: pd.Series,
    ) -> pd.Series:
        candidate_price = sell_prices.where(sell_prices >= high_thresholds)
        grouped = candidate_price.groupby(sell_prices.index.normalize(), group_keys=False)
        return grouped.transform(
            lambda series: series.iloc[::-1].cummax().ffill().iloc[::-1].shift(-1)
        )

    def _add_mode_3_decision_columns(
        self,
        dataframe: pd.DataFrame,
        mode_config: ModeConfig,
    ) -> None:
        if mode_config.decision_rule == "threshold":
            dataframe["mode_3_low_threshold_eur_per_kwh"] = np.nan
            dataframe["mode_3_high_threshold_eur_per_kwh"] = (
                mode_config.threshold_high_eur_per_kwh
            )
        else:
            dataframe["mode_3_low_threshold_eur_per_kwh"] = np.nan
            grouped = dataframe.groupby(dataframe.index.normalize(), group_keys=False)
            dataframe["mode_3_high_threshold_eur_per_kwh"] = grouped[
                "sell_price_eur_per_kwh"
            ].transform(lambda series: series.quantile(mode_config.percentile_high / 100))

        dataframe["future_max_avoid_price_next_24h_eur_per_kwh"] = (
            self.calculate_future_max_avoid_price_next_24h(dataframe)
        )
        dataframe["future_required_reserve_kwh_before_next_solar_window"] = (
            self.calculate_future_required_reserve_kwh_before_next_solar_window(dataframe)
        )
        dataframe["future_min_buy_price_next_24h_eur_per_kwh"] = (
            self.calculate_future_min_buy_price_next_24h(dataframe)
        )
        dataframe["expected_export_revenue_eur_per_kwh"] = self.calculate_future_high_export_price(
            dataframe["sell_price_eur_per_kwh"],
            dataframe["mode_3_high_threshold_eur_per_kwh"],
        )

    def _initialise_result_arrays(self, dataframe: pd.DataFrame) -> dict[str, np.ndarray]:
        row_count = len(dataframe)
        arrays = {
            "soc_kwh": np.zeros(row_count),
            "soc_pct": np.zeros(row_count),
            "laad_kwh": np.zeros(row_count),
            "ontlaad_kwh": np.zeros(row_count),
            "laad_uit_solar_kwh": np.zeros(row_count),
            "laad_uit_net_kwh": np.zeros(row_count),
            "ontlaad_naar_huis_kwh": np.zeros(row_count),
            "ontlaad_naar_net_kwh": np.zeros(row_count),
            "round_trip_loss_kwh": np.zeros(row_count),
            "import_met_batterij_kwh": np.zeros(row_count),
            "export_met_batterij_kwh": np.zeros(row_count),
            "actie": np.full(row_count, "idle", dtype=object),
        }
        if "import_zonder_batterij_kwh" in dataframe:
            arrays["import_met_batterij_kwh"] = dataframe[
                "import_zonder_batterij_kwh"
            ].to_numpy(dtype=float).copy()
        if "export_zonder_batterij_kwh" in dataframe:
            arrays["export_met_batterij_kwh"] = dataframe[
                "export_zonder_batterij_kwh"
            ].to_numpy(dtype=float).copy()
        return arrays

    @staticmethod
    def _apply_result_arrays(dataframe: pd.DataFrame, arrays: dict[str, np.ndarray]) -> None:
        for column, values in arrays.items():
            if column == "actie":
                dataframe[column] = pd.Categorical(values, dtype=ACTION_DTYPE)
            else:
                dataframe[column] = values
        dataframe["batterij_export_kwh"] = dataframe["ontlaad_naar_net_kwh"]
        dataframe["netladen_kwh"] = dataframe["laad_uit_net_kwh"]
        if "timestamp_nl" not in dataframe.columns:
            dataframe["timestamp_nl"] = dataframe.index

    @staticmethod
    def _calculate_charge(
        available_input_kwh: float,
        charge_limit_kwh: float,
        soc_kwh: float,
        config: BatteryConfig,
    ) -> tuple[float, float]:
        storage_room_kwh = max(config.max_soc_kwh - soc_kwh, 0.0)
        max_input_by_room_kwh = storage_room_kwh / config.charge_efficiency
        charge_input_kwh = min(available_input_kwh, charge_limit_kwh, max_input_by_room_kwh)
        soc_increase_kwh = charge_input_kwh * config.charge_efficiency
        return charge_input_kwh, soc_increase_kwh

    @staticmethod
    def _calculate_discharge_to_home(
        demand_kwh: float,
        discharge_limit_kwh: float,
        soc_kwh: float,
        config: BatteryConfig,
    ) -> tuple[float, float]:
        available_soc_kwh = max(soc_kwh - config.min_soc_kwh, 0.0)
        max_delivered_by_soc_kwh = available_soc_kwh * config.discharge_efficiency
        delivered_kwh = min(demand_kwh, discharge_limit_kwh, max_delivered_by_soc_kwh)
        discharge_from_soc_kwh = delivered_kwh / config.discharge_efficiency
        return delivered_kwh, discharge_from_soc_kwh

    @staticmethod
    def _calculate_discharge_to_home_and_grid(
        demand_kwh: float,
        discharge_limit_kwh: float,
        soc_kwh: float,
        config: BatteryConfig,
    ) -> tuple[float, float, float]:
        available_soc_kwh = max(soc_kwh - config.min_soc_kwh, 0.0)
        max_delivered_by_soc_kwh = available_soc_kwh * config.discharge_efficiency
        delivered_total_kwh = min(discharge_limit_kwh, max_delivered_by_soc_kwh)
        delivered_home_kwh = min(demand_kwh, delivered_total_kwh)
        delivered_net_kwh = delivered_total_kwh - delivered_home_kwh
        discharge_from_soc_kwh = delivered_total_kwh / config.discharge_efficiency
        return delivered_home_kwh, delivered_net_kwh, discharge_from_soc_kwh

    def _charge_battery(
        self,
        result: pd.DataFrame,
        index,
        source_column: str,
        available_input_kwh: float,
        charge_limit_kwh: float,
        soc_kwh: float,
        config: BatteryConfig,
    ) -> float:
        storage_room_kwh = max(config.max_soc_kwh - soc_kwh, 0.0)
        max_input_by_room_kwh = storage_room_kwh / config.charge_efficiency
        charge_input_kwh = min(available_input_kwh, charge_limit_kwh, max_input_by_room_kwh)
        soc_increase_kwh = charge_input_kwh * config.charge_efficiency

        result.at[index, "laad_kwh"] = charge_input_kwh
        result.at[index, source_column] = charge_input_kwh
        result.at[index, "round_trip_loss_kwh"] += charge_input_kwh - soc_increase_kwh
        return charge_input_kwh

    def _discharge_to_home(
        self,
        result: pd.DataFrame,
        index,
        demand_kwh: float,
        discharge_limit_kwh: float,
        soc_kwh: float,
        config: BatteryConfig,
    ) -> tuple[float, float]:
        available_soc_kwh = max(soc_kwh - config.min_soc_kwh, 0.0)
        max_delivered_by_soc_kwh = available_soc_kwh * config.discharge_efficiency
        delivered_kwh = min(demand_kwh, discharge_limit_kwh, max_delivered_by_soc_kwh)
        discharge_from_soc_kwh = delivered_kwh / config.discharge_efficiency

        result.at[index, "ontlaad_kwh"] = discharge_from_soc_kwh
        result.at[index, "ontlaad_naar_huis_kwh"] = delivered_kwh
        result.at[index, "round_trip_loss_kwh"] += discharge_from_soc_kwh - delivered_kwh
        result.at[index, "import_met_batterij_kwh"] = demand_kwh - delivered_kwh
        return delivered_kwh, discharge_from_soc_kwh

    def _discharge_to_home_and_grid(
        self,
        result: pd.DataFrame,
        index,
        demand_kwh: float,
        discharge_limit_kwh: float,
        soc_kwh: float,
        config: BatteryConfig,
    ) -> tuple[float, float, float]:
        available_soc_kwh = max(soc_kwh - config.min_soc_kwh, 0.0)
        max_delivered_by_soc_kwh = available_soc_kwh * config.discharge_efficiency
        delivered_total_kwh = min(discharge_limit_kwh, max_delivered_by_soc_kwh)
        delivered_home_kwh = min(demand_kwh, delivered_total_kwh)
        delivered_net_kwh = delivered_total_kwh - delivered_home_kwh
        discharge_from_soc_kwh = delivered_total_kwh / config.discharge_efficiency

        result.at[index, "ontlaad_kwh"] = discharge_from_soc_kwh
        result.at[index, "ontlaad_naar_huis_kwh"] = delivered_home_kwh
        result.at[index, "ontlaad_naar_net_kwh"] = delivered_net_kwh
        result.at[index, "round_trip_loss_kwh"] += discharge_from_soc_kwh - delivered_total_kwh
        result.at[index, "import_met_batterij_kwh"] = demand_kwh - delivered_home_kwh
        result.at[index, "export_met_batterij_kwh"] += delivered_net_kwh
        return delivered_home_kwh, delivered_net_kwh, discharge_from_soc_kwh

    @staticmethod
    def _should_grid_charge_mode_2(
        row: pd.Series,
        round_trip_efficiency: float,
        min_margin_eur_per_kwh: float,
    ) -> bool:
        future_price = row["future_max_avoid_price_eur_per_kwh"]
        buy_price = row["buy_price_eur_per_kwh"]
        if pd.isna(future_price) or pd.isna(buy_price):
            return False
        threshold = buy_price / round_trip_efficiency + min_margin_eur_per_kwh
        return bool(future_price > threshold)

    @staticmethod
    def _should_grid_charge_prices(
        buy_price: float,
        future_price: float,
        round_trip_efficiency: float,
        min_margin_eur_per_kwh: float,
    ) -> bool:
        if np.isnan(future_price) or np.isnan(buy_price):
            return False
        threshold = buy_price / round_trip_efficiency + min_margin_eur_per_kwh
        return bool(future_price > threshold)

    @staticmethod
    def _should_grid_charge_mode_3(
        row: pd.Series,
        mode_config: ModeConfig,
        round_trip_efficiency: float,
    ) -> bool:
        buy_price = row["buy_price_eur_per_kwh"]
        if pd.isna(buy_price):
            return False
        low_threshold = row["mode_3_low_threshold_eur_per_kwh"]
        expected_export_revenue_eur_per_kwh = row["expected_export_revenue_eur_per_kwh"]
        if pd.isna(low_threshold) or pd.isna(expected_export_revenue_eur_per_kwh):
            return False
        if not bool(buy_price <= low_threshold):
            return False

        expected_margin_eur_per_kwh = (
            expected_export_revenue_eur_per_kwh * round_trip_efficiency - buy_price
        )
        return bool(expected_margin_eur_per_kwh >= mode_config.min_margin_eur_per_kwh)

    @staticmethod
    def _should_grid_charge_mode_3_values(
        buy_price: float,
        future_avoid_buy_price_eur_per_kwh: float,
        future_required_reserve_kwh: float,
        future_min_buy_price_eur_per_kwh: float,
        current_soc_kwh: float,
        mode_config: ModeConfig,
        round_trip_efficiency: float,
    ) -> bool:
        if (
            np.isnan(buy_price)
            or np.isnan(future_avoid_buy_price_eur_per_kwh)
            or np.isnan(future_required_reserve_kwh)
        ):
            return False
        if future_required_reserve_kwh <= current_soc_kwh:
            return False
        if not np.isnan(future_min_buy_price_eur_per_kwh) and buy_price > (
            future_min_buy_price_eur_per_kwh + 1e-9
        ):
            return False
        required_price_ratio = max(
            1 / round_trip_efficiency,
            1 + mode_config.min_price_spread_pct / 100,
        )
        if future_avoid_buy_price_eur_per_kwh < buy_price * required_price_ratio:
            return False
        expected_margin_eur_per_kwh = (
            future_avoid_buy_price_eur_per_kwh * round_trip_efficiency - buy_price
        )
        return bool(expected_margin_eur_per_kwh >= mode_config.min_margin_eur_per_kwh)

    @staticmethod
    def _calculate_future_window_max(
        series: pd.Series,
        horizon_intervals: int,
    ) -> pd.Series:
        reversed_max = (
            series.iloc[::-1]
            .rolling(window=horizon_intervals, min_periods=1)
            .max()
            .iloc[::-1]
            .shift(-1)
        )
        return reversed_max

    @staticmethod
    def _calculate_future_window_max_with_publication(
        series: pd.Series,
        timestamps: pd.Index,
        horizon_intervals: int,
    ) -> pd.Series:
        time_index = pd.DatetimeIndex(timestamps)
        same_day_future = series.groupby(time_index.normalize(), group_keys=False).transform(
            lambda day_series: day_series.iloc[::-1].cummax().iloc[::-1].shift(-1)
        )
        next_24h_future = SimEngine._calculate_future_window_max(series, horizon_intervals)
        after_publication_mask = (
            (time_index.hour > 13)
            | ((time_index.hour == 13) & (time_index.minute >= 0))
        )
        return next_24h_future.where(after_publication_mask, same_day_future)

    @staticmethod
    def _calculate_future_window_min(
        series: pd.Series,
        horizon_intervals: int,
    ) -> pd.Series:
        reversed_min = (
            series.iloc[::-1]
            .rolling(window=horizon_intervals, min_periods=1)
            .min()
            .iloc[::-1]
            .shift(-1)
        )
        return reversed_min

    @staticmethod
    def _calculate_future_window_min_with_publication(
        series: pd.Series,
        timestamps: pd.Index,
        horizon_intervals: int,
    ) -> pd.Series:
        time_index = pd.DatetimeIndex(timestamps)
        same_day_future = series.groupby(time_index.normalize(), group_keys=False).transform(
            lambda day_series: day_series.iloc[::-1].cummin().iloc[::-1].shift(-1)
        )
        next_24h_future = SimEngine._calculate_future_window_min(series, horizon_intervals)
        after_publication_mask = (
            (time_index.hour > 13)
            | ((time_index.hour == 13) & (time_index.minute >= 0))
        )
        return next_24h_future.where(after_publication_mask, same_day_future)

    @staticmethod
    def _is_high_export_price(row: pd.Series, mode_config: ModeConfig) -> bool:
        sell_price = row["sell_price_eur_per_kwh"]
        if pd.isna(sell_price):
            return False
        high_threshold = row["mode_3_high_threshold_eur_per_kwh"]
        if pd.isna(high_threshold):
            return False
        return bool(sell_price >= high_threshold)

    @staticmethod
    def _initialise_result_columns(dataframe: pd.DataFrame) -> None:
        zero_columns = (
            "soc_kwh",
            "soc_pct",
            "laad_kwh",
            "ontlaad_kwh",
            "laad_uit_solar_kwh",
            "laad_uit_net_kwh",
            "ontlaad_naar_huis_kwh",
            "ontlaad_naar_net_kwh",
            "round_trip_loss_kwh",
            "import_met_batterij_kwh",
            "export_met_batterij_kwh",
            "batterij_export_kwh",
            "netladen_kwh",
        )
        for column in zero_columns:
            dataframe[column] = 0.0
        dataframe["actie"] = pd.Categorical(
            ["idle"] * len(dataframe),
            dtype=ACTION_DTYPE,
        )
        if "import_zonder_batterij_kwh" in dataframe:
            dataframe["import_met_batterij_kwh"] = dataframe["import_zonder_batterij_kwh"]
        if "export_zonder_batterij_kwh" in dataframe:
            dataframe["export_met_batterij_kwh"] = dataframe["export_zonder_batterij_kwh"]

    @staticmethod
    def _validate_columns(dataframe: pd.DataFrame, required: tuple[str, ...]) -> None:
        missing = [column for column in required if column not in dataframe.columns]
        if missing:
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    @staticmethod
    def _validate_config(config: BatteryConfig) -> None:
        if config.capacity_kwh <= 0:
            raise ValueError("Battery capacity must be greater than 0 kWh.")
        if config.charge_power_kw < 0 or config.discharge_power_kw < 0:
            raise ValueError("Battery charge and discharge power must be non-negative.")
        if not 0 < config.charge_efficiency <= 1:
            raise ValueError("Charge efficiency must be between 0 and 100%.")
        if not 0 < config.discharge_efficiency <= 1:
            raise ValueError("Discharge efficiency must be between 0 and 100%.")
        if config.min_soc_pct < 0 or config.max_soc_pct > 100:
            raise ValueError("SoC limits must be between 0 and 100%.")
        if config.min_soc_pct >= config.max_soc_pct:
            raise ValueError("Minimum SoC must be lower than maximum SoC.")

    @staticmethod
    def _validate_mode_3_config(config: ModeConfig) -> None:
        if config.decision_rule not in {"threshold", "percentile"}:
            raise ValueError("Mode 3 decision rule must be 'threshold' or 'percentile'.")
        if config.min_price_spread_pct < 0:
            raise ValueError("Mode 3 minimum price spread must be non-negative.")

        if config.decision_rule == "threshold":
            if config.threshold_high_eur_per_kwh is None:
                raise ValueError("Mode 3 high threshold is required.")
            return

        if config.percentile_high is None:
            raise ValueError("Mode 3 high percentile is required.")
        if not 0 <= config.percentile_high <= 100:
            raise ValueError("Mode 3 high percentile must be between 0 and 100.")
