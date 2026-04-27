"""Scenario year selection and combination helpers."""

from __future__ import annotations

import pandas as pd


SCENARIO_OPTIONS = (
    "2024",
    "2025",
    "2024+2025 gecombineerd",
)


def resolve_scenario_years(scenario: str) -> tuple[int, ...]:
    if scenario == "2024":
        return (2024,)
    if scenario == "2025":
        return (2025,)
    if scenario == "2024+2025 gecombineerd":
        return (2024, 2025)
    raise ValueError(f"Unsupported scenario selection: {scenario}")


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
