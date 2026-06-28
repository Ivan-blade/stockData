"""数据采集脚本 — 支持手动触发和定时任务"""

from datetime import datetime, date
from sqlalchemy import text
from database import engine
from models import Company, FinancialSummary, DailySnapshot, StockList
import akshare_client as ac
import akshare as ak

# 财务数据采集目标（原 26 只自选股，与全量快照分离）
FINANCIAL_TARGETS = [
    # A股 — 深圳
    {"code": "002475", "exchange": "SZ", "name": "立讯精密"},
    {"code": "000858", "exchange": "SZ", "name": "五粮液"},
    {"code": "000568", "exchange": "SZ", "name": "泸州老窖"},
    {"code": "000725", "exchange": "SZ", "name": "京东方"},
    {"code": "000333", "exchange": "SZ", "name": "美的集团"},
    {"code": "000651", "exchange": "SZ", "name": "格力电器"},
    {"code": "002415", "exchange": "SZ", "name": "海康威视"},
    {"code": "002304", "exchange": "SZ", "name": "洋河股份"},
    {"code": "002714", "exchange": "SZ", "name": "牧原股份"},
    {"code": "002352", "exchange": "SZ", "name": "顺丰控股"},
    # A股 — 上海
    {"code": "600519", "exchange": "SH", "name": "贵州茅台"},
    {"code": "600309", "exchange": "SH", "name": "万华化学"},
    {"code": "600887", "exchange": "SH", "name": "伊利股份"},
    {"code": "601318", "exchange": "SH", "name": "中国平安"},
    # 科创板
    {"code": "688981", "exchange": "SH", "name": "中芯国际"},
    {"code": "688120", "exchange": "SH", "name": "华海清科"},
    # 创业板
    {"code": "300750", "exchange": "SZ", "name": "宁德时代"},
    {"code": "300059", "exchange": "SZ", "name": "东方财富"},
    # 港股
    {"code": "03690", "exchange": "HK", "name": "美团"},
    {"code": "00700", "exchange": "HK", "name": "腾讯"},
    {"code": "02367", "exchange": "HK", "name": "巨子生物"},
    {"code": "01318", "exchange": "HK", "name": "毛戈平"},
    {"code": "09988", "exchange": "HK", "name": "阿里巴巴"},
    {"code": "01024", "exchange": "HK", "name": "快手"},
    {"code": "01810", "exchange": "HK", "name": "小米"},
    {"code": "01530", "exchange": "HK", "name": "三生制药"},
]

# A股代码 → 交易所前缀
EX_PREFIX = {"SZ": "sz", "SH": "sh", "BJ": "bj"}


def collect_stock_list(verbose=True):
    """拉取全量 A 股 + 港股清单写入 stock_list（--list 模式）"""
    import time as _time
    now = datetime.now()
    total = 0

    with engine.connect() as conn:
        # ── A股 ──
        if verbose:
            print("  📋 拉取 A 股清单...", end=" ", flush=True)
        try:
            df = ak.stock_info_a_code_name()
            a_count = 0
            for _, row in df.iterrows():
                code = str(row["code"])
                name = str(row["name"])
                # 根据代码前缀判定交易所
                if code.startswith("6") or code.startswith("688"):
                    ex = "SH"
                elif code.startswith("0") or code.startswith("3"):
                    ex = "SZ"
                elif code.startswith("4") or code.startswith("8"):
                    ex = "BJ"
                else:
                    ex = "SZ"
                conn.execute(text("""INSERT INTO stock_list (code, name, exchange, stock_type, updated_at)
                    VALUES (:code, :name, :ex, 'AHK', :now)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), exchange=VALUES(exchange), updated_at=VALUES(updated_at)"""),
                    {"code": code, "name": name, "ex": ex, "now": now})
                a_count += 1
            conn.commit()
            total += a_count
            if verbose:
                print(f"✅ {a_count} 只")
        except Exception as e:
            if verbose:
                print(f"❌ {e}")

        # ── 港股（单次拉取 get 清单，snapshot 时不用）──
        if verbose:
            print("  📋 拉取港股清单...", end=" ", flush=True)
        try:
            df = ak.stock_hk_spot_em()
            hk_count = 0
            for _, row in df.iterrows():
                code = str(row["代码"]).zfill(5)
                name = str(row.get("名称", ""))
                conn.execute(text("""INSERT INTO stock_list (code, name, exchange, stock_type, updated_at)
                    VALUES (:code, :name, 'HK', 'AHK', :now)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), updated_at=VALUES(updated_at)"""),
                    {"code": code, "name": name, "now": now})
                hk_count += 1
            conn.commit()
            total += hk_count
            if verbose:
                print(f"✅ {hk_count} 只")
        except Exception as e:
            if verbose:
                print(f"❌ {e}")

    return {"list": total}


