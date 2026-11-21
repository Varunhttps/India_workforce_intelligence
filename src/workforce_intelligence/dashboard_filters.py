"""Small, testable dashboard filtering helpers."""
from __future__ import annotations

import pandas as pd

ALL_INDUSTRIES = "All industries"


def industry_options(frames):
    """Return a stable list of industry filter options from available tables."""
    values = {}
    for frame in (frames or {}).values():
        if not isinstance(frame, pd.DataFrame) or frame.empty or "Industry" not in frame.columns:
            continue
        for value in frame["Industry"].dropna():
            display = str(value).strip()
            if display:
                values.setdefault(display.casefold(), display)
    return [ALL_INDUSTRIES, *sorted(values.values(), key=str.casefold)]


def filter_frames_by_industry(frames, selected_industry=ALL_INDUSTRIES):
    """Apply an industry filter to tables that have an Industry column."""
    selected = str(selected_industry or ALL_INDUSTRIES).strip()
    filtered = {}
    for name, frame in (frames or {}).items():
        if not isinstance(frame, pd.DataFrame):
            filtered[name] = frame
        elif selected == ALL_INDUSTRIES or frame.empty or "Industry" not in frame.columns:
            filtered[name] = frame.copy()
        else:
            mask = frame["Industry"].fillna("").astype(str).str.strip().str.casefold() == selected.casefold()
            filtered[name] = frame.loc[mask].copy()
    return filtered
