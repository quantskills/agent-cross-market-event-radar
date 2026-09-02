# Cross-Market Event Radar Agent

**English** | [简体中文](README.md)

Pandadata-backed agent that aggregates **A-share placements and unlock expiries, earnings forecasts vs flash results**, and **HK/US dividends, earnings, meetings, and IR events** into a standardized daily event radar with correlation, priority ranking, dashboards, risk alerts, and research watchlists.

> Applicant: fuzijun · QUANTSKILLS self-selected topic
> The agent outputs research and monitoring results only — no order execution, no return promises.

Original author and functional maintainer: fuzijun. QUANTSKILLS publication maintainer: abgyjaguo. This is an unreviewed community draft and does not claim official certification or endorsement.

## Capabilities

| Layer | What it does |
| --- | --- |
| Data access | 10 Pandadata methods behind one wrapper; credentials from environment only |
| Standardization | A-share + HK/US events into one unified schema with data_completeness |
| Correlation | placement→unlock trail, forecast↔flash consistency, dividend×earnings overlap, clusters |
| Prioritization | proximity 40% × historical impact 35% × completeness 25% + correlation boost |
| Orchestration | one run produces dashboard / alerts / watchlist / full pull log |

## Quick Start

```powershell
py -3.10 -m pip install -r requirements.txt
Copy-Item .env.example .env    # fill in your own Pandadata credentials
py -3.10 scripts/run_pandadata_live.py
py -3.10 scripts/validate_outputs.py
py -3.10 tests/test_radar.py   # offline unit tests (no network)
```

## Outputs (outputs/live/)

`event_dashboard.json`, `event_radar.csv`, `correlated_groups.json`, `priority_watchlist.csv`, `risk_alerts.md`, `run_summary.json`, `placement_discounts.csv`.

See [README.md](README.md) for the full table and directory layout.

## Boundary

- Pandadata or user-provided data only; missing data is flagged, never assumed.
- No unconditional buy/sell commands, no broker connectivity, no return promises.
- See `references/agent-boundary.md`.

## License

GPL-3.0
