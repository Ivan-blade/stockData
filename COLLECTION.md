# 数据采集系统

## 架构概览

```
┌─────────────────────────────────────────────────┐
│  APScheduler（内置，随 FastAPI 启动/停止）         │
│  定时触发 → _run_task() → collector.py 模式      │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│  collector.py                                    │
│  ┌──────────────────────────────────────────┐   │
│  │ get_hk_stock_codes()  → 港股过滤        │   │
│  │ get_us_stock_codes()  → 美股清单        │   │
│  │ refresh_stock_list()  → stock_list 更新 │   │
│  │ collect_snapshots()   → daily_snapshot  │   │
│  │ collect_hk_finance()  → 港股年度财务    │   │
│  │ collect_hk_quarterly()→ 港股季度利润表  │   │
│  │ collect_a_finance()   → A股全量财务     │   │
│  │ collect_us_finance()  → 美股财务        │   │
│  │ collect_us_snapshots() → 美股快照       │   │
│  │ collect_sectors()     → sector_daily    │   │
│  └──────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│  数据源（AKShare + 新浪财经）                     │
│  stock_zh_a_spot_em()           → A股快照       │
│  stock_financial_abstract()     → A股财务摘要    │
│  stock_hk_spot_em()             → 港股行情       │
│  stock_financial_hk_analysis_indicator_em() → 年报│
│  stock_financial_hk_report_em() → 季度利润表     │
│  stock_financial_us_analysis_indicator_em() → 美股│
│  stock_financial_us_report_em() → 美股三张报表   │
│  stock_us_spot()  / get_us_stock_name() → 美股   │
│  stock_us_daily()               → 美股K线        │
│  stock_board_industry_name_em() → 板块数据       │
└──────────────────────────────────────────────────┘
```

## CLI 命令

所有命令从 `backend/` 目录执行：

```bash
cd /path/to/stockData/backend
PYTHONPATH=. python3 collector.py <mode>
```

| 模式 | 说明 | 频率 | 预计耗时 |
|------|------|------|---------|
| `--list` | 全量股票清单 | 一次性 | ~68s |
| `--refresh-list` | 刷新清单（upsert） | **每日** 05:30 | ~2min |
| `--snapshot` | A+H 行情快照 | **每日** 17:00 | A~65s / HK~110s |
| `--us-snapshot` | 美股快照 | **每日** 07:00 | ~30s |
| `--a` | A股财报（自选） | 工作日 15:30 | ~15s |
| `--hk` | 港股财报（自选） | 工作日 16:30 | ~15s |
| `--sector` | 板块日数据 | 工作日 16:00 | ~11s |
| `--hk-finance` | 港股全量财务 | **每月1日** 04:00 | ~6min |
| `--hk-quarterly` | 港股季度利润表 | **每月2日** 04:00 | ~30min |
| `--a-finance` | A股全量财务 | **每月3日** 05:00 | ~68min |
| `--us-finance` | 美股全量财务 | **每月4日** 06:00 | ~5min |

## 定时调度（内置 APScheduler）

随 FastAPI 启动自动注册，关闭自动停止。查看状态：

```bash
GET /api/scheduler/status
# → { running: true, jobs: [{ id, next_run, trigger }...] }
```

| 任务 ID | 时间 | 说明 | 数据源 |
|---------|------|------|--------|
| `stockdata_snapshot` | **17:00** 每天 | A+H 估值快照（收盘/PE/PB/市值） | 东方财富 |
| `stockdata_refresh_list` | **05:30** 每天 | A+H+US 股票清单刷新（upsert） | 东方财富+新浪 |
| `stockdata_us_snapshot` | **07:00** 每天 | 美股快照（收盘/PE/PB/市值） | 新浪财经 |
| `stockdata_ashare` | **15:30** 工作日 | A股基本面（自选） | 东方财富 |
| `stockdata_sectors` | **16:00** 工作日 | 行业+概念板块日数据 | 东方财富 |
| `stockdata_hk` | **16:30** 工作日 | 港股基本面（自选） | 东方财富 |
| `stockdata_hk_finance_monthly` | 每月1日 **04:00** | 港股全量年度财务指标 | 东方财富 |
| `stockdata_hk_quarterly` | 每月2日 **04:00** | 港股季度利润表 | 东方财富 |
| `stockdata_a_finance` | 每月3日 **05:00** | A股全量财务摘要 | 东方财富 |
| `stockdata_us_finance` | 每月4日 **06:00** | 美股全量财务指标 | 东方财富 |

