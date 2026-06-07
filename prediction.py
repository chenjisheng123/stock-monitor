"""
预测引擎
========
多因子预测模型 + 知识库推理。
- 开盘日：PE位置 + 动量 + 事件 + 板块 + 大盘 → 预测涨跌
- 非开盘日：事件 + 新闻情绪 → 预测"如果明天开盘"的走向
- 支持自动发现新因子
- 每个预测包含完整推理链路
"""

import json
import os
import math
from datetime import datetime, timedelta

from config import (
    STOCKS, FACTOR_WEIGHTS, FACTOR_DESCRIPTIONS,
    KB_PREDICTIONS, KB_DISCOVERED_FACTORS, KB_STOCK_PATTERNS,
    DATA_DIR, get_stock_by_code,
)
from data_fetcher import is_trading_day


# ============================================================
# 一、五大核心因子
# ============================================================

def factor_pe_position(stock: dict, pe_ttm: float) -> float:
    """
    因子1：PE位置信号
    逻辑：PE越接近合理区下沿越看涨（价值回归），越接近高位区上沿越看跌
    返回 -1.0 ~ 1.0
    """
    if pe_ttm is None or pe_ttm <= 0:
        return 0.0

    reasonable_low, reasonable_high = stock["pe_reasonable"]
    high_low, high_high = stock["pe_high"]

    if pe_ttm <= reasonable_low:
        # PE极低，强烈看涨
        ratio = pe_ttm / reasonable_low
        return min(1.0, (1 - ratio) * 2 + 0.5)  # 0.5 ~ 1.0
    elif pe_ttm <= reasonable_high:
        # PE在合理区间内，中性偏多
        progress = (pe_ttm - reasonable_low) / (reasonable_high - reasonable_low)
        return 0.3 - progress * 0.3  # 0.0 ~ 0.3
    elif pe_ttm <= high_low:
        # PE在合理区以上但未到高位，中性偏空
        progress = (pe_ttm - reasonable_high) / (high_low - reasonable_high)
        return 0.0 - progress * 0.5  # 0.0 ~ -0.5
    elif pe_ttm <= high_high:
        # PE进入高位区，偏空
        progress = (pe_ttm - high_low) / (high_high - high_low)
        return -0.5 - progress * 0.3  # -0.5 ~ -0.8
    else:
        # PE远超高位，强烈看跌
        ratio = pe_ttm / high_high
        return max(-1.0, -0.8 - (ratio - 1) * 0.5)  # -0.8 ~ -1.0


def factor_momentum(snapshot: dict, prev_snapshot: dict) -> float:
    """
    因子2：短期动量信号
    逻辑：近5日涨跌幅 + 成交量变化
    连续下跌后反弹概率增加（均值回归），连续上涨后回调概率增加
    """
    if not prev_snapshot:
        return 0.0

    prev_price = prev_snapshot.get("price", 0)
    cur_price = snapshot.get("price", 0)
    if prev_price <= 0:
        return 0.0

    change_pct = (cur_price - prev_price) / prev_price * 100

    # 单日涨跌幅转信号
    if change_pct > 5:
        return -0.3   # 暴涨后回调风险
    elif change_pct > 2:
        return 0.2    # 温和上涨，趋势延续
    elif change_pct > 0:
        return 0.1    # 微涨
    elif change_pct > -2:
        return -0.1   # 微跌
    elif change_pct > -5:
        return -0.2   # 温和下跌
    else:
        return 0.3    # 暴跌后反弹概率


def factor_event(stock: dict) -> float:
    """
    因子3：事件临近信号
    逻辑：未来7天有利好事件→看涨，利好事件刚过→看跌（买预期卖事实）
    """
    from events import calculate_event_signal, get_events_by_stock

    event_result = calculate_event_signal(stock["code"])
    base_signal = event_result["signal"]

    # 检查是否有刚过去的事件（3天内的）
    from events import EVENTS
    today = datetime.now().strftime("%Y-%m-%d")
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    for evt in EVENTS:
        if stock["code"] in evt.get("affected_stocks", []):
            if three_days_ago <= evt["date"] < today:
                # 事件刚过，如果之前是利好，可能有"卖事实"效应
                if evt.get("impact") == "bullish":
                    base_signal -= 0.15
                elif evt.get("impact") == "bearish":
                    base_signal += 0.15  # 利空出尽

    return max(-1.0, min(1.0, base_signal))


