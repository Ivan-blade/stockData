"""AKShare 数据封装层 — 所有外部数据源的唯一入口"""

import akshare as ak
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime, date


def get_company_profile(code: str) -> dict:
    """获取公司简介（A股）"""
    try:
        df = ak.stock_profile_cninfo(symbol=code)
        if df.empty:
            return {}
        row = df.iloc[0]
        return {
            "code": code,
            "name": row.get("A股简称", row.get("证券简称", "")),
            "industry": row.get("所属行业", ""),
            "business_scope": row.get("经营范围", ""),
            "listing_date": str(row.get("上市日期", "")),
            "employees": int(row["员工总数"]) if "员工总数" in row and pd.notna(row.get("员工总数")) else None,
            "website": row.get("官方网站", row.get("公司网址", "")),
        }
    except Exception as e:
        return {"error": str(e)}


def get_financial_summary(code: str) -> List[dict]:
    """获取财务摘要 — 返回 [{report_date, indicator, value}, ...]"""
    try:
        df = ak.stock_financial_abstract(symbol=code)
        # df: 指标名作行，日期作列 → 转长格式
        df = df.set_index(["选项", "指标"])
        records = []
        for col in df.columns:  # 每一列 = 一个报告期
            try:
                rd = datetime.strptime(col, "%Y%m%d").date()
            except:
                continue
            for idx in df.index:
                val = df.loc[idx, col]
                if pd.notna(val):
                    indicator = idx[1]  # 指标名称
                    try:
                        numeric = float(val)
                        records.append({
                            "report_date": rd.isoformat(),
                            "indicator": indicator,
                            "value": numeric,
                        })
                    except (ValueError, TypeError):
                        pass
        return records
    except Exception as e:
        return [{"error": str(e)}]


def get_financial_indicators(code: str) -> List[dict]:
    """获取86项财务指标"""
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code)
        # df: 列为指标名，行为报告期
        records = []
        for _, row in df.iterrows():
            rd = row.get("日期", "")
            try:
                rd_date = datetime.strptime(str(rd), "%Y%m%d").date()
            except:
                continue
            for col in df.columns:
                if col == "日期":
                    continue
                val = row[col]
                if pd.notna(val):
                    try:
                        records.append({
                            "report_date": rd_date.isoformat(),
                            "indicator": col,
                            "value": float(val),
                        })
                    except:
                        pass
        return records
    except Exception as e:
        return [{"error": str(e)}]


def get_business_composition(code: str) -> dict:
    """主营业务构成（按产品/地区）"""
    result = {}
    try:
        for indicator in ["按产品", "按地区"]:
            df = ak.stock_zygc_em(symbol=f"sz{code}", indicator=indicator)
            result[indicator] = df.to_dict(orient="records")
    except:
        result = {}
    return result


async def get_kline(code: str, exchange: str, start: str, end: str) -> list:
    """获取日K — 实时转发，不存库"""
    try:
        if exchange == "HK":
            df = ak.stock_hk_hist(symbol=code, period="daily",
                                  start_date=start, end_date=end)
        else:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date=end)
        return df.to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


async def get_realtime_quote(codes: List[str]) -> List[dict]:
    """获取实时行情"""
    try:
        df_a = ak.stock_zh_a_spot_em()
        df_hk = ak.stock_hk_spot_em()
        results = []
        for code in codes:
            row = df_a[df_a["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    "code": code,
                    "name": r.get("名称", ""),
                    "price": float(r.get("最新价", 0)),
                    "change": float(r.get("涨跌额", 0)),
                    "change_pct": float(r.get("涨跌幅", 0)),
                    "volume": int(r.get("成交量", 0)),
                    "amount": float(r.get("成交额", 0)),
                })
                continue
            row_hk = df_hk[df_hk["代码"] == code]
            if not row_hk.empty:
                r = row_hk.iloc[0]
                results.append({
                    "code": code,
                    "name": r.get("名称", ""),
                    "price": float(r.get("最新价", 0)),
                    "change": float(r.get("涨跌额", 0)),
                    "change_pct": float(r.get("涨跌幅", 0)),
                    "volume": int(r.get("成交量", 0)),
                    "amount": float(r.get("成交额", 0)),
                })
        return results
    except Exception as e:
        return [{"error": str(e)}]


async def get_indices() -> List[dict]:
    """获取大盘指数行情"""
    try:
        df = ak.stock_zh_index_spot_em()
        targets = {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006",
            "科创50": "sh000688",
        }
        results = []
        for name, code in targets.items():
            row = df[df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    "name": name,
                    "price": float(r.get("最新价", 0)),
                    "change": float(r.get("涨跌额", 0)),
                    "change_pct": float(r.get("涨跌幅", 0)),
                })
        return results
    except Exception as e:
        return [{"error": str(e)}]
