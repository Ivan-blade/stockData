"""港股快照采集（优化版）

策略：
1. stock_hk_spot_em() 一次拉全量行情（含价格/涨跌幅/成交量）→ 写入 DB
2. 再并行拉取 PE/PB/市值（只对有行情数据的股票）
3. 跳过衍生品/ETF（通过名称关键词过滤）
"""

import sys
import time
import math
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from database import engine
import akshare as ak


def _sf(v):
    """安全转 float，过滤 NaN"""
    if v is None:
        return None
    try:
        v = float(v)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


def _si(v):
    """安全转 int"""
    if v is None:
        return None
    try:
        v = int(v)
        if math.isnan(v) or math.isinf(v):
            return 0
        return v
    except (ValueError, TypeError):
        return 0


# 衍生品/ETF 关键词过滤
DERIVATIVE_KEYWORDS = [
    "法兴", "摩通", "摩利", "瑞银", "汇丰", "花旗", "星展",
    "高盛", "麦银", "国君", "中银", "东亚", "野村", "美林",
    "法巴", "法兴", "荷合", "比联", "瑞信",
    "牛证", "熊证", "CBBC", "Warrant", "ETP",
    "ETF", "ＥＴＦ", "ETN",
    "X ISHARES", "TRACKER", "TR", "ABF",
    "股权", "供股",
]

# 衍生品代码前缀（港股）
DERIVATIVE_CODE_PREFIXES = {
    "1", "2", "4", "5", "8", "9",
    "3", "6", "7",  # 部分衍生品
}


def is_derivative_or_etf(code, name):
    """判断是否为衍生品/ETF（跳过）"""
    name_u = name.upper()
    for kw in DERIVATIVE_KEYWORDS:
        if kw in name_u or kw in name:
            return True
    return False


def collect_hk_snapshot(verbose=True):
    """采集港股快照"""
    now = datetime.now()
    today = date.today()
    total_count = 0

    # ── Step 1: 一次拉全量行情 ──
    t0 = time.time()
    if verbose:
        print("  📸 港股：一次拉取全量行情...", end=" ", flush=True)
    try:
        df = ak.stock_hk_spot_em()
        if verbose:
            print(f"✅ {len(df)} 只（耗时 {time.time()-t0:.1f}s）")
    except Exception as e:
        print(f"❌ stock_hk_spot_em 失败: {e}")
        return 0

    # 过滤有效数据 + 跳过衍生品
    valid = []
    skipped = 0
    for _, row in df.iterrows():
        code = str(row["代码"]).zfill(5)
        name = str(row.get("名称", ""))
        close = _sf(row.get("最新价", 0))
        if close is None or close <= 0:
            continue
        if is_derivative_or_etf(code, name):
            skipped += 1
            continue
        valid.append({
            "code": code,
            "name": name,
            "close": close,
            "volume": _si(row.get("成交量", 0)),
            "amount": _sf(row.get("成交额", 0)) or 0,
            "change_pct": _sf(row.get("涨跌幅", 0)) or 0,
        })

    if verbose:
        print(f"    → 有效 {len(valid)} 只（跳过衍生品/ETF {skipped} 只）")

    if not valid:
        if verbose:
            print("    （无有效数据，跳过）")
        return 0

    # ── Step 2: 批量写入基础行情 ──
    t1 = time.time()
    if verbose:
        print("  💾 写入基础行情...", end=" ", flush=True)
    with engine.connect() as conn:
        for r in valid:
            conn.execute(text("""INSERT INTO daily_snapshot 
                (code,trade_date,close,volume,amount,change_pct,updated_at)
                VALUES (:c,:td,:cl,:vol,:amt,:chg,:now)
                ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                    amount=VALUES(amount),change_pct=VALUES(change_pct),
                    updated_at=VALUES(updated_at)"""),
                {"c": r["code"], "td": today, "cl": r["close"],
                 "vol": r["volume"], "amt": r["amount"] or 0,
                 "chg": r["change_pct"] or 0, "now": now})
            total_count += 1
        conn.commit()
    if verbose:
        print(f"✅ {total_count} 条（写入耗时 {time.time()-t1:.1f}s）")

    # ── Step 3: 并行补 PE/PB/市值 ──
    if verbose:
        print("  📊 补充财务指标（PE/PB/市值）...", end=" ", flush=True)

    hk_codes_to_fetch = [r["code"] for r in valid]

    def fetch_financial(code):
        """获取单只港股财务指标"""
        try:
            fin = ak.stock_hk_financial_indicator_em(symbol=code)
            if fin is None or fin.empty:
                return None
            r = fin.iloc[0]
            pe = _sf(r.get("市盈率"))
            pb = _sf(r.get("市净率"))
            mcap = _sf(r.get("总市值(港元)"))
            return {"code": code, "pe": pe, "pb": pb, "mcap": mcap}
        except Exception:
            return None

    fin_updated = 0
    fin_total = len(hk_codes_to_fetch)
    # 用更多并发 + 不加强制延时，靠 API 自身限流
    batch_size = 50  # 每 50 只打一次进度
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_financial, code): code for code in hk_codes_to_fetch}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result:
                with engine.connect() as conn:
                    conn.execute(text("""UPDATE daily_snapshot SET
                        pe_ttm=:pe, pb=:pb, market_cap=:mcap, updated_at=:now
                        WHERE code=:code AND trade_date=:td"""),
                        {"pe": result["pe"], "pb": result["pb"],
                         "mcap": result["mcap"], "now": now,
                         "code": result["code"], "td": today})
                    conn.commit()
                fin_updated += 1
            if verbose and (i + 1) % batch_size == 0:
                print(f"\n    → {i+1}/{fin_total} 已完成财务指标 {fin_updated} 只...", end=" ", flush=True)

    if verbose:
        print(f"\n    ✅ 财务指标补充完成：{fin_updated}/{fin_total} 只")

    total_elapsed = time.time() - t0
    if verbose:
        print(f"\n  ⏱ 港股快照总耗时：{total_elapsed:.1f}s（{total_count} 条）")
    return total_count


if __name__ == "__main__":
    total = collect_hk_snapshot()
    print(f"\n🎉 完成！新增/更新 {total} 条港股快照记录")
    sys.exit(0 if total > 0 else 1)