def factor_sector(snapshot: dict, all_snapshots: dict, stock: dict) -> float:
    """
    因子4：板块联动信号
    逻辑：同行业其他股票如果整体走强，该股有跟随效应
    """
    industry = stock.get("industry", "")
    same_sector_changes = []

    for code, snap in all_snapshots.items():
        if code == stock["code"]:
            continue
        s = get_stock_by_code(code)
        if s and s.get("industry") == industry:
            chg = snap.get("change_pct", 0)
            if chg is not None:
                same_sector_changes.append(chg)

    if not same_sector_changes:
        return 0.0

    avg_change = sum(same_sector_changes) / len(same_sector_changes)

    # 板块整体涨跌转信号
    if avg_change > 2:
        return 0.3
    elif avg_change > 1:
        return 0.15
    elif avg_change > 0:
        return 0.05
    elif avg_change > -1:
        return -0.05
    elif avg_change > -2:
        return -0.15
    else:
        return -0.3


def factor_market(market_indices: dict) -> float:
    """
    因子5：大盘情绪信号
    逻辑：沪深300+科创50走势反映整体市场风险偏好
    """
    if not market_indices:
        return 0.0

    changes = []
    for name, data in market_indices.items():
        chg = data.get("change_pct", 0)
        if chg is not None:
            changes.append(chg)

    if not changes:
        return 0.0

    avg_change = sum(changes) / len(changes)

    if avg_change > 1.5:
        return 0.3   # 大盘强势，跟涨概率大
    elif avg_change > 0.5:
        return 0.15
    elif avg_change > -0.5:
        return 0.0
    elif avg_change > -1.5:
        return -0.15
    else:
        return -0.3  # 大盘弱势


# ============================================================
# 二、综合预测
# ============================================================

def predict_stock(stock: dict, snapshot: dict, all_snapshots: dict,
                  market_indices: dict, prev_snapshot: dict = None,
                  weights: dict = None) -> dict:
    """
    对单支股票进行综合预测。
    返回完整预测结果，包含每个因子的贡献和推理链路。
    """
    if weights is None:
        weights = FACTOR_WEIGHTS.copy()

    pe_ttm = snapshot.get("pe_ttm")
    code = stock["code"]
    name = stock["name"]

    # 计算各因子得分
    f1 = factor_pe_position(stock, pe_ttm) if pe_ttm else 0.0
    f2 = factor_momentum(snapshot, prev_snapshot)
    f3 = factor_event(stock)
    f4 = factor_sector(snapshot, all_snapshots, stock)
    f5 = factor_market(market_indices)

    # 加权求和
    total_score = (
        f1 * weights.get("pe_position", 0.25) +
        f2 * weights.get("momentum", 0.20) +
        f3 * weights.get("event_proximity", 0.25) +
        f4 * weights.get("sector_correlation", 0.15) +
        f5 * weights.get("market_sentiment", 0.15)
    )

    # 归一化（因为权重和可能不为1）
    weight_sum = sum(weights.values())
    if weight_sum > 0:
        total_score = total_score / weight_sum * 5  # 归一化到 -1 ~ 1
        total_score = max(-1.0, min(1.0, total_score))

    # 判定方向
    if total_score > 0.15:
        direction = "涨"
    elif total_score < -0.15:
        direction = "跌"
    else:
        direction = "平"

    # 置信度
    confidence = abs(total_score)
    if confidence > 0.5:
        confidence_level = "高"
    elif confidence > 0.25:
        confidence_level = "中"
    else:
        confidence_level = "低"

    # 找出主导因子
    factor_scores = {
        "PE位置": (f1, weights.get("pe_position", 0.25)),
        "短期动量": (f2, weights.get("momentum", 0.20)),
        "事件驱动": (f3, weights.get("event_proximity", 0.25)),
        "板块联动": (f4, weights.get("sector_correlation", 0.15)),
        "大盘情绪": (f5, weights.get("market_sentiment", 0.15)),
    }

    weighted_scores = {k: v[0] * v[1] for k, v in factor_scores.items()}
    dominant_factor = max(weighted_scores, key=lambda x: abs(weighted_scores[x]))

    # 构建推理链路
    reasoning = build_reasoning(name, factor_scores, total_score, direction, stock)

    return {
        "code": code,
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "is_trading_day": snapshot.get("is_trading_day", True),
        "current_price": snapshot.get("price"),
        "current_pe": pe_ttm,
        "pe_reasonable_zone": stock["pe_reasonable"],
        "pe_high_zone": stock["pe_high"],
        "factor_scores": {
            "pe_position": round(f1, 3),
            "momentum": round(f2, 3),
            "event_proximity": round(f3, 3),
            "sector_correlation": round(f4, 3),
            "market_sentiment": round(f5, 3),
        },
        "total_score": round(total_score, 3),
        "direction": direction,
        "confidence": round(confidence, 3),
        "confidence_level": confidence_level,
        "dominant_factor": dominant_factor,
        "reasoning": reasoning,
    }


