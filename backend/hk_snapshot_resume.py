"""只采集港股估值快照 — 自动跳过已采集的"""
import sys, time, math
from datetime import datetime
from sqlalchemy import text
from database import engine
import akshare as ak

_now = datetime.now()
_today = _now.date()

def _sf(v, default=0):
    if v is None: return default
    try:
        val = float(v)
        if math.isnan(val) or math.isinf(val): return default
        return val
    except: return default

print(f"  📸 港股快照补采 — {_today}", flush=True)

# 读取所有港股代码
with engine.connect() as conn:
    all_codes = set(r[0] for r in conn.execute(
        text("SELECT code FROM stock_list WHERE exchange = 'HK'")
    ).fetchall())
    # 读取今日已采集的代码
    done_codes = set(r[0] for r in conn.execute(
        text("""SELECT DISTINCT code FROM daily_snapshot 
            WHERE trade_date = :td AND code IN (SELECT code FROM stock_list WHERE exchange = 'HK')"""),
        {"td": _today}
    ).fetchall())

total = len(all_codes)
already = len(done_codes)
remaining = sorted(all_codes - done_codes)

print(f"  → 总计 {total} 只, 已采集 {already} 只, 待采集 {len(remaining)} 只", flush=True)

if not remaining:
    print(f"  ✅ 全部完成!", flush=True)
    sys.exit(0)

# 逐只补采 + 增量写入
from concurrent.futures import ThreadPoolExecutor, as_completed

errors = []
written = 0
BATCH_SIZE = 100

def fetch_hk_stock(code):
    try:
        hist = ak.stock_hk_hist(
            symbol=code, period="daily",
            start_date=_today.isoformat().replace("-", ""),
            end_date=_today.isoformat().replace("-", ""),
        )
        if hist.empty:
            try:
                hist = ak.stock_hk_hist(
                    symbol=code, period="daily",
                    start_date="20200101",
                    end_date=_today.isoformat().replace("-", ""),
                )
            except Exception:
                pass
        if hist.empty:
            return (code, None, "no_hist")

        last = hist.iloc[-1]
        close = _sf(last.get("收盘", 0))
        if close <= 0:
            return (code, None, "close_zero")

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

        return (code, {
            "code": code, "close": close,
            "volume": int(last.get("成交量", 0)) if not (isinstance(last.get("成交量", 0), float) and math.isnan(last.get("成交量", 0))) else 0,
            "change_pct": _sf(last.get("涨跌幅", 0)),
            "pe": pe, "pb": pb, "mcap": mcap,
        }, None)
    except Exception as e:
        return (code, None, str(e))

def write_batch(records):
    if not records:
        return
    with engine.connect() as conn:
        for r in records:
            conn.execute(text("""INSERT INTO daily_snapshot 
                (code,trade_date,close,volume,pe_ttm,pb,market_cap,change_pct,updated_at)
                VALUES (:c,:td,:cl,:vol,:pe,:pb,:mcap,:chg,:now)
                ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                    pe_ttm=VALUES(pe_ttm),pb=VALUES(pb),
                    market_cap=VALUES(market_cap),change_pct=VALUES(change_pct),
                    updated_at=VALUES(updated_at)"""),
                {"c": r["code"], "td": _today, "cl": r["close"],
                 "vol": r["volume"], "chg": r["change_pct"],
                 "pe": r["pe"], "pb": r["pb"], "mcap": r["mcap"], "now": _now})
        conn.commit()
    return len(records)

done_count = 0
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(fetch_hk_stock, code): code for code in remaining}
    batch = []
    for future in as_completed(futures):
        code, result, err = future.result()
        if result:
            batch.append(result)
        if err:
            errors.append((code, err))
        done_count += 1
        if len(batch) >= BATCH_SIZE:
            written += write_batch(batch)
            batch = []
        if done_count % 300 == 0:
            print(f"    → {done_count}/{len(remaining)} 已完成 {written + len(batch)} 只, 错误 {len(errors)}", flush=True)
        time.sleep(0.3)

    if batch:
        written += write_batch(batch)

total_written = already + written
print(f"  ✅ 补采完成: 本次 +{written}, 总计 {total_written}/{total} 只, 错误 {len(errors)}", flush=True)

if errors:
    from collections import Counter
    err_types = Counter()
    for code, err in errors:
        short = err.split("(")[0].strip() if err else "unknown"
        err_types[short] += 1
    print(f"\n  ⚠️ 错误分布 (共 {len(errors)} 只):", flush=True)
    for etype, cnt in err_types.most_common(10):
        print(f"    {etype}: {cnt} 只", flush=True)

print(f"\n=== 最终结果: {total_written}/{total} ===", flush=True)
