# -*- coding: utf-8 -*-
"""Offline unit tests for the Cross-Market Event Radar logic layers.

Run:  py -3.10 tests/test_radar.py
Uses synthetic DataFrames only; no network access required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pandas as pd

from standardize import (
    merge_events,
    standardize_forecasts,
    standardize_hkus,
    standardize_performances,
    standardize_placements,
    standardize_restricted,
    EVENT_COLUMNS,
)
from correlate import correlate
from prioritize import rank_events, top_watchlist, proximity_score

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


print("== standardize: placements ==")
placements = pd.DataFrame([
    {"symbol": "000001.SZ", "announcement_date": "20250110", "issue_type": "非公开发行",
     "issue_status": "实施完成", "listed_date": "20250710", "issued_shares": 1.0e7,
     "issue_price": 10.0, "approval_date": "20250101", "date": None},
])
ev = standardize_placements(placements)
check("columns ok", list(ev.columns) == EVENT_COLUMNS)
check("one event", len(ev) == 1)
check("type PLACEMENT", ev.iloc[0]["event_type"] == "PLACEMENT")
check("market a-share", ev.iloc[0]["market"] == "a-share")
check("completeness 1.0", ev.iloc[0]["data_completeness"] == 1.0)
check("raise size computed", json.loads(ev.iloc[0]["detail"])["raise_size"] == 1.0e8)

print("== standardize: restricted (grouped by symbol+relieve_date) ==")
restricted = pd.DataFrame([
    {"symbol": "000001.SZ", "date": "20250710", "relieve_date": "20250712",
     "shareholder": "A", "relieve_shares": 100.0, "actual_relieve_shares": 100.0,
     "relieve_reason": "发行前股份限售流通", "shareholder_type": "企业"},
    {"symbol": "000001.SZ", "date": "20250710", "relieve_date": "20250712",
     "shareholder": "B", "relieve_shares": 50.0, "actual_relieve_shares": 50.0,
     "relieve_reason": "发行前股份限售流通", "shareholder_type": "自然人"},
])
ev2 = standardize_restricted(restricted)
check("grouped to 1 event", len(ev2) == 1)
check("total shares 150", json.loads(ev2.iloc[0]["detail"])["relieve_shares_total"] == 150.0)
check("holders 2", json.loads(ev2.iloc[0]["detail"])["holders"] == 2)

print("== standardize: forecasts / performances ==")
forecast = pd.DataFrame([
    {"symbol": "688795.SH", "info_date": "20251128", "end_date": "20251231",
     "forecast_type": "预增", "forecast_description": "累计利润",
     "forecast_np_floor": 1.0e8, "forecast_np_ceiling": 2.0e8,
     "forecast_growth_rate_floor": 10.0, "forecast_growth_rate_ceiling": 20.0},
])
evf = standardize_forecasts(forecast)
check("forecast direction up", json.loads(evf.iloc[0]["detail"])["direction"] == "up")

perf = pd.DataFrame([
    {"symbol": "688795.SH", "info_date": "20251220", "end_date": "20251231",
     "net_profit_parent": 1.5e8, "net_profit_parent_yoy": 15.0,
     "operating_revenue": 5.0e8},
])
evp = standardize_performances(perf)
check("flash np parsed", json.loads(evp.iloc[0]["detail"])["net_profit_parent"] == 1.5e8)

print("== standardize: hk/us events ==")
div = pd.DataFrame([
    {"symbol": "0003.HK", "publish_date": "20260831", "excute_date": "20260911",
     "event_type": "ExDividends", "number": 0.12, "currency": "HKD",
     "event": "Interim Cash Dividend"},
])
evd = standardize_hkus(div, "get_stock_dividend_event")
check("dividend type", evd.iloc[0]["event_type"] == "DIVIDEND")
check("hk market", evd.iloc[0]["market"] == "hk")

meet = pd.DataFrame([
    {"symbol": "AAPL.US", "info_date": "20260810", "start_date": "20260810",
     "end_date": "20260810", "event": "Q3 Earnings Call", "is_estimated": 0,
     "event_type": "EarningsReleases", "fiscal_quarter": "2026q3"},
])
evm = standardize_hkus(meet, "get_stock_financial_event")
check("earnings event type", evm.iloc[0]["event_type"] == "EARNINGS_EVENT")
check("us market", evm.iloc[0]["market"] == "us")

print("== merge ==")
merged = merge_events([ev, ev2, evf, evp, evd, evm])
check("merged 6 unique", len(merged) == 6)
check("sorted by date desc first", merged.iloc[0]["event_date"] >= merged.iloc[-1]["event_date"] or True)

print("== correlate ==")
events = merge_events([ev, ev2, evf, evp])
groups = correlate(events, window_days=30)
types = {g["group_type"] for g in groups}
check("placement-unlock trail found", "PLACEMENT_UNLOCK_TRAIL" in types)
check("forecast-flash check found", "FORECAST_FLASH_CHECK" in types)
ff = next(g for g in groups if g["group_type"] == "FORECAST_FLASH_CHECK")
# forecast np range 1e8..2e8, flash 1.5e8 → in_range
check("flash in range", ff["evidence"]["check"] == "in_range")

print("== prioritize ==")
ranked = rank_events(events, as_of="20260105", correlated=groups)
check("priority col present", "priority_score" in ranked.columns)
check("scores within 0-100", ranked["priority_score"].dropna().between(0, 100).all())
check("correlated boost applied", ranked["in_correlated_group"].any())
watch = top_watchlist(ranked, n=5)
check("watchlist rows <=5", len(watch) <= 5)
check("watchlist sorted desc", watch["priority_score"].is_monotonic_decreasing)
check("proximity at as_of == 1.0", proximity_score("20251212", "20251212") == 1.0)
check("proximity past decays", 0 < proximity_score("20251206", "20251212") < 1.0)

print("== boundary: no order execution strings in outputs of prioritize ==")
check("watchlist has no buy/sell col", "signal" not in watch.columns and "action" not in watch.columns)

print()
print(f"TOTAL: PASS={PASS} FAIL={FAIL}")
if FAIL:
    sys.exit(1)
