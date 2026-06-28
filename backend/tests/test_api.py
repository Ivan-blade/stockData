"""API 接口测试 — 覆盖所有端点"""

import unittest
from fastapi.testclient import TestClient
from main import app
from scheduler import init_scheduler

# 为测试初始化调度器（生产环境由 uvicorn startup 触发）
init_scheduler()
client = TestClient(app)


class TestHealth(unittest.TestCase):
    """健康检查"""

    def test_health(self):
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertEqual(res.json()["version"], "0.1.0")


class TestCompanies(unittest.TestCase):
    """公司档案"""

    def test_list(self):
        res = client.get("/api/companies")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)
        self.assertGreater(data["total"], 0)

    def test_list_with_search(self):
        res = client.get("/api/companies?keyword=茅台&page=1&page_size=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data["total"], 0)
        self.assertLessEqual(len(data["items"]), 5)
        # 搜索命中名称
        names = [i["name"] for i in data["items"]]
        self.assertTrue(any("茅台" in n for n in names))

    def test_list_pagination(self):
        res = client.get("/api/companies?page=1&page_size=5")
        d1 = res.json()
        res2 = client.get("/api/companies?page=2&page_size=5")
        d2 = res2.json()
        self.assertEqual(len(d1["items"]), 5)
        self.assertEqual(len(d2["items"]), 5)
        # 两页数据不同
        ids1 = [i["code"] for i in d1["items"]]
        ids2 = [i["code"] for i in d2["items"]]
        self.assertNotEqual(ids1, ids2)

    def test_detail(self):
        res = client.get("/api/companies/000333")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["code"], "000333")
        self.assertEqual(data["name"], "美的集团")

    def test_detail_not_found(self):
        res = client.get("/api/companies/XXXXX")
        self.assertEqual(res.status_code, 404)


class TestFinancial(unittest.TestCase):
    """财务数据"""

    def test_financial(self):
        res = client.get("/api/companies/000333/financial")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertNotIn("indicators", data)  # 已移除
        # 至少有一期数据
        self.assertGreater(len(data["summary"]), 0)
        # 检查关键指标
        first_key = list(data["summary"].keys())[0]
        first = data["summary"][first_key]
        self.assertIn("营业总收入", first)
        self.assertIn("净利润", first)

    def test_financial_empty_code(self):
        res = client.get("/api/companies/XXXXX/financial")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["summary"], {})


class TestKline(unittest.TestCase):
    """日K线"""
    slow = True

    def test_kline(self):
        import time
        res = client.get("/api/kline/000333?exchange=SZ&start=20260601&end=20260628")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)

    def test_kline_hk(self):
        res = client.get("/api/kline/00700?exchange=HK&start=20260601&end=20260628")
        self.assertEqual(res.status_code, 200)


class TestQuotes(unittest.TestCase):
    """实时行情"""
    slow = True

    def test_quotes(self):
        res = client.get("/api/quotes?codes=000333,00700")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        self.assertGreater(len(data["data"]), 0)

    def test_quotes_empty(self):
        res = client.get("/api/quotes?codes=")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["data"], [])


class TestIndices(unittest.TestCase):
    """大盘指数"""
    slow = True

    def test_indices(self):
        res = client.get("/api/indices")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("data", data)
        # 至少包含 上证指数/深证成指
        names = [i["name"] for i in data["data"]]
        self.assertIn("上证指数", names)


class TestSnapshots(unittest.TestCase):
    """估值快照"""

    def test_latest(self):
        res = client.get("/api/snapshots/latest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("date", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)
        self.assertIn("items", data)
        # 检查数据字段
        item = data["items"][0]
        self.assertIn("code", item)
        self.assertIn("close", item)
        self.assertIn("pe_ttm", item)

    def test_snapshots_code_filter(self):
        res = client.get("/api/snapshots?code=000333&days=7")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(len(data["items"]), 0)
        for i in data["items"]:
            self.assertEqual(i["code"], "000333")

    def test_snapshots_days(self):
        res = client.get("/api/snapshots?days=90")
        self.assertEqual(res.status_code, 200)


class TestSectors(unittest.TestCase):
    """板块数据"""

    def test_sectors_industry(self):
        res = client.get("/api/sectors?board_type=industry&limit=5")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["board_type"], "industry")
        self.assertGreaterEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertIn("code", item)
        self.assertIn("name", item)
        self.assertIn("change_pct", item)

    def test_sectors_concept(self):
        res = client.get("/api/sectors?board_type=concept&limit=3")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["board_type"], "concept")
        self.assertLessEqual(len(data["items"]), 3)

    def test_sectors_sort(self):
        res = client.get("/api/sectors?sort_by=up_count&limit=5")
        d1 = res.json()["items"]
        ups = [i["up_count"] or 0 for i in d1]
        # 检查降序
        self.assertEqual(ups, sorted(ups, reverse=True), "up_count 应降序")

    def test_sector_history(self):
        res = client.get("/api/sectors/BK1443/history?days=30")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["code"], "BK1443")
        self.assertIn("name", data)
        self.assertIn("items", data)


class TestWatchlist(unittest.TestCase):
    """自选股"""
    test_code = "002475"

    def setUp(self):
        # 确保测试代码不在自选
        client.delete(f"/api/watchlist/{self.test_code}")

    def test_crud(self):
        # 添加
        res = client.post("/api/watchlist", json={"code": self.test_code, "name": "立讯精密"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], self.test_code)

        # 列表
        res = client.get("/api/watchlist")
        self.assertEqual(res.status_code, 200)
        codes = [i["code"] for i in res.json()]
        self.assertIn(self.test_code, codes)

        # 重复添加应报错
        res = client.post("/api/watchlist", json={"code": self.test_code})
        self.assertEqual(res.status_code, 400)

        # 删除
        res = client.delete(f"/api/watchlist/{self.test_code}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

        # 删除不存在
        res = client.delete(f"/api/watchlist/{self.test_code}")
        self.assertEqual(res.status_code, 404)

    def tearDown(self):
        client.delete(f"/api/watchlist/{self.test_code}")


class TestPortfolio(unittest.TestCase):
    """组合持仓"""
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
        res = client.post("/api/portfolio", json={
            "code": self.test_code, "name": "美的集团",
            "shares": 100, "avg_cost": 75.0,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["code"], self.test_code)

        # 重复添加
        res = client.post("/api/portfolio", json={
            "code": self.test_code, "shares": 100, "avg_cost": 75,
        })
        self.assertEqual(res.status_code, 400)

        # 删除
        res = client.delete(f"/api/portfolio/{self.test_code}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def tearDown(self):
        from database import SessionLocal
        from models import Position
        db = SessionLocal()
        db.query(Position).filter(Position.code == self.test_code).delete()
        db.commit()
        db.close()


class TestScheduler(unittest.TestCase):
    """定时任务状态"""

    def test_scheduler_status(self):
        res = client.get("/api/scheduler/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("running", data)
        self.assertTrue(data["running"])
        self.assertIn("jobs", data)
        # 至少 4 个任务
        job_ids = [j["id"] for j in data["jobs"]]
        self.assertIn("stockdata_snapshot", job_ids)
        self.assertIn("stockdata_sectors", job_ids)


if __name__ == "__main__":
    import sys
    # 默认跳过慢速测试（涉及 AKShare 外部 API）
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    filtered = unittest.TestSuite()
    for s in suite:
        for t in s:
            if not getattr(t, "_testMethodName", None) or getattr(t, "slow", None):
                continue
            filtered.addTest(t)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(filtered)
