"""
股票智能监控系统 — 主调度器
============================
每天运行一次（GitHub Actions触发）：
1. 拉取行情数据
2. 拉取最新新闻
3. 生成预测
4. 验证昨日预测
5. 检查PE触发
6. 生成报告
7. 发送邮件
8. 更新知识库
9. 每周：调整因子权重 + 发现新因子
10. 每月：生成月报
"""

import json
import os
import sys
from datetime import datetime

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, REPORTS_DIR
from data_fetcher import (
    fetch_all_snapshots, fetch_market_index, fetch_daily_news,
    load_previous_snapshot, save_daily_snapshot, is_trading_day,
)
from prediction import (
    predict_all_stocks, predict_non_trading_day,
    save_predictions, discover_new_factors,
)
from accuracy import (
    verify_yesterday_predictions, check_pe_alerts,
    check_major_alerts, adjust_factor_weights, get_accuracy_stats,
)
from reports import (
    generate_daily_report, generate_weekly_report,
    generate_monthly_report, save_report,
)
from mailer import (
    send_daily_email, send_weekly_email, send_monthly_email,
    send_alert_email, load_email_settings,
)


def ensure_dirs():
    """确保所有目录存在"""
    for d in [DATA_DIR, REPORTS_DIR]:
        os.makedirs(d, exist_ok=True)
    for sub in ["daily", "weekly", "monthly"]:
        os.makedirs(os.path.join(REPORTS_DIR, sub), exist_ok=True)


def run_daily():
    """每日主流程"""
    # 自动从GitHub拉取最新代码
    import subprocess
    subprocess.run(["git", "pull", "origin", "master"], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, timeout=30)
    print("=" * 60)
    print(f"股票智能监控系统 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    ensure_dirs()

    # ── 1. 拉取数据 ──
    print("\n[1/8] 拉取行情数据...")
    trading = is_trading_day()
    print(f"  今日状态: {'开盘日' if trading else '休市日'}")

    snapshots = fetch_all_snapshots()
    market_indices = fetch_market_index()
    prev_snapshots = load_previous_snapshot(1)

    success_count = sum(1 for s in snapshots.values() if "error" not in s)
    print(f"  成功拉取: {success_count}/{len(snapshots)} 支股票")

    # ── 2. 拉取新闻 ──
    print("\n[2/8] 拉取最新新闻...")
    news_list = fetch_daily_news()
    print(f"  获取新闻: {len(news_list)} 条")

    # ── 3. 生成预测 ──
    print("\n[3/8] 生成预测...")
    if trading:
        predictions = predict_all_stocks(snapshots, market_indices, prev_snapshots)
    else:
        predictions = predict_non_trading_day(news_list)

    save_predictions(predictions)
    dir_count = {"涨": 0, "跌": 0, "平": 0}
    for p in predictions:
        d = p.get("direction", "平")
        dir_count[d] = dir_count.get(d, 0) + 1
    print(f"  预测结果: 涨{dir_count['涨']}支 跌{dir_count['跌']}支 平{dir_count['平']}支")

    # ── 4. 验证昨日 ──
    print("\n[4/8] 验证昨日预测...")
    if trading:
        accuracy_result = verify_yesterday_predictions(snapshots)
        acc = accuracy_result.get("accuracy", "N/A")
        print(f"  昨日准确率: {acc}{'%' if isinstance(acc, (int, float)) else ''}")
    else:
        accuracy_result = {"status": "holiday", "message": "休市日不验证"}
        print("  休市日，跳过验证")

    # ── 5. 检查PE触发 ──
    print("\n[5/8] 检查PE触发...")
    pe_alerts = check_pe_alerts(snapshots)
    print(f"  PE触发: {len(pe_alerts)} 条提醒")
    for a in pe_alerts:
        print(f"    {a['name']}: {a['message'][:60]}")

    # ── 6. 检查大行情 ──
    print("\n[6/8] 检查大行情...")
    major_alerts = check_major_alerts(snapshots, market_indices)
    if major_alerts:
        print(f"  大行情提醒: {len(major_alerts)} 条")
        for a in major_alerts:
            print(f"    {a['message']}")
    else:
        print("  无异常波动")

    # ── 7. 生成并发送日报 ──
    print("\n[7/8] 生成日报...")
    daily_html = generate_daily_report(
        predictions, accuracy_result, pe_alerts, major_alerts, market_indices
    )
    save_report("daily", daily_html)

    # 发送邮件
    print("  发送邮件...")
    result = send_daily_email(daily_html)
    if result.get("success"):
        print(f"  ✅ 邮件已发送至: {', '.join(result.get('recipients', []))}")
    else:
        print(f"  ❌ 邮件发送失败: {result.get('error', '未知错误')}")

    # ── 8. 保存快照 ──
    print("\n[8/8] 保存今日快照...")
    save_daily_snapshot(snapshots)
    print("  快照已保存")

    # ── 检查是否发送周报 ──
    if datetime.now().weekday() == 0:  # 周一
        print("\n📊 生成周报...")
        weekly_html = generate_weekly_report()
        save_report("weekly", weekly_html)
        result = send_weekly_email(weekly_html)
        if result.get("success"):
            print("  ✅ 周报已发送")

        # 调整因子权重
        print("  🧠 调整因子权重...")
        adj_result = adjust_factor_weights()
        print(f"  权重调整状态: {adj_result.get('status','unknown')}")

        # 发现新因子
        print("  🔍 扫描新因子...")
        new_factors = discover_new_factors()
        if new_factors:
            for nf in new_factors:
                print(f"  ✨ {nf}")

    # ── 检查是否发送月报 ──
    if datetime.now().day == 1:  # 每月1号
        print("\n📊 生成月报...")
        monthly_html = generate_monthly_report()
        save_report("monthly", monthly_html)
        result = send_monthly_email(monthly_html)
        if result.get("success"):
            print("  ✅ 月报已发送")

    # ── 发送紧急提醒 ──
    if major_alerts:
        alert_html = "<html><body><h2>🚨 大行情提醒</h2><ul>"
        for a in major_alerts:
            alert_html += f"<li>{a['message']}</li>"
        alert_html += "</ul></body></html>"
        send_alert_email("大行情提醒", alert_html)

    print("\n" + "=" * 60)
    print("✅ 每日运行完成")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="手动运行一次")
    parser.add_argument("--check", action="store_true", help="仅检查配置")
    args = parser.parse_args()

    if args.check:
        print("检查系统配置...")
        settings = load_email_settings()
        if settings.get("sender_email") and settings.get("sender_password"):
            print("✅ 邮箱已配置")
        else:
            print("⚠️ 邮箱未配置，请在管理端设置")
        print(f"✅ 监控股票: {len([s for s in __import__('config').STOCKS if s['status']=='active'])} 支")
        print(f"✅ 事件日历: {len(__import__('config').EVENTS)} 条")
        sys.exit(0)

    run_daily()
