from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# ── Company ──
class CompanyOut(BaseModel):
    code: str
    name: str
    exchange: str
    industry: Optional[str] = None
    business_scope: Optional[str] = None
    listing_date: Optional[date] = None
    total_shares: Optional[int] = None
    employees: Optional[int] = None
    website: Optional[str] = None

    class Config:
        from_attributes = True


# ── 财务 ──
class FinancialSummaryOut(BaseModel):
    report_date: date
    data: dict  # {指标名: 数值}


class FinancialIndicatorOut(BaseModel):
    report_date: date
    data: dict


# ── Kline（不存库，仅传输）──
class KlineItem(BaseModel):
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: int
    amount: float


# ── 自选股 ──
class WatchlistAdd(BaseModel):
    code: str
    name: Optional[str] = None
    note: Optional[str] = None


class WatchlistOut(BaseModel):
    code: str
    name: Optional[str] = None
    added_at: Optional[datetime] = None
    note: Optional[str] = None


# ── 行情（实时）──
class QuoteItem(BaseModel):
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: Optional[int] = None
    amount: Optional[float] = None


# ── 持仓 ──
class PositionAdd(BaseModel):
    code: str
    name: Optional[str] = None
    shares: float
    avg_cost: float
    buy_date: Optional[date] = None
    note: Optional[str] = None


class PositionOut(BaseModel):
    code: str
    name: Optional[str] = None
    shares: float
    avg_cost: float
    market_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    buy_date: Optional[date] = None
    note: Optional[str] = None
    updated_at: Optional[datetime] = None


# ── 大盘指数 ──
class IndexQuote(BaseModel):
    name: str
    price: float
    change: float
    change_pct: float
