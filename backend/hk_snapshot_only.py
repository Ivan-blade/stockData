"""只采集港股估值快照"""
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

def _si(v, default=0):
    return int(_sf(v, default))

print(f"  📸 港股快照采集 — {_today}", flush=True)

# 1. 读取港股代码列表
with engine.connect() as conn:
    hk_codes = [r[0] for r in conn.execute(
        text("SELECT code FROM stock_list WHERE exchange = 'HK'")
    ).fetchall()]

print(f"  → 从 stock_list 读取 {len(hk_codes)} 只港股", flush=True)

# 2. 逐只采集
from concurrent.futures import ThreadPoolExecutor, as_completed

hk_results = []
errors = []

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
            "code": code,
            "close": close,
            "volume": int(last.get("成交量", 0)) if not (isinstance(last.get("成交量", 0), float) and math.isnan(last.get("成交量", 0))) else 0,
            "change_pct": _sf(last.get("涨跌幅", 0)),
            "pe": pe,
            "pb": pb,
            "mcap": mcap,
        }, None)
    except Exception as e:
        return (code, None, str(e))

total = len(hk_codes)
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(fetch_hk_stock, code): code for code in hk_codes}
    done = 0
    for future in as_completed(futures):
        code, result, err = future.result()
        if result:
            hk_results.append(result)
        if err:
            errors.append((code, err))
        done += 1
        if done % 200 == 0:
            print(f"    → {done}/{total} 已完成 {len(hk_results)} 只, 错误 {len(errors)}", flush=True)
        time.sleep(0.3)

print(f"  ✅ 采集完成: {len(hk_results)}/{total} 只成功, {len(errors)} 只失败", flush=True)

# 3. 批量写入
if hk_results:
    with engine.connect() as conn:
        for r in hk_results:
            conn.execute(text("""INSERT INTO daily_snapshot 
                (code,trade_date,close,volume,pe_ttm,pb,market_cap,change_pct,updated_at)
                VALUES (:c,:td,:cl,:vol,:pe,:pb,:mcap,:chg,:now)
                ON DUPLICATE KEY UPDATE close=VALUES(close),volume=VALUES(volume),
                    pe_ttm=VALUES(pe_ttm),pb=VALUES(pb),
                    market_cap=VALUES(market_cap),change_pct=VALUES(change_pct),
                    updated_at=VALUES(updated_at)"""),
                {"c": r["code"], "td": _today, "cl": r["close"],
                 "vol": r["volume"],
                 "chg": r["change_pct"],
                 "pe": r["pe"], "pb": r["pb"], "mcap": r["mcap"], "now": _now})
        conn.commit()
    print(f"  💾 写入 daily_snapshot: {len(hk_results)} 条", flush=True)

# 4. 错误统计
if errors:
    from collections import Counter
    err_types = Counter()
    for code, err in errors:
        short = err.split("(")[0].strip() if err else "unknown"
        err_types[short] += 1
    print(f"\n  ⚠️ 错误分布 (共 {len(errors)} 只):", flush=True)
    for etype, cnt in err_types.most_common(10):
        print(f"    {etype}: {cnt} 只", flush=True)

print(f"\n=== 结果: 成功 {len(hk_results)} 只 / 总计 {total} 只 ===", flush=True)