def upsert_company(db, code, exchange, name):
    """建/更新公司档案"""
    profile = ac.get_company_profile(code)
    if not profile or "error" in profile:
        # A股才有 profile，港股走公司简介API
        existing = db.query(Company).filter(Company.code == code).first()
        if not existing:
            c = Company(code=code, name=name, exchange=exchange)
            db.add(c)
            return f"新建: {name}"
        return f"已存在: {name}"

    existing = db.query(Company).filter(Company.code == code).first()
    if existing:
        existing.name = profile.get("name", name)
        existing.industry = profile.get("industry")
        existing.business_scope = profile.get("business_scope")
        existing.employees = profile.get("employees")
        existing.website = profile.get("website")
    else:
        c = Company(
            code=code, name=profile.get("name", name),
            exchange=exchange,
            industry=profile.get("industry"),
            business_scope=profile.get("business_scope"),
            employees=profile.get("employees"),
            website=profile.get("website"),
        )
        db.add(c)
    return f"简介就绪: {profile.get('name', name)}"


def upsert_financial_summary(conn, code, records):
    """批量 INSERT IGNORE 财务摘要，同时更新 updated_at"""
    now = datetime.now()
    count = 0
    for r in records:
        if "error" in r:
            continue
        sql = text("""INSERT INTO financial_summary 
            (code, report_date, indicator, value, updated_at)
            VALUES (:code, :rd, :ind, :val, :now)
            ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)
        """)
        result = conn.execute(sql, {
            "code": code, "rd": r["report_date"],
            "ind": r["indicator"], "val": r["value"],
            "now": now,
        })
        if result.rowcount > 0:
            count += 1
    return count


def collect_all(targets=None, verbose=True):
    """
    全量/增量采集（财务数据，仅限 FINANCIAL_TARGETS）
    
    Args:
        targets: 要采集的公司列表，None 则采集全部 FINANCIAL_TARGETS
        verbose: 是否打印日志
    
    Returns:
        dict: 采集统计
    """
    if targets is None:
        targets = FINANCIAL_TARGETS

    stats = {"companies": 0, "summary": 0}

    # 公司简介用 ORM
    from database import SessionLocal
    db = SessionLocal()
    try:
        for t in targets:
            msg = upsert_company(db, t["code"], t["exchange"], t["name"])
            stats["companies"] += 1
            if verbose:
                print(f"  🏢 {t['code']}: {msg}")
        db.commit()
    finally:
        db.close()

    # 财务数据用 raw SQL（批量快）
    with engine.connect() as conn:
        for t in targets:
            code = t["code"]
            exchange = t["exchange"]

            if exchange == "HK":
                if verbose:
                    print(f"  📊 {code}: 港股（暂只建档，财务接口待接入）")
            else:
                # A股：财务摘要
                if verbose:
                    print(f"  📊 {code}: 财务摘要...", end=" ", flush=True)
                records = ac.get_financial_summary(code)
                if records and "error" not in records[0]:
                    c = upsert_financial_summary(conn, code, records)
                    stats["summary"] += c
                    if verbose:
                        print(f"{c} 条")
                else:
                    if verbose:
                        print("跳过")

                conn.commit()

    return stats


def _sf(v, default=0):
    """safe_float — NaN/Inf/None → default"""
    if v is None:
        return default
    try:
        val = float(v)
        import math
        if math.isnan(val) or math.isinf(val):
            return default
        return val
    except (ValueError, TypeError):
        return default


def _si(v, default=0):
    """safe_int — NaN/Inf/None → default"""
    return int(_sf(v, default))


