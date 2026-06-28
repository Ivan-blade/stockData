from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Company, Watchlist, Position
from schemas import (
    CompanyOut, WatchlistOut, WatchlistAdd,
    PositionOut, PositionAdd,
)
import akshare_client as ac

router = APIRouter(prefix="/api", tags=["companies"])


# ── 公司列表（分页 + 搜索）──
@router.get("/companies")
def list_companies(
    keyword: str = Query("", description="按名称模糊搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if keyword:
        q = q.filter(Company.name.like(f"%{keyword}%"))
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/companies/{code}", response_model=CompanyOut)
def get_company(code: str, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.code == code).first()
    if not c:
        raise HTTPException(404, f"公司 {code} 不存在")
    return c


# ── 财务(从 MySQL 读) ──
@router.get("/companies/{code}/financial")
def get_financial(code: str, db: Session = Depends(get_db)):
    from models import FinancialSummary, FinancialIndicator

    summaries = db.query(FinancialSummary).filter(
        FinancialSummary.code == code
    ).all()
    indicators = db.query(FinancialIndicator).filter(
        FinancialIndicator.code == code
    ).all()

    # 按 report_date 聚合
    sum_by_date = {}
    for s in summaries:
        d = str(s.report_date)
        if d not in sum_by_date:
            sum_by_date[d] = {}
        sum_by_date[d][s.indicator] = s.value

    ind_by_date = {}
    for s in indicators:
        d = str(s.report_date)
        if d not in ind_by_date:
            ind_by_date[d] = {}
        ind_by_date[d][s.indicator] = s.value

    return {"summary": sum_by_date, "indicators": ind_by_date}


# ── 日K（实时转发）──
@router.get("/kline/{code}")
async def get_kline(
    code: str,
    exchange: str = Query("SZ", description="SZ/SH/HK"),
    start: str = Query("20260601"),
    end: str = Query("20260630"),
):
    data = await ac.get_kline(code, exchange, start, end)
    return {"code": code, "data": data}


# ── 实时行情 ──
@router.get("/quotes")
async def get_quotes(codes: str = Query(..., description="逗号分隔的股票代码")):
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    data = await ac.get_realtime_quote(code_list)
    return {"data": data}


# ── 大盘指数 ──
@router.get("/indices")
async def get_indices():
    data = await ac.get_indices()
    return {"data": data}


# ── 自选股 ──
@router.get("/watchlist", response_model=List[WatchlistOut])
def list_watchlist(db: Session = Depends(get_db)):
    return db.query(Watchlist).all()


@router.post("/watchlist", response_model=WatchlistOut)
def add_watchlist(item: WatchlistAdd, db: Session = Depends(get_db)):
    exists = db.query(Watchlist).filter(Watchlist.code == item.code).first()
    if exists:
        raise HTTPException(400, f"{item.code} 已在自选")
    w = Watchlist(code=item.code, name=item.name, note=item.note)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


@router.delete("/watchlist/{code}")
def remove_watchlist(code: str, db: Session = Depends(get_db)):
    w = db.query(Watchlist).filter(Watchlist.code == code).first()
    if not w:
        raise HTTPException(404)
    db.delete(w)
    db.commit()
    return {"ok": True}


# ── 组合持仓 ──
@router.get("/portfolio", response_model=List[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    # 获取实时价格计算盈亏
    codes = [p.code for p in positions]
    import asyncio
    quotes = asyncio.run(ac.get_realtime_quote(codes))
    price_map = {q["code"]: q["price"] for q in quotes}

    result = []
    for p in positions:
        mp = price_map.get(p.code)
        out = PositionOut(
            code=p.code, name=p.name,
            shares=p.shares, avg_cost=p.avg_cost,
            market_price=mp,
            buy_date=p.buy_date, note=p.note,
            updated_at=p.updated_at,
        )
        if mp:
            out.market_value = round(p.shares * mp, 2)
            cost_total = p.shares * p.avg_cost
            out.pnl = round(out.market_value - cost_total, 2)
            out.pnl_pct = round((mp - p.avg_cost) / p.avg_cost * 100, 2)
        result.append(out)
    return result


@router.post("/portfolio", response_model=PositionOut)
def add_position(item: PositionAdd, db: Session = Depends(get_db)):
    exists = db.query(Position).filter(Position.code == item.code).first()
    if exists:
        raise HTTPException(400, f"{item.code} 已在组合中")
    p = Position(
        code=item.code, name=item.name,
        shares=item.shares, avg_cost=item.avg_cost,
        buy_date=item.buy_date, note=item.note,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return PositionOut(
        code=p.code, name=p.name,
        shares=p.shares, avg_cost=p.avg_cost,
        buy_date=p.buy_date, note=p.note,
    )


@router.delete("/portfolio/{code}")
def remove_position(code: str, db: Session = Depends(get_db)):
    p = db.query(Position).filter(Position.code == code).first()
    if not p:
        raise HTTPException(404)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ── 数据采集（手动触发）──
import time

@router.post("/collect")
def trigger_collect():
    """手动触发数据采集"""
    from collector import collect_all, print_stats
    start = time.time()
    stats = collect_all(verbose=False)
    elapsed = time.time() - start
    return {
        "ok": True,
        "elapsed": f"{elapsed:.1f}s",
        "stats": stats,
    }


@router.post("/collect/{code}")
def trigger_collect_one(code: str):
    """采集指定公司"""
    from collector import collect_all
    from models import Company
    from database import SessionLocal

    db = SessionLocal()
    c = db.query(Company).filter(Company.code == code).first()
    db.close()

    exchange = c.exchange if c else "SZ"
    name = c.name if c else code

    start = time.time()
    stats = collect_all(targets=[{"code": code, "exchange": exchange, "name": name}], verbose=False)
    elapsed = time.time() - start
    return {"ok": True, "elapsed": f"{elapsed:.1f}s", "stats": stats}


# ── 估值快照 ──
@router.get("/snapshots")
def list_snapshots(
    code: str = Query("", description="股票代码"),
    days: int = Query(30, ge=1, le=365, description="最近N天"),
    db: Session = Depends(get_db),
):
    from models import DailySnapshot
    q = db.query(DailySnapshot)
    if code:
        q = q.filter(DailySnapshot.code == code)
    q = q.order_by(DailySnapshot.trade_date.desc()).limit(days)
    items = q.all()
    return {
        "total": len(items),
        "items": [
            {
                "code": i.code,
                "trade_date": str(i.trade_date),
                "close": i.close,
                "pe_ttm": i.pe_ttm,
                "pb": i.pb,
                "market_cap": i.market_cap,
                "volume": i.volume,
                "turnover": i.turnover,
                "change_pct": i.change_pct,
            }
            for i in items
        ],
    }


@router.get("/snapshots/latest")
def latest_snapshots(db: Session = Depends(get_db)):
    """获取所有公司的最新一条快照"""
    from models import DailySnapshot
    from sqlalchemy import func as sa_func
    # 取最新日期
    latest_date = db.query(sa_func.max(DailySnapshot.trade_date)).scalar()
    if not latest_date:
        return {"date": None, "items": []}
    items = db.query(DailySnapshot).filter(DailySnapshot.trade_date == latest_date).all()
    a_count = sum(1 for i in items if i.pe_ttm and i.pe_ttm > 0)
    return {
        "date": str(latest_date),
        "total": len(items),
        "has_pe": a_count,
        "items": [
            {
                "code": i.code,
                "close": i.close,
                "pe_ttm": i.pe_ttm,
                "pb": i.pb,
                "market_cap": i.market_cap,
                "turnover": i.turnover,
                "change_pct": i.change_pct,
            }
            for i in items
        ],
    }


@router.post("/collect/snapshot")
def trigger_snapshot():
    """手动触发估值快照采集"""
    from collector import collect_snapshots
    import time
    start = time.time()
    stats = collect_snapshots(verbose=False)
    elapsed = time.time() - start
    return {"ok": True, "elapsed": f"{elapsed:.1f}s", "stats": stats}
