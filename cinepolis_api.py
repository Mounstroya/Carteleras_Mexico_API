"""
Cliente de la API GraphQL interna que usa cinepolis.com/mx.

Descubierta a partir de un HAR capturado navegando el sitio. Todos los
endpoints cuelgan de api-g.cinepolis.com y solo requieren un header
`x-apikey` que va embebido en el bundle de JS del sitio (no es un secreto
de sesión ni de usuario, es la misma llave que usa cualquier navegador
al cargar la página).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Any

import requests


def _load_dotenv(path: Path) -> None:
    """Carga KEY=VALUE de un .env local a os.environ, sin pisar variables
    que ya esten definidas (ej. por el entorno real)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(Path(__file__).parent / ".env")

API_URL = "https://api-g.cinepolis.com"
API_KEY = "lQM6Mkvri1iHksKKCfpAiwGXq0YUZA7Nn6XAXRPr4i13LwXo"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "x-apikey": API_KEY,
    "Referer": "https://cinepolis.com/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) "
        "Gecko/20100101 Firefox/140.0"
    ),
}

CACHE_PATH = Path(__file__).parent / "cache_cities.json"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 1 semana

# Relay opcional: si Cinepolis bloquea la IP de donde corre este script
# (Cloudflare suele bloquear IPs de datacenter/cloud), se puede desviar el
# trafico por un relay HTTP corriendo en una IP residencial. Se activa solo
# si ambas variables de entorno estan definidas; si no, pega directo a la
# API como siempre. El relay reenvia unicamente a api-g.cinepolis.com (no
# es un proxy abierto) y espera el mismo body+respuesta que la API real.
RELAY_URL = os.environ.get("CINEPOLIS_RELAY_URL", "").rstrip("/")
RELAY_TOKEN = os.environ.get("CINEPOLIS_RELAY_TOKEN", "")


def _graphql(path: str, operation_name: str, query: str, variables: dict) -> dict:
    body = {"operationName": operation_name, "variables": variables, "query": query}

    if RELAY_URL and RELAY_TOKEN:
        resp = requests.post(
            f"{RELAY_URL}/relay",
            params={"path": path},
            json=body,
            headers={"X-Worker-Token": RELAY_TOKEN},
            timeout=25,
        )
    else:
        resp = requests.post(f"{API_URL}{path}", json=body, headers=HEADERS, timeout=20)

    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL error en {operation_name}: {payload['errors']}")
    return payload["data"]


# --------------------------------------------------------------------------
# Cines / ciudades
# --------------------------------------------------------------------------

