from __future__ import annotations

from ..config import Config, env
from .base import Provider


def make_provider(cfg: Config, override: str | None = None) -> Provider:
    """Elige el proveedor según config/.env. `override` fuerza uno concreto."""
    name = (override or cfg.provider or "auto").lower()
    if name == "auto":
        if env("TRAVELPAYOUTS_TOKEN"):
            name = "travelpayouts"
        elif env("AMADEUS_CLIENT_ID") and env("AMADEUS_CLIENT_SECRET"):
            name = "amadeus"
        else:
            name = "mock"

    if name == "travelpayouts":
        from .travelpayouts import TravelpayoutsProvider
        return TravelpayoutsProvider(env("TRAVELPAYOUTS_TOKEN"))
    if name == "amadeus":
        from .amadeus import AmadeusProvider
        return AmadeusProvider(
            env("AMADEUS_CLIENT_ID"), env("AMADEUS_CLIENT_SECRET"), env("AMADEUS_ENV", "test")
        )
    if name == "mock":
        from .mock import MockProvider
        return MockProvider()
    raise ValueError(f"Proveedor desconocido: {name}")
