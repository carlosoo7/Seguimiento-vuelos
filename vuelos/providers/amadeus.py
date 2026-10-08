from __future__ import annotations

import calendar
import time
from datetime import date, timedelta

import requests

from ..storage import Observation
from .base import Provider, ProviderError

HOSTS = {"test": "https://test.api.amadeus.com", "production": "https://api.amadeus.com"}


class AmadeusProvider(Provider):
    """Amadeus Self-Service.

    1) Intenta `flight-dates` (precio más barato por día, 1 llamada por ruta/mes).
    2) Si no está disponible para la ruta (habitual en el entorno test), muestrea
       `flight-offers` cada `step_days` días, 1 llamada por fecha.
    Docs: https://developers.amadeus.com/self-service/category/flights
    """

    name = "amadeus"

    def __init__(self, client_id: str, client_secret: str, env: str = "test", step_days: int = 3):
        if not client_id or not client_secret:
            raise ProviderError("Faltan AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET en .env")
        self.host = HOSTS.get(env, HOSTS["test"])
        self.client_id = client_id
        self.client_secret = client_secret
        self.step_days = step_days
        self._token: str | None = None
        self._token_exp = 0.0

    # --- auth ---------------------------------------------------------------
    def _headers(self) -> dict:
        if not self._token or time.time() > self._token_exp - 30:
            resp = requests.post(
                f"{self.host}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                raise ProviderError(f"Amadeus auth: HTTP {resp.status_code} {resp.text[:200]}")
            body = resp.json()
            self._token = body["access_token"]
            self._token_exp = time.time() + float(body.get("expires_in", 1700))
        return {"Authorization": f"Bearer {self._token}"}

    # --- búsqueda -----------------------------------------------------------
    def search_month(self, origin, destination, month, one_way, currency):
        year, mon = (int(x) for x in month.split("-"))
        first = date(year, mon, 1)
        last = date(year, mon, calendar.monthrange(year, mon)[1])
        today = date.today()
        if last < today:
            return []
        first = max(first, today + timedelta(days=1))

        obs = self._flight_dates(origin, destination, first, last, one_way, currency)
        if obs:
            return obs
        return self._sample_offers(origin, destination, first, last, one_way, currency)

    def _flight_dates(self, origin, destination, first, last, one_way, currency):
        params = {
            "origin": origin,
            "destination": destination,
            "departureDate": f"{first.isoformat()},{last.isoformat()}",
            "oneWay": "true" if one_way else "false",
            "nonStop": "false",
            "viewBy": "DATE",
        }
        try:
            data = self.get_json(
                f"{self.host}/v1/shopping/flight-dates", params=params, headers=self._headers(), retries=1
            )
        except ProviderError:
            return []  # ruta sin datos cacheados -> fallback
        out = []
        for d in data.get("data", []):
            out.append(
                Observation(
                    origin=origin,
                    destination=destination,
                    departure_at=d["departureDate"],
                    return_at=d.get("returnDate"),
                    price=float(d["price"]["total"]),
                    currency=str(data.get("meta", {}).get("currency", currency)).upper(),
                    link=d.get("links", {}).get("flightOffers", ""),
                )
            )
        return out

    def _sample_offers(self, origin, destination, first, last, one_way, currency):
        out: list[Observation] = []
        day = first
        while day <= last:
            params = {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": day.isoformat(),
                "adults": 1,
                "currencyCode": currency,
                "max": 10,
            }
            if not one_way:
                params["returnDate"] = (day + timedelta(days=7)).isoformat()
            try:
                data = self.get_json(
                    f"{self.host}/v2/shopping/flight-offers", params=params, headers=self._headers()
                )
            except ProviderError:
                day += timedelta(days=self.step_days)
                continue
            for offer in data.get("data", []):
                it = offer["itineraries"][0]
                seg0 = it["segments"][0]
                out.append(
                    Observation(
                        origin=origin,
                        destination=destination,
                        departure_at=seg0["departure"]["at"],
                        return_at=(
                            offer["itineraries"][1]["segments"][0]["departure"]["at"]
                            if len(offer["itineraries"]) > 1 else None
                        ),
                        price=float(offer["price"].get("grandTotal", offer["price"]["total"])),
                        currency=offer["price"].get("currency", currency),
                        airline=seg0.get("carrierCode", ""),
                        flight_number=f"{seg0.get('carrierCode','')}{seg0.get('number','')}",
                        transfers=len(it["segments"]) - 1,
                    )
                )
            day += timedelta(days=self.step_days)
            time.sleep(0.2)
        return out
