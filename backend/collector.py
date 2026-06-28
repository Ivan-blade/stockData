"""数据采集脚本 — 支持手动触发和定时任务"""

from datetime import datetime, date
from sqlalchemy import text
from database import engine
from models import Company, FinancialSummary, FinancialIndicator, DailySnapshot
import akshare_client as ac
import akshare as ak

# 采集公司清单（A股用代码，港股用 code+交易所标识）
TARGET_COMPANIES = [
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
    # 美股（暂不自动采集）
]

# A股代码 → 交易所前缀
EX_PREFIX = {"SZ": "sz", "SH": "sh", "BJ": "bj"}


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


def upsert_financial_indicator(conn, code, records):
    """批量插入财务指标"""
    now = datetime.now()
    count = 0
    for r in records:
        if "error" in r:
            continue
        sql = text("""INSERT INTO financial_indicator
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
    全量/增量采集
    
    Args:
        targets: 要采集的公司列表，None 则采集全部
        verbose: 是否打印日志
    
    Returns:
        dict: 采集统计
    """
    if targets is None:
        targets = TARGET_COMPANIES

    stats = {"companies": 0, "summary": 0, "indicators": 0}

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

            # 财务数据（A、港接口不同）
        if exchange == "HK":
            if verbose:
                print(f"  📊 {code}: 港股（暂只建档，财务接口待接入）")
        else:
            # A股：财务摘要
            if verbose:
                print(f"  📊 {code}: 财务摘要...", end=" ")
            records = ac.get_financial_summary(code)
            if records and "error" not in records[0]:
                c = upsert_financial_summary(conn, code, records)
                stats["summary"] += c
                if verbose:
                    print(f"{c} 条")
            else:
                if verbose:
                    print("跳过")

            # A股：财务指标
            if verbose:
                print(f"  📊 {code}: 财务指标...", end=" ")
            records = ac.get_financial_indicators(code)
            if records and "error" not in records[0]:
                c = upsert_financial_indicator(conn, code, records)
                stats["indicators"] += c
                if verbose:
                    print(f"{c} 条")
            else:
                if verbose:
                    print("跳过")

        conn.commit()

    return stats


def collect_snapshots(targets=None, verbose=True):
    """采集每日估值快照（收盘价+PE/PB/市值）"""
    if targets is None:
        a_targets = [t for t in TARGET_COMPANIES if t["exchange"] != "HK"]
        hk_targets = [t for t in TARGET_COMPANIES if t["exchange"] == "HK"]
    else:
        a_targets = [t for t in targets if t["exchange"] != "HK"]
        hk_targets = [t for t in targets if t["exchange"] == "HK"]

    import akshare as ak
    now = datetime.now()
    today = now.date()
    total_count = 0

    # ── A股 ──
    if a_targets:
        if verbose:
            print("  📸 拉取A股行情...", end=" ", flush=True)
        try:
            df = ak.stock_zh_a_spot_em()
            a_codes = {t["code"] for t in a_targets}
            with engine.connect() as conn:
                for _, row in df.iterrows():
                    code = str(row["代码"])
                    if code not in a_codes:
                        continue
                    close = float(row.get("最新价", 0))
                    if close <= 0:
                        continue
                    conn.execute(text("""INSERT INTO daily_snapshot 
                        (code,trade_date,close,volume,amount,turnover,pe_ttm,pb,market_cap,amplitude,change_pct,updated_at)
                        VALUES (:c,:td,:cl,:vol,:amt,:turn,:pe,:pb,:mcap,:amp,:chg,:now)
                        ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                            turnover=VALUES(turnover),pe_ttm=VALUES(pe_ttm),pb=VALUES(pb),
                            market_cap=VALUES(market_cap),change_pct=VALUES(change_pct),
                            updated_at=VALUES(updated_at)"""),
                        {"c":code,"td":today,"cl":close,"vol":int(row.get("成交量",0)),"amt":float(row.get("成交额",0)),
                         "turn":float(row.get("换手率",0)),"pe":float(row.get("市盈率-动态",0)),
                         "pb":float(row.get("市净率",0)),"mcap":float(row.get("总市值",0)),
                         "amp":float(row.get("振幅",0)),"chg":float(row.get("涨跌幅",0)),"now":now})
                    total_count += 1
                conn.commit()
            if verbose:
                print(f"✅ A股 {total_count} 条")
        except Exception as e:
            if verbose:
                print(f"❌ {e}")

    # ── 港股（逐只拉取，避免 stock_hk_spot_em 多进程不稳定）──
    if hk_targets:
        if verbose:
            print("  📸 拉取港股行情...", end=" ", flush=True)
        import time as _time
        hk_count = 0
        with engine.connect() as conn:
            for t in hk_targets:
                code = t["code"]
                try:
                    # 个股日K（取最新一天得收盘价+涨跌幅+成交量）
                    hist = ak.stock_hk_hist(
                        symbol=code, period="daily",
                        start_date=today.isoformat().replace("-", ""),
                        end_date=today.isoformat().replace("-", ""),
                    )
                    if hist.empty:
                        continue
                    last = hist.iloc[-1]
                    close = float(last.get("收盘", 0))
                    if close <= 0:
                        continue

                    # 财务指标（PE/PB/市值）
                    fin = ak.stock_hk_financial_indicator_em(symbol=code)
                    pe = pb = mcap = None
                    if not fin.empty:
                        r = fin.iloc[0]
                        pe = float(r["市盈率"]) if r.get("市盈率") else None
                        pb = float(r["市净率"]) if r.get("市净率") else None
                        mcap = float(r["总市值(港元)"]) if r.get("总市值(港元)") else None

                    conn.execute(text("""INSERT INTO daily_snapshot 
                        (code,trade_date,close,volume,pe_ttm,pb,market_cap,change_pct,updated_at)
                        VALUES (:c,:td,:cl,:vol,:pe,:pb,:mcap,:chg,:now)
                        ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                            pe_ttm=VALUES(pe_ttm),pb=VALUES(pb),
                            market_cap=VALUES(market_cap),change_pct=VALUES(change_pct),
                            updated_at=VALUES(updated_at)"""),
                        {"c":code,"td":today,"cl":close,
                         "vol": int(last.get("成交量", 0)),
                         "chg": float(last.get("涨跌幅", 0)),
                         "pe": pe, "pb": pb, "mcap": mcap, "now": now})
                    hk_count += 1
                    total_count += 1
                except Exception as e:
                    if verbose:
                        print(f"\n    ⚠️ {code}: {e}")
                _time.sleep(0.3)  # 避免频率限制
            conn.commit()
        if verbose:
            print(f"✅ 港股 {hk_count} 条（含PE/PB/市值）")

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

    # ── 检查前一个月数据，缺则补填 ──
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
    print(f"   财务指标: {stats['indicators']} 条")
    print(f"{'='*40}")


if __name__ == "__main__":
    import sys
    import time

    # 支持参数：--a 只采A股, --hk 只采港股
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "--a":
        targets = [t for t in TARGET_COMPANIES if t["exchange"] != "HK"]
        label = "A股"
    elif mode == "--hk":
        targets = [t for t in TARGET_COMPANIES if t["exchange"] == "HK"]
        label = "港股"
    elif mode == "--snapshot":
        start = time.time()
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
    else:
        targets = None
        label = "全部"

    start = time.time()
    print(f"🚀 开始采集（{label}）")
    print("=" * 40)
    stats = collect_all(targets=targets)
    print_stats(stats, time.time() - start)
