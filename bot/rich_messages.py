"""Rich Messages — Telegram Bot API 10.1

Generates HTML and sends via sendRichMessage.
Format: {"rich_message": {"html": "<h1>...</h1><table bordered striped>...</table>"}}
"""

import logging
from html import escape as _h

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


def h(text: str) -> str:
    return _h(str(text))


def doc(*blocks: str) -> str:
    return "\n".join(blocks)


def heading(level: int, text: str) -> str:
    return f"<h{level}>{text}</h{level}>"


def para(*children: str) -> str:
    return f"<p>{' '.join(children)}</p>"


def bold(text: str) -> str:
    return f"<b>{h(text)}</b>"


def italic(text: str) -> str:
    return f"<i>{h(text)}</i>"


def link(url: str, text: str = "") -> str:
    return f'<a href="{h(url)}">{h(text or url)}</a>'


def divider() -> str:
    return "<hr/>"


def spoiler(text: str) -> str:
    return f"<tg-spoiler>{h(text)}</tg-spoiler>"


def table(headers: list[str], rows: list[list[str]], bordered: bool = True, striped: bool = True) -> str:
    attrs = []
    if bordered:
        attrs.append("bordered")
    if striped:
        attrs.append("striped")
    attr_str = " ".join(attrs)
    parts = [f"<table {attr_str}>"]
    parts.append("<tr>" + "".join(f"<th>{h(c)}</th>" for c in headers) + "</tr>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{h(c)}</td>" for c in row) + "</tr>")
    parts.append("</table>")
    return "\n".join(parts)


def list_ordered(*items: str) -> str:
    return "<ol>" + "".join(f"<li>{item}</li>" for item in items) + "</ol>"


def list_bullet(*items: str) -> str:
    return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def blockquote(*children: str) -> str:
    return "<blockquote>" + "\n".join(children) + "</blockquote>"


def pre(text: str) -> str:
    return f"<pre><code>{h(text)}</code></pre>"


async def send_rich(chat_id: int, rich_html: str, reply_markup: dict | None = None) -> int | None:
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendRichMessage"
    payload: dict = {
        "chat_id": chat_id,
        "rich_message": {"html": rich_html},
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("ok"):
                return data["result"]["message_id"]
            logger.warning(f"sendRichMessage failed: {data.get('description')}")
    except Exception:
        logger.exception("sendRichMessage error")
    return None
