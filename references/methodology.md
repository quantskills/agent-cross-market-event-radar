# Methodology — Cross-Market Event Radar

## 1. 数据接入

Agent 以 PandaData 为统一数据底座，一次运行拉取 10 个额定接口：

| 模块 | 接口 | 说明 |
| --- | --- | --- |
| A 股定增（Alpha 研究信号） | `get_stock_private_placement` | 按公告日区间拉全市场定增发行明细 |
| A 股限售解禁 | `get_restricted_list` | 对窗口内定增股票逐只查询未来 180 天解禁明细 |
| 业绩预告 | `get_fina_forecast` | 按信息发布日逐日回看 14 天 |
| 业绩快报 | `get_fina_performance` | 全量拉取后本地按日期过滤 |
| 港美股分红 | `get_stock_dividend_event` | 按日期区间 |
| 港美股市场活动 | `get_stock_market_event` | 按日期区间 |
| 港美股股东大会 | `get_stock_meeting_event` | 按日期区间 |
| 港美股财务披露 | `get_stock_financial_event` | 按日期区间 |
| 港美股 IR 活动 | `get_stock_ir_event` | 按日期区间 |
| A 股日线行情 | `get_stock_daily` | 用于定增发行折扣计算（公告日收盘价） |

凭据只从环境变量 `PANDADATA_USERNAME` / `PANDADATA_PASSWORD` / `PANDADATA_BASE_URL` 读取，不写入代码。每一次拉取都会记录到 `run_summary.json` 的 `pull_log`（方法、参数、行数、耗时），保证可复现。

## 2. 事件标准化

所有事件统一映射到单一 schema：

```
event_id, event_type, event_date, symbol, market, title, detail,
data_completeness, source_method, extra
```

- `market` ∈ {`a-share`, `hk`, `us`}（按代码后缀判断）。
- `event_type` ∈ {`PLACEMENT`, `UNLOCK`, `EARNINGS_FORECAST`, `EARNINGS_FLASH`, `DIVIDEND`, `MARKET_EVENT`, `MEETING`, `EARNINGS_EVENT`, `IR_EVENT`}。
- `data_completeness` ∈ [0,1]，为关键字段缺失比例的补集；缺失数据标记为不完整，不做假设填充。
- 业绩预告方向映射：预增/略增/扭亏/减亏→`up`，预减/略减/首亏/续亏/增亏→`down`，续盈→`flat`，其他→`unknown`。

## 3. 事件关联（30 天窗口，除非另注）

| 关联类型 | 触发条件 |
| --- | --- |
| `PLACEMENT_UNLOCK_TRAIL` | 定增公告后，同公司解禁日落在上市日（或公告日）之后 30 天内 |
| `FORECAST_FLASH_CHECK` | 同公司预告与快报 30 天内；校验快报净利润是否落入预告区间 / 方向是否一致（`in_range` / `mismatch` / `direction_match` / `direction_mismatch` / `insufficient_data`） |
| `DIVIDEND_EARNINGS_OVERLAP` | 分红除净与财报事件 7 天内重叠 |
| `EVENT_CLUSTER` | 同公司 30 天内事件数 ≥ 3 |

## 4. 优先级排序

```
priority_score (0-100) = 40% × 临近度 + 35% × 历史影响 + 25% × 数据完整性 + 关联加分
```

- 临近度：以运行日为 1.0，未来 30 天线性衰减到 0；已过期事件按 7 天更快衰减。
- 历史影响：事件类型先验权重（预告 0.85、快报/财报事件 0.80、定增 0.75、解禁 0.70、分红 0.60 等）。这是研究观点的排序参考，不是收益承诺。
- 数据完整性：标准化层输出。
- 关联加分：处于关联组内的事件加 6-10 分（同组内取最高，不叠加）。

## 5. 产物

| 文件 | 内容 |
| --- | --- |
| `event_dashboard.json` | 每日事件看板（按日期×市场、类型×市场计数） |
| `event_radar.csv` | 标准化事件总表（含优先级分） |
| `correlated_groups.json` | 关联事件组及证据 |
| `priority_watchlist.csv` | Top-N 研究候选清单 |
| `risk_alerts.md` | 人读风险提示（解禁压力/业绩变脸/事件聚集/分红财报重叠） |
| `run_summary.json` | 运行元数据与 pull_log，保证可复现 |

## 6. 边界

Agent 输出研究与监控结果；不生成买卖指令、不接入下单通道、不承诺收益。数据缺失时输出 `insufficient_data` 或以完整性分数体现，不用假设补齐。