CITIES_QUERY = """
query Cities($countryId: String!) {
  cities(country_id: $countryId) {
    edges {
      node {
        id
        name
        timezone
        cinemas {
          id
          name
          cityId
          lat
          lng
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""


@dataclass
class Cinema:
    id: str
    name: str
    city_id: str
    city_name: str
    timezone: str
    lat: float
    lng: float


def fetch_cinemas(country_id: str = "MX") -> list[Cinema]:
    """Trae todas las ciudades/cines desde la API (sin caché)."""
    data = _graphql(
        "/shared-services/locations/graphql", "Cities", CITIES_QUERY, {"countryId": country_id}
    )
    cinemas: list[Cinema] = []
    for edge in data["cities"]["edges"]:
        city = edge["node"]
        for c in city["cinemas"]:
            if c["lat"] is None or c["lng"] is None:
                continue
            cinemas.append(
                Cinema(
                    id=c["id"],
                    name=c["name"],
                    city_id=city["id"],
                    city_name=city["name"],
                    timezone=city["timezone"],
                    lat=float(c["lat"]),
                    lng=float(c["lng"]),
                )
            )
    return cinemas


def get_cinemas(country_id: str = "MX", force_refresh: bool = False) -> list[Cinema]:
    """Igual que fetch_cinemas pero con caché local de ~1 semana en disco."""
    if not force_refresh and CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_TTL_SECONDS:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if raw.get("country_id") == country_id:
                return [Cinema(**c) for c in raw["cinemas"]]

    cinemas = fetch_cinemas(country_id)
    CACHE_PATH.write_text(
        json.dumps(
            {"country_id": country_id, "cinemas": [c.__dict__ for c in cinemas]},
            ensure_ascii=False,
        ),
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
    lat: float, lng: float, cinemas: list[Cinema] | None = None, n: int = 5, country_id: str = "MX"
) -> list[tuple[Cinema, float]]:
    """Devuelve las n cines mas cercanos a (lat, lng) como (Cinema, distancia_km)."""
    if cinemas is None:
        cinemas = get_cinemas(country_id)
    with_dist = [(c, _haversine_km(lat, lng, c.lat, c.lng)) for c in cinemas]
    with_dist.sort(key=lambda x: x[1])
    return with_dist[:n]


# --------------------------------------------------------------------------
# Cartelera (peliculas)
# --------------------------------------------------------------------------

MOVIES_QUERY = """
query Movies($countryId: String!, $category: String, $limit: Int) {
  movies(countryId: $countryId, category: $category, limit: $limit) {
    totalCount
    edges {
      node {
        id
        name
        originalName
        rating
        genre
        length
        languages
        formats
        __typename
      }
      __typename
    }
    __typename
  }
}
"""


@dataclass
class Movie:
    id: str
    name: str
    original_name: str
    rating: str | None = None
    genre: list[str] = field(default_factory=list)
    length: str | None = None
    languages: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)


def get_movies(country_id: str = "MX", category: str = "now-playing", limit: int = 200) -> list[Movie]:
    data = _graphql(
        "/v2/billboards/graphql",
        "Movies",
        MOVIES_QUERY,
        {"countryId": country_id, "category": category, "limit": limit},
    )
    movies = []
    for edge in data["movies"]["edges"]:
        n = edge["node"]
        movies.append(
            Movie(
                id=n["id"],
                name=n["name"],
                original_name=n["originalName"],
                rating=n.get("rating"),
                genre=n.get("genre") or [],
                length=n.get("length"),
                languages=n.get("languages") or [],
                formats=n.get("formats") or [],
            )
        )
    return movies


def _normalize(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def find_movie(query: str, movies: list[Movie]) -> Movie | None:
    """Busca la mejor coincidencia por nombre (ignora acentos/mayusculas)."""
    q = _normalize(query)

    # 1) coincidencia exacta o por substring en nombre/nombre original
    candidates = [
        m for m in movies if q in _normalize(m.name) or q in _normalize(m.original_name)
    ]
    if candidates:
        # prioriza el mas corto (mas especifico / menos ruido)
        candidates.sort(key=lambda m: len(m.name))
        return candidates[0]

    # 2) fuzzy match como fallback
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
# Horarios (billboard)
# --------------------------------------------------------------------------

BILLBOARD_QUERY = """
query Billboard($countryId: String!, $movieId: String!, $cinemas: String!, $timezone: String) {
  billboard(countryId: $countryId, movieId: $movieId, cinemas: $cinemas, timezone: $timezone) {
    dates
    schedules {
      cinemaId
      dates {
        date
        languages {
          displayLanguage
          showtimes {
            format { name }
            datetime
            screen
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""


@dataclass
class Showtime:
    date: str
    datetime: str
    language: str
    format: str
    screen: str | None


def get_showtimes(
    movie_id: str, cinema_id: str, timezone: str = "America/Mexico_City", country_id: str = "MX"
) -> list[Showtime]:
    data = _graphql(
        "/v1/billboards/graphql",
        "Billboard",
        BILLBOARD_QUERY,
        {
            "countryId": country_id,
            "movieId": movie_id,
            "cinemas": cinema_id,
            "timezone": timezone,
        },
    )
    billboard = data.get("billboard")
    if not billboard:
        return []
    result: list[Showtime] = []
    for schedule in billboard["schedules"]:
        for d in schedule["dates"]:
            for lang in d["languages"]:
                for st in lang["showtimes"]:
                    result.append(
                        Showtime(
                            date=d["date"],
                            datetime=st["datetime"],
                            language=lang["displayLanguage"],
                            format=st["format"]["name"],
                            screen=st.get("screen"),
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
    n_cinemas: int = 5,
    country_id: str = "MX",
) -> dict[str, Any]:
    """
    Dado un nombre de pelicula (aproximado) y una ubicacion (lat, lng),
    regresa los cines mas cercanos y sus horarios para esa pelicula.
    """
    movies = get_movies(country_id=country_id)
    movie = find_movie(movie_query, movies)
    if movie is None:
        return {"movie_query": movie_query, "movie": None, "cinemas": []}

    cinemas = get_cinemas(country_id=country_id)
    near = nearest_cinemas(lat, lng, cinemas, n=n_cinemas, country_id=country_id)

    results = []
    for cinema, dist_km in near:
        showtimes = get_showtimes(movie.id, cinema.id, timezone=cinema.timezone, country_id=country_id)
        if not showtimes:
            continue
        results.append(
            {
                "cinema": cinema.name,
                "cinema_id": cinema.id,
                "city": cinema.city_name,
                "distance_km": round(dist_km, 1),
                "showtimes": [
                    {
                        "date": s.date,
                        "time": s.datetime.split("T")[1][:5],
                        "language": s.language,
                        "format": s.format,
                    }
                    for s in showtimes
                ],
            }
        )

    return {
        "movie_query": movie_query,
        "movie": {"id": movie.id, "name": movie.name},
        "cinemas": results,
    }