def build_reasoning(name: str, factor_scores: dict, total_score: float,
                    direction: str, stock: dict) -> str:
    """构建人类可读的推理链路"""
    parts = []

    for factor_name, (score, weight) in factor_scores.items():
        if abs(score) > 0.1:
            direction_word = "看多" if score > 0 else "看空"
            parts.append(f"{factor_name}:{direction_word}({score:.2f},权重{weight:.0%})")

    reasoning = f"{name}综合得分{total_score:.2f},判断明日「{direction}」\n"
    reasoning += "因子分解: " + " | ".join(parts) if parts else "各因子信号均不显著"
    reasoning += f"\nPE合理区{stock['pe_reasonable']},PE高位区{stock['pe_high']}"

    return reasoning


def predict_all_stocks(snapshots: dict, market_indices: dict,
                       prev_snapshots: dict = None) -> list:
    """
    对所有活跃股票进行预测。
    1. 加载当前因子权重（可能已被系统调整过）
    2. 加载知识库中的个股规律
    3. 对每支股执行预测
    4. 如果有自动发现的因子，也加入计算
    """
    # 加载当前权重
    weights = FACTOR_WEIGHTS.copy()
    accuracy_file = os.path.join(DATA_DIR, "accuracy.json")
    if os.path.exists(accuracy_file):
        try:
            with open(accuracy_file, "r", encoding="utf-8") as f:
                acc_data = json.load(f)
            if "current_weights" in acc_data:
                weights = acc_data["current_weights"]
        except Exception:
            pass

    # 加载自动发现的因子
    discovered_factors = load_discovered_factors()

    predictions = []
    for stock in STOCKS:
        if stock["status"] != "active":
            continue

        code = stock["code"]
        snapshot = snapshots.get(code, {})
        if "error" in snapshot:
            predictions.append({
                "code": code, "name": stock["name"],
                "error": snapshot["error"],
                "date": datetime.now().strftime("%Y-%m-%d"),
            })
            continue

        prev = prev_snapshots.get(code) if prev_snapshots else None
        result = predict_stock(stock, snapshot, snapshots, market_indices, prev, weights)

        # 如果有发现的新因子，追加其影响
        if discovered_factors:
            for df_name, df_config in discovered_factors.items():
                if df_config.get("enabled", False):
                    extra_score = apply_discovered_factor(df_name, df_config, stock, snapshot)
                    if extra_score != 0:
                        result["factor_scores"][df_name] = round(extra_score, 3)

        predictions.append(result)

    return predictions


# ============================================================
# 三、非交易日预测
# ============================================================