## 股票清单过滤规则

### 港股
港股 `stock_hk_spot_em()` 返回 4,600+ 只品种（含 ETF、债券、窝轮等）。`get_hk_stock_codes()` 按顺序过滤：

1. **停牌过滤**：最新价 <= 0 → 跳过
2. **债券前缀过滤**：`05xx`、`40xx` 前缀 → 100% 债券，跳过
3. **已知无数据代码**：`HK_NO_DATA_CODES` set → API 确认无财务数据
4. **衍生品关键词**：备兑、做多、做空、ETF、REIT 等 → 跳过
5. **智能名称过滤** `_is_likely_stock()`：纯 ASCII 短名、债券到期标注模式 → 跳过

最终返回 ~2,950 只真实港股。

### 美股
美股 `get_us_stock_codes()` 调用 `stock_us_spot()`（新浪财经），符号过滤 `^[A-Z]{1,5}$`。

### 刷新策略
`refresh_stock_list()` 使用 **INSERT...ON DUPLICATE KEY UPDATE**，**不删除**任何已有数据。即使网络失败也不影响现有清单。

## API 接口

### 全量采集

```bash
POST /api/collect              # 全量：公司建档 + 财务数据
POST /api/collect/snapshot     # 快照：A股全量 + 港股行情
POST /api/collect/sector       # 板块：行业 + 概念
```

### 单只采集

```bash
POST /api/collect/{code}       # 单只：识别 A/HK/US → 财务数据
```

**单只采集逻辑：**
1. 查 `StockList` 表 → 获取 `exchange`
2. 调用对应交易所的财务采集
3. 若为港股则额外采集季度利润表

## 数据量参考

| 表 | 行数 | 说明 |
|----|------|------|
| `stock_list` | ~8,500 | A 5,527 + HK 2,950 + US ~5k-8k |
| `financial_summary` | ~2,400万 | A+H 全量财务指标 |
| `daily_snapshot` | ~14,000 | A+H 每日快照 |
| `sector_daily` | ~1,000 | 行业+概念板块 |

## 数据源说明

所有数据通过 [AKShare](https://github.com/akfamily/akshare) 从公开金融网站获取，**个人研究用途**。

| 数据 | AKShare 函数 | 数据源 |
|------|-------------|--------|
| A股全量行情 | `stock_zh_a_spot_em()` | 东方财富 |
| A股代码 | `stock_info_a_code_name()` | 东方财富 |
| A股财务摘要 | `stock_financial_abstract()` | 东方财富 |
| 港股行情 | `stock_hk_spot_em()` | 东方财富 |
| 港股年度财务 | `stock_financial_hk_analysis_indicator_em()` | 东方财富 |
| 港股季度利润表 | `stock_financial_hk_report_em()` | 东方财富 |
| 美股行情 | `stock_us_spot()` | 新浪财经 |
| 美股代码 | `get_us_stock_name()` | 新浪财经 |
| 美股K线 | `stock_us_daily()` | 新浪财经 |
| 美股财务指标 | `stock_financial_us_analysis_indicator_em()` | 东方财富 |
| 美股三张报表 | `stock_financial_us_report_em()` | 东方财富 |
| 板块数据 | `stock_board_industry_name_em()` | 东方财富 |
| 大盘指数 | `stock_zh_index_spot_em()` | 东方财富 |

## 注意事项

1. **东财 CDN 夜间可能不通**：`push2.eastmoney.com` 深夜（~22:00-08:00）可能因 Azure CDN 路由不可达，白天正常
2. **美股 `get_us_stock_name()` 耗时 ~10min**：新浪分页 API（884页+JS解密），`@lru_cache()` 缓存后同进程秒出
3. **`refresh_stock_list()` 不删数据**：使用 upsert 模式，即使网络失败也不影响已有数据
4. **港股无需全量**：~2,000 只非股票品种（债券/ETF/衍生品）已被过滤，不占用采集资源