def collect_snapshots(verbose=True):
    """采集每日估值快照（全量 A 股 + 港股）"""
    import time as _time
    now = datetime.now()
    today = now.date()
    total_count = 0

    # ── A股：从 stock_zh_a_spot_em() 批量拉取全量 ──
    if verbose:
        print("  📸 拉取 A 股全量行情...", end=" ", flush=True)
    try:
        df = ak.stock_zh_a_spot_em()
        a_count = 0
        with engine.connect() as conn:
            for _, row in df.iterrows():
                code = str(row["代码"])
                close = _sf(row.get("最新价", 0))
                if close <= 0:
                    continue
                conn.execute(text("""INSERT INTO daily_snapshot 
                    (code,trade_date,close,volume,amount,turnover,pe_ttm,pb,market_cap,amplitude,change_pct,updated_at)
                    VALUES (:c,:td,:cl,:vol,:amt,:turn,:pe,:pb,:mcap,:amp,:chg,:now)
                    ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                        turnover=VALUES(turnover),pe_ttm=VALUES(pe_ttm),pb=VALUES(pb),
                        market_cap=VALUES(market_cap),change_pct=VALUES(change_pct),
                        updated_at=VALUES(updated_at)"""),
                    {"c":code,"td":today,"cl":close,
                     "vol":_si(row.get("成交量", 0)),
                     "amt":_sf(row.get("成交额", 0)),
                     "turn":_sf(row.get("换手率", 0)),
                     "pe":_sf(row.get("市盈率-动态", 0)),
                     "pb":_sf(row.get("市净率", 0)),
                     "mcap":_sf(row.get("总市值", 0)),
                     "amp":_sf(row.get("振幅", 0)),
                     "chg":_sf(row.get("涨跌幅", 0)),
                     "now":now})
                # 同步更新 stock_list 名称（自动跟随除权除息变化）
                name = str(row.get("名称", "")).replace("XD", "").replace("XR", "").replace("DR", "").strip()
                if name:
                    conn.execute(text("UPDATE stock_list SET name = :name, updated_at = :now WHERE code = :code AND name != :name"),
                                 {"name": name, "now": now, "code": code})
                a_count += 1
            conn.commit()
        total_count += a_count
        if verbose:
            print(f"✅ {a_count} 条")
    except Exception as e:
        if verbose:
            print(f"❌ {e}")

    # ── 港股：从 stock_list 读全量代码，逐个拉取 ──
    if verbose:
        print("  📸 拉取港股全量行情（逐只，间隔 0.3s）...", end=" ", flush=True)
    try:
        with engine.connect() as conn:
            hk_codes = [r[0] for r in conn.execute(
                text("SELECT code FROM stock_list WHERE exchange = 'HK'")
            ).fetchall()]
    except Exception as e:
        hk_codes = []
        if verbose:
            print(f"  ⚠️ 读取 stock_list 失败: {e}")

    if not hk_codes:
        if verbose:
            print("（无港股清单，跳过）")
    else:
        hk_count = 0
        hk_total = len(hk_codes)
        hk_results = []

        def fetch_hk_stock(code):
            """获取单只港股行情+财务指标"""
            import math
            try:
                # 个股日K 取最新价
                hist = ak.stock_hk_hist(
                    symbol=code, period="daily",
                    start_date=today.isoformat().replace("-", ""),
                    end_date=today.isoformat().replace("-", ""),
                )
                if hist.empty:
                    try:
                        hist = ak.stock_hk_hist(
                            symbol=code, period="daily",
                            start_date="20200101",
                            end_date=today.isoformat().replace("-", ""),
                        )
                    except Exception:
                        pass
                if hist.empty:
                    return None
                last = hist.iloc[-1]
                close = _sf(last.get("收盘", 0))
                if close <= 0:
                    return None

                # 财务指标（PE/PB/市值）
                try:
                    fin = ak.stock_hk_financial_indicator_em(symbol=code)
                except Exception:
                    fin = None
                pe = pb = mcap = None
                if fin is not None and hasattr(fin, "empty") and not fin.empty:
                    r = fin.iloc[0]
                    if hasattr(r, "get"):
                        pe = _sf(r.get("市盈率"))
                        pb = _sf(r.get("市净率"))
                        mcap = _sf(r.get("总市值(港元)"))

                return {
                    "code": code,
                    "close": close,
                    "volume": int(last.get("成交量", 0)) if not (isinstance(last.get("成交量", 0), float) and math.isnan(last.get("成交量", 0))) else 0,
                    "change_pct": _sf(last.get("涨跌幅", 0)),
                    "pe": pe,
                    "pb": pb,
                    "mcap": mcap,
                }
            except Exception as e:
                if verbose:
                    print(f"\n    ⚠️ {code}: {e}")
                return None

        from concurrent.futures import ThreadPoolExecutor, as_completed
        hk_total = len(hk_codes)
        hk_results = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_hk_stock, code): code for code in hk_codes}
            done = 0
            for future in as_completed(futures):
                result = future.result()
                if result:
                    hk_results.append(result)
                done += 1
                if verbose and done % 100 == 0:
                    print(f"\n    → {done}/{hk_total} 已完成 {len(hk_results)} 只...", end=" ", flush=True)
                _time.sleep(0.3)  # 整体限流

        # 批量写入
        hk_count = len(hk_results)
        if hk_results:
            with engine.connect() as conn:
                for r in hk_results:
                    total_count += 1
                    conn.execute(text("""INSERT INTO daily_snapshot 
                        (code,trade_date,close,volume,pe_ttm,pb,market_cap,change_pct,updated_at)
                        VALUES (:c,:td,:cl,:vol,:pe,:pb,:mcap,:chg,:now)
                        ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                            pe_ttm=VALUES(pe_ttm),pb=VALUES(pb),
                            market_cap=VALUES(market_cap),change_pct=VALUES(change_pct),
                            updated_at=VALUES(updated_at)"""),
                        {"c": r["code"], "td": today, "cl": r["close"],
                         "vol": r["volume"],
                         "chg": r["change_pct"],
                         "pe": r["pe"], "pb": r["pb"], "mcap": r["mcap"], "now": now})
            conn.commit()
        if verbose:
            print(f"✅ 港股 {hk_count}/{hk_total} 条")
            if hk_count < hk_total:
                print(f"   ⚠️ 未采集到 {(hk_total - hk_count)} 只（可能是停牌/无数据）")

    return {"snapshot": total_count}


