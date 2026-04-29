"""Data loading and preprocessing for the thuisbatterij simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable

import pandas as pd
from pypdf import PdfReader


P1E_REQUIRED_COLUMNS = (
    "time",
    "Import T1 kWh",
    "Import T2 kWh",
    "Export T1 kWh",
    "Export T2 kWh",
)
PRICE_REQUIRED_COLUMNS = ("datum_nl", "prijs_excl_belastingen")
HA_REQUIRED_COLUMNS = ("entity_id", "state", "last_changed")
SOLAR_LIFETIME_ENTITY = "sensor.gerardus_total_energieopbrengst_levenslang"
RESOURCE_FILES = {
    2024: {
        "p1e": "P1e-2024-1-1-2024-12-31.csv",
        "prices": "jeroen_punt_nl_dynamische_stroomprijzen_jaar_2024.csv",
        "solar": "history HA 2024.csv",
    },
    2025: {
        "p1e": "P1e-2025-1-1-2025-12-31.csv",
        "prices": "jeroen_punt_nl_dynamische_stroomprijzen_jaar_2025.csv",
        "solar": "history HA 2025.csv",
    },
    2026: {
        "p1e": "P1e-2026-1-1-2026-4-27.csv",
        "prices": "jeroen_punt_nl_dynamische_stroomprijzen_jaar_2026.csv",
        "solar": "history HA 2026.csv",
    },
}
RESOURCE_LABELS = {
    "p1e": "P1e",
    "prices": "Prijzen",
    "solar": "Home Assistant",
}
DATA_QUALITY_FLAG_DTYPE = pd.CategoricalDtype(categories=("",))
FRANK_TERM_INVOICE_PATTERN = "Frank termijn *.pdf"
FRANK_MONTH_ORDER = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}
FRANK_MONTH_ABBREVIATIONS = {
    "januari": "jan",
    "februari": "feb",
    "maart": "mrt",
    "april": "apr",
    "mei": "mei",
    "juni": "jun",
    "juli": "jul",
    "augustus": "aug",
    "september": "sep",
    "oktober": "okt",
    "november": "nov",
    "december": "dec",
}
FRANK_INVOICE_SECTIONS = ("Gas", "Stroom", "Teruglevering")


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


@dataclass(frozen=True)
class ResourceFileStatus:
    """Status for one expected resource file."""

    label: str
    path: Path
    exists: bool
    size_bytes: int | None = None


@dataclass(frozen=True)
class P1eFileSummary:
    """Human-readable summary for one P1e file."""

    path: Path
    interval_count: int
    first_timestamp: pd.Timestamp | None
    last_timestamp: pd.Timestamp | None
    total_import_kwh: float
    total_export_kwh: float
    issue_count: int
    issue_codes: tuple[str, ...]


@dataclass(frozen=True)
class GoldenDataFrameSummary:
    """Summary for a fully joined yearly input dataframe."""

    year: int
    interval_count: int
    first_timestamp: pd.Timestamp | None
    last_timestamp: pd.Timestamp | None
    total_import_kwh: float
    total_export_kwh: float
    total_solar_kwh: float
    total_demand_kwh: float
    missing_price_count: int
    issue_count: int
    issue_codes: tuple[str, ...]


@dataclass(frozen=True)
class FrankTermInvoiceSummary:
    """Parsed monthly Frank term invoice for sanity checks."""

    path: Path
    month_name_nl: str
    month_number: int
    invoice_total_eur: float
    expected_electricity_component_eur: float
    expected_gas_component_eur: float


class DataManager:
    """Prepare historical input data for simulation."""

    def __init__(self, resources_path: str | Path = "resources") -> None:
        self.resources_path = Path(resources_path)

    def get_resource_statuses(self) -> list[ResourceFileStatus]:
        statuses: list[ResourceFileStatus] = []
        for year, files in RESOURCE_FILES.items():
            for resource_key, filename in files.items():
                path = self.resources_path / filename
                statuses.append(
                    ResourceFileStatus(
                        label=f"{RESOURCE_LABELS[resource_key]} {year}",
                        path=path,
                        exists=path.exists(),
                        size_bytes=path.stat().st_size if path.exists() else None,
                    )
                )
        return statuses

    def summarize_p1e_file(self, path: str | Path) -> P1eFileSummary:
        result = self.load_p1e_csv(path)
        dataframe = result.dataframe
        issue_codes = tuple(sorted({issue.code for issue in result.report.issues}))

        if dataframe.empty:
            first_timestamp = None
            last_timestamp = None
        else:
            first_timestamp = pd.Timestamp(dataframe.index.min())
            last_timestamp = pd.Timestamp(dataframe.index.max())

        return P1eFileSummary(
            path=Path(path),
            interval_count=len(dataframe),
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            total_import_kwh=float(dataframe["import_kwh"].sum()) if not dataframe.empty else 0.0,
            total_export_kwh=float(dataframe["export_kwh"].sum()) if not dataframe.empty else 0.0,
            issue_count=len(result.report.issues),
            issue_codes=issue_codes,
        )

    def summarize_available_p1e_files(self) -> list[P1eFileSummary]:
        summaries: list[P1eFileSummary] = []
        for status in self.get_resource_statuses():
            if status.label.startswith("P1e") and status.exists:
                summaries.append(self.summarize_p1e_file(status.path))
        return summaries

    def summarize_available_golden_dataframes(self) -> list[GoldenDataFrameSummary]:
        summaries: list[GoldenDataFrameSummary] = []
        for year in RESOURCE_FILES:
            paths = self.get_year_resource_paths(year)
            if all(path.exists() for path in paths.values()):
                result = self.build_golden_dataframe(
                    paths["p1e"],
                    paths["prices"],
                    paths["solar"],
                )
                summaries.append(self.summarize_golden_dataframe(year, result))
        return summaries

    def get_year_resource_paths(self, year: int) -> dict[str, Path]:
        if year not in RESOURCE_FILES:
            raise ValueError(f"Unsupported scenario year: {year}")
        return {
            key: self.resources_path / filename
            for key, filename in RESOURCE_FILES[year].items()
        }

    def summarize_frank_term_invoices(self) -> list[FrankTermInvoiceSummary]:
        summaries = []
        for path in sorted(self.resources_path.glob(FRANK_TERM_INVOICE_PATTERN)):
            summaries.append(self.summarize_frank_term_invoice(path))
        return sorted(summaries, key=lambda summary: summary.month_number)

    def summarize_frank_term_invoice(self, path: str | Path) -> FrankTermInvoiceSummary:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return self._parse_frank_term_invoice_text(Path(path), text)

    def summarize_golden_dataframe(
        self,
        year: int,
        result: DataManagerResult,
    ) -> GoldenDataFrameSummary:
        dataframe = result.dataframe
        issue_codes = tuple(sorted({issue.code for issue in result.report.issues}))

        if dataframe.empty:
            first_timestamp = None
            last_timestamp = None
        else:
            first_timestamp = pd.Timestamp(dataframe.index.min())
            last_timestamp = pd.Timestamp(dataframe.index.max())

        return GoldenDataFrameSummary(
            year=year,
            interval_count=len(dataframe),
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            total_import_kwh=self._sum_column(dataframe, "import_kwh"),
            total_export_kwh=self._sum_column(dataframe, "export_kwh"),
            total_solar_kwh=self._sum_column(dataframe, "solar_kwh"),
            total_demand_kwh=self._sum_column(dataframe, "demand_kwh"),
            missing_price_count=int(dataframe["spot_price_eur_per_kwh"].isna().sum())
            if "spot_price_eur_per_kwh" in dataframe
            else 0,
            issue_count=len(result.report.issues),
            issue_codes=issue_codes,
        )

    def _parse_frank_term_invoice_text(
        self,
        path: Path,
        text: str,
    ) -> FrankTermInvoiceSummary:
        month_match = re.search(r"Termijnfactuur\s+([A-Za-zÀ-ÿ]+)", text, flags=re.IGNORECASE)
        if month_match is None:
            raise ValueError(f"Could not parse invoice month from {path.name}.")
        month_name_nl = month_match.group(1).strip().lower()
        if month_name_nl not in FRANK_MONTH_ORDER:
            raise ValueError(f"Unsupported Dutch invoice month '{month_name_nl}' in {path.name}.")

        invoice_totals = re.findall(
            r"Notabedrag\s*(?:Incl\.\s*[\d,]+\s*BTW\s*)?[€â‚¬]\s*([\d\.,]+)",
            text,
            flags=re.IGNORECASE,
        )
        if not invoice_totals:
            raise ValueError(f"Could not parse invoice total from {path.name}.")

        fixed_electricity_component_eur = self._parse_fixed_electricity_component(text)
        expected_gas_component_eur = self._parse_expected_component_amount(
            text,
            component_label="Verwachte kosten",
            month_name_nl=month_name_nl,
            section_label="Gas",
        )
        expected_stroom_cost_eur = self._parse_expected_component_amount(
            text,
            component_label="Verwachte kosten",
            month_name_nl=month_name_nl,
            section_label="Stroom",
        )
        expected_teruglevering_eur = self._parse_expected_component_amount(
            text,
            component_label="Verwachte opbrengst",
            month_name_nl=month_name_nl,
            section_label="Teruglevering",
        )

        return FrankTermInvoiceSummary(
            path=path,
            month_name_nl=month_name_nl,
            month_number=FRANK_MONTH_ORDER[month_name_nl],
            invoice_total_eur=self._parse_euro_number(invoice_totals[0]),
            expected_electricity_component_eur=(
                fixed_electricity_component_eur
                + expected_stroom_cost_eur
                + expected_teruglevering_eur
            ),
            expected_gas_component_eur=expected_gas_component_eur,
        )

    def _parse_fixed_electricity_component(self, text: str) -> float:
        labels = (
            "Vaste leveringskosten",
            "Energiebelasting & ODE",
            "Vermindering energiebelasting",
            "Netbeheerkosten",
        )
        total_eur = 0.0
        for label in labels:
            row_snippet = self._extract_row_block(
                text,
                row_label=label,
                next_markers=(
                    "Vaste leveringskosten",
                    "Energiebelasting & ODE",
                    "Vermindering energiebelasting",
                    "Netbeheerkosten",
                    "Het dynamische deel",
                    "Gas",
                ),
            )
            amounts = re.findall(r"€\s*([-\d\.,]+)", row_snippet, flags=re.IGNORECASE)
            if len(amounts) < 2:
                raise ValueError(f"Could not parse fixed cost row '{label}' from invoice text.")
            total_eur += self._parse_euro_number(amounts[-1])
        return total_eur

    @staticmethod
    def _parse_expected_component_amount(
        text: str,
        component_label: str,
        month_name_nl: str,
        section_label: str | None = None,
    ) -> float:
        month_abbreviation = FRANK_MONTH_ABBREVIATIONS[month_name_nl]
        if section_label is not None:
            section_text = DataManager._extract_invoice_section(text, section_label)
        else:
            section_text = text
        row_label = f"{component_label} {month_abbreviation}"
        row_snippet = DataManager._extract_row_block(
            section_text,
            row_label=row_label,
            next_markers=(
                "Verwachte kosten",
                "Werkelijke kosten",
                "Betaald voor",
                "Verwachte opbrengst",
                "Werkelijke opbrengst",
                "Het verschuldigde bedrag",
                "Leveringsadres:",
                "Notabedrag",
                "Gas",
                "Stroom",
                "Teruglevering",
            ),
        )
        amounts = re.findall(r"€\s*([-\d\.,]+)", row_snippet, flags=re.IGNORECASE)
        if not amounts:
            raise ValueError(
                f"Could not parse '{component_label} {month_name_nl}' amount from invoice text."
            )
        return DataManager._parse_euro_number(amounts[-1])

    @staticmethod
    def _extract_invoice_section(text: str, section_label: str) -> str:
        section_start = text.find(section_label)
        if section_start == -1:
            raise ValueError(f"Could not find invoice section '{section_label}'.")
        section_end = len(text)
        for next_label in FRANK_INVOICE_SECTIONS:
            if next_label == section_label:
                continue
            next_index = text.find(next_label, section_start + len(section_label))
            if next_index != -1:
                section_end = min(section_end, next_index)
        return text[section_start:section_end]

    @staticmethod
    def _extract_row_block(text: str, row_label: str, next_markers: Iterable[str]) -> str:
        row_start = text.lower().find(row_label.lower())
        if row_start == -1:
            raise ValueError(f"Could not find invoice row '{row_label}'.")

        row_end = len(text)
        search_from = row_start + len(row_label)
        for marker in next_markers:
            if marker.lower() == row_label.lower():
                continue
            marker_index = text.lower().find(marker.lower(), search_from)
            if marker_index != -1:
                row_end = min(row_end, marker_index)
        return text[row_start:row_end]

    @staticmethod
    def _parse_euro_number(value: str) -> float:
        normalized = value.replace(".", "").replace(",", ".")
        return float(normalized)

    def load_price_csv(self, path: str | Path) -> pd.DataFrame:
        dataframe = pd.read_csv(path, sep=";", decimal=",")
        return self.preprocess_prices(dataframe)

    def preprocess_prices(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        self._validate_columns(dataframe.columns, PRICE_REQUIRED_COLUMNS)

        result = dataframe.copy()
        result["timestamp_nl"] = pd.to_datetime(result["datum_nl"])
        result["spot_price_eur_per_kwh"] = result["prijs_excl_belastingen"].astype(float)
        result = result[["timestamp_nl", "spot_price_eur_per_kwh"]]
        result = result.sort_values("timestamp_nl")
        return result.set_index("timestamp_nl", drop=False)

    def load_solar_csv(self, path: str | Path) -> DataManagerResult:
        dataframe = pd.read_csv(path)
        return self.preprocess_solar_lifetime(dataframe)

    def preprocess_solar_lifetime(self, dataframe: pd.DataFrame) -> DataManagerResult:
        report = DataQualityReport()
        self._validate_columns(dataframe.columns, HA_REQUIRED_COLUMNS)

        working = dataframe.loc[dataframe["entity_id"] == SOLAR_LIFETIME_ENTITY].copy()
        if working.empty:
            report.add(
                "SOLAR_LIFETIME_SENSOR_MISSING",
                f"No rows found for {SOLAR_LIFETIME_ENTITY}.",
            )
            return DataManagerResult(self._empty_solar_frame(), report)

        working["state_numeric"] = pd.to_numeric(working["state"], errors="coerce")
        invalid_count = int(working["state_numeric"].isna().sum())
        if invalid_count:
            report.add(
                "SOLAR_INVALID_STATE",
                f"Ignored {invalid_count} non-numeric solar lifetime rows.",
            )
        working = working.dropna(subset=["state_numeric"])
        if working.empty:
            return DataManagerResult(self._empty_solar_frame(), report)

        working["timestamp_nl"] = (
            pd.to_datetime(working["last_changed"], utc=True)
            .dt.tz_convert("Europe/Amsterdam")
            .dt.tz_localize(None)
        )
        working = working.sort_values("timestamp_nl")
        working["timestamp_nl"] = working["timestamp_nl"].dt.floor("h")
        working = (
            working.groupby("timestamp_nl", sort=True, as_index=False)
            .agg(state_numeric=("state_numeric", "last"))
        )
        working["solar_hourly_kwh"] = working["state_numeric"].diff()
        working = working.iloc[1:].copy()

        negative_mask = working["solar_hourly_kwh"] < 0
        for timestamp in working.loc[negative_mask, "timestamp_nl"]:
            report.add(
                "SOLAR_NEGATIVE_DIFFERENCE",
                "Negative solar lifetime difference detected and set to 0.",
                pd.Timestamp(timestamp),
                "solar_hourly_kwh",
            )
        working.loc[negative_mask, "solar_hourly_kwh"] = 0.0

        quarter_rows = []
        for row in working.itertuples(index=False):
            interval_start = pd.Timestamp(row.timestamp_nl) - pd.Timedelta(hours=1)
            quarter_kwh = float(row.solar_hourly_kwh) / 4
            for offset in range(4):
                quarter_rows.append(
                    {
                        "timestamp_nl": interval_start + pd.Timedelta(minutes=15 * offset),
                        "solar_kwh": quarter_kwh,
                    }
                )

        if not quarter_rows:
            return DataManagerResult(self._empty_solar_frame(), report)

        result = pd.DataFrame(quarter_rows)
        result = result.groupby("timestamp_nl", sort=True, as_index=False)["solar_kwh"].sum()
        result = result.set_index("timestamp_nl", drop=False)
        result["data_quality_flags"] = pd.Series(
            pd.Categorical([""] * len(result), dtype=DATA_QUALITY_FLAG_DTYPE),
            index=result.index,
        )
        return DataManagerResult(result, report)

    def build_golden_dataframe(
        self,
        p1e_path: str | Path,
        price_path: str | Path,
        solar_path: str | Path,
    ) -> DataManagerResult:
        p1e_result = self.load_p1e_csv(p1e_path)
        prices = self.load_price_csv(price_path)
        solar_result = self.load_solar_csv(solar_path)

        report = DataQualityReport(
            issues=[*p1e_result.report.issues, *solar_result.report.issues]
        )
        golden = self._join_prices_to_intervals(p1e_result.dataframe, prices)
        golden = golden.join(solar_result.dataframe[["solar_kwh"]], how="left")
        golden["solar_kwh"] = golden["solar_kwh"].fillna(0.0)

        missing_prices = golden["spot_price_eur_per_kwh"].isna()
        if missing_prices.any():
            report.add(
                "PRICE_MISSING_INTERVALS",
                f"Missing spot price for {int(missing_prices.sum())} interval(s).",
            )

        golden = self.calculate_energy_balance(golden)
        balance_report = self.validate_energy_balance(
            golden,
            expected_import_kwh=float(p1e_result.dataframe["import_kwh"].sum()),
            expected_export_kwh=float(p1e_result.dataframe["export_kwh"].sum()),
        )
        report.issues.extend(balance_report.issues)
        golden["timestamp_nl"] = golden.index
        golden["data_quality_flags"] = pd.Series(
            pd.Categorical([""] * len(golden), dtype=DATA_QUALITY_FLAG_DTYPE),
            index=golden.index,
        )
        return DataManagerResult(golden, report)

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
                (
                    f"Found {duplicate_count} duplicated local timestamp rows; "
                    "interval values were summed."
                ),
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
        grouped["data_quality_flags"] = pd.Categorical(
            [""] * len(grouped),
            dtype=DATA_QUALITY_FLAG_DTYPE,
        )
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

        spring_dst_candidates = index[(index.month == 3) & (index.day >= 25)]
        if spring_dst_candidates.empty:
            return False

        counts = pd.Series(1, index=spring_dst_candidates).groupby(
            spring_dst_candidates.normalize()
        ).count()
        return bool((counts == 92).any())

    @staticmethod
    def _join_prices_to_intervals(
        intervals: pd.DataFrame,
        prices: pd.DataFrame,
    ) -> pd.DataFrame:
        price_series = prices["spot_price_eur_per_kwh"].sort_index()
        interval_index = intervals.index
        joined = intervals.copy()
        joined["spot_price_eur_per_kwh"] = price_series.reindex(interval_index, method="ffill")
        return joined

    @staticmethod
    def _empty_solar_frame() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "timestamp_nl": pd.Series(dtype="datetime64[ns]"),
                "solar_kwh": pd.Series(dtype="float64"),
                "data_quality_flags": pd.Series(dtype=DATA_QUALITY_FLAG_DTYPE),
            }
        ).set_index("timestamp_nl", drop=False)

    @staticmethod
    def _sum_column(dataframe: pd.DataFrame, column: str) -> float:
        if column not in dataframe or dataframe.empty:
            return 0.0
        return float(dataframe[column].sum())

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
