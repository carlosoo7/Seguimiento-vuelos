from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .storage import Store


@dataclass
class Deal:
    origin: str
    destination: str
    kind: str
    departure_at: str
    price: float
    currency: str
    airline: str
    flight_number: str
    transfers: int
    median: float | None
    n_obs: int
    reason: str          # "mediana" | "tope" | "mediana+tope"
    link: str
    return_at: str | None = None

    @property
    def discount(self) -> float | None:
        """Fracción de descuento frente a la mediana (0.6 = 60 % más barato)."""
        if not self.median:
            return None
        return 1 - self.price / self.median

    @property
    def key(self) -> str:
        return f"{self.origin}-{self.destination}-{self.departure_at[:16]}"

    @property
    def links(self) -> dict[str, str]:
        """Enlaces de compra {nombre: url}."""
        from .links import purchase_links
        return purchase_links(self.origin, self.destination, self.departure_at, self.return_at, self.link)

    def score(self) -> float:
        """Para ordenar: mayor descuento primero; sin mediana, ordena por precio."""
        return self.discount if self.discount is not None else 0.0


def find_deals(store: Store, cfg: Config, ratio: float | None = None) -> list[Deal]:
    """Compara la última foto de precios de cada ruta con su histórico y los topes."""
    ratio = ratio if ratio is not None else cfg.ratio
    stats_cache: dict[tuple[str, str], dict] = {}
    deals: list[Deal] = []

    for row in store.latest_per_route():
        route = (row["origin"], row["destination"])
        if route not in stats_cache:
            stats_cache[route] = store.route_stats(*route, cfg.lookback_days)
        st = stats_cache[route]
        kind = cfg.kind_of(*route)
        cap = cfg.caps.get(kind)
        price = float(row["price"])

        reasons = []
        reliable = st["n"] >= cfg.min_observations and st["median"]
        if reliable and price <= ratio * st["median"]:
            reasons.append("mediana")
        if cap is not None and price <= cap:
            reasons.append("tope")
        if not reasons:
            continue

        deals.append(
            Deal(
                origin=row["origin"],
                destination=row["destination"],
                kind=kind,
                departure_at=row["departure_at"],
                price=price,
                currency=row["currency"],
                airline=row["airline"] or "",
                flight_number=row["flight_number"] or "",
                transfers=int(row["transfers"] or 0),
                median=st["median"] if reliable else None,
                n_obs=st["n"],
                reason="+".join(reasons),
                link=row["link"] or "",
                return_at=row["return_at"],
            )
        )

    deals.sort(key=lambda d: (-d.score(), d.price))
    return deals
