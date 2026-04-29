"""Scenario year selection and combination helpers."""

from __future__ import annotations

import pandas as pd


SCENARIO_OPTIONS = (
    "2024",
    "2025",
    "2026 t/m 27 april",
    "2024+2025 gecombineerd",
)


def resolve_scenario_years(scenario: str) -> tuple[int, ...]:
    if scenario == "2024":
        return (2024,)
    if scenario == "2025":
        return (2025,)
    if scenario == "2026 t/m 27 april":
        return (2026,)
    if scenario == "2024+2025 gecombineerd":
        return (2024, 2025)
    raise ValueError(f"Unsupported scenario selection: {scenario}")


def get_year_display_label(year: int) -> str:
    if year == 2026:
        return "2026 t/m 27 april"
    return str(year)


def format_scenario_label(scenario: str) -> str:
    if scenario == "2024+2025 gecombineerd":
        return scenario
    years = resolve_scenario_years(scenario)
    if len(years) == 1:
        return get_year_display_label(years[0])
    return scenario


def combine_yearly_frames(yearly_frames: dict[int, pd.DataFrame]) -> pd.DataFrame:
    if not yearly_frames:
        return pd.DataFrame()

    combined = pd.concat(
        [yearly_frames[year] for year in sorted(yearly_frames)],
        axis=0,
    )
    if "timestamp_nl" in combined.columns:
        if combined.index.name == "timestamp_nl":
            combined = combined.sort_index()
        else:
            combined = combined.sort_values("timestamp_nl")
    else:
        combined = combined.sort_index()
    return combined
