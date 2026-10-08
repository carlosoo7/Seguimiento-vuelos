from __future__ import annotations

import requests

from .analyzer import Deal
from .config import env


def fmt_price(price: float, currency: str) -> str:
    if currency == "COP":
        return f"${price:,.0f} COP"
    return f"{price:,.2f} {currency}"


def fmt_departure(iso: str) -> str:
    # "2026-11-03T06:10:00-05:00" -> "2026-11-03 06:10"
    if "T" in iso:
        return iso[:16].replace("T", " ")
    return iso[:10]


def deal_line(d: Deal) -> str:
    disc = f" (-{d.discount:.0%} vs mediana)" if d.discount is not None else ""
    vuelo = f" {d.airline}{d.flight_number}".rstrip()
    escalas = "directo" if d.transfers == 0 else f"{d.transfers} escala(s)"
    return (
        f"{d.origin}->{d.destination} {fmt_departure(d.departure_at)} "
        f"{fmt_price(d.price, d.currency)}{disc}{vuelo} ({escalas})"
    )


def send_telegram(deals: list[Deal]) -> bool:
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat or not deals:
        return False
    lines = ["✈️ Chollos de vuelo encontrados:"]
    for d in deals[:30]:
        links = d.links
        line = "• " + deal_line(d)
        line += "\n  Comprar: " + " | ".join(f"{name}: {url}" for name, url in list(links.items())[:2])
        if "Proveedor" in links:
            line += f"\n  Precio visto en: {links['Proveedor']}"
        lines.append(line)
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": "\n".join(lines), "disable_web_page_preview": True},
        timeout=30,
    )
    return resp.ok
