from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass
class Route:
    origin: str
    destination: str
    kind: str  # "nacional" | "internacional"

    @property
    def key(self) -> str:
        return f"{self.origin}-{self.destination}"


@dataclass
class Config:
    currency: str
    provider: str
    months_ahead: int
    one_way: bool
    pause_seconds: float
    routes: list[Route]
    ratio: float
    min_observations: int
    lookback_days: int
    caps: dict[str, float]
    telegram: bool
    db_path: Path = field(default_factory=lambda: ROOT / "vuelos.db")

    def kind_of(self, origin: str, destination: str) -> str:
        for r in self.routes:
            if r.origin == origin and r.destination == destination:
                return r.kind
        return "internacional"


def load(path: Path | None = None) -> Config:
    path = path or ROOT / "config.yaml"
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    dests = raw.get("destinations", {})
    routes: list[Route] = []
    for origin in raw.get("origins", []):
        for d in dests.get("nacionales", []):
            if d != origin:
                routes.append(Route(origin, d, "nacional"))
        for d in dests.get("internacionales", []):
            routes.append(Route(origin, d, "internacional"))

    scan = raw.get("scan", {})
    deals = raw.get("deals", {})
    return Config(
        currency=str(raw.get("currency", "COP")).upper(),
        provider=str(raw.get("provider", "auto")).lower(),
        months_ahead=int(scan.get("months_ahead", 3)),
        one_way=bool(scan.get("one_way", True)),
        pause_seconds=float(scan.get("pause_seconds", 0.4)),
        routes=routes,
        ratio=float(deals.get("ratio", 0.5)),
        min_observations=int(deals.get("min_observations", 10)),
        lookback_days=int(deals.get("lookback_days", 90)),
        caps={k: float(v) for k, v in (deals.get("absolute_caps") or {}).items()},
        telegram=bool(raw.get("notify", {}).get("telegram", False)),
        db_path=(ROOT / raw["db_path"]) if raw.get("db_path") else ROOT / "vuelos.db",
    )


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()
