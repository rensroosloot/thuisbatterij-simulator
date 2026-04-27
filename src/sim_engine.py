"""Battery simulation engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


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
        self._initialise_result_columns(result)

        soc_kwh = min(max(config.start_soc_kwh, config.min_soc_kwh), config.max_soc_kwh)
        charge_limit_kwh = config.charge_power_kw * 0.25
        discharge_limit_kwh = config.discharge_power_kw * 0.25

        for row_number, (index, row) in enumerate(result.iterrows()):
            netto_baseline_kwh = float(row["netto_baseline_kwh"])
            action = "idle"

            if netto_baseline_kwh < 0:
                surplus_kwh = -netto_baseline_kwh
                storage_room_kwh = max(config.max_soc_kwh - soc_kwh, 0.0)
                max_input_by_room_kwh = storage_room_kwh / config.charge_efficiency
                charge_input_kwh = min(surplus_kwh, charge_limit_kwh, max_input_by_room_kwh)
                soc_increase_kwh = charge_input_kwh * config.charge_efficiency
                soc_kwh += soc_increase_kwh

                result.at[index, "laad_kwh"] = charge_input_kwh
                result.at[index, "laad_uit_solar_kwh"] = charge_input_kwh
                result.at[index, "round_trip_loss_kwh"] = charge_input_kwh - soc_increase_kwh
                result.at[index, "export_met_batterij_kwh"] = surplus_kwh - charge_input_kwh
                action = "solar_charge" if charge_input_kwh > 0 else "idle"

            elif netto_baseline_kwh > 0:
                demand_kwh = netto_baseline_kwh
                available_soc_kwh = max(soc_kwh - config.min_soc_kwh, 0.0)
                max_delivered_by_soc_kwh = available_soc_kwh * config.discharge_efficiency
                delivered_kwh = min(demand_kwh, discharge_limit_kwh, max_delivered_by_soc_kwh)
                discharge_from_soc_kwh = delivered_kwh / config.discharge_efficiency
                soc_kwh -= discharge_from_soc_kwh

                result.at[index, "ontlaad_kwh"] = discharge_from_soc_kwh
                result.at[index, "ontlaad_naar_huis_kwh"] = delivered_kwh
                result.at[index, "round_trip_loss_kwh"] = discharge_from_soc_kwh - delivered_kwh
                result.at[index, "import_met_batterij_kwh"] = demand_kwh - delivered_kwh
                action = "discharge_home" if delivered_kwh > 0 else "idle"

            result.at[index, "soc_kwh"] = soc_kwh
            result.at[index, "soc_pct"] = (soc_kwh / config.capacity_kwh * 100) if config.capacity_kwh else 0.0
            result.at[index, "actie"] = action

            if row_number == 0 and "timestamp_nl" not in result.columns:
                result.at[index, "timestamp_nl"] = index

        result["batterij_export_kwh"] = result["ontlaad_naar_net_kwh"]
        result["netladen_kwh"] = result["laad_uit_net_kwh"]
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
        self._initialise_result_columns(result)

        soc_kwh = min(
            max(battery_config.start_soc_kwh, battery_config.min_soc_kwh),
            battery_config.max_soc_kwh,
        )
        charge_limit_kwh = battery_config.charge_power_kw * 0.25
        discharge_limit_kwh = battery_config.discharge_power_kw * 0.25
        round_trip_efficiency = (
            battery_config.charge_efficiency * battery_config.discharge_efficiency
        )

        for row_number, (index, row) in enumerate(result.iterrows()):
            netto_baseline_kwh = float(row["netto_baseline_kwh"])
            action = "idle"
            charged_this_interval = False

            if netto_baseline_kwh < 0:
                surplus_kwh = -netto_baseline_kwh
                charge_input_kwh = self._charge_battery(
                    result,
                    index,
                    source_column="laad_uit_solar_kwh",
                    available_input_kwh=surplus_kwh,
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += charge_input_kwh * battery_config.charge_efficiency
                result.at[index, "export_met_batterij_kwh"] = surplus_kwh - charge_input_kwh
                charged_this_interval = charge_input_kwh > 0
                action = "solar_charge" if charged_this_interval else "idle"

            if netto_baseline_kwh >= 0 and self._should_grid_charge_mode_2(
                row=row,
                round_trip_efficiency=round_trip_efficiency,
                min_margin_eur_per_kwh=mode_config.min_margin_eur_per_kwh,
            ):
                charge_input_kwh = self._charge_battery(
                    result,
                    index,
                    source_column="laad_uit_net_kwh",
                    available_input_kwh=charge_limit_kwh,
                    charge_limit_kwh=charge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh += charge_input_kwh * battery_config.charge_efficiency
                result.at[index, "import_met_batterij_kwh"] = (
                    max(netto_baseline_kwh, 0.0) + charge_input_kwh
                )
                charged_this_interval = charge_input_kwh > 0
                action = "grid_charge" if charged_this_interval else "idle"

            if netto_baseline_kwh > 0 and not charged_this_interval:
                delivered_kwh, discharge_from_soc_kwh = self._discharge_to_home(
                    result,
                    index,
                    demand_kwh=netto_baseline_kwh,
                    discharge_limit_kwh=discharge_limit_kwh,
                    soc_kwh=soc_kwh,
                    config=battery_config,
                )
                soc_kwh -= discharge_from_soc_kwh
                action = "discharge_home" if delivered_kwh > 0 else "idle"

            result.at[index, "soc_kwh"] = soc_kwh
            result.at[index, "soc_pct"] = (
                soc_kwh / battery_config.capacity_kwh * 100
                if battery_config.capacity_kwh
                else 0.0
            )
            result.at[index, "actie"] = action
            if row_number == 0 and "timestamp_nl" not in result.columns:
                result.at[index, "timestamp_nl"] = index

        result["batterij_export_kwh"] = result["ontlaad_naar_net_kwh"]
        result["netladen_kwh"] = result["laad_uit_net_kwh"]
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
        dataframe["actie"] = "idle"
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
