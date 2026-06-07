"""
进化引擎
========
1. 每日验证预测 → 计算准确率
2. 每周调整因子权重
3. 自动发现新因子
4. 更新知识库
"""

import json
import os
from datetime import datetime, timedelta

from config import (
    FACTOR_WEIGHTS, FACTOR_DESCRIPTIONS,
    KB_PREDICTIONS, KB_ACCURACY, DATA_DIR,
)


def verify_yesterday_predictions(today_snapshots: dict) -> dict:
    """
    验证昨日预测 vs 今日实际。
    从预测记录中找到昨天的预测，对比今天实际涨跌。
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        if not os.path.exists(KB_PREDICTIONS):
            return {"status": "no_history", "message": "尚无预测历史"}

        with open(KB_PREDICTIONS, "r", encoding="utf-8") as f:
            records = json.load(f)

        # 找昨天的预测
        yesterday_preds = [r for r in records if r.get("date") == yesterday]
        if not yesterday_preds:
            return {"status": "no_prediction", "message": f"昨日({yesterday})无预测记录"}

        # 也找前天的快照（用于计算实际涨跌）
        prev_snapshots = {}
        prev_file = os.path.join(DATA_DIR, f"snapshot_{yesterday}.json")
        if os.path.exists(prev_file):
            with open(prev_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
            prev_snapshots = prev_data.get("snapshots", {})

        results = []
        correct_count = 0
        total = 0

        for pred in yesterday_preds:
            if "error" in pred:
                continue

            code = pred.get("code")
            predicted_dir = pred.get("direction")
            today_snap = today_snapshots.get(code, {})

            if "error" in today_snap or not today_snap.get("price"):
                continue

            yesterday_snap = prev_snapshots.get(code, {})
            yesterday_price = yesterday_snap.get("price", 0)
            today_price = today_snap.get("price", 0)

            if yesterday_price <= 0:
                continue

            actual_change = (today_price - yesterday_price) / yesterday_price * 100
            if actual_change > 0.3:
                actual_dir = "涨"
            elif actual_change < -0.3:
                actual_dir = "跌"
            else:
                actual_dir = "平"

            correct = (predicted_dir == actual_dir)
            if correct:
                correct_count += 1
            total += 1

            # 更新预测记录的验证结果
            pred["verified"] = True
            pred["actual_direction"] = actual_dir
            pred["actual_change_pct"] = round(actual_change, 2)
            pred["correct"] = correct

            results.append(pred)

        # 保存回预测历史
        for i, r in enumerate(records):
            for vr in results:
                if r.get("date") == vr.get("date") and r.get("code") == vr.get("code"):
                    records[i] = vr

        with open(KB_PREDICTIONS, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        accuracy = round(correct_count / total * 100, 1) if total > 0 else 0

        return {
            "status": "verified",
            "date": yesterday,
            "total": total,
            "correct": correct_count,
            "accuracy": accuracy,
            "details": results,
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_accuracy_stats() -> dict:
    """获取历史准确率统计"""
    if not os.path.exists(KB_PREDICTIONS):
        return {"total_predictions": 0, "overall_accuracy": 0}

    try:
        with open(KB_PREDICTIONS, "r", encoding="utf-8") as f:
            records = json.load(f)

        verified = [r for r in records if r.get("verified")]
        if not verified:
            return {"total_predictions": len(records), "overall_accuracy": 0, "note": "尚无验证数据"}

        correct = sum(1 for r in verified if r.get("correct"))
        total = len(verified)

        # 按股票统计
        by_stock = {}
        for r in verified:
            code = r.get("code")
            name = r.get("name", code)
            if code not in by_stock:
                by_stock[code] = {"name": name, "correct": 0, "total": 0}
            by_stock[code]["total"] += 1
            if r.get("correct"):
                by_stock[code]["correct"] += 1

        for code in by_stock:
            by_stock[code]["accuracy"] = round(
                by_stock[code]["correct"] / by_stock[code]["total"] * 100, 1
            )

        # 按日期统计（最近30天）
        by_date = {}
        for r in verified:
            date = r.get("date", "")
            if date not in by_date:
                by_date[date] = {"correct": 0, "total": 0}
            by_date[date]["total"] += 1
            if r.get("correct"):
                by_date[date]["correct"] += 1

        date_stats = []
        for date in sorted(by_date.keys())[-30:]:
            d = by_date[date]
            date_stats.append({
                "date": date,
                "accuracy": round(d["correct"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
                "total": d["total"],
            })

        return {
            "total_predictions": total,
            "overall_accuracy": round(correct / total * 100, 1) if total > 0 else 0,
            "by_stock": by_stock,
            "by_date": date_stats,
            "recent_30d_accuracy": round(
                sum(d["correct"] for d in by_date.values()) /
                sum(d["total"] for d in by_date.values()) * 100, 1
            ) if by_date else 0,
        }

    except Exception as e:
        return {"error": str(e)}


def adjust_factor_weights() -> dict:
    """
    自动调整因子权重。
    分析每个因子在历史预测中的独立表现：
    - 因子得分和实际方向一致的次数越多 → 权重加大
    - 因子得分和实际方向相反的次数越多 → 权重减小
    每周运行一次。
    """
    if not os.path.exists(KB_PREDICTIONS):
        return {"status": "insufficient_data", "weights": FACTOR_WEIGHTS}

    try:
        with open(KB_PREDICTIONS, "r", encoding="utf-8") as f:
            records = json.load(f)

        verified = [r for r in records if r.get("verified") and "factor_scores" in r]
        if len(verified) < 10:
            return {"status": "insufficient_data", "weights": FACTOR_WEIGHTS, "note": f"仅有{len(verified)}条验证记录"}

        # 加载当前权重
        current_weights = FACTOR_WEIGHTS.copy()
        acc_file = KB_ACCURACY
        if os.path.exists(acc_file):
            with open(acc_file, "r", encoding="utf-8") as f:
                acc_data = json.load(f)
            if "current_weights" in acc_data:
                current_weights = acc_data["current_weights"]

        # 分析每个因子的独立准确率
        factor_performance = {}
        for factor_name in current_weights:
            correct_signal = 0
            total_signal = 0

            for r in verified:
                scores = r.get("factor_scores", {})
                if factor_name not in scores:
                    continue

                factor_score = scores[factor_name]
                actual_dir = r.get("actual_direction")

                # 因子得分方向 vs 实际方向
                if factor_score > 0.05 and actual_dir == "涨":
                    correct_signal += 1
                elif factor_score < -0.05 and actual_dir == "跌":
                    correct_signal += 1
                elif abs(factor_score) <= 0.05 and actual_dir == "平":
                    correct_signal += 1
                total_signal += 1

            accuracy = correct_signal / total_signal if total_signal > 0 else 0.5
            factor_performance[factor_name] = {
                "accuracy": round(accuracy, 3),
                "samples": total_signal,
            }

        # 调整权重
        new_weights = {}
        for factor_name, perf in factor_performance.items():
            old_weight = current_weights.get(factor_name, 0.2)
            accuracy = perf["accuracy"]

            # 根据准确率调整
            if accuracy > 0.6:
                # 表现好，加权重
                new_weights[factor_name] = min(0.40, old_weight + 0.03)
            elif accuracy > 0.55:
                # 还可以，微调
                new_weights[factor_name] = old_weight + 0.01
            elif accuracy < 0.45:
                # 表现差，减权重
                new_weights[factor_name] = max(0.05, old_weight - 0.05)
            elif accuracy < 0.50:
                new_weights[factor_name] = max(0.08, old_weight - 0.02)
            else:
                new_weights[factor_name] = old_weight

        # 归一化到和为1
        weight_sum = sum(new_weights.values())
        if weight_sum > 0:
            new_weights = {k: round(v / weight_sum, 4) for k, v in new_weights.items()}

        # 保存
        history = []
        if os.path.exists(acc_file):
            with open(acc_file, "r", encoding="utf-8") as f:
                acc_data = json.load(f)
            history = acc_data.get("weight_history", [])

        history.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "previous_weights": current_weights,
            "new_weights": new_weights,
            "factor_performance": factor_performance,
        })

        # 只保留最近52周
        history = history[-52:]

        with open(acc_file, "w", encoding="utf-8") as f:
            json.dump({
                "current_weights": new_weights,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "weight_history": history,
                "factor_performance": factor_performance,
            }, f, ensure_ascii=False, indent=2)

        return {
            "status": "adjusted",
            "previous_weights": current_weights,
            "new_weights": new_weights,
            "factor_performance": factor_performance,
            "changes": {
                k: round(new_weights[k] - current_weights.get(k, 0), 4)
                for k in new_weights
            },
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_pe_alerts(snapshots: dict) -> list:
    """检查PE触发提醒"""
    from config import get_stock_by_code

    alerts = []
    for stock_config in __import__('config').STOCKS:
        if stock_config["status"] != "active":
            continue

        code = stock_config["code"]
        snap = snapshots.get(code, {})
        pe_ttm = snap.get("pe_ttm")
        if not pe_ttm or pe_ttm <= 0:
            continue

        reasonable_low, reasonable_high = stock_config["pe_reasonable"]
        high_low, high_high = stock_config["pe_high"]

        if pe_ttm <= reasonable_high:
            if pe_ttm <= reasonable_low:
                level = "strong_buy"
                msg = f"🔥 PE={pe_ttm:.1f}已跌破合理区下沿({reasonable_low})，严重低估！"
            else:
                level = "buy_zone"
                msg = f"🟢 PE={pe_ttm:.1f}进入合理区间({reasonable_low}-{reasonable_high})，建议关注买入"

            alerts.append({
                "code": code,
                "name": stock_config["name"],
                "level": level,
                "message": msg,
                "pe_ttm": pe_ttm,
                "zone": f"{reasonable_low}-{reasonable_high}",
            })

        elif pe_ttm >= high_low:
            if pe_ttm >= high_high:
                level = "strong_sell"
                msg = f"🔴 PE={pe_ttm:.1f}已突破高位区上沿({high_high})，严重高估！"
            else:
                level = "sell_zone"
                msg = f"⚠️ PE={pe_ttm:.1f}进入高位区({high_low}-{high_high})，考虑卖出"

            alerts.append({
                "code": code,
                "name": stock_config["name"],
                "level": level,
                "message": msg,
                "pe_ttm": pe_ttm,
                "zone": f"{high_low}-{high_high}",
            })

    return alerts


def check_major_alerts(snapshots: dict, market_indices: dict) -> list:
    """检查大行情：大盘波动>2%、个股波动>5%、PE突变"""
    alerts = []

    # 大盘波动
    for name, data in market_indices.items():
        chg = data.get("change_pct", 0)
        if chg and abs(chg) > 2:
            alerts.append({
                "type": "market",
                "level": "major",
                "message": f"⚠️ {name}单日波动{chg:+.1f}%，超过2%阈值"
            })

    # 个股波动
    for code, snap in snapshots.items():
        if "error" in snap:
            continue
        chg = snap.get("change_pct", 0) or 0
        if abs(chg) > 5:
            from config import get_stock_by_code
            s = get_stock_by_code(code)
            name = s["name"] if s else code
            alerts.append({
                "type": "stock",
                "level": "major",
                "code": code,
                "name": name,
                "message": f"⚠️ {name}单日波动{chg:+.1f}%，超过5%阈值"
            })

    return alerts
