from sqlalchemy import Column, String, Float, Date, DateTime, BigInteger, Text, Integer, Enum as SAEnum, Boolean, UniqueConstraint
from sqlalchemy.sql import func
import enum
from database import Base


class Exchange(str, enum.Enum):
    A_SHENZHEN = "SZ"
    A_SHANGHAI = "SH"
    A_BEIJING = "BJ"
    HK = "HK"
    US = "US"


class Company(Base):
    __tablename__ = "company"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), nullable=False, comment="公司名称")
    exchange = Column(String(5), nullable=False, comment="交易所")
    industry = Column(String(50), comment="行业")
    business_scope = Column(Text, comment="主营业务")
    listing_date = Column(Date, comment="上市日期")
    total_shares = Column(BigInteger, comment="总股本")
    float_shares = Column(BigInteger, comment="流通股本")
    employees = Column(Integer, comment="员工人数")
    website = Column(String(200), comment="公司网址")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FinancialSummary(Base):
    """财务摘要 — 每季度一条，80+指标"""
    __tablename__ = "financial_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True, comment="股票代码")
    report_date = Column(Date, nullable=False, comment="财报截止日")
    indicator = Column(String(50), nullable=False, comment="指标名称（如 营业收入/净利润/总资产...）")
    value = Column(Float, comment="数值")
    updated_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("code", "report_date", "indicator", name="uq_fin_summary"),
    )


class FinancialIndicator(Base):
    """财务指标 — 每季度一条"""
    __tablename__ = "financial_indicator"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    report_date = Column(Date, nullable=False)
    indicator = Column(String(50), nullable=False, comment="指标名")
    value = Column(Float, comment="数值")
    updated_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("code", "report_date", "indicator", name="uq_fin_indicator"),
    )


class Watchlist(Base):
    """自选股"""
    __tablename__ = "watchlist"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), comment="名称（冗余，方便展示）")
    added_at = Column(DateTime, server_default=func.now())
    note = Column(String(200), comment="备注")


class Position(Base):
    """组合持仓"""
    __tablename__ = "position"

    code = Column(String(10), primary_key=True, comment="股票代码")
    name = Column(String(50), comment="名称")
    shares = Column(Float, nullable=False, comment="持仓股数")
    avg_cost = Column(Float, nullable=False, comment="成本均价")
    buy_date = Column(Date, comment="首次买入日期")
    note = Column(String(200), comment="备注")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DailySnapshot(Base):
    """每日估值快照（收盘价+PE/PB/市值）"""
    __tablename__ = "daily_snapshot"

    code = Column(String(10), primary_key=True, comment="股票代码")
    trade_date = Column(Date, primary_key=True, comment="交易日")
    close = Column(Float, comment="收盘价")
    volume = Column(BigInteger, comment="成交量")
    amount = Column(Float, comment="成交额")
    turnover = Column(Float, comment="换手率")
    pe_ttm = Column(Float, comment="动态市盈率")
    pb = Column(Float, comment="市净率")
    market_cap = Column(Float, comment="总市值")
    amplitude = Column(Float, comment="振幅")
    change_pct = Column(Float, comment="涨跌幅")
    updated_at = Column(DateTime, server_default=func.now())


class SectorDaily(Base):
    """行业板块日数据 — 每天 ~500 行，保留 60 天"""
    __tablename__ = "sector_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, comment="交易日")
    board_type = Column(String(10), nullable=False, comment="板块类型: industry(行业) / concept(概念)")
    code = Column(String(10), nullable=False, comment="板块代码 BKxxxx")
    name = Column(String(50), nullable=False, comment="板块名称")
    rank = Column(Integer, comment="排名")
    change_pct = Column(Float, comment="涨跌幅(%)")
    change_amount = Column(Float, comment="涨跌额")
    price = Column(Float, comment="最新价")
    total_market_cap = Column(BigInteger, comment="总市值")
    turnover = Column(Float, comment="换手率(%)")
    up_count = Column(Integer, comment="上涨家数")
    down_count = Column(Integer, comment="下跌家数")
    lead_stock = Column(String(50), comment="领涨股票")
    lead_change = Column(Float, comment="领涨股票涨跌幅")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("trade_date", "board_type", "code", name="uq_sector_day"),
    )
