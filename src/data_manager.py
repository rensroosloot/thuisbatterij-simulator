"""Data loading and preprocessing for the thuisbatterij simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd


P1E_REQUIRED_COLUMNS = (
    "time",
    "Import T1 kWh",
    "Import T2 kWh",
    "Export T1 kWh",
    "Export T2 kWh",
)


@dataclass(frozen=True)
class DataQualityIssue:
    """A single data quality finding."""

    code: str
    message: str
    timestamp: pd.Timestamp | None = None
    column: str | None = None


@dataclass
class DataQualityReport:
    """Collected data quality findings for a preprocessing run."""

    issues: list[DataQualityIssue] = field(default_factory=list)

    def add(
        self,
        code: str,
        message: str,
        timestamp: pd.Timestamp | None = None,
        column: str | None = None,
    ) -> None:
        self.issues.append(
            DataQualityIssue(
                code=code,
                message=message,
                timestamp=timestamp,
                column=column,
            )
        )

    def has_issue(self, code: str) -> bool:
        return any(issue.code == code for issue in self.issues)

    def count(self, code: str) -> int:
        return sum(1 for issue in self.issues if issue.code == code)


@dataclass(frozen=True)
class DataManagerResult:
    """Processed dataframe plus quality report."""

    dataframe: pd.DataFrame
    report: DataQualityReport


class DataManager:
    """Prepare historical input data for simulation."""

    def __init__(self, resources_path: str | Path = "resources") -> None:
        self.resources_path = Path(resources_path)

    def load_p1e_csv(self, path: str | Path) -> DataManagerResult:
        dataframe = pd.read_csv(path)
        return self.preprocess_p1e(dataframe)

    def preprocess_p1e(self, dataframe: pd.DataFrame) -> DataManagerResult:
        """Convert cumulative P1e meter readings to interval energy.

        The important DST rule from DS-001 is preserved here: cumulative meter
        readings are differenced first, and only interval kWh values are summed
        for duplicate local timestamps.
        """

        report = DataQualityReport()
        self._validate_columns(dataframe.columns, P1E_REQUIRED_COLUMNS)

        working = dataframe.copy()
        working["_source_order"] = range(len(working))
        working["timestamp_nl"] = pd.to_datetime(working["time"])
        working = working.sort_values(["timestamp_nl", "_source_order"])

        working["import_total_kwh"] = (
            working["Import T1 kWh"].astype(float) + working["Import T2 kWh"].astype(float)
        )
        working["export_total_kwh"] = (
            working["Export T1 kWh"].astype(float) + working["Export T2 kWh"].astype(float)
        )
        working["import_kwh"] = working["import_total_kwh"].diff()
        working["export_kwh"] = working["export_total_kwh"].diff()

        if not working.empty:
            first_timestamp = pd.Timestamp(working.iloc[0]["timestamp_nl"])
            report.add(
                "P1E_NO_PREVIOUS_READING",
                "First P1e row has no previous reading and is excluded.",
                first_timestamp,
            )

        interval_rows = working.iloc[1:].copy()
        self._handle_negative_diffs(interval_rows, report)

        duplicate_count = int(interval_rows["timestamp_nl"].duplicated(keep=False).sum())
        if duplicate_count:
            report.add(
                "P1E_DUPLICATE_LOCAL_TIMESTAMPS",
                f"Found {duplicate_count} duplicated local timestamp rows; interval values were summed.",
            )

        grouped = (
            interval_rows.groupby("timestamp_nl", sort=True)
            .agg(
                import_kwh=("import_kwh", "sum"),
                export_kwh=("export_kwh", "sum"),
                import_total_kwh=("import_total_kwh", "last"),
                export_total_kwh=("export_total_kwh", "last"),
            )
            .reset_index()
        )
        grouped["data_quality_flags"] = ""
        grouped = grouped.set_index("timestamp_nl", drop=False)

        return DataManagerResult(grouped, report)

    def calculate_energy_balance(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        required = ("import_kwh", "export_kwh", "solar_kwh")
        self._validate_columns(dataframe.columns, required)

        result = dataframe.copy()
        result["demand_kwh"] = result["import_kwh"] - result["export_kwh"] + result["solar_kwh"]
        result["netto_baseline_kwh"] = result["demand_kwh"] - result["solar_kwh"]
        result["import_zonder_batterij_kwh"] = result["netto_baseline_kwh"].clip(lower=0)
        result["export_zonder_batterij_kwh"] = (-result["netto_baseline_kwh"]).clip(lower=0)
        return result

    def validate_energy_balance(
        self,
        dataframe: pd.DataFrame,
        expected_import_kwh: float,
        expected_export_kwh: float,
        tolerance_pct: float = 1.0,
    ) -> DataQualityReport:
        self._validate_columns(dataframe.columns, ("import_kwh", "export_kwh"))
        report = DataQualityReport()

        self._check_total_within_tolerance(
            report,
            code="ENERGY_BALANCE_IMPORT_OUT_OF_TOLERANCE",
            label="import",
            actual_kwh=float(dataframe["import_kwh"].sum()),
            expected_kwh=expected_import_kwh,
            tolerance_pct=tolerance_pct,
        )
        self._check_total_within_tolerance(
            report,
            code="ENERGY_BALANCE_EXPORT_OUT_OF_TOLERANCE",
            label="export",
            actual_kwh=float(dataframe["export_kwh"].sum()),
            expected_kwh=expected_export_kwh,
            tolerance_pct=tolerance_pct,
        )
        return report

    def detect_spring_dst_gap(self, timestamps: Iterable[pd.Timestamp]) -> bool:
        index = pd.DatetimeIndex(pd.to_datetime(list(timestamps)))
        if index.empty:
            return False

        counts = pd.Series(1, index=index).groupby(index.normalize()).count()
        return bool((counts == 92).any())

    @staticmethod
    def _validate_columns(columns: Iterable[str], required: Iterable[str]) -> None:
        missing = [column for column in required if column not in columns]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Missing required column(s): {missing_text}")

    @staticmethod
    def _handle_negative_diffs(dataframe: pd.DataFrame, report: DataQualityReport) -> None:
        for column in ("import_kwh", "export_kwh"):
            negative_mask = dataframe[column] < 0
            for timestamp in dataframe.loc[negative_mask, "timestamp_nl"]:
                report.add(
                    "P1E_NEGATIVE_DIFFERENCE",
                    f"Negative interval value detected in {column}.",
                    pd.Timestamp(timestamp),
                    column,
                )
            dataframe.loc[negative_mask, column] = 0.0

    @staticmethod
    def _check_total_within_tolerance(
        report: DataQualityReport,
        code: str,
        label: str,
        actual_kwh: float,
        expected_kwh: float,
        tolerance_pct: float,
    ) -> None:
        if expected_kwh == 0:
            is_outside_tolerance = abs(actual_kwh) > 0
            deviation_pct = 100.0 if is_outside_tolerance else 0.0
        else:
            deviation_pct = abs(actual_kwh - expected_kwh) / abs(expected_kwh) * 100
            is_outside_tolerance = deviation_pct > tolerance_pct

        if is_outside_tolerance:
            report.add(
                code,
                (
                    f"Total {label} differs by {deviation_pct:.2f}% "
                    f"(actual {actual_kwh:.3f} kWh, expected {expected_kwh:.3f} kWh)."
                ),
            )

