# Example Prompts — Cross-Market Event Radar

## 中文

- 「帮我看看最近 A 股和港美股有哪些值得关注的公司事件，按优先级排一下。」
- 「扫描近一个月的定增公告，哪些股票未来半年内有限售解禁压力？」
- 「最近有没有业绩预告和快报方向不一致的公司（业绩变脸风险）？」
- 「生成今天的事件看板，标注数据不完整的事件。」
- 「找出同时有分红除净和财报发布的港股公司。」

## English

- "Aggregate the latest A-share and HK/US corporate events and rank them by priority."
- "Scan recent private-placement announcements; which names face unlock pressure within six months?"
- "Any companies whose earnings flash contradicts their earlier forecast?"
- "Build today's event dashboard and flag incomplete-data events."
- "Find HK names with dividend ex-date overlapping an earnings event."

## 运行方式

```powershell
py -3.10 scripts/run_pandadata_live.py
```

产物输出在 `outputs/live/`，先看 `risk_alerts.md`（人读提示）与 `priority_watchlist.csv`（Top-N 候选），细节看 `event_radar.csv` 与 `correlated_groups.json`。