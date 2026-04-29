import pandas as pd

from src.scenario_runner import (
    combine_yearly_frames,
    get_year_display_label,
    resolve_scenario_years,
)


def test_resolve_scenario_years_supports_combined_selection():
    assert resolve_scenario_years("2024") == (2024,)
    assert resolve_scenario_years("2025") == (2025,)
    assert resolve_scenario_years("2026 t/m 27 april") == (2026,)
    assert resolve_scenario_years("2024+2025 gecombineerd") == (2024, 2025)


def test_get_year_display_label_formats_partial_2026():
    assert get_year_display_label(2024) == "2024"
    assert get_year_display_label(2026) == "2026 t/m 27 april"


def test_combine_yearly_frames_sorts_on_timestamp():
    frame_2025 = pd.DataFrame(
        {
            "timestamp_nl": [pd.Timestamp("2025-01-01 00:00:00")],
            "value": [2.0],
        }
    ).set_index("timestamp_nl", drop=False)
    frame_2024 = pd.DataFrame(
        {
            "timestamp_nl": [pd.Timestamp("2024-01-01 00:00:00")],
            "value": [1.0],
        }
    ).set_index("timestamp_nl", drop=False)

    combined = combine_yearly_frames({2025: frame_2025, 2024: frame_2024})

    assert combined["value"].tolist() == [1.0, 2.0]
