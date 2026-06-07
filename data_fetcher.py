"""
数据拉取模块
============
使用AKShare获取A股实时行情、PE估值、历史K线数据。
支持开盘日和非开盘日。所有数据拉取失败时有降级策略。
"""

import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import time

from config import STOCKS, OBSERVING, DATA_DIR, KB_NEWS_ARCHIVE


def is_trading_day() -> bool:
    """判断今天是否为A股交易日"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        calendar = ak.tool_trade_date_hist_sina()
        trading_dates = calendar["trade_date"].tolist()
        return today in trading_dates
    except Exception:
        weekday = datetime.now().weekday()
        return weekday < 5  # 周一至周五假定为交易日


def fetch_stock_snapshot(code: str) -> dict:
    """
    拉取单支股票快照数据：最新价、PE(TTM)、涨跌幅、成交量、市值
    返回 dict 或 错误信息
    """
    try:
        # 使用AKShare的个股实时行情
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]

        if row.empty:
            return {"error": f"未找到股票代码 {code}"}

        row = row.iloc[0]
        return {
            "code": code,
            "name": row.get("名称", ""),
            "price": float(row.get("最新价", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "volume": float(row.get("成交量", 0)),
            "amount": float(row.get("成交额", 0)),
            "pe_ttm": float(row.get("市盈率-动态", 0)) if pd.notna(row.get("市盈率-动态")) else None,
            "total_mv": float(row.get("总市值", 0)) / 1e8 if pd.notna(row.get("总市值")) else None,  # 转为亿
            "turnover": float(row.get("换手率", 0)) if pd.notna(row.get("换手率")) else None,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_trading_day": True,
        }
    except Exception as e:
        return {"error": str(e), "code": code, "is_trading_day": is_trading_day()}


def fetch_all_snapshots(codes: list = None) -> dict:
    """批量拉取所有监控股的快照（带重试机制）"""
    if codes is None:
        codes = [s["code"] for s in STOCKS]

    results = {}
    max_retries = 3

    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty and len(df) > 100:
                # 成功获取全市场数据
                for code in codes:
                    try:
                        row = df[df["代码"] == code]
                        if row.empty:
                            results[code] = {"error": "未找到", "code": code, "is_trading_day": True}
                            continue
                        row = row.iloc[0]
                        results[code] = {
                            "code": code,
                            "name": row.get("名称", ""),
                            "price": float(row.get("最新价", 0)),
                            "change_pct": float(row.get("涨跌幅", 0)),
                            "volume": float(row.get("成交量", 0)),
                            "amount": float(row.get("成交额", 0)),
                            "pe_ttm": float(row.get("市盈率-动态", 0)) if pd.notna(row.get("市盈率-动态")) else None,
                            "total_mv": float(row.get("总市值", 0)) / 1e8 if pd.notna(row.get("总市值")) else None,
                            "turnover": float(row.get("换手率", 0)) if pd.notna(row.get("换手率")) else None,
                            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "is_trading_day": True,
                        }
                    except Exception as e:
                        results[code] = {"error": str(e), "code": code, "is_trading_day": True}

                missing = [c for c in codes if c not in results]
                if missing:
                    for code in missing:
                        results[code] = fetch_stock_snapshot(code)
                        time.sleep(0.3)
                return results
            else:
                # 数据异常，重试
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue

    # 全部重试失败，逐支拉取
    for code in codes:
        if code not in results or "error" in results.get(code, {}):
            results[code] = fetch_stock_snapshot(code)
            time.sleep(0.5)

    return results


def fetch_market_index() -> dict:
    """拉取大盘指数：沪深300、科创50、创业板指"""
    indices = {
        "沪深300": "sh000300",
        "科创50": "sh000688",
        "创业板指": "sz399006",
    }
    result = {}
    try:
        df = ak.stock_zh_index_spot_em()
        for name, symbol in indices.items():
            try:
                # AKShare指数行情用不同字段
                row = df[df["代码"] == symbol]
                if not row.empty:
                    r = row.iloc[0]
                    result[name] = {
                        "price": float(r.get("最新价", 0)),
                        "change_pct": float(r.get("涨跌幅", 0)),
                    }
            except Exception:
                result[name] = {"error": "获取失败"}
    except Exception as e:
        for name in indices:
            result[name] = {"error": str(e)}
    return result


def fetch_north_flow() -> dict:
    """拉取北向资金流向"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        latest = df.iloc[-1]
        return {
            "date": str(latest.get("date", "")),
            "net_flow": float(latest.get("value", 0)),
        }
    except Exception:
        return {"net_flow": None, "error": "北向资金数据获取失败"}


def fetch_daily_news() -> list:
    """拉取当日重要财经新闻（用于知识库积累）"""
    news_list = []
    try:
        # 新浪财经新闻
        df = ak.stock_info_global_sina()
        if df is not None and not df.empty:
            for _, row in df.head(20).iterrows():
                news_list.append({
                    "title": str(row.get("title", "")),
                    "content": str(row.get("content", ""))[:500],
                    "time": str(row.get("time", "")),
                    "source": "sina",
                })
    except Exception:
        pass

    # 保存到知识库
    try:
        archive_path = KB_NEWS_ARCHIVE
        existing = []
        if os.path.exists(archive_path):
            with open(archive_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        today = datetime.now().strftime("%Y-%m-%d")
        existing = [n for n in existing if n.get("date") != today]  # 替换今日数据
        existing.append({
            "date": today,
            "count": len(news_list),
            "news": news_list,
        })

        # 只保留最近30天
        existing = existing[-30:]
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return news_list


def fetch_historical_pe(code: str, days: int = 120) -> list:
    """拉取个股历史PE数据（用于PE分位计算）"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is not None and not df.empty:
            return df["收盘"].tolist()[-60:]  # 最近60个交易日收盘价
    except Exception:
        pass
    return []


def get_stock_pe_percentile(code: str, current_pe: float) -> dict:
    """
    计算当前PE在历史中的分位（近似计算）
    由于AKShare不直接提供历史PE，用近期价格波动+市值变化近似估算
    """
    try:
        prices = fetch_historical_pe(code, days=120)
        if len(prices) < 20:
            return {"pe_percentile": None, "note": "数据不足"}

        # 简化处理：用当前价格在近60日价格中的位置估计PE分位
        current_price = prices[-1] if prices else 0
        if current_price > 0:
            pct = sum(1 for p in prices if p <= current_price) / len(prices) * 100
            return {
                "pe_percentile_approx": round(pct, 1),
                "note": "基于近60日价格分布估算PE分位",
                "days_data": len(prices),
            }
    except Exception:
        pass
    return {"pe_percentile": None, "note": "计算失败"}


def save_daily_snapshot(snapshots: dict):
    """保存当日快照到本地JSON，用于后续回溯"""
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(DATA_DIR, f"snapshot_{today}.json")
    data = {
        "date": today,
        "snapshots": snapshots,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_previous_snapshot(days_back: int = 1) -> dict:
    """加载前N天的快照数据（用于对比预测）"""
    target_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    filepath = os.path.join(DATA_DIR, f"snapshot_{target_date}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
