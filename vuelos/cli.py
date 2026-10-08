from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from rich.console import Console
from rich.table import Table

from . import config as cfgmod
from .analyzer import find_deals
from .notifier import deal_line, fmt_departure, fmt_price, send_telegram
from .providers import make_provider
from .providers.base import ProviderError
from .report import write_report
from .storage import Store

console = Console(width=max(110, Console().width))


def months_from_today(n: int) -> list[str]:
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


# ---------------------------------------------------------------- comandos --
def cmd_scan(args, cfg, store):
    provider = make_provider(cfg, args.provider)
    months = months_from_today(args.months or cfg.months_ahead)
    scan_id = store.start_scan(provider.name)
    console.print(
        f"[bold]Escaneo #{scan_id}[/] con [cyan]{provider.name}[/]: "
        f"{len(cfg.routes)} rutas x {len(months)} meses ({', '.join(months)})"
    )
    total, errors = 0, 0
    for i, route in enumerate(cfg.routes, 1):
        for month in months:
            try:
                obs = provider.search_month(route.origin, route.destination, month, cfg.one_way, cfg.currency)
            except ProviderError as exc:
                errors += 1
                console.print(f"  [red]x[/] {route.key} {month}: {exc}")
                continue
            store.add_many(scan_id, provider.name, obs)
            total += len(obs)
            time.sleep(cfg.pause_seconds if provider.name != "mock" else 0)
        console.print(f"  [{i:>3}/{len(cfg.routes)}] {route.key:<8} ok", end="\r")
    console.print()
    console.print(f"[green]Guardadas {total} observaciones[/] ({errors} errores).")
    return scan_id


MOCK_WARNING = (
    "DATOS SIMULADOS: el último escaneo usó el proveedor 'mock', que inventa precios para probar "
    "el programa. Ningún chollo es real. Pon TRAVELPAYOUTS_TOKEN o las claves de Amadeus en .env "
    "y vuelve a ejecutar `scan` para obtener precios reales."
)


def warn_if_mock(store):
    if store.last_provider() == "mock":
        console.print(f"[bold yellow on red] {MOCK_WARNING} [/]")


def print_deals(deals, limit: int):
    if not deals:
        console.print("[yellow]No hay chollos con los criterios actuales.[/]")
        return
    t = Table(title=f"Chollos ({len(deals)} encontrados, mostrando {min(limit, len(deals))})")
    t.add_column("Ruta", no_wrap=True)
    t.add_column("Salida", no_wrap=True)
    t.add_column("Precio", justify="right", no_wrap=True)
    t.add_column("vs mediana", justify="right")
    t.add_column("Mediana", justify="right")
    t.add_column("Vuelo")
    t.add_column("Escalas", justify="center")
    t.add_column("Motivo")
    t.add_column("Comprar", no_wrap=True)
    for d in deals[:limit]:
        disc = f"[bold green]-{d.discount:.0%}[/]" if d.discount is not None else "-"
        med = fmt_price(d.median, d.currency) if d.median else f"(n={d.n_obs})"
        links = d.links
        buy = " · ".join(
            f"[link={url}]{'Origen' if name == 'Proveedor' else name.split()[0]}[/link]"
            for name, url in links.items()
        )
        t.add_row(
            f"{d.origin}->{d.destination}",
            fmt_departure(d.departure_at),
            f"[bold]{fmt_price(d.price, d.currency)}[/]",
            disc,
            med,
            f"{d.airline}{d.flight_number}",
            "directo" if d.transfers == 0 else str(d.transfers),
            d.reason,
            buy,
        )
    console.print(t)
    console.print("[dim]Los nombres de la columna Comprar son enlaces (Ctrl+clic en terminales compatibles). "
                  "Usa --links para ver las URL o `report` para un HTML con botones.[/]")


def print_links(deals, limit: int):
    for d in deals[:limit]:
        console.print(f"[bold]{d.origin}->{d.destination} {fmt_departure(d.departure_at)} "
                      f"{fmt_price(d.price, d.currency)}[/]")
        for name, url in d.links.items():
            console.print(f"    {name:<15} {url}", markup=False, highlight=False)


