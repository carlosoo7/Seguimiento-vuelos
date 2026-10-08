from __future__ import annotations

import calendar
import hashlib
import random
from datetime import date, datetime, timedelta

from ..storage import Observation
from .base import Provider

# Precio base aproximado por tramo (COP) para que la simulación sea verosímil.
BASE_DOMESTIC = 220_000
BASE_INTL = {
    "MIA": 1_100_000, "FLL": 1_000_000, "MCO": 1_150_000, "JFK": 1_500_000,
    "MEX": 1_000_000, "CUN": 950_000, "PTY": 700_000, "SJO": 800_000,
    "LIM": 750_000, "UIO": 650_000, "SCL": 1_300_000, "EZE": 1_500_000,
    "GRU": 1_400_000, "MAD": 2_600_000, "BCN": 2_700_000, "PUJ": 1_050_000,
}
AIRLINES = ["AV", "LA", "VE", "JA", "WN", "CM", "AA"]
HOURS = [5, 6, 7, 9, 11, 13, 15, 17, 19, 21, 23]


class MockProvider(Provider):
    """Genera precios sintéticos con patrón semanal y chollos ocasionales.

    Sirve para probar el flujo completo sin credenciales. El azar es determinista
    por (ruta, fecha, día de escaneo) así que el histórico tiene sentido.
    """

    name = "mock"

    def search_month(self, origin, destination, month, one_way, currency):
        year, mon = (int(x) for x in month.split("-"))
        days = calendar.monthrange(year, mon)[1]
        today = date.today()
        base = BASE_INTL.get(destination, BASE_DOMESTIC)
        out: list[Observation] = []
        for day in range(1, days + 1):
            d = date(year, mon, day)
            if d <= today:
                continue
            seed = hashlib.md5(f"{origin}{destination}{d}{today}".encode()).hexdigest()
            rng = random.Random(seed)
            weekend = 1.25 if d.weekday() in (4, 6) else 1.0           # viernes y domingo más caros
            lead = 1.0 + max(0, 21 - (d - today).days) * 0.02            # sube al acercarse la fecha
            for _ in range(rng.randint(2, 4)):
                price = base * weekend * lead * rng.uniform(0.85, 1.35)
                if rng.random() < 0.01:                                 # ~1 % chollos reales
                    price *= rng.uniform(0.3, 0.55)
                hour = rng.choice(HOURS)
                dep = datetime(d.year, d.month, d.day, hour, rng.choice([0, 10, 25, 40, 55]))
                out.append(
                    Observation(
                        origin=origin,
                        destination=destination,
                        departure_at=dep.strftime("%Y-%m-%dT%H:%M:00-05:00"),
                        return_at=None if one_way else (dep + timedelta(days=7)).isoformat(),
                        price=round(price, -3),
                        currency=currency,
                        airline=rng.choice(AIRLINES),
                        flight_number=str(rng.randint(100, 9999)),
                        transfers=0 if rng.random() < 0.7 else 1,
                        link="",
                    )
                )
        return out
