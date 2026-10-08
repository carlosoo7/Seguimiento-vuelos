from __future__ import annotations

from ..storage import Observation
from .base import Provider, ProviderError

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsProvider(Provider):
    """Aviasales Data API (Travelpayouts).

    Devuelve los precios más baratos ya cacheados por Aviasales para una ruta y mes.
    Una llamada por ruta/mes. Ideal para escanear muchas rutas sin agotar cuotas.
    Docs: https://support.travelpayouts.com/hc/en-us/articles/203956163
    """

    name = "travelpayouts"

    def __init__(self, token: str):
        if not token:
            raise ProviderError("Falta TRAVELPAYOUTS_TOKEN en .env")
        self.token = token

    def search_month(self, origin, destination, month, one_way, currency):
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": month,          # YYYY-MM -> todo el mes
            "one_way": "true" if one_way else "false",
            "direct": "false",
            "sorting": "price",
            "unique": "false",
            "limit": 1000,
            "page": 1,
            "currency": currency.lower(),
            "market": "co",
            "token": self.token,
        }
        data = self.get_json(API, params=params)
        if not data.get("success", True):
            raise ProviderError(f"Travelpayouts error: {data.get('error')}")
        out: list[Observation] = []
        for item in data.get("data", []):
            if not item.get("price") or not item.get("departure_at"):
                continue
            out.append(
                Observation(
                    origin=item.get("origin", origin),
                    destination=item.get("destination", destination),
                    departure_at=item["departure_at"],
                    return_at=item.get("return_at") or None,
                    price=float(item["price"]),
                    currency=str(data.get("currency", currency)).upper(),
                    airline=item.get("airline", ""),
                    flight_number=str(item.get("flight_number", "")),
                    transfers=int(item.get("transfers", 0) or 0),
                    link="https://www.aviasales.com" + item.get("link", ""),
                )
            )
        return out
