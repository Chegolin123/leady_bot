import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

ALERT_RULES = {
    "api_down": {"level": "critical", "message": "API не отвечает на /health"},
    "proxy_failed_3": {"level": "critical", "message": "3+ прокси недоступны"},
    "bot_crash": {"level": "critical", "message": "Бот упал (корутина завершилась)"},
    "license_expiring": {"level": "warning", "message": "Лицензия истекает через 3 дня"},
    "license_expired": {"level": "critical", "message": "Лицензия истекла, бот заблокирован"},
    "payment_failed": {"level": "warning", "message": "Платёж не прошёл (YooKassa)"},
    "disk_usage_90": {"level": "warning", "message": "Диск заполнен >90%"},
    "memory_usage_90": {"level": "critical", "message": "Память >90% (OOM риск)"},
    "backup_failed": {"level": "critical", "message": "Бэкап не удался"},
    "db_connection_failed": {"level": "critical", "message": "Нет соединения с PostgreSQL"},
    "redis_connection_failed": {"level": "warning", "message": "Нет соединения с Redis"},
    "high_error_rate": {"level": "warning", "message": "Высокий процент ошибок (>5%)"},
}


async def send_telegram_alert(message: str, level: str = "warning"):
    """Отправка алерта в Telegram."""
    if not settings.ALERT_TELEGRAM_BOT_TOKEN or not settings.ALERT_TELEGRAM_CHAT_ID:
        return

    emoji = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(level, "⚠️")
    text = f"{emoji} <b>[{level.upper()}]</b>\n{message}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.ALERT_TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": settings.ALERT_TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


def send_email_alert(subject: str, body: str):
    """Отправка алерта на email (fallback)."""
    if not settings.SMTP_HOST or not settings.ALERT_EMAIL:
        return

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[CRM-Bot] {subject}"
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.ALERT_EMAIL

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")


async def fire_alert(rule_name: str, details: Optional[str] = None):
    """Отправить алерт по правилу."""
    rule = ALERT_RULES.get(rule_name)
    if not rule:
        logger.warning(f"Unknown alert rule: {rule_name}")
        return

    message = rule["message"]
    if details:
        message += f"\n\n{details}"

    level = rule["level"]
    logger.log(
        logging.CRITICAL if level == "critical" else logging.WARNING,
        f"ALERT [{rule_name}]: {message}",
    )

    await send_telegram_alert(message, level)

    if level == "critical":
        # Email fallback для критичных алертов
        send_email_alert(f"[{level.upper()}] {rule_name}", message)