def collect_sectors(verbose: bool = True, backfill_months: int = 1) -> dict:
    """采集行业/概念板块日数据，每日收盘后调用"""
    from datetime import timedelta
    from sqlalchemy import func as sa_func

    now = datetime.now()
    today = now.date()
    stats = {"industry": 0, "concept": 0, "cleaned": 0}

    def save_board(df, board_type: str) -> int:
        count = 0
        with engine.connect() as conn:
            for _, row in df.iterrows():
                try:
                    chg = float(row.get("涨跌幅", 0)) if "涨跌幅" in row else 0
                    conn.execute(text("""INSERT INTO sector_daily
                        (trade_date, board_type, code, name, `rank`, change_pct, change_amount,
                         price, total_market_cap, turnover, up_count, down_count,
                         lead_stock, lead_change, created_at)
                        VALUES (:td,:bt,:code,:name,:rk,:chg,:chg_amt,
                         :price,:mcap,:turn,:up,:down,:lead,:ld_chg,:now)
                        ON DUPLICATE KEY UPDATE
                         change_pct=VALUES(change_pct), up_count=VALUES(up_count),
                         down_count=VALUES(down_count), lead_stock=VALUES(lead_stock),
                         lead_change=VALUES(lead_change)"""),
                        {"td": today, "bt": board_type, "code": str(row.get("板块代码", "")),
                         "name": str(row.get("板块名称", "")), "rk": int(row.get("排名", 0)),
                         "chg": chg,
                         "chg_amt": float(row.get("涨跌额", 0)) if "涨跌额" in row else 0,
                         "price": float(row.get("最新价", 0)) if "最新价" in row else 0,
                         "mcap": int(row.get("总市值", 0)) if "总市值" in row else 0,
                         "turn": float(row.get("换手率", 0)) if "换手率" in row else 0,
                         "up": int(row.get("上涨家数", 0)) if "上涨家数" in row else 0,
                         "down": int(row.get("下跌家数", 0)) if "下跌家数" in row else 0,
                         "lead": str(row.get("领涨股票", "")),
                         "ld_chg": float(row.get("领涨股票-涨跌幅", 0))
                                   if "领涨股票-涨跌幅" in row else 0,
                         "now": now})
                    count += 1
                except Exception:
                    pass
            conn.commit()
        return count

    # ── 行业板块 ──
    if verbose:
        print("  📊 行业板块...", end=" ", flush=True)
    try:
        df = ak.stock_board_industry_name_em()
        stats["industry"] = save_board(df, "industry")
        if verbose:
            print(f"✅ {stats['industry']} 条")
    except Exception as e:
        if verbose:
            print(f"❌ 行业: {e}")

    # ── 概念板块 ──
    if verbose:
        print("  📊 概念板块...", end=" ", flush=True)
    try:
        df = ak.stock_board_concept_name_em()
        stats["concept"] = save_board(df, "concept")
        if verbose:
            print(f"✅ {stats['concept']} 条")
    except Exception as e:
        if verbose:
            print(f"❌ 概念: {e}")

    # ── 清理 60 天前旧数据 ──
    cutoff = today - timedelta(days=60)
    with engine.connect() as conn:
        r = conn.execute(
            text("DELETE FROM sector_daily WHERE trade_date < :cutoff"),
            {"cutoff": cutoff}
        )
        conn.commit()
        stats["cleaned"] = r.rowcount if r.rowcount > 0 else 0
    if verbose:
        print(f"  🧹 清理 60 天前: {stats['cleaned']} 条")

    # ── 检查历史数据完整性 ──
    if verbose:
        print("  🔍 检查历史数据完整性...", end=" ", flush=True)
    try:
        with engine.connect() as conn:
            existing_dates = set(
                r[0] for r in conn.execute(
                    text("SELECT DISTINCT trade_date FROM sector_daily "
                         "WHERE trade_date >= :start AND trade_date < :today "
                         "AND board_type = 'industry'"),
                    {"start": today - timedelta(days=backfill_months * 31), "today": today}
                ).fetchall()
            )

        d = today - timedelta(days=1)
        missing = 0
        while d >= today - timedelta(days=backfill_months * 31):
            if d.isoweekday() <= 5 and d not in existing_dates:
                missing += 1
            d -= timedelta(days=1)

        if missing > 0:
            if verbose:
                print(f"缺 {missing} 天 (AKShare无法回溯板块快照, 仅记录)")
        else:
            if verbose:
                print("✅ 完整")
        stats["missing_days"] = missing
    except Exception as e:
        if verbose:
            print(f"❌: {e}")

    return stats