def predict_non_trading_day(news_list: list = None) -> list:
    """
    非交易日：基于当日新闻+即将来临的事件，预测"如果明天开盘"的走势
    """
    if news_list is None:
        from data_fetcher import fetch_daily_news
        news_list = fetch_daily_news()

    predictions = []
    for stock in STOCKS:
        if stock["status"] != "active":
            continue

        # 非交易日主要看事件信号
        from events import calculate_event_signal, get_events_by_stock
        event_result = calculate_event_signal(stock["code"])
        event_score = event_result["signal"]

        # 简单新闻分析（基于关键词匹配）
        news_score = analyze_news_for_stock(stock, news_list)

        total = event_score * 0.6 + news_score * 0.4
        direction = "涨" if total > 0.1 else ("跌" if total < -0.1 else "平")

        predictions.append({
            "code": stock["code"],
            "name": stock["name"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "is_trading_day": False,
            "direction": direction,
            "confidence": round(abs(total), 3),
            "reasoning": f"非交易日预测: 事件信号{event_score:.2f} + 新闻信号{news_score:.2f}",
            "events": event_result.get("events", []),
        })

    return predictions


def analyze_news_for_stock(stock: dict, news_list: list) -> float:
    """简单新闻情绪分析（关键词匹配）"""
    if not news_list:
        return 0.0

    name = stock["name"]
    industry = stock.get("industry", "")
    industry_keywords = {
        "新能源车": ["新能源", "电动车", "智能驾驶", "自动驾驶"],
        "芯片设计": ["芯片", "半导体", "MCU", "Flash"],
        "存储模组": ["存储", "NAND", "DRAM", "SSD"],
        "光器件": ["光模块", "光通信", "800G", "1.6T"],
        "CIS芯片": ["CIS", "摄像头", "图像传感器"],
        "半导体设备": ["设备", "刻蚀", "薄膜", "晶圆厂"],
        "内存接口": ["DDR5", "内存", "接口"],
        "刻蚀设备": ["刻蚀", "薄膜沉积", "设备"],
        "封装测试": ["封装", "封测", "先进封装"],
        "存储+封测": ["存储", "封装", "封测"],
        "智驾域控": ["智能驾驶", "域控", "自动驾驶"],
        "存储分销": ["存储", "分销", "SK海力士"],
    }

    keywords = industry_keywords.get(industry, []) + [name]
    score = 0.0

    for news in news_list:
        title = news.get("title", "")
        for kw in keywords:
            if kw in title:
                score += 0.05  # 提及即可，轻微正偏
                break

    return max(-0.5, min(0.5, score))


# ============================================================
# 四、知识库：自动发现新因子
# ============================================================

def load_discovered_factors() -> dict:
    """加载系统自动发现的因子"""
    if os.path.exists(KB_DISCOVERED_FACTORS):
        try:
            with open(KB_DISCOVERED_FACTORS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_discovered_factors(factors: dict):
    """保存自动发现的因子"""
    with open(KB_DISCOVERED_FACTORS, "w", encoding="utf-8") as f:
        json.dump(factors, f, ensure_ascii=False, indent=2)


def apply_discovered_factor(name: str, config: dict, stock: dict, snapshot: dict) -> float:
    """应用自动发现的因子"""
    # 简化版：根据因子类型计算得分
    factor_type = config.get("type", "")
    if factor_type == "news_sentiment":
        return config.get("base_score", 0.0)
    elif factor_type == "volume_pattern":
        # 量价关系
        turnover = snapshot.get("turnover", 0) or 0
        if turnover > config.get("threshold", 5):
            return config.get("signal", 0.1)
    elif factor_type == "price_pattern":
        change = snapshot.get("change_pct", 0) or 0
        threshold = config.get("threshold", 2)
        if abs(change) > threshold:
            return -config.get("signal", 0.1)  # 反向信号
    return 0.0


def discover_new_factors() -> list:
    """
    分析近期预测记录，自动发现新的有效因子。
    返回新发现的因子列表。
    每周运行一次。
    """
    if not os.path.exists(KB_PREDICTIONS):
        return []

    try:
        with open(KB_PREDICTIONS, "r", encoding="utf-8") as f:
            records = json.load(f)

        if len(records) < 20:
            return []  # 数据不够，不分析

        discovered = load_discovered_factors()
        new_factors = []

        # 候选因子：换手率异常
        high_turnover_correct = 0
        high_turnover_total = 0
        for r in records[-30:]:
            if r.get("turnover", 0) > 5:
                high_turnover_total += 1
                if r.get("correct"):
                    high_turnover_correct += 1

        if high_turnover_total >= 5:
            accuracy = high_turnover_correct / high_turnover_total
            if accuracy > 0.6:
                factor_name = "volume_anomaly"
                discovered[factor_name] = {
                    "name": "成交量异常信号",
                    "type": "volume_pattern",
                    "threshold": 5,
                    "signal": 0.15,
                    "accuracy": round(accuracy, 3),
                    "discovered_date": datetime.now().strftime("%Y-%m-%d"),
                    "enabled": True,
                }
                new_factors.append(f"发现新因子:{factor_name}(准确率{accuracy:.0%})")

        # 候选因子：连续涨跌
        # ... 更多自动发现逻辑可以在进化过程中扩展

        save_discovered_factors(discovered)
        return new_factors

    except Exception as e:
        return [f"因子发现出错: {str(e)}"]


def save_predictions(predictions: list):
    """保存预测到知识库"""
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        existing = []
        if os.path.exists(KB_PREDICTIONS):
            with open(KB_PREDICTIONS, "r", encoding="utf-8") as f:
                existing = json.load(f)

        # 替换今日预测
        existing = [p for p in existing if p.get("date") != today]
        existing.extend(predictions)

        with open(KB_PREDICTIONS, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存预测记录失败: {e}")
