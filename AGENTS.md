---
name: agent-cross-market-event-radar
description: "Aggregate cross-market corporate events (A-share placements and unlock expiries, earnings forecasts vs flash results, HK/US dividends, earnings, meetings, IR events) from Pandadata into a standardized daily event radar with correlation, priority ranking, dashboards, and risk alerts for research use without order execution."
metadata:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: quantskills/agent-cross-market-event-radar
  repository_url: https://github.com/quantskills/agent-cross-market-event-radar
  project_type: agent
  collection: pandadata-research-monitor-agents
  license: GPL-3.0-only
  category: monitor-agent
  tags: [cross-market, corporate-events, event-radar, a-share, hk-us, pandadata]
  platforms: [claude-code, codex, cursor, hermes, openclaw]
  language: zh-en
  status: draft
  validation_level: unreviewed
  maintainer_type: community
  creator: fuzijun
  maintainer: fuzijun
  publication_maintainer: abgyjaguo
  requires: [skill-pandadata-api]
  pandadata_methods: [get_stock_private_placement, get_restricted_list, get_fina_forecast, get_fina_performance, get_stock_dividend_event, get_stock_market_event, get_stock_meeting_event, get_stock_financial_event, get_stock_ir_event, get_stock_daily]
  summary_zh: "跨市场公司事件雷达：统一汇总 A 股定增解禁、业绩披露与港美股分红、财报、会议、IR 事件，输出每日事件看板、风险提示与研究候选清单。"
  summary_en: "Cross-market corporate event radar: aggregates A-share placement/unlock and earnings events with HK/US dividend, earnings, meeting, and IR events into a standardized daily dashboard."
quantSkills:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: quantskills/agent-cross-market-event-radar
  repository_url: https://github.com/quantskills/agent-cross-market-event-radar
  project_type: agent
  collection: pandadata-research-monitor-agents
  license: GPL-3.0-only
  category: monitor-agent
  tags: [cross-market, corporate-events, event-radar, a-share, hk-us, pandadata]
  platforms: [claude-code, codex, cursor, hermes, openclaw]
  language: zh-en
  status: draft
  validation_level: unreviewed
  maintainer_type: community
  creator: fuzijun
  maintainer: fuzijun
  publication_maintainer: abgyjaguo
  requires: [skill-pandadata-api]
  pandadata_methods: [get_stock_private_placement, get_restricted_list, get_fina_forecast, get_fina_performance, get_stock_dividend_event, get_stock_market_event, get_stock_meeting_event, get_stock_financial_event, get_stock_ir_event, get_stock_daily]
  summary_zh: "跨市场公司事件雷达：统一汇总 A 股定增解禁、业绩披露与港美股分红、财报、会议、IR 事件，输出每日事件看板、风险提示与研究候选清单。"
  summary_en: "Cross-market corporate event radar: aggregates A-share placement/unlock and earnings events with HK/US dividend, earnings, meeting, and IR events into a standardized daily dashboard."
---

# Cross-Market Event Radar（跨市场公司事件雷达）

Use this Agent when a user needs a Pandadata-backed, cross-market corporate event answer for:

> 今天和未来一段时间，A 股与港美股有哪些值得关注的公司事件？哪些事件互相印证或互相矛盾？哪些应该优先研究？

The Agent aggregates, standardizes, correlates, and ranks corporate events. It produces research and monitoring materials only. It does not place orders and does not promise returns.

## Operating Boundary

- Read Pandadata-sourced or user-provided data only.
- Mark missing data as incomplete (`data_completeness`) instead of filling gaps with assumptions.
- Produce reviewable artifacts with evidence.
- Output research and monitoring results only; never generate unconditional buy/sell commands and never connect to broker execution.

## Core Workflow

1. **数据接入** — pull raw data from ten Pandadata methods (A-share placements, restricted-share unlocks, earnings forecasts, earnings flash results, and five HK/US event types plus daily quotes).
2. **事件标准化** — map every source row into one unified event schema: `event_type / event_date / symbol / market / title / detail / data_completeness`.
3. **事件关联** — group related events inside the same company and time window (placement → unlock trail, forecast → flash direction check, dividend → earnings overlap).
4. **优先级排序** — score each event by proximity × historical impact × data completeness.
5. **统一调度与产物** — emit the daily event dashboard, risk alerts, and a research watchlist.

## Output Contract

Produce under `outputs/live/`:

- `event_dashboard.json` — daily event dashboard (per-day event counts by type and market).
- `event_radar.csv` — the standardized event table.
- `correlated_groups.json` — correlated event groups with relationship labels.
- `priority_watchlist.csv` — Top-N ranked research candidates.
- `risk_alerts.md` — human-readable risk alerts (unlock pressure, forecast/flash mismatch, event clusters).
- `run_summary.json` — reproducible run metadata (windows, row counts, method list).

## Pandadata Methods

- A 股定增：`get_stock_private_placement`
- A 股限售解禁：`get_restricted_list`
- 业绩预告：`get_fina_forecast`
- 业绩快报：`get_fina_performance`
- 港美股分红：`get_stock_dividend_event`
- 港美股市场活动：`get_stock_market_event`
- 港美股股东大会：`get_stock_meeting_event`
- 港美股财务披露：`get_stock_financial_event`
- 港美股 IR 活动：`get_stock_ir_event`
- A 股日线行情：`get_stock_daily`

## Python Utility Script

Live regeneration:

```powershell
py -3.10 -m pip install -r requirements.txt
Copy-Item .env.example .env   # fill in your own credentials
py -3.10 scripts/run_pandadata_live.py
py -3.10 scripts/validate_outputs.py
py -3.10 tests/test_radar.py
```

`run_pandadata_live.py` reads `PANDADATA_USERNAME`, `PANDADATA_PASSWORD`, and optional `PANDADATA_BASE_URL` from the environment or a local `.env` file, then rebuilds `outputs/live/`.

## References

- `references/methodology.md`: standardization, correlation, and ranking logic.
- `references/data-and-outputs.md`: data sources and public output files.
- `references/agent-boundary.md`: what the Agent does and does not do.
