# -*- coding: utf-8 -*-
"""Event standardization layer.

Maps every source row into the unified event schema:

    event_id, event_type, event_date, symbol, market, title, detail,
    data_completeness, source_method, extra (json)

`market` is one of: a-share / hk / us.
`data_completeness` in [0, 1]: 1.0 = all key fields present.
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

EVENT_COLUMNS = [
    "event_id", "event_type", "event_date", "symbol", "market", "title",
    "detail", "data_completeness", "source_method", "extra",
]


def _mk_event_id(event_type: str, symbol: str, event_date: str, seq: int) -> str:
    return f"{event_type}|{symbol}|{event_date}|{seq:04d}"


def _completeness(*values: Any) -> float:
    """Fraction of the supplied key values that are present."""
    vals = [v for v in values]
    if not vals:
        return 0.0
    ok = sum(1 for v in vals if v is not None and (not isinstance(v, float) or not pd.isna(v)) and str(v) != "")
    return round(ok / len(vals), 2)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _safe_number(value: Any):
    try:
        f = float(value)
        if pd.isna(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def standardize_placements(df: pd.DataFrame) -> pd.DataFrame:
    """A 股定增发行明细 → PLACEMENT 事件。"""
    rows = []
    for i, r in df.iterrows():
        price = _safe_number(r.get("issue_price"))
        shares = _safe_number(r.get("issued_shares"))
        size = price * shares if price and shares else None
        rows.append({
            "event_id": _mk_event_id("PLACEMENT", _to_str(r.get("symbol")), _to_str(r.get("announcement_date")), i),
            "event_type": "PLACEMENT",
            "event_date": _to_str(r.get("announcement_date")),
            "symbol": _to_str(r.get("symbol")),
            "market": "a-share",
            "title": f"定增公告 {_to_str(r.get('symbol'))} {_to_str(r.get('issue_type'))}",
            "detail": json.dumps({
                "issue_type": _to_str(r.get("issue_type")),
                "issue_status": _to_str(r.get("issue_status")),
                "issue_price": price,
                "issued_shares": shares,
                "raise_size": size,
                "listed_date": _to_str(r.get("listed_date")),
                "approval_date": _to_str(r.get("approval_date")),
            }, ensure_ascii=False),
            "data_completeness": _completeness(r.get("symbol"), r.get("announcement_date"), price, shares),
            "source_method": "get_stock_private_placement",
            "extra": "{}",
        })
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def standardize_restricted(df: pd.DataFrame) -> pd.DataFrame:
    """A 股限售解禁明细 → UNLOCK 事件（按 symbol+relieve_date 聚合）。"""
    rows = []
    if df.empty:
        return pd.DataFrame(rows, columns=EVENT_COLUMNS)
    grouped = df.groupby(["symbol", "relieve_date"], sort=False)
    seq = 0
    for (symbol, relieve_date), g in grouped:
        total = g["relieve_shares"].sum() if "relieve_shares" in g else None
        holders = len(g)
        reasons = "、".join(sorted({_to_str(x) for x in g.get("relieve_reason", []) if _to_str(x)}))
        rows.append({
            "event_id": _mk_event_id("UNLOCK", _to_str(symbol), _to_str(relieve_date), seq),
            "event_type": "UNLOCK",
            "event_date": _to_str(relieve_date),
            "symbol": _to_str(symbol),
            "market": "a-share",
            "title": f"限售解禁 {_to_str(symbol)}",
            "detail": json.dumps({
                "relieve_shares_total": _safe_number(total),
                "holders": holders,
                "relieve_reason": reasons,
                "info_date": _to_str(g.iloc[0].get("date")),
            }, ensure_ascii=False),
            "data_completeness": _completeness(symbol, relieve_date, total),
            "source_method": "get_restricted_list",
            "extra": "{}",
        })
        seq += 1
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


FORECAST_DIRECTION = {
    "预增": "up", "略增": "up", "扭亏": "up", "续盈": "flat",
    "预减": "down", "略减": "down", "首亏": "down", "续亏": "down",
    "增亏": "down", "减亏": "up", "不确定": "unknown",
}


def standardize_forecasts(df: pd.DataFrame) -> pd.DataFrame:
    """业绩预告 → EARNINGS_FORECAST 事件（含方向）。"""
    rows = []
    for i, r in df.iterrows():
        ftype = _to_str(r.get("forecast_type"))
        direction = FORECAST_DIRECTION.get(ftype, "unknown")
        rows.append({
            "event_id": _mk_event_id("EARNINGS_FORECAST", _to_str(r.get("symbol")), _to_str(r.get("info_date")), i),
            "event_type": "EARNINGS_FORECAST",
            "event_date": _to_str(r.get("info_date")),
            "symbol": _to_str(r.get("symbol")),
            "market": "a-share",
            "title": f"业绩预告 {_to_str(r.get('symbol'))} {ftype}",
            "detail": json.dumps({
                "forecast_type": ftype,
                "direction": direction,
                "end_date": _to_str(r.get("end_date")),
                "np_floor": _safe_number(r.get("forecast_np_floor")),
                "np_ceiling": _safe_number(r.get("forecast_np_ceiling")),
                "growth_floor": _safe_number(r.get("forecast_growth_rate_floor")),
                "growth_ceiling": _safe_number(r.get("forecast_growth_rate_ceiling")),
            }, ensure_ascii=False),
            "data_completeness": _completeness(r.get("symbol"), r.get("info_date"), ftype),
            "source_method": "get_fina_forecast",
            "extra": "{}",
        })
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def standardize_performances(df: pd.DataFrame) -> pd.DataFrame:
    """业绩快报 → EARNINGS_FLASH 事件（含净利润与同比）。"""
    rows = []
    for i, r in df.iterrows():
        np_parent = _safe_number(r.get("net_profit_parent"))
        yoy = _safe_number(r.get("net_profit_parent_yoy"))
        rows.append({
            "event_id": _mk_event_id("EARNINGS_FLASH", _to_str(r.get("symbol")), _to_str(r.get("info_date")), i),
            "event_type": "EARNINGS_FLASH",
            "event_date": _to_str(r.get("info_date")),
            "symbol": _to_str(r.get("symbol")),
            "market": "a-share",
            "title": f"业绩快报 {_to_str(r.get('symbol'))}",
            "detail": json.dumps({
                "end_date": _to_str(r.get("end_date")),
                "net_profit_parent": np_parent,
                "net_profit_parent_yoy": yoy,
                "operating_revenue": _safe_number(r.get("operating_revenue")),
            }, ensure_ascii=False),
            "data_completeness": _completeness(r.get("symbol"), r.get("info_date"), np_parent),
            "source_method": "get_fina_performance",
            "extra": "{}",
        })
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def _hkus_market(symbol: str) -> str:
    return "hk" if symbol.upper().endswith(".HK") else "us"


HKUS_TYPE_MAP = {
    "get_stock_dividend_event": "DIVIDEND",
    "get_stock_market_event": "MARKET_EVENT",
    "get_stock_meeting_event": "MEETING",
    "get_stock_financial_event": "EARNINGS_EVENT",
    "get_stock_ir_event": "IR_EVENT",
}


def standardize_hkus(df: pd.DataFrame, source_method: str) -> pd.DataFrame:
    """港美股五类事件 → 统一事件。"""
    event_type = HKUS_TYPE_MAP[source_method]
    rows = []
    for i, r in df.iterrows():
        symbol = _to_str(r.get("symbol"))
        date = _to_str(r.get("publish_date")) or _to_str(r.get("info_date"))
        if source_method == "get_stock_dividend_event":
            detail = {
                "execute_date": _to_str(r.get("excute_date")),
                "number": _safe_number(r.get("number")),
                "currency": _to_str(r.get("currency")),
                "event_type_flag": _to_str(r.get("event_type_flag")),
            }
        else:
            detail = {
                "event_start": _to_str(r.get("start_date")),
                "event_end": _to_str(r.get("end_date")),
                "event_class": _to_str(r.get("event_type")),
                "fiscal_quarter": _to_str(r.get("fiscal_quarter")),
                "is_estimated": _safe_number(r.get("is_estimated")),
            }
        rows.append({
            "event_id": _mk_event_id(event_type, symbol, date, i),
            "event_type": event_type,
            "event_date": date,
            "symbol": symbol,
            "market": _hkus_market(symbol),
            "title": _to_str(r.get("event"))[:120],
            "detail": json.dumps(detail, ensure_ascii=False),
            "data_completeness": _completeness(symbol, date, r.get("event")),
            "source_method": source_method,
            "extra": "{}",
        })
    return pd.DataFrame(rows, columns=EVENT_COLUMNS)


def merge_events(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """合并全部事件并排序去重。"""
    merged = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame(columns=EVENT_COLUMNS)
    if merged.empty:
        return merged
    merged = merged.drop_duplicates(subset=["event_id"]).sort_values(
        ["event_date", "market", "event_type", "symbol"]
    ).reset_index(drop=True)
    return merged
