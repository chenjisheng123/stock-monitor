"""
股票智能监控系统 — Web管理端
=============================
Streamlit 应用，部署在 Streamlit Cloud（免费）。
功能：加股/删股、加邮箱/删邮箱、改发送时间、查看系统状态、AI对话。
"""

import streamlit as st
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import STOCKS, OBSERVING, FACTOR_WEIGHTS, EMAIL_CONFIG, DATA_DIR, KB_PREDICTIONS
from mailer import load_email_settings, save_email_settings, test_email_config
from accuracy import get_accuracy_stats


st.set_page_config(
    page_title="股票智能监控",
    page_icon="📊",
    layout="wide",
)

# ============================================================
# 侧边栏 — 导航
# ============================================================
st.sidebar.title("📊 股票智能监控")

menu = st.sidebar.radio(
    "导航",
    ["🏠 系统概览", "📧 邮件设置", "📈 股票管理", "💬 AI对话"],
    label_visibility="collapsed",
)

# ============================================================
# 系统概览
# ============================================================
if menu == "🏠 系统概览":
    st.title("🏠 系统概览")

    stats = get_accuracy_stats()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("监控股票", f"{len(STOCKS)} 支")
    with col2:
        st.metric("总预测次数", stats.get("total_predictions", 0))
    with col3:
        st.metric("总体准确率", f"{stats.get('overall_accuracy', 0)}%")

    col4, col5 = st.columns(2)
    with col4:
        st.metric("近30日准确率", f"{stats.get('recent_30d_accuracy', 0)}%")
    with col5:
        settings = load_email_settings()
        has_email = bool(settings.get("sender_email") and settings.get("sender_password"))
        has_recipient = bool(settings.get("recipients"))
        status = "✅ 已配置" if has_email and has_recipient else "⚠️ 待配置"
        st.metric("邮件状态", status)

    st.subheader("📈 准确率趋势（近30日）")
    if stats.get("by_date"):
        dates = [d["date"] for d in stats["by_date"]]
        accs = [d["accuracy"] for d in stats["by_date"]]
        st.line_chart({"准确率(%)": accs}, x=dates if len(dates) <= 30 else None)

    st.subheader("📋 当前PE监控状态")
    pe_data = []
    for s in STOCKS:
        pe_data.append({
            "股票": s["name"],
            "行业": s["industry"],
            "PE合理区": f"{s['pe_reasonable'][0]}-{s['pe_reasonable'][1]}x",
            "PE高位区": f"{s['pe_high'][0]}-{s['pe_high'][1]}x",
            "状态": s["status"],
        })
    st.dataframe(pe_data, use_container_width=True)


# ============================================================
# 邮件设置
# ============================================================
elif menu == "📧 邮件设置":
    st.title("📧 邮件设置")

    settings = load_email_settings()

    tab1, tab2 = st.tabs(["发件配置", "收件人管理"])

    with tab1:
        st.subheader("发件邮箱（QQ邮箱）")

        sender = st.text_input(
            "QQ邮箱地址",
            value=settings.get("sender_email", ""),
            placeholder="12345678@qq.com",
        )

        password = st.text_input(
            "SMTP授权码",
            value=settings.get("sender_password", ""),
            type="password",
            placeholder="16位授权码（不是QQ密码）",
        )
        st.caption("如何获取？登录QQ邮箱 → 设置 → 账户 → 开启POP3/SMTP → 获取授权码")

        send_time = st.selectbox(
            "每日发送时间",
            options=[f"{h:02d}:00" for h in range(6, 24)] + [f"{h:02d}:30" for h in range(6, 24)],
            index=0,
        )
        st.caption("注意：此设置仅影响管理端显示，云端实际运行时间由GitHub Actions控制")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存配置", use_container_width=True):
                settings["sender_email"] = sender
                settings["sender_password"] = password
                settings["send_time"] = send_time
                save_email_settings(settings)
                st.success("✅ 已保存")
        with col2:
            if st.button("🧪 测试发送", use_container_width=True):
                if not sender or not password:
                    st.error("请先填写邮箱和授权码")
                elif not settings.get("recipients"):
                    st.error("请先在「收件人管理」中添加收件邮箱")
                else:
                    result = test_email_config(
                        sender, password, settings["recipients"][0]
                    )
                    if result.get("success"):
                        st.success(f"✅ 测试邮件已发送至 {settings['recipients'][0]}")
                    else:
                        st.error(f"❌ {result.get('error')}")

    with tab2:
        st.subheader("收件人管理")

        recipients = settings.get("recipients", [])

        # 添加
        new_recipient = st.text_input(
            "添加收件邮箱",
            placeholder="xxxxx@qq.com",
        )
        if st.button("➕ 添加", use_container_width=True):
            if new_recipient and "@" in new_recipient:
                if new_recipient not in recipients:
                    recipients.append(new_recipient)
                    settings["recipients"] = recipients
                    save_email_settings(settings)
                    st.success(f"✅ 已添加 {new_recipient}")
                    st.rerun()
                else:
                    st.warning("该邮箱已存在")
            else:
                st.error("请输入有效的邮箱地址")

        # 列表
        if recipients:
            st.write("当前收件人：")
            for i, r in enumerate(recipients):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"📧 {r}")
                with col2:
                    if st.button("🗑️ 删除", key=f"del_{i}"):
                        recipients.pop(i)
                        settings["recipients"] = recipients
                        save_email_settings(settings)
                        st.rerun()
        else:
            st.info("尚未添加收件人")


