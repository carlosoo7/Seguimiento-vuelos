"""Informe HTML de chollos con botones de compra."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from .analyzer import Deal
from .notifier import fmt_departure, fmt_price

STYLE = """
body{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:24px;background:#f6f7f9;color:#1b1f24}
h1{margin:0 0 4px} .sub{color:#666;margin-bottom:20px}
table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08)}
th,td{padding:10px 12px;border-bottom:1px solid #e6e8eb;text-align:left;vertical-align:top}
th{background:#f0f2f5;font-weight:600;position:sticky;top:0}
tr:hover td{background:#fafbfc}
.price{font-weight:700;white-space:nowrap} .disc{color:#15803d;font-weight:700}
.muted{color:#777;font-size:.9em}
.btn{display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;border-radius:6px;background:#2563eb;
     color:#fff;text-decoration:none;font-size:.85em;white-space:nowrap}
.btn.alt{background:#64748b} .btn.prov{background:#0f766e}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;background:#eef2ff;color:#3730a3;font-size:.8em}
"""


MOCK_BANNER = """<div style="background:#fef2f2;border:2px solid #dc2626;color:#991b1b;padding:14px 16px;
border-radius:8px;margin-bottom:18px;font-weight:600">
⚠️ DATOS SIMULADOS. El último escaneo usó el proveedor <code>mock</code>, que inventa precios para
probar el programa. Ningún chollo de esta lista es real: los botones abren la búsqueda verdadera y verás
el precio actual. Para precios reales pon <code>TRAVELPAYOUTS_TOKEN</code> (o las claves de Amadeus) en
<code>.env</code> y ejecuta <code>python main.py scan</code>.</div>"""


def render(deals: list[Deal], title: str, currency: str, simulated: bool = False) -> str:
    rows = []
    for d in deals:
        links = d.links
        buttons = []
        for i, (name, url) in enumerate(links.items()):
            cls = "btn prov" if name == "Proveedor" else ("btn" if i == 0 else "btn alt")
            label = "Ver precio en origen" if name == "Proveedor" else name
            buttons.append(f'<a class="{cls}" href="{escape(url)}" target="_blank" rel="noopener">{escape(label)}</a>')
        disc = f'<span class="disc">-{d.discount:.0%}</span>' if d.discount is not None else "-"
        med = fmt_price(d.median, d.currency) if d.median else f'<span class="muted">sin histórico (n={d.n_obs})</span>'
        vuelo = f"{d.airline}{d.flight_number}".strip() or "-"
        escalas = "directo" if d.transfers == 0 else f"{d.transfers} escala(s)"
        ret = f'<div class="muted">vuelta {fmt_departure(d.return_at)}</div>' if d.return_at else ""
        rows.append(
            "<tr>"
            f"<td><b>{d.origin} → {d.destination}</b><br><span class='tag'>{d.kind}</span></td>"
            f"<td>{fmt_departure(d.departure_at)}{ret}</td>"
            f"<td class='price'>{fmt_price(d.price, d.currency)}</td>"
            f"<td>{disc}<div class='muted'>mediana {med}</div></td>"
            f"<td>{escape(vuelo)}<div class='muted'>{escalas}</div></td>"
            f"<td>{escape(d.reason)}</td>"
            f"<td>{''.join(buttons)}</td>"
            "</tr>"
        )
    body = "".join(rows) or "<tr><td colspan='7'>No hay chollos con los criterios actuales.</td></tr>"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>{STYLE}</style></head><body>
<h1>{escape(title)}</h1>
{MOCK_BANNER if simulated else ""}
<div class="sub">{len(deals)} chollos · generado {now} · precios en {escape(currency)} ·
los enlaces abren la búsqueda en cada buscador; el precio final puede variar.</div>
<table><thead><tr><th>Ruta</th><th>Salida</th><th>Precio</th><th>vs mediana</th><th>Vuelo</th><th>Motivo</th><th>Comprar</th></tr></thead>
<tbody>{body}</tbody></table></body></html>"""


def write_report(deals: list[Deal], path: Path, title: str, currency: str, simulated: bool = False) -> Path:
    path.write_text(render(deals, title, currency, simulated), encoding="utf-8")
    return path
