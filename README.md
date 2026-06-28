# QuickView · stockData

轻量级股票数据分析系统。Python + MySQL 采集基本面与估值快照，React 前端展示。

## 目录

- [快速启动](#-快速启动)
- [架构](#-架构)
- [功能](#-功能)
- [API 接口](#-api-接口)
- [数据采集](#-数据采集)
- [项目结构](#-项目结构)
- [技术栈](#-技术栈)

---

## 🚀 快速启动

### 1. MySQL

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS stock_data DEFAULT CHARACTER SET utf8mb4"
```

### 2. 数据采集（Python）

```bash
cd backend
pip install akshare pandas sqlalchemy pymysql python-dotenv pydantic fastapi uvicorn httpx

# 建表 + 首次全量采集
PYTHONPATH=. python3 collector.py

# 采集估值快照（收盘价 + PE/PB/市值）
PYTHONPATH=. python3 collector.py --snapshot
```

### 3. 后端 API

```bash
cd backend
API_PORT=8900 PYTHONPATH=. python3 main.py
# → http://localhost:8900
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173（自动代理 /api 到 8900）
```

---

## 🏗 架构

```
┌─────────────────────────────────────────────────┐
│  前端 (React 18 + TypeScript + Vite + Tailwind)  │
│  概览 · 公司库 · 基本面                          │
│  Zustand 状态管理 · Vite proxy → 后端            │
└──────────────────────┬──────────────────────────┘
                       │ /api/*
┌──────────────────────┴──────────────────────────┐
│  后端 (Python FastAPI)                           │
│  REST API · CORS · 自动文档 (/docs)             │
└──────────────────────┬──────────────────────────┘
                       │ SQLAlchemy
┌──────────────────────┴──────────────────────────┐
│  MySQL 数据仓库                                   │
│  company · financial_summary ·                   │
│  financial_indicator · daily_snapshot            │
│  watchlist · position                            │
└──────────────────────┬──────────────────────────┘
                       │ AKShare (东方财富)
┌──────────────────────┴──────────────────────────┐
│  数据采集层 (Python)                              │
│  日常：估值快照 · 收盘价 · PE · PB · 市值         │
│  季度：财报摘要 · 86项财务指标                     │
└──────────────────────────────────────────────────┘
```

### 数据流

```
┌──────────────┬─────────────────┬──────────────────┐
│   数据种类    │    采集方式      │     存储位置       │
├──────────────┼─────────────────┼──────────────────┤
│  公司档案     │ 一次采集，后续更新 │ company 表        │
│  财务摘要     │ 季度更新       │ financial_summary │
│  财务指标     │ 季度更新       │ financial_indicator│
│  估值快照     │ 每日采集(凌晨3点)│ daily_snapshot    │
│  日K行情      │ 实时拉取不存库   │ 前端直接调AKShare  │
│  自选/持仓    │ 手动录入        │ watchlist/position│
└──────────────┴─────────────────┴──────────────────┘
```

### 定时任务

| 任务 | 时间 | 说明 |
|:----|:----|:------|
| 估值快照 | 交易日 03:00 | 采前日收盘价+PE/PB/市值 |
| A股基本面 | 交易日 15:30 | 财务摘要+指标 |
| 港股基本面 | 交易日 16:30 | 利润表/资产负债表/现金流 |
| 手动触发 | `POST /api/collect` | 全量更新 |
| 手动快照 | `POST /api/collect/snapshot` | 仅估值的快照 |

---

## 🎯 功能

### 概览页
- 统计卡片：公司总数 / A股数 / 港股数 / 快照日期
- 行情快照表：26家公司最新收盘价、涨跌幅、PE、PB、市值
- 点击表头排序（三态：无→升→降）
- 输入框搜索过滤
- 分页（每页10条）

### 公司库
- 26家公司档案（含名称、行业、经营范围）
- 搜索过滤
- 单公司手动采集

### 基本面
- 选择公司查看财务数据
- 搜索式下拉快速定位
- 展示13项核心指标：营收、成本、净利润、PE、PB、ROE等
- 历史报告期列表

### 主题切换
- 深色/浅色模式（默认浅色）
- 自动记住偏好

---

## 📡 API 接口

所有接口位于 `http://localhost:8900/api`。FastAPI 自动生成文档：`http://localhost:8900/docs`

| 端点 | 方法 | 说明 |
|------|:----:|------|
| `/api/companies` | GET | 公司列表（分页+搜索） |
| | | `?keyword=茅台&page=1&page_size=20` |
| `/api/companies/{code}` | GET | 公司详情 |
| `/api/companies/{code}/financial` | GET | 财务摘要+指标 |
| `/api/kline/{code}` | GET | 日K（实时转发不存库） |
| `/api/quotes?codes=` | GET | 实时行情 |
| `/api/indices` | GET | 大盘指数 |
| `/api/snapshots/latest` | GET | 最新估值快照 |
| `/api/snapshots?code=&days=` | GET | 历史估值快照 |
| `/api/watchlist` | GET/POST/DELETE | 自选股管理 |
| `/api/portfolio` | GET/POST/DELETE | 持仓管理 |
| `/api/collect` | POST | 手动触发财务采集 |
| `/api/collect/snapshot` | POST | 手动触发快照采集 |
| `/api/collect/{code}` | POST | 采集指定公司 |

### 入参示例

```bash
# 搜索+分页
curl '/api/companies?keyword=茅台&page=1&page_size=5'

# 估值快照
curl '/api/snapshots/latest'

# 历史PE
curl '/api/snapshots?code=002475&days=90'

# 手动采集
curl -X POST '/api/collect/snapshot'
```

### 返回格式

```json
// GET /api/companies
{
  "total": 26,
  "page": 1,
  "page_size": 20,
  "items": [{ "code": "002475", "name": "立讯精密", "exchange": "SZ", ... }]
}

// GET /api/snapshots/latest
{
  "date": "2026-06-28",
  "total": 26,
  "has_pe": 25,
  "items": [
    {
      "code": "002475",
      "close": 68.00,
      "pe_ttm": 26.98,
      "pb": 5.21,
      "market_cap": 23313769530.91,
      "turnover": 4.66,
      "change_pct": -8.63
    }
  ]
}
```

---

## 📂 项目结构

```
stockData/
├── README.md
├── .env                     # MySQL 连接配置
│
├── backend/                 # Python 后端
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置（DB/端口）
│   ├── database.py          # SQLAlchemy 连接
│   ├── models.py            # 6张表 ORM 模型
│   ├── schemas.py           # Pydantic 数据模型
│   ├── akshare_client.py    # AKShare 封装层
│   ├── collector.py         # 采集脚本（CLI + API 共用）
│   ├── routers/
│   │   └── api.py           # REST API 路由
│   └── requirements.txt
│
├── frontend/                # React 前端
│   ├── index.html
│   ├── vite.config.ts       # Vite + Tailwind + API 代理
│   ├── src/
│   │   ├── main.tsx         # 入口
│   │   ├── App.tsx          # 根组件 + 标签路由
│   │   ├── index.css        # Tailwind 入口
│   │   ├── api/client.ts    # API 调用封装
│   │   ├── stores/
│   │   │   ├── themeStore.ts   # 主题状态（Zustand）
│   │   │   └── companyStore.ts # 公司数据状态（Zustand）
│   │   ├── components/
│   │   │   └── Layout.tsx      # 页面框架
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx   # 概览（快照表）
│   │   │   ├── Companies.tsx   # 公司库
│   │   │   └── Financial.tsx   # 基本面
│   │   └── types/index.ts      # TypeScript 类型
│   └── package.json
│
└── alembic/                 # 数据库迁移（备用）
    ├── env.py
    └── versions/001_initial.py
```

---

## 🧪 测试

### 快速运行

```bash
cd backend
PYTHONPATH=. python3 tests/test_api.py
# 31 tests in ~0.5s ✅
```

### 测试架构

```
backend/tests/
├── test_api.py              # 31 条测试用例
└── fixtures/                # 静态响应数据（9 个 JSON）
```

### 编码规则

1. **零外部网络依赖** — 不得调用 AKShare 或其他外部 API。涉及外部数据的测试必须使用 `fixtures/` 下的 JSON fixture 文件。

2. **Mock async 外部函数** — 路由中调用的 async 函数（如 `routers.api.ac.get_indices`）用 `AsyncMock` 拦截：

```python
@patch("routers.api.ac.get_indices", new_callable=AsyncMock)
def test_indices(self, mock_indices):
    mock_indices.return_value = load_fixture("indices.json")["data"]
    res = client.get("/api/indices")
    assert res.status_code == 200
```

3. **数据库测试不 mock** — 直接操作本地 MySQL，不自建 mock DB。测试前后通过 `setUp/tearDown` 清理数据（自选/持仓等）。

4. **数据结构校验优先** — 优先测返回 JSON 的字段完整性（字段存在、类型正确），而非具体数值。

```python
# ✅ 推荐：校验字段存在
for f in ["code", "name", "close", "pe_ttm"]:
    self.assertIn(f, item)
    
# ❌ 避免：校验具体数值
self.assertEqual(item["close"], 78.55)
```

5. **纯转换测试** — 新增 `TestTransformation` 类，直接用 fixture 数据校验 model 映射逻辑，不经过 HTTP 请求：

```python
class TestTransformation(unittest.TestCase):
    def test_company_to_out(self):
        raw = load_fixture("company.json")
        self.assertEqual(raw["code"], "000333")
        self.assertIn("exchange", raw)
```

6. **新增 fixture** — 如果新增端点需要外部数据，先通过 curl 采集真实响应保存为 fixture，再用 mock 测试：

```bash
curl -s 'http://localhost:8899/api/snapshots/latest' \
  -o tests/fixtures/snapshot.json
```

7. **运行速度** — 全部测试应在 1 秒内完成。如果超过则说明有未 mock 的外部调用。

---

## 🛠 技术栈

### 后端
| 组件 | 选型 |
|------|------|
| 框架 | FastAPI (Python) |
| 数据库 | MySQL 8.0 |
| ORM | SQLAlchemy 2.0 |
| 数据源 | AKShare（东方财富） |
| 迁移 | Alembic |

### 前端
| 组件 | 选型 |
|------|------|
| 框架 | React 18 |
| 语言 | TypeScript |
| 构建 | Vite |
| 样式 | Tailwind CSS |
| 状态 | Zustand |
| 图标 | Lucide React |
| 图表 | ECharts（待接入） |

---

## 📝 备注

- **数据来源**：AKShare 封装东方财富内部API，非官方接口，仅供研究参考
- **A股/港股**：两者接口不同，定时任务分开执行
- **美股**：暂不覆盖，可通过 yfinance/edgartools 补充
- **财务数据**：季度更新，非交易日采集结果不变
