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
    exchange: str = Query("", description="SZ/SH/HK/A"),
    db: Session = Depends(get_db),
):
    from models import StockList as CompanyModel
    q = db.query(CompanyModel)
    if keyword:
        q = q.filter(CompanyModel.name.like(f"%{keyword}%"))
    if exchange == "HK":
        q = q.filter(CompanyModel.exchange == "HK")
    elif exchange == "A":
        q = q.filter(CompanyModel.exchange.in_(["SZ", "SH"]))
    elif exchange:
        q = q.filter(CompanyModel.exchange == exchange)
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
    from models import FinancialSummary

    summaries = db.query(FinancialSummary).filter(
        FinancialSummary.code == code
    ).all()

    # 按 report_date 聚合
    sum_by_date = {}
    for s in summaries:
        d = str(s.report_date)
        if d not in sum_by_date:
            sum_by_date[d] = {}
        sum_by_date[d][s.indicator] = s.value

    return {"summary": sum_by_date}


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


# ── 板块数据 ──
@router.get("/sectors")
def list_sectors(
    board_type: str = Query("industry", description="industry / concept"),
    trade_date: str = Query("", description="指定日期 YYYY-MM-DD，默认最新"),
    sort_by: str = Query("change_pct", description="排序字段"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """获取行业/概念板块排行"""
    from models import SectorDaily
    from sqlalchemy import func as sa_func

    q = db.query(SectorDaily)
    if board_type:
        q = q.filter(SectorDaily.board_type == board_type)
    if trade_date:
        q = q.filter(SectorDaily.trade_date == trade_date)
    else:
        # 取最新日期
        latest_date = db.query(sa_func.max(SectorDaily.trade_date)).filter(
            SectorDaily.board_type == board_type
        ).scalar()
        if latest_date:
            q = q.filter(SectorDaily.trade_date == latest_date)

    if sort_by in ("change_pct", "up_count", "turnover", "total_market_cap"):
        q = q.order_by(getattr(SectorDaily, sort_by).desc())

    items = q.limit(limit).all()
    date_str = str(items[0].trade_date) if items else None
    return {
        "trade_date": date_str,
        "board_type": board_type,
        "total": len(items),
        "items": [
            {
                "code": i.code,
                "name": i.name,
                "rank": i.rank,
                "change_pct": i.change_pct,
                "price": i.price,
                "turnover": i.turnover,
                "up_count": i.up_count,
                "down_count": i.down_count,
                "total_market_cap": i.total_market_cap,
                "lead_stock": i.lead_stock,
                "lead_change": i.lead_change,
            }
            for i in items
        ],
    }


@router.get("/sectors/{code}/history")
def sector_history(
    code: str,
    days: int = Query(60, ge=1, le=120),
    db: Session = Depends(get_db),
):
    """获取单板块的历史日数据"""
    from models import SectorDaily
    q = db.query(SectorDaily).filter(
        SectorDaily.code == code
    ).order_by(SectorDaily.trade_date.desc()).limit(days)
    items = q.all()
    return {
        "code": code,
        "name": items[0].name if items else "",
        "items": [
            {
                "trade_date": str(i.trade_date),
                "change_pct": i.change_pct,
                "up_count": i.up_count,
                "down_count": i.down_count,
                "turnover": i.turnover,
            }
            for i in items
        ],
    }


@router.post("/collect/sector")
def trigger_sector_collect():
    """手动触发板块数据采集"""
    from collector import collect_sectors
    import time
    start = time.time()
    stats = collect_sectors(verbose=False)
    elapsed = time.time() - start
    return {
        "ok": True,
        "elapsed": f"{elapsed:.1f}s",
        "stats": stats,
    }


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
    from models import Company, StockList
    from database import SessionLocal

    db = SessionLocal()
    # 优先查 Company 表，再查 StockList 表
    c = db.query(Company).filter(Company.code == code).first()
    if not c:
        s = db.query(StockList).filter(StockList.code == code).first()
        exchange = s.exchange if s else "SZ"
        name = s.name if s else code
    else:
        exchange = c.exchange
        name = c.name
    db.close()

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
def latest_snapshots(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    sort_by: str = Query("market_cap", description="排序字段"),
    sort_desc: bool = Query(True, description="是否降序"),
    exchange: str = Query("", description="SZ/SH/HK"),
    keyword: str = Query("", description="按名称或代码搜索"),
):
    """获取最新快照（服务端分页 + 排序）"""
    from models import DailySnapshot, StockList
    from sqlalchemy import func as sa_func

    latest_date = db.query(sa_func.max(DailySnapshot.trade_date)).scalar()
    if not latest_date:
        return {"date": None, "total": 0, "has_pe": 0, "items": []}

    q = db.query(
        DailySnapshot, StockList.name
    ).outerjoin(
        StockList, DailySnapshot.code == StockList.code
    ).filter(DailySnapshot.trade_date == latest_date)

    if exchange == "HK":
        q = q.filter(StockList.exchange == "HK")
    elif exchange == "A":
        q = q.filter(StockList.exchange.in_(["SZ", "SH"]))
    elif exchange:
        q = q.filter(StockList.exchange == exchange)

    if keyword:
        q = q.filter(
            StockList.name.like(f"%{keyword}%") |
            DailySnapshot.code.like(f"%{keyword}%")
        )

    # 总条数
    total = q.count()
    has_pe = q.filter(DailySnapshot.pe_ttm.isnot(None)).count()

    # 排序
    sort_col = getattr(DailySnapshot, sort_by, DailySnapshot.market_cap)
    q = q.order_by(sort_col.desc() if sort_desc else sort_col.asc())

    # 分页
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "date": str(latest_date),
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_pe": has_pe,
        "items": [
            {
                "code": s.code,
                "name": name or s.code,
                "close": s.close,
                "pe_ttm": s.pe_ttm,
                "pb": s.pb,
                "market_cap": s.market_cap,
                "turnover": s.turnover,
                "change_pct": s.change_pct,
            }
            for s, name in rows
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
