# Data & Outputs

## 数据源（PandaData，统一数据底座）

| 接口 | 模块 | 关键字段 |
| --- | --- | --- |
| `get_stock_private_placement` | A 股定增 | symbol, announcement_date, issue_type, issue_status, listed_date, issued_shares, issue_price, approval_date |
| `get_restricted_list` | A 股解禁 | symbol, date, relieve_date, shareholder, shareholder_type, relieve_shares, actual_relieve_shares, relieve_reason |
| `get_fina_forecast` | 业绩预告 | symbol, info_date, end_date, forecast_type, forecast_np_floor/ceiling, forecast_growth_rate_floor/ceiling |
| `get_fina_performance` | 业绩快报 | symbol, info_date, end_date, net_profit_parent, net_profit_parent_yoy, operating_revenue |
| `get_stock_dividend_event` | 港美股分红 | symbol, publish_date, excute_date, event_type, number, currency, event |
| `get_stock_market_event` | 港美股市场活动 | symbol, info_date, start_date, end_date, event, event_type, fiscal_quarter |
| `get_stock_meeting_event` | 港美股股东大会 | 同上 |
| `get_stock_financial_event` | 港美股财务披露 | 同上 |
| `get_stock_ir_event` | 港美股 IR 活动 | 同上 |
| `get_stock_daily` | A 股日线 | symbol, date, close, pre_close, trade_status |

凭据通过环境变量注入：`PANDADATA_USERNAME`、`PANDADATA_PASSWORD`、可选 `PANDADATA_BASE_URL`（默认 `http://pandadata.pandaaiquant.com`）。参见 `.env.example`。

## 公开产物（outputs/live/）

| 文件 | 格式 | 用途 |
| --- | --- | --- |
| `event_dashboard.json` | JSON | 每日事件看板：窗口内按日期×市场、类型×市场的事件计数 |
| `event_radar.csv` | CSV (UTF-8-SIG) | 标准化事件总表：统一 schema + 优先级分 |
| `correlated_groups.json` | JSON | 关联事件组：定增-解禁链、预告-快报校验、分红-财报重叠、事件聚集 |
| `priority_watchlist.csv` | CSV (UTF-8-SIG) | Top-N 研究候选清单 |
| `risk_alerts.md` | Markdown | 人读风险提示（研究参考，不构成投资建议） |
| `run_summary.json` | JSON | 运行窗口、事件计数、10 个接口清单、pull_log（每次拉取的参数/行数/耗时） |
| `placement_discounts.csv` | CSV (UTF-8-SIG) | 定增发行折扣明细（issue_price vs 公告日收盘价，Alpha 研究信号） |

## 再生成

```powershell
py -3.10 -m pip install -r requirements.txt
Copy-Item .env.example .env    # 填入你自己的凭据
py -3.10 scripts/run_pandadata_live.py
py -3.10 scripts/validate_outputs.py
```

可选参数：`--start-date YYYYMMDD`、`--end-date YYYYMMDD`、`--watchlist-size N`、`--restrict-sample N`（解禁查询的定增股票数上限）。

每次运行都会完全重建 `outputs/live/`，`run_summary.json` 中的 `pull_log` 记录了全部数据拉取，保证结果可复现、可审计。