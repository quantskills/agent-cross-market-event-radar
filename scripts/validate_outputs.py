# -*- coding: utf-8 -*-
"""Validate the public outputs under outputs/live/.

Run after a live run:  py -3.10 scripts/validate_outputs.py
Exits non-zero on any validation failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "live"

REQUIRED_FILES = [
    "event_dashboard.json",
    "event_radar.csv",
    "correlated_groups.json",
    "priority_watchlist.csv",
    "risk_alerts.md",
    "run_summary.json",
]

REQUIRED_EVENT_FIELDS = ["event_id", "event_type", "event_date", "symbol", "market", "data_completeness"]
VALID_MARKETS = {"a-share", "hk", "us"}

FAIL = 0


def check(name: str, cond: bool) -> None:
    global FAIL
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        FAIL += 1


def main() -> None:
    print("== outputs/live validation ==")
    for f in REQUIRED_FILES:
        check(f"exists {f}", (OUT / f).exists())

    try:
        radar = (OUT / "event_radar.csv").read_text(encoding="utf-8-sig").splitlines()
        header = radar[0].split(",")
        check("radar has required fields", all(c in header for c in REQUIRED_EVENT_FIELDS))
        rows = [dict(zip(header, line.split(",", len(header) - 1))) for line in radar[1:]]
        check("radar markets valid", all(r.get("market") in VALID_MARKETS or not r.get("market") for r in rows))
        dup = len({r["event_id"] for r in rows}) != len(rows)
        check("radar event_id unique", not dup)
    except Exception as exc:
        check(f"radar parse error: {exc}", False)

    try:
        dash = json.loads((OUT / "event_dashboard.json").read_text(encoding="utf-8"))
        check("dashboard has as_of", "as_of" in dash)
        check("dashboard has total_events", "total_events" in dash)
    except Exception as exc:
        check(f"dashboard parse error: {exc}", False)

    try:
        groups = json.loads((OUT / "correlated_groups.json").read_text(encoding="utf-8"))
        check("groups is list", isinstance(groups, list))
        check("groups have type+ids", all("group_type" in g and "event_ids" in g for g in groups))
    except Exception as exc:
        check(f"groups parse error: {exc}", False)

    try:
        summary = json.loads((OUT / "run_summary.json").read_text(encoding="utf-8"))
        check("summary lists 10 methods", len(summary.get("pandadata_methods", [])) == 10)
        check("summary boundary stated", "no order execution" in summary.get("boundary", ""))
        check("summary events counted", isinstance(summary.get("events_total"), int))
    except Exception as exc:
        check(f"summary parse error: {exc}", False)

    try:
        alerts = (OUT / "risk_alerts.md").read_text(encoding="utf-8")
        check("alerts mention no-advice", "不构成投资建议" in alerts)
        check("alerts mention no execution", "不直接下单" in alerts)
    except Exception as exc:
        check(f"alerts parse error: {exc}", False)

    print()
    print(f"VALIDATION: {'ALL PASS' if FAIL == 0 else f'{FAIL} FAIL'}")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
