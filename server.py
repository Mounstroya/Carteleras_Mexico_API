"""
Servidor MCP que expone horarios de Cinepolis y Cinemex (Mexico) como tools,
para que un agente de IA (openclaw, Claude, etc.) los pueda llamar directo.

Uso:
    .venv/bin/python server.py

Se comunica por stdio (transporte estandar de MCP).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import cinemex_api
import cinepolis_api

mcp = FastMCP("cines-mx")


@mcp.tool()
def buscar_horarios_cinepolis(
    pelicula: str, lat: float, lng: float, n_cines: int = 5
) -> dict:
    """
    Busca horarios de una pelicula en los cines Cinepolis mas cercanos a una
    ubicacion (Mexico). Regresa, por cada cine cercano que la este exhibiendo,
    su distancia en km y los horarios agrupados por fecha (proximos ~6 dias).

    Args:
        pelicula: nombre (aproximado) de la pelicula, ej. "coyote vs acme".
        lat: latitud de la ubicacion del usuario.
        lng: longitud de la ubicacion del usuario.
        n_cines: cuantos cines cercanos revisar (default 5).
    """
    return cinepolis_api.find_showtimes_near(pelicula, lat, lng, n_cinemas=n_cines)


@mcp.tool()
def buscar_horarios_cinemex(
    pelicula: str, lat: float, lng: float, fecha: str | None = None, n_cines: int = 5
) -> dict:
    """
    Busca horarios de una pelicula en los cines Cinemex mas cercanos a una
    ubicacion (Mexico), para un dia especifico.

    Args:
        pelicula: nombre (aproximado) de la pelicula, ej. "spider-man".
        lat: latitud de la ubicacion del usuario.
        lng: longitud de la ubicacion del usuario.
        fecha: fecha en formato YYYY-MM-DD. Si se omite, usa hoy.
        n_cines: cuantos cines cercanos revisar (default 5).
    """
    return cinemex_api.find_showtimes_near(pelicula, lat, lng, target_date=fecha, n_cinemas=n_cines)


@mcp.tool()
def buscar_horarios(
    pelicula: str, lat: float, lng: float, fecha: str | None = None, n_cines: int = 5
) -> dict:
    """
    Busca horarios de una pelicula en Cinepolis Y Cinemex a la vez, en los
    cines mas cercanos a una ubicacion, y regresa todo junto ordenado por
    distancia. Util cuando al usuario no le importa la cadena, solo el cine
    mas cercano que la este exhibiendo.

    Args:
        pelicula: nombre (aproximado) de la pelicula.
        lat: latitud de la ubicacion del usuario.
        lng: longitud de la ubicacion del usuario.
        fecha: fecha en formato YYYY-MM-DD, solo aplica a Cinemex. Si se
            omite, usa hoy. Cinepolis siempre regresa los proximos dias.
        n_cines: cuantos cines cercanos revisar por cadena (default 5).
    """
    cinepolis = cinepolis_api.find_showtimes_near(pelicula, lat, lng, n_cinemas=n_cines)
    cinemex = cinemex_api.find_showtimes_near(pelicula, lat, lng, target_date=fecha, n_cinemas=n_cines)

    cines = []
    for c in cinepolis.get("cinemas", []):
        cines.append({**c, "cadena": "Cinepolis"})
    for c in cinemex.get("cinemas", []):
        cines.append({**c, "cadena": "Cinemex"})
    cines.sort(key=lambda c: c["distance_km"])

    return {
        "pelicula_buscada": pelicula,
        "cinepolis_match": cinepolis.get("movie"),
        "cinemex_match": cinemex.get("movie"),
        "cines": cines,
    }


if __name__ == "__main__":
    mcp.run()
