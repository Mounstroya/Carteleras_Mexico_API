"""
Cliente de la API REST interna que usa cinemex.com.

Descubierta a partir de un HAR capturado navegando el sitio. Es una API
REST normal (no GraphQL) en api.cinemex.com, versionada (/rest/v2.37.2/).
Solo requiere un header `X-API-Consumer-Key` que va embebido en el JS del
sitio (llave publica de cliente, no un secreto de sesion).

Endpoints usados:
- GET /cinemas/                                  -> catalogo completo de cines (con lat/lng)
- GET /movies/                                   -> cartelera nacional (peliculas en exhibicion)
- GET /cinemas/area/{area_id}/movies/?date=...   -> peliculas + horarios de todos los cines de esa zona, para una fecha
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date as date_cls
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.cinemex.com/rest/v2.37.2"
API_KEY = "XXQha7vz4kdvoMSdixhN"

HEADERS = {
    "Accept": "*/*",
    "X-API-Consumer-Key": API_KEY,
    "Referer": "https://cinemex.com/",
    "Origin": "https://cinemex.com",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) "
        "Gecko/20100101 Firefox/140.0"
    ),
}

CACHE_PATH = Path(__file__).parent / "cache_cinemex_cinemas.json"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 1 semana


def _get(path: str, params: dict | None = None) -> Any:
    resp = requests.get(f"{API_URL}{path}", params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------
# Cines
# --------------------------------------------------------------------------


@dataclass
class Cinema:
    id: int
    name: str
    lat: float
    lng: float
    area_id: int
    area_name: str
    state_name: str


def fetch_cinemas() -> list[Cinema]:
    """Trae el catalogo completo de cines (sin cache)."""
    raw = _get("/cinemas/")
    cinemas = []
    for c in raw:
        if c.get("lat") is None or c.get("lng") is None:
            continue
        cinemas.append(
            Cinema(
                id=c["id"],
                name=c["name"],
                lat=float(c["lat"]),
                lng=float(c["lng"]),
                area_id=c["area"]["id"],
                area_name=c["area"]["name"],
                state_name=c["state"]["name"],
            )
        )
    return cinemas


def get_cinemas(force_refresh: bool = False) -> list[Cinema]:
    """Igual que fetch_cinemas pero con cache local de ~1 semana en disco."""
    if not force_refresh and CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            return [Cinema(**c) for c in raw["cinemas"]]

    cinemas = fetch_cinemas()
    CACHE_PATH.write_text(
        json.dumps({"cinemas": [c.__dict__ for c in cinemas]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return cinemas


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def nearest_cinemas(
    lat: float, lng: float, cinemas: list[Cinema] | None = None, n: int = 5
) -> list[tuple[Cinema, float]]:
    """Devuelve los n cines mas cercanos a (lat, lng) como (Cinema, distancia_km)."""
    if cinemas is None:
        cinemas = get_cinemas()
    with_dist = [(c, _haversine_km(lat, lng, c.lat, c.lng)) for c in cinemas]
    with_dist.sort(key=lambda x: x[1])
    return with_dist[:n]


# --------------------------------------------------------------------------
# Cartelera nacional (para resolver nombre de pelicula -> id)
# --------------------------------------------------------------------------


@dataclass
class Movie:
    id: int
    name: str


def get_movies() -> list[Movie]:
    raw = _get("/movies/")
    return [Movie(id=m["id"], name=m["name"]) for m in raw]


def _normalize(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def find_movie(query: str, movies: list[Movie]) -> Movie | None:
    """Busca la mejor coincidencia por nombre (ignora acentos/mayusculas)."""
    q = _normalize(query)

    candidates = [m for m in movies if q in _normalize(m.name)]
    if candidates:
        candidates.sort(key=lambda m: len(m.name))
        return candidates[0]

    import difflib

    names = {m.id: _normalize(m.name) for m in movies}
    match = difflib.get_close_matches(q, names.values(), n=1, cutoff=0.5)
    if not match:
        return None
    for m in movies:
        if _normalize(m.name) == match[0]:
            return m
    return None


# --------------------------------------------------------------------------
# Horarios por zona
# --------------------------------------------------------------------------


@dataclass
class Showtime:
    date: str
    time: str
    version_label: str
    screen: str | None


def get_area_billboard(area_id: int, target_date: str) -> dict:
    """Trae peliculas + horarios de TODOS los cines de una zona, para una fecha (YYYY-MM-DD)."""
    return _get(f"/cinemas/area/{area_id}/movies/", params={"include_dates": 1, "date": target_date})


def _extract_showtimes_for_cinema(area_data: dict, cinema_id: int, movie_id: int) -> list[Showtime]:
    result: list[Showtime] = []
    for cinema in area_data.get("cinemas", []):
        if cinema["id"] != cinema_id:
            continue
        for movie in cinema.get("movies", []):
            if movie["id"] != movie_id:
                continue
            for version in movie.get("versions", []):
                for session in version.get("sessions", []):
                    if session["cinema_id"] != cinema_id:
                        continue
                    result.append(
                        Showtime(
                            date=session["datetime"].split("T")[0],
                            time=session["datetime"].split("T")[1][:5],
                            version_label=version["label"],
                            screen=session.get("auditorium_name"),
                        )
                    )
    return result


# --------------------------------------------------------------------------
# Funcion de alto nivel: lo que va a usar el agente
# --------------------------------------------------------------------------


def find_showtimes_near(
    movie_query: str,
    lat: float,
    lng: float,
    target_date: str | None = None,
    n_cinemas: int = 5,
) -> dict[str, Any]:
    """
    Dado un nombre de pelicula (aproximado), una ubicacion (lat, lng) y
    opcionalmente una fecha (YYYY-MM-DD, default hoy), regresa los cines
    Cinemex mas cercanos y sus horarios para esa pelicula.
    """
    if target_date is None:
        target_date = date_cls.today().isoformat()

    movies = get_movies()
    movie = find_movie(movie_query, movies)
    if movie is None:
        return {"movie_query": movie_query, "movie": None, "date": target_date, "cinemas": []}

    cinemas = get_cinemas()
    near = nearest_cinemas(lat, lng, cinemas, n=n_cinemas)

    # agrupa por area para no pedir la misma zona mas de una vez
    area_ids = {c.area_id for c, _ in near}
    area_data = {area_id: get_area_billboard(area_id, target_date) for area_id in area_ids}

    results = []
    for cinema, dist_km in near:
        showtimes = _extract_showtimes_for_cinema(area_data[cinema.area_id], cinema.id, movie.id)
        if not showtimes:
            continue
        results.append(
            {
                "cinema": cinema.name,
                "cinema_id": cinema.id,
                "area": cinema.area_name,
                "distance_km": round(dist_km, 1),
                "showtimes": [
                    {"date": s.date, "time": s.time, "version": s.version_label}
                    for s in showtimes
                ],
            }
        )

    return {
        "movie_query": movie_query,
        "movie": {"id": movie.id, "name": movie.name},
        "date": target_date,
        "cinemas": results,
    }
