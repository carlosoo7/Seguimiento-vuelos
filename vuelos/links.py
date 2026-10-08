"""Enlaces de compra (deep links) a buscadores de vuelos para una ruta y fecha."""
from __future__ import annotations

from datetime import date
from urllib.parse import quote


def _d(iso: str) -> date:
    return date.fromisoformat(iso[:10])


def google_flights(origin: str, destination: str, departure: str, ret: str | None = None) -> str:
    q = f"Flights from {origin} to {destination} on {_d(departure).isoformat()}"
    q += f" returning {_d(ret).isoformat()}" if ret else " one way"
    return "https://www.google.com/travel/flights?hl=es&curr=COP&q=" + quote(q)


def skyscanner(origin: str, destination: str, departure: str, ret: str | None = None) -> str:
    dep = _d(departure).strftime("%y%m%d")
    path = f"{origin.lower()}/{destination.lower()}/{dep}/"
    if ret:
        path += _d(ret).strftime("%y%m%d") + "/"
    return (
        f"https://www.skyscanner.com.co/transport/flights/{path}"
        "?adults=1&currency=COP&locale=es-CO&market=CO&cabinclass=economy"
    )


def kayak(origin: str, destination: str, departure: str, ret: str | None = None) -> str:
    url = f"https://www.kayak.com.co/flights/{origin}-{destination}/{_d(departure).isoformat()}"
    if ret:
        url += f"/{_d(ret).isoformat()}"
    return url + "?sort=price_a"


def aviasales(origin: str, destination: str, departure: str, ret: str | None = None) -> str:
    code = f"{origin}{_d(departure).strftime('%d%m')}{destination}"
    if ret:
        code += _d(ret).strftime("%d%m")
    return f"https://www.aviasales.com/search/{code}1?currency=cop"


def purchase_links(
    origin: str, destination: str, departure: str, ret: str | None = None, provider_link: str = ""
) -> dict[str, str]:
    """Devuelve {nombre: url} en orden de preferencia."""
    links = {
        "Google Flights": google_flights(origin, destination, departure, ret),
        "Skyscanner": skyscanner(origin, destination, departure, ret),
        "Kayak": kayak(origin, destination, departure, ret),
        "Aviasales": aviasales(origin, destination, departure, ret),
    }
    if provider_link and provider_link not in links.values():
        links["Proveedor"] = provider_link
    return links
