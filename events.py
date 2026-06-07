"""
事件日历模块
============
管理行业会议/峰会/新品发布时间表。
每个事件标注影响股票、利好/利空方向、影响程度。
事件后追踪实际影响，更新事件规律知识库。
"""

import json
import os
from datetime import datetime, timedelta

from config import EVENTS, ONGOING_RISKS, STOCKS, DATA_DIR, KB_EVENTS_IMPACT


def get_upcoming_events(days: int = 7) -> list:
    """获取未来N天内即将发生的事件"""
    today = datetime.now().strftime("%Y-%m-%d")
    deadline = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    upcoming = []
    for evt in EVENTS:
        if today <= evt["date"] <= deadline:
            upcoming.append(evt)

    return sorted(upcoming, key=lambda x: x["date"])


def get_events_by_stock(code: str, days: int = 30) -> list:
    """获取某支股票未来N天内的事件"""
    upcoming = get_upcoming_events(days)
    stock_events = []
    for evt in upcoming:
        if code in evt.get("affected_stocks", []) or "ALL" in evt.get("affected_stocks", []):
            stock_events.append(evt)
    return stock_events


def calculate_event_signal(code: str) -> dict:
    """
    计算某支股票的事件信号得分。
    综合考虑：
    - 未来7天利好事件数量+程度
    - 未来7天利空事件数量+程度
    - 刚发生过的事件（买预期卖事实效应）
    返回 -1.0 到 +1.0 的信号分数
    """
    events = get_events_by_stock(code, days=7)
    if not events:
        return {"signal": 0.0, "reason": "未来7天无直接事件", "events": []}

    score = 0.0
    details = []

    for evt in events:
        impact_map = {"high": 0.3, "medium": 0.2, "low": 0.1}
        weight = impact_map.get(evt.get("impact_level", "low"), 0.1)

        if evt.get("impact") == "bullish":
            score += weight
            details.append(f"+{weight}:{evt['title']}")
        elif evt.get("impact") == "bearish":
            score -= weight
            details.append(f"-{weight}:{evt['title']}")
        else:
            details.append(f"0:{evt['title']}")

    # 限制在 [-1, 1]
    score = max(-1.0, min(1.0, score))

    # 判断逻辑
    if score > 0.3:
        reason = f"未来7天有{len(events)}个事件,偏利好(得分{score})"
    elif score < -0.3:
        reason = f"未来7天有{len(events)}个事件,偏利空(得分{score})"
    else:
        reason = f"未来7天有{len(events)}个事件,整体中性(得分{score})"

    return {
        "signal": score,
        "reason": reason,
        "events": [e["title"] for e in events],
        "details": details,
    }


def get_ongoing_risks(code: str) -> list:
    """获取影响特定股票的持续性风险"""
    risks = []
    for risk in ONGOING_RISKS:
        if code in risk.get("affected_stocks", []):
            risks.append(risk)
    return risks


def track_event_outcome(event_title: str, pre_prediction: str, actual_result: str):
    """
    追踪事件的实际影响。
    事件发生后，记录预判 vs 实际，用于优化未来事件判断。
    """
    record = {
        "event": event_title,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "pre_prediction": pre_prediction,
        "actual_result": actual_result,
        "correct": pre_prediction == actual_result,
    }

    try:
        existing = []
        if os.path.exists(KB_EVENTS_IMPACT):
            with open(KB_EVENTS_IMPACT, "r", encoding="utf-8") as f:
                existing = json.load(f)

        existing.append(record)
        # 保留最近200条
        existing = existing[-200:]

        with open(KB_EVENTS_IMPACT, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return record


def get_event_patterns(code: str) -> dict:
    """从知识库中提取某支股票对事件的历史反应规律"""
    try:
        if not os.path.exists(KB_EVENTS_IMPACT):
            return {"patterns_found": 0, "patterns": []}

        with open(KB_EVENTS_IMPACT, "r", encoding="utf-8") as f:
            records = json.load(f)

        # 分析事件类型 vs 实际反应
        total = len(records)
        correct = sum(1 for r in records if r.get("correct"))
        accuracy = round(correct / total * 100, 1) if total > 0 else 0

        return {
            "patterns_found": total,
            "overall_accuracy": accuracy,
            "recent_events": records[-10:] if records else [],
        }
    except Exception:
        return {"patterns_found": 0, "patterns": []}


def generate_event_summary() -> str:
    """生成事件摘要，用于日报"""
    upcoming = get_upcoming_events(7)
    if not upcoming:
        return "未来7天无重大行业事件。"

    lines = []
    for evt in upcoming:
        impact_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}
        level_emoji = {"high": "★★★", "medium": "★★☆", "low": "★☆☆"}
        emoji = impact_emoji.get(evt.get("impact", "neutral"), "⚪")
        level = level_emoji.get(evt.get("impact_level", "low"), "★☆☆")

        affected_names = []
        for code in evt.get("affected_stocks", []):
            if code == "ALL":
                affected_names = ["全部"]
                break
            for s in STOCKS:
                if s["code"] == code:
                    affected_names.append(s["name"])

        line = f"{emoji} {evt['date']} {evt['title']} {level}\n"
        line += f"   影响: {', '.join(affected_names)} | {evt.get('logic', '')}"
        lines.append(line)

    return "\n".join(lines)


def get_next_major_event() -> dict:
    """获取下一个重大事件（影响程度为high的）"""
    upcoming = get_upcoming_events(30)
    for evt in upcoming:
        if evt.get("impact_level") == "high":
            days_left = (datetime.strptime(evt["date"], "%Y-%m-%d") - datetime.now()).days
            evt["days_left"] = days_left
            return evt
    return None