def print_stats(stats, elapsed):
    """打印采集结果"""
    print(f"\n{'='*40}")
    print(f"✅ 采集完成！用时 {elapsed:.1f}s")
    print(f"   公司建档: {stats['companies']} 家")
    print(f"   财务摘要: {stats['summary']} 条")
    print(f"{'='*40}")


if __name__ == "__main__":
    import sys
    import time

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "--list":
        start = time.time()
        print("🚀 开始采集全量股票清单")
        print("=" * 40)
        stats = collect_stock_list(verbose=True)
        elapsed = time.time() - start
        print(f"\n{'='*40}")
        print(f"✅ 股票清单采集完成！用时 {elapsed:.1f}s")
        print(f"   总计: {stats['list']} 只")
        print(f"{'='*40}")
        sys.exit(0)

    elif mode == "--snapshot":
        start = time.time()
        print("🚀 开始全量估值快照采集")
        print("=" * 40)
        stats = collect_snapshots(verbose=True)
        elapsed = time.time() - start
        print(f"\n{'='*40}")
        print(f"✅ 估值快照采集完成！用时 {elapsed:.1f}s")
        print(f"   行情: {stats['snapshot']} 条")
        print(f"{'='*40}")
        sys.exit(0)

    elif mode == "--sector":
        start = time.time()
        stats = collect_sectors(verbose=True)
        elapsed = time.time() - start
        print(f"\n{'='*40}")
        print(f"✅ 板块数据采集完成！用时 {elapsed:.1f}s")
        print(f"   行业: {stats['industry']}  概念: {stats['concept']}")
        print(f"   清理: {stats['cleaned']} 条  缺天数: {stats.get('missing_days', 0)}")
        print(f"{'='*40}")
        sys.exit(0)

    elif mode in ("--a", "--hk"):
        targets = None
        label = "A股" if mode == "--a" else "港股"
        start = time.time()
        print(f"🚀 开始采集财务数据（{label}）")
        print("=" * 40)
        stats = collect_all(targets=targets)
        print_stats(stats, time.time() - start)

    else:
        start = time.time()
        print("🚀 开始采集财务数据（全部 FINANCIAL_TARGETS）")
        print("=" * 40)
        stats = collect_all(targets=None)
        print_stats(stats, time.time() - start)
