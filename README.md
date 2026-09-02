# Cross-Market Event Radar（跨市场公司事件雷达 Agent）

**简体中文** | [English](README.en.md)

以 PandaData 为统一数据底座，自动汇总 **A 股定增解禁、业绩披露**与**港美股分红、财报、会议、IR** 等公司事件；按事件类型、临近程度、历史影响和数据完整性生成**每日事件看板、风险提示与研究候选清单**。

> 申报主体：甫子君（fuzijun）· QUANTSKILLS 量枢院自主选题
> Agent 输出研究与监控结果，不直接下单，不承诺收益。

原作者与功能维护者：fuzijun；QUANTSKILLS 发布维护：abgyjaguo。本项目为尚未经维护者评审的社区草案，不代表官方认证或推荐。

## 核心能力

| 层 | 能力 |
| --- | --- |
| 数据接入 | 10 个 PandaData 额定接口统一封装，凭据仅从环境变量读取 |
| 事件标准化 | A 股/港美股 10+ 类事件 → 统一 schema（含 data_completeness） |
| 事件关联 | 定增→解禁链、预告→快报一致性、分红→财报重叠、事件聚集 |
| 优先级排序 | 临近度 40% × 历史影响 35% × 数据完整性 25% + 关联加分 |
| 统一调度 | 一次运行产出看板 / 风险提示 / 候选清单 / 运行日志 |

## 快速开始

```powershell
py -3.10 -m pip install -r requirements.txt
Copy-Item .env.example .env    # 填入你自己的 PandaData 凭据
py -3.10 scripts/run_pandadata_live.py
py -3.10 scripts/validate_outputs.py
py -3.10 tests/test_radar.py   # 离线单元测试（无需网络）
```

## 产物（outputs/live/）

| 文件 | 说明 |
| --- | --- |
| `event_dashboard.json` | 每日事件看板（日期×市场、类型×市场计数） |
| `event_radar.csv` | 标准化事件总表（含优先级分） |
| `correlated_groups.json` | 关联事件组及证据 |
| `priority_watchlist.csv` | Top-N 研究候选清单 |
| `risk_alerts.md` | 人读风险提示 |
| `run_summary.json` | 运行元数据 + 全部拉取日志（可复现） |
| `placement_discounts.csv` | 定增发行折扣明细（Alpha 研究信号） |

## 目录结构

```
agent-cross-market-event-radar/
├── AGENTS.md                  # Agent 契约（边界/工作流/输出）
├── agents/openai.yaml         # OpenAI-style agent 配置
├── examples/prompt.md         # 示例提示词
├── references/                # 方法论 / 数据与产物 / 边界
├── scripts/
│   ├── data_access.py         # 数据接入层
│   ├── standardize.py         # 事件标准化层
│   ├── correlate.py           # 事件关联层
│   ├── prioritize.py          # 优先级排序层
│   ├── run_pandadata_live.py  # 调度与产物层（主入口）
│   └── validate_outputs.py    # 产物校验
├── tests/test_radar.py        # 离线单元测试
└── outputs/live/              # 本地生成的真实运行产物（不提交 Git）
```

## 边界

- 只使用 PandaData 或用户授权数据；缺失数据标记不完整，不做假设填充。
- 不生成无条件买卖指令，不接入下单通道，不承诺收益。
- 详见 `references/agent-boundary.md`。

## License

GPL-3.0
