# -*- coding: utf-8 -*-
"""Priority ranking layer.

priority_score (0-100) = 40% proximity + 35% historical impact + 25% completeness

- proximity: closer to the as-of date ranks higher; events already past are
  decayed but still visible for 7 days.
- historical impact: per event-type prior weight (research view, not a promise).
- completeness: data_completeness from the standardization layer.
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

PROXIMITY_WEIGHT = 0.40
IMPACT_WEIGHT = 0.35
COMPLETENESS_WEIGHT = 0.25

EVENT_IMPACT = {
    "EARNINGS_FORECAST": 0.85,
    "EARNINGS_FLASH": 0.80,
    "EARNINGS_EVENT": 0.80,
    "PLACEMENT": 0.75,
    "UNLOCK": 0.70,
    "DIVIDEND": 0.60,
    "MEETING": 0.50,
    "IR_EVENT": 0.45,
    "MARKET_EVENT": 0.40,
}

BOOST_GROUPS = {
    "PLACEMENT_UNLOCK_TRAIL": 10,
    "FORECAST_FLASH_CHECK": 10,
    "DIVIDEND_EARNINGS_OVERLAP": 8,
    "EVENT_CLUSTER": 6,
}


def _parse_dt(s: str):
    try:
        return datetime.strptime(str(s), "%Y%m%d")
    except (TypeError, ValueError):
        return None


def proximity_score(event_date: str, as_of: str, horizon_days: int = 30) -> float | None:
    """1.0 at as_of, linearly decaying to 0 at horizon; past events decay faster (7d)."""
    ed, ao = _parse_dt(event_date), _parse_dt(as_of)
    if ed is None or ao is None:
        return None
    delta = (ed - ao).days
    if delta == 0:
        return 1.0
    if delta > 0:
        return max(0.0, 1.0 - delta / horizon_days)
    return max(0.0, 1.0 + delta / 7.0)


def rank_events(events: pd.DataFrame, as_of: str, correlated: list[dict] | None = None,
                horizon_days: int = 30) -> pd.DataFrame:
    """Attach priority columns and return events sorted by priority_score desc."""
    df = events.copy()
    if df.empty:
        return df

    correlated = correlated or []
    boost: dict[str, int] = {}
    for grp in correlated:
        points = BOOST_GROUPS.get(grp["group_type"], 0)
        for eid in grp["event_ids"]:
            boost[eid] = max(boost.get(eid, 0), points)

    def score_row(row) -> dict:
        prox = proximity_score(row["event_date"], as_of, horizon_days)
        impact = EVENT_IMPACT.get(row["event_type"], 0.3)
        comp = float(row.get("data_completeness", 0.0) or 0.0)
        if prox is None:
            return {"proximity": None, "impact": round(impact, 2),
                    "completeness": comp, "priority_score": None,
                    "in_correlated_group": row["event_id"] in boost}
        base = 100 * (PROXIMITY_WEIGHT * prox + IMPACT_WEIGHT * impact + COMPLETENESS_WEIGHT * comp)
        total = min(100.0, base + boost.get(row["event_id"], 0))
        return {"proximity": round(prox, 3), "impact": round(impact, 2),
                "completeness": comp, "priority_score": round(total, 1),
                "in_correlated_group": row["event_id"] in boost}

    scores = df.apply(score_row, axis=1, result_type="expand")
    df = pd.concat([df, scores], axis=1)
    df = df.sort_values(["priority_score", "event_date"], ascending=[False, False], na_position="last")
    return df.reset_index(drop=True)


def top_watchlist(ranked: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Top-N research candidates with the columns users need."""
    cols = ["priority_score", "event_date", "event_type", "symbol", "market",
            "title", "data_completeness", "in_correlated_group"]
    if ranked.empty:
        return pd.DataFrame(columns=cols)
    watch = ranked[ranked["priority_score"].notna()].head(n)
    return watch[cols].reset_index(drop=True)
