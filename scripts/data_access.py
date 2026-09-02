# -*- coding: utf-8 -*-
"""Data access layer for the Cross-Market Event Radar.

Every Pandadata call goes through this module so credentials stay in
environment variables (never in code) and every raw pull is recorded for
reproducibility.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://pandadata.pandaaiquant.com"

PANDADATA_METHODS = [
    "get_stock_private_placement",
    "get_restricted_list",
    "get_fina_forecast",
    "get_fina_performance",
    "get_stock_dividend_event",
    "get_stock_market_event",
    "get_stock_meeting_event",
    "get_stock_financial_event",
    "get_stock_ir_event",
    "get_stock_daily",
]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def init_panda(base_url: Optional[str] = None) -> Any:
    """Initialize panda_data with credentials from the environment or .env."""
    _load_env_file(ROOT / ".env")
    username = os.getenv("PANDADATA_USERNAME") or os.getenv("PANDA_DATA_USERNAME")
    password = os.getenv("PANDADATA_PASSWORD") or os.getenv("PANDA_DATA_PASSWORD")
    base = base_url or os.getenv("PANDADATA_BASE_URL") or os.getenv("PANDA_DATA_BASE_URL") or DEFAULT_BASE_URL
    if not username or not password:
        raise RuntimeError(
            "Missing Pandadata credentials. Set PANDADATA_USERNAME and "
            "PANDADATA_PASSWORD in the environment or in a local .env file."
        )
    try:
        import panda_data
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Missing package panda-data. Run: pip install -r requirements.txt") from exc

    panda_data.init_token(username=username, password=password, base_url=base)
    return panda_data


class DataAccess:
    """Thin wrapper that records every pull and normalizes empty results."""

    def __init__(self, panda: Any = None) -> None:
        self.panda = panda if panda is not None else init_panda()
        self.pull_log: list[dict[str, Any]] = []

    def _record(self, method: str, params: dict[str, Any], rows: int, seconds: float) -> None:
        self.pull_log.append(
            {"method": method, "params": {k: v for k, v in params.items() if v not in (None, "", [])},
             "rows": rows, "seconds": round(seconds, 2)}
        )

    def _call(self, method: str, **params: Any):
        started = time.time()
        try:
            frame = getattr(self.panda, method)(**params)
        except Exception as exc:  # service errors become empty frames + log entry
            self._record(method, params, -1, time.time() - started)
            self.pull_log[-1]["error"] = str(exc)[:200]
            import pandas as pd
            return pd.DataFrame()
        import pandas as pd
        if frame is None:
            frame = pd.DataFrame()
        self._record(method, params, len(frame), time.time() - started)
        return frame

    # ---------- A-share placement / unlock (Alpha module) ----------

    def fetch_placements(self, start_date: str, end_date: str):
        """全市场定增发行明细（按公告日区间）。"""
        return self._call("get_stock_private_placement", symbol=[], start_date=start_date, end_date=end_date)

    def fetch_restricted(self, symbol: str, start_date: str, end_date: str):
        """单只股票限售解禁明细（接口要求指定 symbol）。"""
        return self._call("get_restricted_list", symbol=symbol, start_date=start_date, end_date=end_date)

    def fetch_daily(self, symbol: str, start_date: str, end_date: str):
        """单只股票日线行情（未复权）。"""
        return self._call("get_stock_daily", symbol=symbol, start_date=start_date, end_date=end_date)

    # ---------- Earnings forecast / flash (earnings-risk module) ----------

    def fetch_forecasts_by_date(self, info_date: str):
        """某一日全市场业绩预告（接口按 info_date 精确过滤）。"""
        return self._call("get_fina_forecast", symbol=[], info_date=info_date, end_quarter="")

    def fetch_performances_all(self):
        """全量业绩快报（数据量小，本地过滤）。"""
        return self._call("get_fina_performance", symbol=[], info_date="", end_quarter="")

    # ---------- HK/US corporate events (cross-market calendar module) ----------

    def fetch_hkus_event(self, method: str, start_date: str, end_date: str):
        """港美股事件（dividend/market/meeting/financial/ir），按日期区间。"""
        valid = {
            "get_stock_dividend_event",
            "get_stock_market_event",
            "get_stock_meeting_event",
            "get_stock_financial_event",
            "get_stock_ir_event",
        }
        if method not in valid:
            raise ValueError(f"unknown HK/US event method: {method}")
        return self._call(method, symbol=[], start_date=start_date, end_date=end_date)
