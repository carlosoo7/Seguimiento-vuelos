from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class Observation:
    origin: str
    destination: str
    departure_at: str          # ISO 8601, idealmente con hora
    price: float
    currency: str
    airline: str = ""
    flight_number: str = ""
    transfers: int = 0
    return_at: str | None = None
    link: str = ""

    @property
    def departure_date(self) -> str:
        return self.departure_at[:10]


SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    provider TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    observed_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_at TEXT NOT NULL,
    return_at TEXT,
    airline TEXT,
    flight_number TEXT,
    transfers INTEGER,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    link TEXT
);
CREATE INDEX IF NOT EXISTS idx_prices_route ON prices(origin, destination, departure_at);
CREATE INDEX IF NOT EXISTS idx_prices_scan ON prices(scan_id);
CREATE TABLE IF NOT EXISTS deals_seen (
    key TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    price REAL NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # --- escritura -------------------------------------------------------
    def start_scan(self, provider: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO scans(started_at, provider) VALUES (?, ?)", (utcnow(), provider)
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_many(self, scan_id: int, provider: str, obs: list[Observation]) -> None:
        now = utcnow()
        self.conn.executemany(
            """INSERT INTO prices(scan_id, observed_at, provider, origin, destination,
               departure_at, return_at, airline, flight_number, transfers, price, currency, link)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (scan_id, now, provider, o.origin, o.destination, o.departure_at, o.return_at,
                 o.airline, o.flight_number, o.transfers, o.price, o.currency, o.link)
                for o in obs
            ],
        )
        self.conn.commit()

    # --- lectura ---------------------------------------------------------
    def latest_per_route(self) -> list[sqlite3.Row]:
        """Vuelo más barato por (ruta, fecha de salida) del escaneo más reciente de cada ruta."""
        return self.conn.execute(
            """
            WITH last AS (
                SELECT origin, destination, MAX(scan_id) AS scan_id
                FROM prices GROUP BY origin, destination
            ),
            ranked AS (
                SELECT p.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY p.origin, p.destination, substr(p.departure_at,1,10)
                           ORDER BY p.price, p.departure_at
                       ) AS rn
                FROM prices p JOIN last l
                  ON p.origin=l.origin AND p.destination=l.destination AND p.scan_id=l.scan_id
            )
            SELECT * FROM ranked WHERE rn = 1
            ORDER BY origin, destination, departure_at
            """
        ).fetchall()

    def route_stats(self, origin: str, destination: str, lookback_days: int) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        prices = [
            r[0]
            for r in self.conn.execute(
                "SELECT price FROM prices WHERE origin=? AND destination=? AND observed_at>=?",
                (origin, destination, since),
            )
        ]
        if not prices:
            return {"n": 0, "median": None, "p25": None, "min": None}
        prices.sort()
        p25 = statistics.quantiles(prices, n=4)[0] if len(prices) >= 2 else prices[0]
        return {"n": len(prices), "median": statistics.median(prices), "p25": p25, "min": prices[0]}

    def history(self, origin: str, destination: str, days: int) -> list[sqlite3.Row]:
        """Un punto por escaneo: precio mínimo encontrado y cuándo salía ese vuelo."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return self.conn.execute(
            """SELECT s.started_at, MIN(p.price) AS min_price,
                      (SELECT departure_at FROM prices p2 WHERE p2.scan_id=p.scan_id
                         AND p2.origin=p.origin AND p2.destination=p.destination
                         ORDER BY price LIMIT 1) AS best_departure,
                      COUNT(*) AS n
               FROM prices p JOIN scans s ON s.id=p.scan_id
               WHERE p.origin=? AND p.destination=? AND p.observed_at>=?
               GROUP BY p.scan_id ORDER BY s.started_at""",
            (origin, destination, since),
        ).fetchall()

    def calendar(self, origin: str, destination: str) -> list[sqlite3.Row]:
        """Precio más barato por fecha de salida en el último escaneo de la ruta."""
        return self.conn.execute(
            """SELECT substr(departure_at,1,10) AS d, MIN(price) AS price
               FROM prices WHERE origin=? AND destination=?
                 AND scan_id=(SELECT MAX(scan_id) FROM prices WHERE origin=? AND destination=?)
               GROUP BY d ORDER BY d""",
            (origin, destination, origin, destination),
        ).fetchall()

    def mark_deal(self, key: str, price: float) -> bool:
        """True si el chollo es nuevo (no se había avisado a ese precio o menor)."""
        row = self.conn.execute("SELECT price FROM deals_seen WHERE key=?", (key,)).fetchone()
        if row and row[0] <= price:
            return False
        self.conn.execute(
            "INSERT OR REPLACE INTO deals_seen(key, first_seen, price) VALUES (?,?,?)",
            (key, utcnow(), price),
        )
        self.conn.commit()
        return True

    def last_provider(self) -> str | None:
        row = self.conn.execute("SELECT provider FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def summary(self) -> dict:
        r = self.conn.execute(
            "SELECT COUNT(*) AS n, COUNT(DISTINCT origin||destination) AS routes, "
            "COUNT(DISTINCT scan_id) AS scans, MIN(observed_at) AS first, MAX(observed_at) AS last "
            "FROM prices"
        ).fetchone()
        return dict(r)