def cmd_deals(args, cfg, store):
    deals = find_deals(store, cfg, ratio=args.ratio)
    if args.kind:
        deals = [d for d in deals if d.kind == args.kind]
    warn_if_mock(store)
    print_deals(deals, args.top)
    if args.links:
        print_links(deals, args.top)
    warn_if_mock(store)


def cmd_report(args, cfg, store):
    deals = find_deals(store, cfg, ratio=args.ratio)
    if args.kind:
        deals = [d for d in deals if d.kind == args.kind]
    origins = ", ".join(sorted({r.origin for r in cfg.routes}))
    out = cfgmod.ROOT / (args.out or f"chollos-{cfg.db_path.stem}.html")
    write_report(deals[: args.top], out, f"Chollos de vuelo desde {origins}", cfg.currency,
                 simulated=store.last_provider() == "mock")
    warn_if_mock(store)
    console.print(f"[green]Informe con {min(len(deals), args.top)} chollos:[/] {out}")
    if args.open:
        import webbrowser
        webbrowser.open(out.as_uri())


def cmd_history(args, cfg, store):
    o, d = args.origin.upper(), args.destination.upper()
    st = store.route_stats(o, d, args.days)
    console.print(
        f"[bold]{o}->{d}[/] últimos {args.days} días: n={st['n']} "
        f"mediana={fmt_price(st['median'], cfg.currency) if st['median'] else '-'} "
        f"p25={fmt_price(st['p25'], cfg.currency) if st['p25'] else '-'} "
        f"mín={fmt_price(st['min'], cfg.currency) if st['min'] else '-'}"
    )
    t = Table(title="Mínimo encontrado en cada escaneo")
    t.add_column("Escaneo (UTC)")
    t.add_column("Mínimo", justify="right")
    t.add_column("Salida del vuelo")
    t.add_column("Obs.", justify="right")
    for r in store.history(o, d, args.days):
        t.add_row(r["started_at"][:16].replace("T", " "), fmt_price(r["min_price"], cfg.currency),
                  fmt_departure(r["best_departure"]), str(r["n"]))
    console.print(t)


def cmd_calendar(args, cfg, store):
    o, d = args.origin.upper(), args.destination.upper()
    rows = store.calendar(o, d)
    if not rows:
        console.print("[yellow]Sin datos para esa ruta. Ejecuta primero `scan`.[/]")
        return
    st = store.route_stats(o, d, cfg.lookback_days)
    median = st["median"]
    t = Table(title=f"{o}->{d}: precio más barato por fecha (último escaneo)")
    t.add_column("Fecha")
    t.add_column("Día")
    t.add_column("Precio", justify="right")
    t.add_column("vs mediana", justify="right")
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    for r in rows:
        dt = date.fromisoformat(r["d"])
        rel = (1 - r["price"] / median) if median else None
        price_s = fmt_price(r["price"], cfg.currency)
        if median and r["price"] <= cfg.ratio * median:
            price_s = f"[bold green]{price_s}[/]"
        rel_s = f"{-rel:+.0%}" if rel is not None else "-"
        t.add_row(r["d"], dias[dt.weekday()], price_s, rel_s)
    console.print(t)


def cmd_routes(args, cfg, store):
    t = Table(title=f"{len(cfg.routes)} rutas configuradas")
    t.add_column("Origen")
    t.add_column("Destino")
    t.add_column("Tipo")
    for r in cfg.routes:
        t.add_row(r.origin, r.destination, r.kind)
    console.print(t)


def cmd_status(args, cfg, store):
    s = store.summary()
    console.print(f"Base de datos: {cfg.db_path}")
    console.print(f"Observaciones: {s['n']}  Rutas con datos: {s['routes']}  Escaneos: {s['scans']}")
    console.print(f"Primera: {s['first'] or '-'}   Última: {s['last'] or '-'}")
    prov = make_provider(cfg, None)
    console.print(f"Proveedor activo: [cyan]{prov.name}[/]")


