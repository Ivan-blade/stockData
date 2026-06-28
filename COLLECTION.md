# 数据采集系统

## 架构概览

```
┌─────────────────────────────────────────────────┐
│  APScheduler（内置，随 FastAPI 启动/停止）         │
│  定时触发 → _run_task() → collector.py CLI 模式  │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│  collector.py                                    │
│  ┌──────────────────────────────────────────┐   │
│  │ collect_stock_list()  → stock_list 表   │   │
│  │ collect_all()          → company + fin  │   │
│  │ collect_snapshots()    → daily_snapshot │   │
│  │ collect_hk_finance()   → fin (年度)     │   │
│  │ collect_hk_quarterly() → fin (季度)     │   │
│  │ collect_sectors()      → sector_daily   │   │
│  └──────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│  数据源（AKShare）                                │
│  stock_zh_a_spot_em()      → A股快照            │
│  stock_financial_abstract() → A股财务摘要         │
│  stock_hk_spot_em()         → 港股行情            │
│  stock_hk_financial_indicator_em() → 港股 PE/PB   │
│  stock_financial_hk_analysis_indicator_em() → 年报 │
│  stock_financial_hk_report_em() → 季度利润表      │
│  stock_board_industry_name_em() → 板块数据        │
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
| `--snapshot` | A股+港股行情快照 | **每日** 03:00 | A股 ~65s / 港股 ~110s |
| `--a` | A股财务数据 | **每日** 15:30 | ~15s（仅19家） |
| `--hk` | 港股财务数据 | **每日** 16:30 | ~15s |
| `--sector` | 板块日数据 | **每日** 16:00 | ~11s |
| `--hk-finance` | 港股年度财务指标 | **每月1日** 04:00 | ~6min |
| `--hk-quarterly` | 港股季度利润表 | **每月2日** 04:00 | ~30min |

## API 接口

### 全量采集

```bash
POST /api/collect              # 全量：公司建档 + 财务数据
POST /api/collect/snapshot     # 快照：A股全量 + 港股行情
POST /api/collect/sector       # 板块：行业 + 概念
```

### 单只采集

```bash
POST /api/collect/{code}       # 单只：识别 A/HK → 财务 + 季度利润表
```

**单只采集逻辑：**
1. 查 `Company` 表 → 有则用其 `exchange`
2. 无则查 `StockList` 表 → 有则用其 `exchange`
3. 都无则默认 `SZ`
4. 调用 `collect_all()` 采财务数据
5. 若为港股则额外采集季度利润表

## 定时调度（内置 APScheduler）

随 FastAPI 启动自动注册，关闭自动停止。查看状态：

```bash
GET /api/scheduler/status
# → { running: true, jobs: [{ id, next_run, trigger }...] }
```

| 任务 ID | 时间 | 说明 |
|---------|------|------|
| `stockdata_snapshot` | 交易日 03:00 | 估值快照（A股+港股） |
| `stockdata_ashare` | 交易日 15:30 | A股基本面 |
| `stockdata_sectors` | 交易日 16:00 | 板块日数据 |
| `stockdata_hk` | 交易日 16:30 | 港股基本面 |
| `stockdata_hk_finance` | 每月1日 04:00 | 港股年度财务指标 |
| `stockdata_hk_quarterly` | 每月2日 04:00 | 港股季度利润表 |

## 数据量

| 表 | 行数 | 大小 |
|----|------|------|
| `financial_summary` | ~66万 | ~17.6 MB |
| `daily_snapshot` | ~8,500 | ~1.7 MB |
| `stock_list` | ~10,200 | ~1.5 MB |
| `sector_daily` | ~1,000 | ~0.2 MB |
| 其他（company/position/watchlist） | ~30 | ~0.1 MB |
| **总计** | — | **~21 MB** |

## 数据源说明

所有数据通过 [AKShare](https://github.com/akfamily/akshare) 从东方财富等公开金融网站获取，**个人研究用途**，不对数据准确性做保证。

关键接口：

| 数据 | AKShare 函数 | 数据源 |
|------|-------------|--------|
| A股全量行情 | `stock_zh_a_spot_em()` | 东方财富 |
| A股财务摘要 | `stock_financial_abstract()` | 东方财富 |
| 港股行情 | `stock_hk_spot_em()` | 东方财富 |
| 港股PE/PB/市值 | `stock_hk_financial_indicator_em()` | 东方财富 |
| 港股年度财务指标 | `stock_financial_hk_analysis_indicator_em()` | 东方财富 |
| 港股季度利润表 | `stock_financial_hk_report_em()` | 东方财富 |
| 板块数据 | `stock_board_industry_name_em()` | 东方财富 |
| 大盘指数 | `stock_zh_index_spot_em()` | 东方财富 |
