from __future__ import annotations

import time

import requests

from ..storage import Observation


class ProviderError(RuntimeError):
    pass


class Provider:
    """Interfaz común: devuelve observaciones de precio para una ruta y un mes."""

    name = "base"

    def search_month(
        self, origin: str, destination: str, month: str, one_way: bool, currency: str
    ) -> list[Observation]:
        """`month` en formato YYYY-MM."""
        raise NotImplementedError

    # Utilidad compartida: GET con reintentos ante 429/5xx.
    @staticmethod
    def get_json(url: str, *, params=None, headers=None, retries: int = 3, timeout: int = 30) -> dict:
        last: Exception | None = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            except requests.RequestException as exc:  # red caída, DNS, etc.
                last = exc
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                last = ProviderError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        raise ProviderError(f"Fallo tras {retries} intentos: {last}")