def cmd_watch(args, cfg, store):
    every = args.every * 3600
    console.print(f"Modo vigilancia: escaneo cada {args.every} h. Ctrl+C para salir.")
    while True:
        cmd_scan(args, cfg, store)
        deals = find_deals(store, cfg)
        new = [d for d in deals if store.mark_deal(d.key, d.price)]
        print_deals(deals, args.top)
        if new:
            console.print(f"[bold green]{len(new)} chollo(s) nuevo(s):[/]")
            for d in new:
                console.print("  • " + deal_line(d))
                console.print(f"    {d.links['Google Flights']}", markup=False, highlight=False)
            out = cfgmod.ROOT / f"chollos-{cfg.db_path.stem}.html"
            write_report(deals[: args.top], out, "Chollos de vuelo", cfg.currency,
                         simulated=store.last_provider() == "mock")
            console.print(f"  Informe HTML actualizado: {out}")
            if cfg.telegram and send_telegram(new):
                console.print("  (enviado a Telegram)")
        warn_if_mock(store)
        if args.once:
            break
        console.print(f"Durmiendo {args.every} h...")
        try:
            time.sleep(every)
        except KeyboardInterrupt:
            break


# ------------------------------------------------------------------ parser --
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vuelos", description="Rastreador de vuelos baratos desde Colombia")
    p.add_argument("--config", help="ruta a config.yaml alternativo")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="descarga precios de todas las rutas y los guarda")
    s.add_argument("--provider", choices=["travelpayouts", "amadeus", "mock"])
    s.add_argument("--months", type=int, help="meses hacia adelante (por defecto config)")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("deals", help="muestra los chollos del último escaneo")
    s.add_argument("--top", type=int, default=40)
    s.add_argument("--ratio", type=float, help="umbral vs mediana, ej. 0.6 (por defecto config)")
    s.add_argument("--kind", choices=["nacional", "internacional"])
    s.add_argument("--links", action="store_true", help="imprime las URL de compra de cada chollo")
    s.set_defaults(fn=cmd_deals)

    s = sub.add_parser("report", help="genera un HTML con los chollos y botones de compra")
    s.add_argument("--top", type=int, default=100)
    s.add_argument("--ratio", type=float)
    s.add_argument("--kind", choices=["nacional", "internacional"])
    s.add_argument("--out", help="nombre del archivo HTML (por defecto chollos-<db>.html)")
    s.add_argument("--open", action="store_true", help="abrir en el navegador al terminar")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("history", help="evolución del precio mínimo de una ruta")
    s.add_argument("origin")
    s.add_argument("destination")
    s.add_argument("--days", type=int, default=90)
    s.set_defaults(fn=cmd_history)

    s = sub.add_parser("calendar", help="precio por fecha de salida de una ruta")
    s.add_argument("origin")
    s.add_argument("destination")
    s.set_defaults(fn=cmd_calendar)

    s = sub.add_parser("watch", help="escanea periódicamente y avisa de chollos nuevos")
    s.add_argument("--every", type=float, default=6, help="horas entre escaneos")
    s.add_argument("--once", action="store_true", help="un solo ciclo (útil para cron)")
    s.add_argument("--provider", choices=["travelpayouts", "amadeus", "mock"])
    s.add_argument("--months", type=int)
    s.add_argument("--top", type=int, default=25)
    s.set_defaults(fn=cmd_watch)

    sub.add_parser("routes", help="lista las rutas configuradas").set_defaults(fn=cmd_routes)
    sub.add_parser("status", help="estado de la base de datos y proveedor").set_defaults(fn=cmd_status)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = cfgmod.load(args.config)
    store = Store(cfg.db_path)
    try:
        args.fn(args, cfg, store)
    except KeyboardInterrupt:
        console.print("\nInterrumpido.")
        sys.exit(130)
