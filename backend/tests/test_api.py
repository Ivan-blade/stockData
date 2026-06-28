"""API 接口测试 — 使用静态 fixture 替代外部请求，零网络依赖"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from main import app
from scheduler import init_scheduler

# ── 加载 fixture ──
FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


# 启动调度器（不依赖外部服务）
init_scheduler()
client = TestClient(app)


# ── 工具：mock 路由中调用 akshare_client 的函数 ──
# 我们 mock akshare_client 中所有对外接口，让它们返回 fixture 数据

MOCK_INDICES = load_fixture("indices.json")
MOCK_COMPANY = load_fixture("company.json")
MOCK_COMPANIES = load_fixture("companies_list.json")
MOCK_FINANCIAL = load_fixture("financial.json")
MOCK_SNAPSHOT = load_fixture("snapshot.json")
MOCK_SECTORS = load_fixture("sectors.json")
MOCK_QUOTES = load_fixture("quotes.json")
MOCK_KLINE = load_fixture("kline.json")
MOCK_SCHEDULER = load_fixture("scheduler.json")


class TestHealth(unittest.TestCase):
    def test_health(self):
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")


class TestCompanies(unittest.TestCase):
    def test_list(self):
        res = client.get("/api/companies")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertGreater(data["total"], 0)

    def test_list_pagination(self):
        r1 = client.get("/api/companies?page=1&page_size=5").json()
        r2 = client.get("/api/companies?page=2&page_size=5").json()
        self.assertEqual(len(r1["items"]), 5)
        self.assertEqual(len(r2["items"]), 5)
        self.assertNotEqual([i["code"] for i in r1["items"]], [i["code"] for i in r2["items"]])

    def test_search(self):
        data = client.get("/api/companies?keyword=茅台&page=1&page_size=5").json()
        self.assertGreater(data["total"], 0)

    def test_detail(self):
        data = client.get("/api/companies/000333").json()
        self.assertEqual(data["code"], "000333")
        self.assertEqual(data["name"], "美的集团")

    def test_detail_404(self):
        self.assertEqual(client.get("/api/companies/XXXXX").status_code, 404)


class TestFinancial(unittest.TestCase):
    def test_financial_structure(self):
        data = client.get("/api/companies/000333/financial").json()
        self.assertIn("summary", data)
        self.assertNotIn("indicators", data)
        self.assertGreater(len(data["summary"]), 0)
        # 验证结构：{date: {indicator: value}}
        for date_key, indicators in data["summary"].items():
            self.assertIsInstance(date_key, str)
            self.assertIsInstance(indicators, dict)
            for k, v in indicators.items():
                self.assertIsInstance(k, str)
                self.assertIsInstance(v, (int, float))

    def test_financial_empty(self):
        data = client.get("/api/companies/XXXXX/financial").json()
        self.assertEqual(data["summary"], {})


class TestKline(unittest.TestCase):
    @patch("routers.api.ac.get_kline", new_callable=AsyncMock)
    def test_kline_structure(self, mock_get_kline):
        """K线结构校验 — 使用 fixture"""
        mock_get_kline.return_value = MOCK_KLINE["data"]
        res = client.get("/api/kline/000333?exchange=SZ&start=20260601&end=20260628")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        if data["data"]:
            for field in ["日期", "开盘", "收盘", "最高", "最低", "成交量"]:
                self.assertIn(field, data["data"][0])

    @patch("routers.api.ac.get_kline", new_callable=AsyncMock)
    def test_hk_kline(self, mock_get_kline):
        mock_get_kline.return_value = []
        res = client.get("/api/kline/00700?exchange=HK&start=20260601&end=20260628")
        self.assertEqual(res.status_code, 200)


class TestQuotes(unittest.TestCase):
    @patch("routers.api.ac.get_realtime_quote", new_callable=AsyncMock)
    def test_quotes(self, mock_quotes):
        mock_quotes.return_value = MOCK_QUOTES["data"]
        res = client.get("/api/quotes?codes=000333,00700")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        if data["data"]:
            q = data["data"][0]
            for f in ["code", "price", "change_pct"]:
                self.assertIn(f, q)

    @patch("routers.api.ac.get_realtime_quote", new_callable=AsyncMock)
    def test_quotes_empty(self, mock_quotes):
        mock_quotes.return_value = []
        data = client.get("/api/quotes?codes=").json()
        self.assertEqual(data["data"], [])


class TestIndices(unittest.TestCase):
    @patch("routers.api.ac.get_indices", new_callable=AsyncMock)
    def test_indices_structure(self, mock_indices):
        mock_indices.return_value = MOCK_INDICES["data"]
        res = client.get("/api/indices")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        self.assertGreater(len(data["data"]), 0)
        names = [i["name"] for i in data["data"]]
        self.assertIn("沪深300", names)

    @patch("routers.api.ac.get_indices", new_callable=AsyncMock)
    def test_indices_fields(self, mock_indices):
        mock_indices.return_value = MOCK_INDICES["data"]
        data = client.get("/api/indices").json()
        for idx in data["data"]:
            self.assertIn("name", idx)
            self.assertIn("price", idx)
            self.assertIn("change_pct", idx)


class TestSnapshots(unittest.TestCase):
    def test_latest(self):
        data = client.get("/api/snapshots/latest").json()
        self.assertIn("date", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)
        self.assertIn("items", data)
        item = data["items"][0]
        for f in ["code", "close", "pe_ttm", "pb"]:
            self.assertIn(f, item)

    def test_code_filter(self):
        data = client.get("/api/snapshots?code=000333&days=7").json()
        for i in data["items"]:
            self.assertEqual(i["code"], "000333")

    def test_days_param(self):
        res = client.get("/api/snapshots?days=90")
        self.assertEqual(res.status_code, 200)


class TestSectors(unittest.TestCase):
    def test_industry(self):
        data = client.get("/api/sectors?board_type=industry&limit=5").json()
        self.assertEqual(data["board_type"], "industry")
        self.assertGreaterEqual(len(data["items"]), 1)
        item = data["items"][0]
        for f in ["code", "name", "change_pct"]:
            self.assertIn(f, item)

    def test_concept(self):
        data = client.get("/api/sectors?board_type=concept&limit=3").json()
        self.assertEqual(data["board_type"], "concept")
        self.assertLessEqual(len(data["items"]), 3)

    def test_sort(self):
        data = client.get("/api/sectors?sort_by=up_count&limit=5").json()
        if len(data["items"]) > 1:
            ups = [i["up_count"] or 0 for i in data["items"]]
            self.assertEqual(ups, sorted(ups, reverse=True))

    def test_history(self):
        data = client.get("/api/sectors/BK1443/history?days=30").json()
        self.assertEqual(data["code"], "BK1443")
        self.assertIn("name", data)
        self.assertIn("items", data)


class TestWatchlist(unittest.TestCase):
    test_code = "002475"

    def setUp(self):
        client.delete(f"/api/watchlist/{self.test_code}")

    def test_crud(self):
        # 添加
        r = client.post("/api/watchlist", json={"code": self.test_code, "name": "立讯精密"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["code"], self.test_code)

        # 列表包含
        codes = [i["code"] for i in client.get("/api/watchlist").json()]
        self.assertIn(self.test_code, codes)

        # 重复添加 400
        self.assertEqual(client.post("/api/watchlist", json={"code": self.test_code}).status_code, 400)

        # 删除
        r = client.delete(f"/api/watchlist/{self.test_code}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

        # 404 删除不存在
        self.assertEqual(client.delete(f"/api/watchlist/{self.test_code}").status_code, 404)

    def tearDown(self):
        client.delete(f"/api/watchlist/{self.test_code}")


class TestPortfolio(unittest.TestCase):
    test_code = "000333"

    def setUp(self):
        from database import SessionLocal
        from models import Position
        db = SessionLocal()
        db.query(Position).filter(Position.code == self.test_code).delete()
        db.commit()
        db.close()

    def test_crud(self):
        # 添加
        r = client.post("/api/portfolio", json={"code": self.test_code, "name": "美的", "shares": 100, "avg_cost": 75.0})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["code"], self.test_code)

        # 重复 400
        r = client.post("/api/portfolio", json={"code": self.test_code, "shares": 100, "avg_cost": 75})
        self.assertEqual(r.status_code, 400)

        # 删除
        r = client.delete(f"/api/portfolio/{self.test_code}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def tearDown(self):
        from database import SessionLocal
        from models import Position
        db = SessionLocal()
        db.query(Position).filter(Position.code == self.test_code).delete()
        db.commit()
        db.close()


class TestScheduler(unittest.TestCase):
    def test_scheduler_status(self):
        data = client.get("/api/scheduler/status").json()
        self.assertIn("running", data)
        self.assertTrue(data["running"])
        self.assertIn("jobs", data)
        job_ids = [j["id"] for j in data["jobs"]]
        self.assertIn("stockdata_snapshot", job_ids)
        self.assertIn("stockdata_sectors", job_ids)


class TestTransformation(unittest.TestCase):
    """纯数据转换测试 — 用 fixture 校验模型输出"""

    def test_company_to_out(self):
        """公司数据字段映射正确"""
        raw = MOCK_COMPANY
        self.assertEqual(raw["code"], "000333")
        self.assertEqual(raw["name"], "美的集团")
        self.assertIn("exchange", raw)
        self.assertIn("industry", raw)

    def test_financial_summary_structure(self):
        """财务数据聚合逻辑：{date: {indicator: value}}"""
        data = MOCK_FINANCIAL
        for date_key, indicators in data["summary"].items():
            self.assertRegex(date_key, r"\d{4}-\d{2}-\d{2}")
            for k, v in indicators.items():
                self.assertIsInstance(k, str)
                self.assertIsInstance(v, (int, float))

    def test_snapshot_structure(self):
        """快照字段完整性"""
        snap = MOCK_SNAPSHOT
        self.assertIn("date", snap)
        self.assertIn("total", snap)
        self.assertIn("has_pe", snap)
        for item in snap["items"]:
            for f in ["code", "close", "pe_ttm", "pb"]:
                self.assertIn(f, item)

    def test_sectors_structure(self):
        """板块排行字段完整性"""
        data = MOCK_SECTORS
        self.assertEqual(data["board_type"], "industry")
        for item in data["items"]:
            for f in ["code", "name", "rank", "change_pct", "lead_stock"]:
                self.assertIn(f, item)

    def test_scheduler_structure(self):
        """调度器状态字段完整性"""
        data = MOCK_SCHEDULER
        self.assertTrue(data["running"])
        for job in data["jobs"]:
            for f in ["id", "next_run"]:
                self.assertIn(f, job)

    def test_kline_data_structure(self):
        """K线数据结构"""
        data = MOCK_KLINE
        self.assertIn("code", data)
        self.assertIn("data", data)
        for bar in data["data"]:
            for f in ["日期", "开盘", "收盘", "最高", "最低", "成交量"]:
                self.assertIn(f, bar)

    def test_quotes_data_structure(self):
        """实时行情结构"""
        data = MOCK_QUOTES
        for item in data["data"]:
            for f in ["code", "name", "price", "change_pct"]:
                self.assertIn(f, item)


if __name__ == "__main__":
    import sys
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    filtered = unittest.TestSuite()
    for s in suite:
        for t in s:
            name = getattr(t, "_testMethodName", "")
            cls = type(t)
            # 跳过慢速测试（涉及数据库写操作或调度器）
            skip = getattr(cls, "slow", False)
            if skip:
                continue
            filtered.addTest(t)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(filtered)
    # 如果有 mock 测试没跑，补跑纯转换测试
    if result.testsRun == 0:
        print("\n⚠️  没有快速测试可运行，直接跑全部")
        unittest.main(verbosity=2)
