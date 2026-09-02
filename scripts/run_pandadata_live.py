# -*- coding: utf-8 -*-
"""Cross-Market Event Radar — live run orchestrator.

Pulls real data from ten Pandadata methods, standardizes, correlates, ranks,
and writes the public outputs under outputs/live/:

- event_dashboard.json    daily event dashboard
- event_radar.csv         standardized event table
- correlated_groups.json  correlated event groups
- priority_watchlist.csv  Top-N ranked research candidates
- risk_alerts.md          human-readable risk alerts
- run_summary.json        reproducible run metadata

Research and monitoring only. No order execution, no return promises.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from data_access import DataAccess, PANDADATA_METHODS
from standardize import (
    merge_events,
    standardize_forecasts,
    standardize_hkus,
    standardize_performances,
    standardize_placements,
    standardize_restricted,
)
from correlate import correlate
from prioritize import rank_events, top_watchlist

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "live"

HKUS_METHODS = [
    "get_stock_dividend_event",
    "get_stock_market_event",
    "get_stock_meeting_event",
    "get_stock_financial_event",
    "get_stock_ir_event",
]

DEFAULT_A_SHARE_WINDOW_DAYS = 30
DEFAULT_HKUS_WINDOW_DAYS = 30
FORECAST_LOOKBACK_DAYS = 14
UNLOCK_HORIZON_DAYS = 180


def _fmt(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def run(start_date: str | None = None, end_date: str | None = None,
        watchlist_size: int = 20, restrict_sample: int = 40) -> dict:
    """Execute one full radar run. Returns the run summary dict."""
    as_of = end_date or _fmt(datetime.now())
    start = start_date or _fmt(datetime.now() - timedelta(days=DEFAULT_A_SHARE_WINDOW_DAYS))
    hkus_start = _fmt(datetime.strptime(as_of, "%Y%m%d") - timedelta(days=DEFAULT_HKUS_WINDOW_DAYS))

    da = DataAccess()
    frames = []

    # ---------- Module 1: A-share placement / unlock (Alpha research signals) ----------
    placements_raw = da.fetch_placements(start_date=start, end_date=as_of)
    frames.append(standardize_placements(placements_raw))

    unlock_frames = []
    if not placements_raw.empty:
        symbols = placements_raw["symbol"].dropna().unique().tolist()[:restrict_sample]
        # 解禁通常发生在上市后 6-24 个月；雷达关注未来 UNLOCK_HORIZON_DAYS 内的解禁
        unlock_from = _fmt(datetime.strptime(as_of, "%Y%m%d") + timedelta(days=1))
        unlock_to = _fmt(datetime.strptime(as_of, "%Y%m%d") + timedelta(days=UNLOCK_HORIZON_DAYS))
        for sym in symbols:
            unlock_frames.append(da.fetch_restricted(sym, start_date=unlock_from, end_date=unlock_to))
    unlock_non_empty = [f for f in unlock_frames if not f.empty]
    unlock_raw = pd.concat(unlock_non_empty, ignore_index=True) if unlock_non_empty else pd.DataFrame()
    unlock_events = standardize_restricted(unlock_raw)

    # discount via daily quotes when placement has issue_price + listed info
    discount_rows = []
    if not placements_raw.empty:
        for _, p in placements_raw.iterrows():
            sym = p.get("symbol")
            price = p.get("issue_price")
            ann = p.get("announcement_date")
            if not (sym and price and ann):
                continue
            daily = da.fetch_daily(sym, ann, ann)
            if daily.empty:
                continue
            close = float(daily.iloc[0]["close"]) if pd.notna(daily.iloc[0]["close"]) else None
            if close:
                discount_rows.append({
                    "symbol": sym, "announcement_date": ann,
                    "issue_price": float(price), "close": close,
                    "discount": round(1.0 - float(price) / close, 4),
                })
    discount_df = pd.DataFrame(discount_rows)

    placement_events = frames[-1]

    # ---------- Module 2: earnings forecast vs flash (earnings-risk module) ----------
    forecast_frames = []
    for offset in range(FORECAST_LOOKBACK_DAYS, -1, -1):
        d = _fmt(datetime.strptime(as_of, "%Y%m%d") - timedelta(days=offset))
        forecast_frames.append(da.fetch_forecasts_by_date(d))
    forecast_non_empty = [f for f in forecast_frames if not f.empty]
    forecasts_raw = pd.concat(forecast_non_empty, ignore_index=True) if forecast_non_empty else pd.DataFrame()
    frames.append(standardize_forecasts(forecasts_raw))

    performances_raw = da.fetch_performances_all()
    if not performances_raw.empty:
        performances_raw = performances_raw[
            (performances_raw["info_date"] >= start) & (performances_raw["info_date"] <= as_of)
        ]
    frames.append(standardize_performances(performances_raw))

    # ---------- Module 3: HK/US corporate events (cross-market calendar) ----------
    hkus_events = []
    for method in HKUS_METHODS:
        raw = da.fetch_hkus_event(method, start_date=hkus_start, end_date=as_of)
        hkus_events.append(standardize_hkus(raw, method))
    frames.extend(hkus_events)
    frames.append(unlock_events)

    events = merge_events(frames)

    # ---------- Correlation & ranking ----------
    correlated = correlate(events, window_days=30)
    ranked = rank_events(events, as_of=as_of, correlated=correlated)
    watchlist = top_watchlist(ranked, n=watchlist_size)

    # ---------- Outputs ----------
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    radar_path = OUT_DIR / "event_radar.csv"
    export_cols = [c for c in ["event_id", "event_type", "event_date", "symbol", "market", "title",
                               "data_completeness", "priority_score", "in_correlated_group",
                               "proximity", "impact", "source_method", "detail"] if c in ranked.columns]
    ranked[export_cols].to_csv(radar_path, index=False, encoding="utf-8-sig")

    groups_path = OUT_DIR / "correlated_groups.json"
    groups_path.write_text(json.dumps(correlated, ensure_ascii=False, indent=2), encoding="utf-8")

    watch_path = OUT_DIR / "priority_watchlist.csv"
    watchlist.to_csv(watch_path, index=False, encoding="utf-8-sig")

    # dashboard: per-day counts by type/market within window
    dashboard = {}
    if not events.empty:
        window = events[(events["event_date"] >= hkus_start) & (events["event_date"] <= as_of)]
        by_day = window.groupby(["event_date", "market"]).size().unstack(fill_value=0)
        by_type = window.groupby(["event_type", "market"]).size().unstack(fill_value=0)
        dashboard = {
            "as_of": as_of,
            "window_days": DEFAULT_HKUS_WINDOW_DAYS,
            "total_events": int(len(window)),
            "daily_counts": {d: {m: int(v) for m, v in row.items()} for d, row in by_day.iterrows()},
            "type_market_matrix": {t: {m: int(v) for m, v in row.items()} for t, row in by_type.iterrows()},
        }
    else:
        dashboard = {"as_of": as_of, "total_events": 0}
    (OUT_DIR / "event_dashboard.json").write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    # risk alerts (plain language, research-only)
    alerts = []
    unlock_after = unlock_events[unlock_events["event_date"] >= as_of] if not unlock_events.empty else pd.DataFrame()
    if not unlock_after.empty:
        top_unlock = unlock_after.sort_values("event_date").head(5)
        for _, u in top_unlock.iterrows():
            det = json.loads(u["detail"])
            alerts.append(
                f"[解禁压力] {u['symbol']} 将于 {u['event_date']} 解禁，"
                f"合计 {det.get('relieve_shares_total', 0):,.0f} 股 / {det.get('holders', '?')} 名股东（{det.get('relieve_reason', '')}）。"
            )
    mismatches = [g for g in correlated if g["group_type"] == "FORECAST_FLASH_CHECK"
                  and g["evidence"].get("check") in ("mismatch", "direction_mismatch")]
    for g in mismatches[:5]:
        alerts.append(
            f"[业绩变脸] {g['symbol']} 预告与快报方向不一致：{g['relation']}。"
        )
    clusters = [g for g in correlated if g["group_type"] == "EVENT_CLUSTER"]
    for g in clusters[:5]:
        alerts.append(f"[事件聚集] {g['symbol']}：{g['relation']}。")
    overlaps = [g for g in correlated if g["group_type"] == "DIVIDEND_EARNINGS_OVERLAP"]
    for g in overlaps[:5]:
        alerts.append(f"[分红+财报重叠] {g['symbol']}：{g['relation']}。")
    if not alerts:
        alerts.append("窗口内未发现解禁压力、业绩变脸、事件聚集或分红财报重叠等需关注信号。")

    alerts_path = OUT_DIR / "risk_alerts.md"
    alerts_lines = [
        "# 风险提示（研究参考，不构成投资建议）",
        "",
        f"- 数据截至：{as_of}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    alerts_lines += [f"- {a}" for a in alerts]
    alerts_lines += [
        "",
        "> 本 Agent 仅输出研究与监控结果，不直接下单，不承诺收益。",
    ]
    alerts_path.write_text("\n".join(alerts_lines), encoding="utf-8")

    # run summary for reproducibility
    summary = {
        "agent": "agent-cross-market-event-radar",
        "as_of": as_of,
        "a_share_window": [start, as_of],
        "hkus_window": [hkus_start, as_of],
        "forecast_lookback_days": FORECAST_LOOKBACK_DAYS,
        "restrict_sample_limit": restrict_sample,
        "events_total": int(len(events)),
        "events_by_type": {k: int(v) for k, v in events["event_type"].value_counts().items()} if not events.empty else {},
        "events_by_market": {k: int(v) for k, v in events["market"].value_counts().items()} if not events.empty else {},
        "correlated_groups": len(correlated),
        "watchlist_rows": int(len(watchlist)),
        "discount_rows": int(len(discount_df)),
        "pandadata_methods": PANDADATA_METHODS,
        "pull_log": da.pull_log,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "boundary": "research and monitoring only; no order execution; no return promises",
    }
    if not discount_df.empty:
        discount_df.to_csv(OUT_DIR / "placement_discounts.csv", index=False, encoding="utf-8-sig")
    (OUT_DIR / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-Market Event Radar live run")
    parser.add_argument("--start-date", default=None, help="A-share window start YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="as-of date YYYYMMDD")
    parser.add_argument("--watchlist-size", type=int, default=20)
    parser.add_argument("--restrict-sample", type=int, default=40,
                        help="max symbols to query restricted-list details for")
    args = parser.parse_args()
    summary = run(args.start_date, args.end_date, args.watchlist_size, args.restrict_sample)
    print(json.dumps({k: v for k, v in summary.items() if k != "pull_log"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
