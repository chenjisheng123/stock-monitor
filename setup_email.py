"""从GitHub Secrets读取邮件配置"""
import json
import os

sender_email = os.environ.get("SENDER_EMAIL", "")
sender_password = os.environ.get("SENDER_PASSWORD", "")
recipients_str = os.environ.get("RECIPIENTS", "")

recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]

config = {
    "sender_email": sender_email,
    "sender_password": sender_password,
    "recipients": recipients,
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "send_time": "08:00",
}

os.makedirs("data", exist_ok=True)
with open("data/email_settings.json", "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"✅ 邮件配置已保存: {len(recipients)} 个收件人")
