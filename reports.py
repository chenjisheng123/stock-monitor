"""
报告生成模块
============
日报 / 周报 / 月报 / 季报 / 年报
"""

import json
import os
from datetime import datetime, timedelta

from config import STOCKS, DATA_DIR, KB_PREDICTIONS, KB_ACCURACY


def generate_daily_report(predictions: list, accuracy_result: dict,
                          pe_alerts: list, major_alerts: list,
                          market_indices: dict) -> str:
    """生成日报HTML"""
    today = datetime.now().strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]
    is_trade = predictions[0].get("is_trading_day", True) if predictions else True

    # 准确率
    acc = accuracy_result.get("accuracy", 0) if accuracy_result.get("status") == "verified" else None

    # PE提醒区
    pe_section = ""
    if pe_alerts:
        for a in pe_alerts:
            emoji = {"strong_buy": "🔥", "buy_zone": "🟢", "sell_zone": "⚠️", "strong_sell": "🔴"}
            pe_section += f"<tr><td>{emoji.get(a['level'],'')}</td><td><b>{a['name']}</b></td><td>PE={a['pe_ttm']:.1f}</td><td>{a['zone']}</td><td>{a['message']}</td></tr>\n"
    else:
        pe_section = "<tr><td colspan='5'>今日无PE触发提醒</td></tr>"

    # 预测区
    pred_section = ""
    for p in predictions:
        if "error" in p:
            pred_section += f"<tr><td>{p['name']}</td><td colspan='4'>数据异常: {p['error']}</td></tr>\n"
            continue

        direction_emoji = {"涨": "📈", "跌": "📉", "平": "➡️"}
        conf_color = {"高": "#e74c3c", "中": "#f39c12", "低": "#95a5a6"}
        conf = p.get("confidence_level", "低")
        color = conf_color.get(conf, "#95a5a6")

        pe = p.get("current_pe", "N/A")
        pe_str = f"{pe:.1f}" if isinstance(pe, (int, float)) and pe else "N/A"

        pred_section += (
            f"<tr>"
            f"<td><b>{p['name']}</b></td>"
            f"<td>{direction_emoji.get(p['direction'],'')} {p['direction']}</td>"
            f"<td><span style='color:{color};font-weight:bold'>{conf}</span></td>"
            f"<td>PE={pe_str}</td>"
            f"<td style='font-size:12px'>{p.get('reasoning','')[:120]}</td>"
            f"</tr>\n"
        )

    # 大行情提醒
    major_section = ""
    if major_alerts:
        for a in major_alerts:
            major_section += f"<p>⚠️ {a['message']}</p>\n"
    else:
        major_section = "<p>✅ 今日无异常波动</p>"

    # 事件区
    from events import generate_event_summary
    event_text = generate_event_summary()

    # 大盘区
    market_text = ""
    if market_indices:
        for name, data in market_indices.items():
            chg = data.get("change_pct", 0) or 0
            emoji = "🔴" if chg < -1 else ("🟢" if chg > 1 else "⚪")
            market_text += f"{emoji} {name}: {data.get('price','N/A')} ({chg:+.2f}%) &nbsp; "

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #f5f6fa; margin:0; padding:20px; }}
.container {{ max-width:700px; margin:0 auto; }}
.header {{ background: linear-gradient(135deg, #2c3e50, #34495e); color:white; padding:25px; border-radius:10px 10px 0 0; }}
.header h1 {{ margin:0; font-size:22px; }}
.header span {{ font-size:14px; opacity:0.8; }}
.card {{ background:white; margin-bottom:15px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
.card-title {{ padding:12px 18px; font-weight:bold; font-size:16px; border-bottom:1px solid #eee; }}
.card-body {{ padding:15px 18px; }}
table {{ width:100%; border-collapse:collapse; }}
th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid #f0f0f0; font-size:14px; }}
th {{ background:#f8f9fa; font-weight:bold; }}
.highlight {{ background:#fff3cd; }}
.footer {{ text-align:center; color:#999; font-size:12px; padding:20px; }}
.accuracy-badge {{ display:inline-block; padding:4px 12px; border-radius:20px; font-weight:bold; font-size:14px; }}
.accuracy-good {{ background:#d4edda; color:#155724; }}
.accuracy-ok {{ background:#fff3cd; color:#856404; }}
.accuracy-low {{ background:#f8d7da; color:#721c24; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>📊 行业情报日报</h1>
<span>{today} {weekday} | {'开盘日' if is_trade else '休市日'}</span>
{'<br><span class="accuracy-badge ' + ('accuracy-good' if acc and acc >= 60 else 'accuracy-ok' if acc and acc >= 50 else 'accuracy-low') + '">昨日预测准确率: ' + str(acc) + '%</span>' if acc is not None else ''}
</div>

<div class="card">
<div class="card-title">🔔 PE估值触发提醒</div>
<div class="card-body">
<table>
<tr><th>级别</th><th>股票</th><th>当前PE</th><th>触发区间</th><th>操作建议</th></tr>
{pe_section}
</table>
</div>
</div>

<div class="card">
<div class="card-title">🔮 今日涨跌预测</div>
<div class="card-body">
<table>
<tr><th>股票</th><th>方向</th><th>信心度</th><th>PE</th><th>推理逻辑</th></tr>
{pred_section}
</table>
</div>
</div>

<div class="card">
<div class="card-title">🚨 大行情提醒</div>
<div class="card-body">{major_section}</div>
</div>

<div class="card">
<div class="card-title">📅 7天内重要事件</div>
<div class="card-body"><pre style="white-space:pre-wrap;font-size:13px;line-height:1.8">{event_text}</pre></div>
</div>

<div class="card">
<div class="card-title">📈 大盘指数</div>
<div class="card-body">{market_text if market_text else '数据获取中...'}</div>
</div>

<div class="footer">
<p>🔄 系统每日自动进化中 | AI驱动 | 仅供参考不构成投资建议</p>
<p>报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</div>

</div>
</body>
</html>
"""
    return html


def generate_weekly_report() -> str:
    """生成周报"""
    from accuracy import get_accuracy_stats

    stats = get_accuracy_stats()
    today = datetime.now().strftime("%Y年%m月%d日")

    # 本周准确率
    week_acc = stats.get("recent_30d_accuracy", 0)
    overall_acc = stats.get("overall_accuracy", 0)

    # 因子权重
    weights_text = ""
    acc_file = KB_ACCURACY
    if os.path.exists(acc_file):
        with open(acc_file, "r", encoding="utf-8") as f:
            acc_data = json.load(f)
        w = acc_data.get("current_weights", {})
        for factor, weight in w.items():
            weights_text += f"<tr><td>{factor}</td><td>{weight:.1%}</td></tr>\n"

    # 个股准确率
    stock_rows = ""
    by_stock = stats.get("by_stock", {})
    for code, sdata in sorted(by_stock.items(), key=lambda x: x[1].get("accuracy", 0), reverse=True):
        stock_rows += (
            f"<tr><td>{sdata['name']}</td>"
            f"<td>{sdata['accuracy']}%</td>"
            f"<td>{sdata['correct']}/{sdata['total']}</td></tr>\n"
        )

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
body {{ font-family:'Microsoft YaHei',Arial,sans-serif; background:#f5f6fa; padding:20px; }}
.container {{ max-width:700px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#2c3e50,#8e44ad); color:white; padding:25px; border-radius:10px 10px 0 0; }}
.card {{ background:white; margin-bottom:15px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
.card-title {{ padding:12px 18px; font-weight:bold; font-size:16px; border-bottom:1px solid #eee; }}
.card-body {{ padding:15px 18px; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ padding:8px; text-align:left; border-bottom:1px solid #f0f0f0; }}
th {{ background:#f8f9fa; }}
.footer {{ text-align:center; color:#999; font-size:12px; padding:20px; }}
</style></head>
<body>
<div class="container">
<div class="header">
<h1>📊 周报 | 股票智能监控系统</h1>
<span>{today}</span>
</div>
<div class="card">
<div class="card-title">📈 准确率总览</div>
<div class="card-body">
<p>本周(近30日)准确率: <b style="font-size:24px;color:#2c3e50;">{week_acc}%</b></p>
<p>历史总准确率: <b>{overall_acc}%</b> (共{stats.get('total_predictions',0)}次预测)</p>
</div>
</div>
<div class="card">
<div class="card-title">🎯 当前因子权重</div>
<div class="card-body"><table><tr><th>因子</th><th>权重</th></tr>{weights_text}</table></div>
</div>
<div class="card">
<div class="card-title">🏆 个股预测准确率排名</div>
<div class="card-body"><table><tr><th>股票</th><th>准确率</th><th>正确/总数</th></tr>{stock_rows}</table></div>
</div>
<div class="footer"><p>🔄 系统持续进化中 | 仅供参考不构成投资建议</p></div>
</div>
</body>
</html>
"""
    return html


def generate_monthly_report() -> str:
    """生成月报"""
    from accuracy import get_accuracy_stats
    stats = get_accuracy_stats()
    today = datetime.now().strftime("%Y年%m月%d日")

    # 准确率趋势
    trend_rows = ""
    for d in stats.get("by_date", [])[-30:]:
        trend_rows += f"<tr><td>{d['date']}</td><td>{d['accuracy']}%</td><td>{d['total']}次</td></tr>\n"

    # PE状态总览
    pe_rows = ""
    for s in STOCKS:
        pe_rows += (
            f"<tr><td>{s['name']}</td><td>{s['industry']}</td>"
            f"<td>{s['pe_reasonable'][0]}-{s['pe_reasonable'][1]}x</td>"
            f"<td>{s['pe_high'][0]}-{s['pe_high'][1]}x</td></tr>\n"
        )

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
body {{ font-family:'Microsoft YaHei',Arial,sans-serif; background:#f5f6fa; padding:20px; }}
.container {{ max-width:700px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#2c3e50,#c0392b); color:white; padding:25px; border-radius:10px 10px 0 0; }}
.card {{ background:white; margin-bottom:15px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
.card-title {{ padding:12px 18px; font-weight:bold; font-size:16px; border-bottom:1px solid #eee; }}
.card-body {{ padding:15px 18px; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ padding:8px; text-align:left; border-bottom:1px solid #f0f0f0; font-size:13px; }}
th {{ background:#f8f9fa; }}
.footer {{ text-align:center; color:#999; font-size:12px; padding:20px; }}
</style></head>
<body>
<div class="container">
<div class="header">
<h1>📊 月报 | 股票智能监控系统</h1>
<span>{today}</span>
</div>
<div class="card">
<div class="card-title">📈 月度准确率</div>
<div class="card-body">
<p>总预测次数: <b>{stats.get('total_predictions',0)}</b></p>
<p>总准确率: <b style="font-size:24px;">{stats.get('overall_accuracy',0)}%</b></p>
</div>
</div>
<div class="card">
<div class="card-title">📉 每日准确率趋势</div>
<div class="card-body"><table><tr><th>日期</th><th>准确率</th><th>预测数</th></tr>{trend_rows}</table></div>
</div>
<div class="card">
<div class="card-title">📋 股票池PE配置总览</div>
<div class="card-body"><table><tr><th>股票</th><th>行业</th><th>PE合理区</th><th>PE高位区</th></tr>{pe_rows}</table></div>
</div>
<div class="card">
<div class="card-title">💡 本月建议</div>
<div class="card-body">
<p>1. 检查近30日准确率趋势，如持续下降需考虑是否增加新因子</p>
<p>2. 关注准确率偏低的个股，分析预测偏差原因</p>
<p>3. 审视PE区间设置是否仍然合理（市场整体估值中枢是否发生变化）</p>
</div>
</div>
<div class="footer"><p>🔄 系统自动进化中 | 仅供参考不构成投资建议</p></div>
</div>
</body>
</html>
"""
    return html


def save_report(report_type: str, html_content: str):
    """保存报告到本地"""
    today = datetime.now().strftime("%Y-%m-%d")
    report_dir = os.path.join("reports", report_type)
    os.makedirs(report_dir, exist_ok=True)
    filepath = os.path.join(report_dir, f"{today}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    return filepath
