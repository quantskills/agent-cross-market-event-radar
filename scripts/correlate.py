# -*- coding: utf-8 -*-
"""Event correlation layer.

Groups related events inside the same company / time window:

- PLACEMENT → UNLOCK trail      (placement followed by unlock inside window)
- EARNINGS_FORECAST ↔ EARNINGS_FLASH  (direction match / mismatch on same report period)
- DIVIDEND ↔ EARNINGS_EVENT overlap  (same company within N days)
- CLUSTER                        (>=3 events of any type, same company, same window)
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

WINDOW_DAYS = 30


def _parse_dt(s: str):
    try:
        return datetime.strptime(str(s), "%Y%m%d")
    except (TypeError, ValueError):
        return None


def _days_between(a: str, b: str) -> int | None:
    da, db = _parse_dt(a), _parse_dt(b)
    if da is None or db is None:
        return None
    return abs((da - db).days)


def _get(detail_json: str, key: str):
    try:
        return json.loads(detail_json).get(key)
    except (TypeError, ValueError):
        return None


def correlate(events: pd.DataFrame, window_days: int = WINDOW_DAYS) -> list[dict]:
    """Return correlated event groups as a list of dicts."""
    if events.empty:
        return []
    groups: list[dict] = []

    by_symbol = {s: g for s, g in events.groupby("symbol")}

    # 1) PLACEMENT -> UNLOCK trail (same symbol, unlock after placement within window)
    for symbol, g in by_symbol.items():
        placements = g[g["event_type"] == "PLACEMENT"]
        unlocks = g[g["event_type"] == "UNLOCK"]
        for _, p in placements.iterrows():
            listed = _get(p["detail"], "listed_date") or p["event_date"]
            for _, u in unlocks.iterrows():
                gap = _days_between(listed, u["event_date"])
                if gap is not None and 0 <= gap <= window_days:
                    groups.append({
                        "group_type": "PLACEMENT_UNLOCK_TRAIL",
                        "symbol": symbol,
                        "market": p["market"],
                        "window_days": window_days,
                        "relation": f"placement {p['event_date']} (listed {listed}) unlocks on {u['event_date']} (+{gap}d)",
                        "event_ids": [p["event_id"], u["event_id"]],
                        "evidence": {"gap_days": gap},
                    })

    # 2) EARNINGS_FORECAST <-> EARNINGS_FLASH on same report period
    for symbol, g in by_symbol.items():
        forecasts = g[g["event_type"] == "EARNINGS_FORECAST"]
        flashes = g[g["event_type"] == "EARNINGS_FLASH"]
        for _, f in forecasts.iterrows():
            f_dir = _get(f["detail"], "direction")
            f_np_lo = _get(f["detail"], "np_floor")
            f_np_hi = _get(f["detail"], "np_ceiling")
            for _, fl in flashes.iterrows():
                gap = _days_between(f["event_date"], fl["event_date"])
                if gap is None or gap > window_days:
                    continue
                flash_np = _get(fl["detail"], "net_profit_parent")
                match = None
                if f_dir in ("up", "down") and flash_np is not None and f_np_lo is not None:
                    if flash_np >= f_np_lo and (f_np_hi is None or flash_np <= f_np_hi):
                        match = "in_range"
                    else:
                        match = "mismatch"
                if f_dir in ("up", "down") and flash_np is not None:
                    actual_dir = "up" if flash_np >= 0 else "down"
                    if match is None:
                        match = "direction_match" if actual_dir == f_dir else "direction_mismatch"
                groups.append({
                    "group_type": "FORECAST_FLASH_CHECK",
                    "symbol": symbol,
                    "market": f["market"],
                    "window_days": window_days,
                    "relation": f"forecast {f['event_date']} vs flash {fl['event_date']} → {match or 'insufficient_data'}",
                    "event_ids": [f["event_id"], fl["event_id"]],
                    "evidence": {"forecast_direction": f_dir, "flash_np": flash_np, "check": match},
                })

    # 3) DIVIDEND <-> EARNINGS_EVENT overlap (same company within window)
    for symbol, g in by_symbol.items():
        divs = g[g["event_type"] == "DIVIDEND"]
        earnings = g[g["event_type"] == "EARNINGS_EVENT"]
        for _, d in divs.iterrows():
            for _, e in earnings.iterrows():
                gap = _days_between(d["event_date"], e["event_date"])
                if gap is not None and gap <= 7:
                    groups.append({
                        "group_type": "DIVIDEND_EARNINGS_OVERLAP",
                        "symbol": symbol,
                        "market": d["market"],
                        "window_days": 7,
                        "relation": f"dividend {d['event_date']} overlaps earnings event {e['event_date']} ({gap}d apart)",
                        "event_ids": [d["event_id"], e["event_id"]],
                        "evidence": {"gap_days": gap},
                    })

    # 4) CLUSTER: >=3 events same symbol within window
    for symbol, g in by_symbol.items():
        dates = sorted({d for d in g["event_date"] if _parse_dt(d)}, reverse=True)
        for anchor in dates:
            inside = [
                row for _, row in g.iterrows()
                if (gap := _days_between(anchor, row["event_date"])) is not None and gap <= window_days
            ]
            if len(inside) >= 3:
                ids = sorted({r["event_id"] for r in inside})
                groups.append({
                    "group_type": "EVENT_CLUSTER",
                    "symbol": symbol,
                    "market": inside[0]["market"],
                    "window_days": window_days,
                    "relation": f"{len(ids)} events clustered around {anchor} within {window_days}d",
                    "event_ids": ids,
                    "evidence": {"event_count": len(ids), "anchor_date": anchor},
                })
                break  # one cluster per symbol is enough

    # dedup groups by (type, symbol, event_ids)
    seen = set()
    unique = []
    for grp in groups:
        key = (grp["group_type"], grp["symbol"], tuple(grp["event_ids"]))
        if key not in seen:
            seen.add(key)
            unique.append(grp)
    return unique