# ============================================================
# 股票管理
# ============================================================
elif menu == "📈 股票管理":
    st.title("📈 股票管理")

    tab1, tab2 = st.tabs(["当前监控池", "添加/删除"])

    with tab1:
        st.subheader(f"核心监控 ({len([s for s in STOCKS if s['status']=='active'])} 支)")

        for s in STOCKS:
            with st.expander(f"{s['name']} ({s['code']}) — {s['industry']}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("PE合理区", f"{s['pe_reasonable'][0]}-{s['pe_reasonable'][1]}x")
                with c2:
                    st.metric("PE高位区", f"{s['pe_high'][0]}-{s['pe_high'][1]}x")
                with c3:
                    st.metric("加入日期", s.get("added_date", "N/A"))
                st.caption(s.get("notes", ""))

        st.subheader(f"观察池 ({len(OBSERVING)} 支)")
        for s in OBSERVING:
            st.write(f"👁️ {s['name']} ({s['code']}) — {s['industry']} | {s.get('watch_reason','')}")

    with tab2:
        st.subheader("➕ 添加股票")
        code = st.text_input("股票代码（6位）", placeholder="例如: 601127")
        name = st.text_input("股票名称", placeholder="例如: 赛力斯")
        industry = st.selectbox("行业", [
            "新能源车", "芯片设计", "存储模组", "光器件", "CIS芯片",
            "半导体设备", "内存接口", "刻蚀设备", "封装测试", "智驾域控",
            "存储分销", "晶圆代工", "光模块", "存储+封测", "其他",
        ])
        pe_low = st.number_input("PE合理区下沿", value=20)
        pe_high = st.number_input("PE合理区上沿", value=35)
        pe_sell_low = st.number_input("PE高位区下沿", value=50)
        pe_sell_high = st.number_input("PE高位区上沿", value=65)

        if st.button("✅ 确认添加", use_container_width=True):
            if code and name:
                new_stock = {
                    "code": code,
                    "name": name,
                    "industry": industry,
                    "pe_reasonable": [pe_low, pe_high],
                    "pe_high": [pe_sell_low, pe_sell_high],
                    "status": "active",
                    "added_date": datetime.now().strftime("%Y-%m-%d"),
                    "notes": "",
                }
                STOCKS.append(new_stock)
                from config import DATA_DIR
                config_file = os.path.join(os.path.dirname(__file__), "config.py")
                st.success(f"✅ 已添加 {name}。注意：云端代码需要更新才能生效。")
                st.info("请联系管理员更新GitHub代码以永久生效。")
            else:
                st.error("请填写代码和名称")

        st.subheader("➖ 删除股票")
        remove_name = st.selectbox("选择要删除的股票", [s["name"] for s in STOCKS])
        if st.button("🗑️ 确认删除", use_container_width=True):
            st.warning("请在GitHub代码中手动删除，或联系管理员。管理端暂不支持直接删除。")


# ============================================================
# AI对话
# ============================================================
elif menu == "💬 AI对话":
    st.title("💬 智能对话")

    st.caption("询问系统关于预测逻辑、个股分析、行业趋势等问题")

    # 聊天历史
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "你好！我是股票智能监控系统。你可以问我：\n\n• 为什么今天预测XX股涨/跌？\n• XX股最近的PE走势如何？\n• 下周有什么重要事件？\n• 系统最近的预测准确率怎样？\n• 当前因子权重是多少？"}
        ]

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("输入你的问题..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.write(prompt)

        # 生成回复
        response = generate_chat_response(prompt)

        with st.chat_message("assistant"):
            st.write(response)

        st.session_state.chat_history.append({"role": "assistant", "content": response})


def generate_chat_response(prompt: str) -> str:
    """根据用户问题生成回复"""
    prompt_lower = prompt.lower()

    # 准确率
    if "准确率" in prompt_lower or "预测率" in prompt_lower:
        stats = get_accuracy_stats()
        return (
            f"📊 系统预测准确率：\n\n"
            f"• 总体准确率：**{stats.get('overall_accuracy', 0)}%**\n"
            f"• 近30日准确率：**{stats.get('recent_30d_accuracy', 0)}%**\n"
            f"• 总预测次数：{stats.get('total_predictions', 0)}\n\n"
            f"系统每天都在学习和调整因子权重，准确率趋势持续优化中。"
        )

    # 因子权重
    if "因子" in prompt_lower or "权重" in prompt_lower:
        from config import KB_ACCURACY
        weights_text = ""
        if os.path.exists(KB_ACCURACY):
            with open(KB_ACCURACY, "r", encoding="utf-8") as f:
                acc_data = json.load(f)
            w = acc_data.get("current_weights", FACTOR_WEIGHTS)
            for factor, weight in w.items():
                weights_text += f"• {factor}: **{weight:.1%}**\n"
        else:
            for factor, weight in FACTOR_WEIGHTS.items():
                weights_text += f"• {factor}: **{weight:.1%}** (初始权重)\n"

        return f"🎯 当前因子权重：\n\n{weights_text}\n权重由系统自动调整，表现好的因子会获得更高权重。"

    # 事件
    if "事件" in prompt_lower or "会议" in prompt_lower or "下周" in prompt_lower:
        from events import generate_event_summary
        summary = generate_event_summary()
        return f"📅 未来7天重要事件：\n\n{summary}"

    # PE
    if "pe" in prompt_lower or "估值" in prompt_lower:
        text = "📊 当前PE估值状态：\n\n"
        for s in STOCKS:
            text += (
                f"**{s['name']}**：合理区 {s['pe_reasonable'][0]}-{s['pe_reasonable'][1]}x，"
                f"高位区 {s['pe_high'][0]}-{s['pe_high'][1]}x\n"
            )
        return text

    # 股票
    for s in STOCKS:
        if s["name"] in prompt:
            return (
                f"📈 **{s['name']}** ({s['code']}) — {s['industry']}\n\n"
                f"PE合理区间：{s['pe_reasonable'][0]}-{s['pe_reasonable'][1]}x（买入触发）\n"
                f"PE高位区间：{s['pe_high'][0]}-{s['pe_high'][1]}x（卖出触发）\n\n"
                f"备注：{s.get('notes', '无')}\n\n"
                f"💡 当前PE低于合理区下沿时，系统会发送买入提醒。"
            )

    # 默认
    return (
        "我是股票智能监控系统的AI助手。我可以回答以下问题：\n\n"
        "📊 **准确率**：系统预测准确率怎么样？\n"
        "🎯 **因子权重**：当前各因子权重是多少？\n"
        "📅 **事件日历**：下周有什么重要会议？\n"
        "📈 **PE估值**：各股当前PE状态？\n"
        "💬 **个股分析**：输入股票名称查看详细信息\n\n"
        "请告诉我你想了解什么？"
    )


if __name__ == "__main__":
    pass  # 由 streamlit run 启动
