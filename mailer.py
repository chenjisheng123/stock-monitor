"""
邮件发送模块
============
通过QQ邮箱SMTP发送HTML格式的报告。
支持多收件人。
"""

import smtplib
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from config import EMAIL_CONFIG, DATA_DIR

# 配置文件路径
EMAIL_SETTINGS_FILE = os.path.join(DATA_DIR, "email_settings.json")


def load_email_settings() -> dict:
    """加载邮件配置（支持用户自定义）"""
    settings = EMAIL_CONFIG.copy()

    if os.path.exists(EMAIL_SETTINGS_FILE):
        try:
            with open(EMAIL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            settings.update(user_settings)
        except Exception:
            pass

    return settings


def save_email_settings(settings: dict):
    """保存邮件配置"""
    with open(EMAIL_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def send_email(subject: str, html_content: str, recipients: list = None) -> dict:
    """
    发送HTML邮件。
    返回发送结果。
    """
    settings = load_email_settings()

    sender_email = settings.get("sender_email", "")
    sender_password = settings.get("sender_password", "")

    if not sender_email or not sender_password:
        return {
            "success": False,
            "error": "邮箱未配置。请在管理端设置发件邮箱和SMTP授权码。",
        }

    if recipients is None:
        recipients = settings.get("recipients", [])

    if not recipients:
        return {
            "success": False,
            "error": "没有收件人。请在管理端添加收件邮箱。",
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"股票监控系统 <{sender_email}>"
        msg["To"] = ", ".join(recipients)

        msg.attach(MIMEText(html_content, "html", "utf-8"))

        server = smtplib.SMTP_SSL(
            settings.get("smtp_server", "smtp.qq.com"),
            settings.get("smtp_port", 465),
        )
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()

        return {
            "success": True,
            "recipients": recipients,
            "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "error": "SMTP认证失败，请检查邮箱地址和授权码是否正确。",
        }
    except smtplib.SMTPConnectError:
        return {
            "success": False,
            "error": "无法连接到SMTP服务器，请检查网络。",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"发送失败: {str(e)}",
        }


def send_daily_email(html_content: str) -> dict:
    """发送日报"""
    today = datetime.now().strftime("%m.%d")
    subject = f"【日报】{today} | 股票智能监控系统"
    return send_email(subject, html_content)


def send_weekly_email(html_content: str) -> dict:
    """发送周报"""
    today = datetime.now().strftime("%m.%d")
    subject = f"【周报】{today} | 股票智能监控系统"
    return send_email(subject, html_content)


def send_monthly_email(html_content: str) -> dict:
    """发送月报"""
    today = datetime.now().strftime("%m.%d")
    subject = f"【月报】{today} | 股票智能监控系统"
    return send_email(subject, html_content)


def send_alert_email(subject: str, html_content: str) -> dict:
    """发送紧急提醒"""
    return send_email(f"🚨 {subject}", html_content)


def test_email_config(sender_email: str, sender_password: str,
                      test_recipient: str) -> dict:
    """测试邮件配置是否正常"""
    settings = load_email_settings()
    settings["sender_email"] = sender_email
    settings["sender_password"] = sender_password
    save_email_settings(settings)

    html = """
    <html><body>
    <h2>✅ 股票监控系统 — 邮件配置测试成功</h2>
    <p>如果您收到这封邮件，说明SMTP配置正确。</p>
    <p>系统将按计划发送每日/每周/每月报告到此邮箱。</p>
    </body></html>
    """

    return send_email("✅ 股票监控系统 - 测试邮件", html, [test_recipient])
