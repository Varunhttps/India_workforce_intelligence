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



def weekly_statuses(frame, current_week=None):
    """Classify observations using dates and explicit observation-week history, not stale labels."""
    from datetime import date, timedelta

    if frame is None:
        return pd.Series(dtype=object)
    current = pd.to_datetime(current_week or date.today().isoformat(), errors="coerce")
    if pd.isna(current):
        current = pd.Timestamp(date.today())
    current_date = current.date()
    current_monday = (current_date - timedelta(days=current_date.weekday())).isoformat()

    def week_key(value):
        text = str(value or "").strip()
        parsed = pd.to_datetime(text, errors="coerce", format="%Y-%m-%d")
        if pd.isna(parsed):
            parsed = pd.to_datetime(text, errors="coerce", format="%d%m%Y")
        if pd.isna(parsed):
            return ""
        day = parsed.date()
        return (day - timedelta(days=day.weekday())).isoformat()

    first = frame.get("First Seen", pd.Series("", index=frame.index)).map(week_key)
    # Prefer the explicit observation-week list when available. This prevents a
    # stale/duplicated date column from masking an actual current-week sighting.
    observation_weeks = frame.get("Observation Weeks", pd.Series("", index=frame.index))
    observed_current = observation_weeks.map(
        lambda value: current_monday in {week_key(part) for part in str(value or "").split(",") if part.strip()}
    )
    last_values = frame.get("Last Seen", frame.get("Latest Week", pd.Series("", index=frame.index)))
    last = last_values.map(week_key)
    derived = []
    for first_week, last_week, observed in zip(first, last, observed_current):
        if first_week == current_monday:
            derived.append("New this week")
        elif observed or last_week == current_monday:
            derived.append("Recurring this week")
        elif first_week and last_week:
            derived.append("Last seen before this week")
        else:
            derived.append("Unknown")
    # Historical Weekly Status labels are intentionally not trusted; they can be
    # stale after date metadata is refreshed. Always derive from observation dates.
    return pd.Series(derived, index=frame.index, dtype=object)
