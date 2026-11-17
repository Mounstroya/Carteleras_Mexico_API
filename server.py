"""
Servidor MCP que expone horarios de Cinepolis y Cinemex (Mexico) como tools,
para que un agente de IA (openclaw, Claude, etc.) los pueda llamar directo.

Uso:
    .venv/bin/python server.py

Se comunica por stdio (transporte estandar de MCP).
"""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

import cinemex_api
import cinepolis_api
import cli

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
    # si una cadena falla, regresa la otra y marca el error (cinepolis_error /
    # cinemex_error) en vez de tronar todo
    return cli.buscar(pelicula, lat, lng, "todas", fecha, n_cines)


@mcp.tool()
def cartelera_cercana(
    lat: float, lng: float, fecha: str | None = None, desde: str | None = None, n_cines: int = 3
) -> str:
    """
    Que hay en el cine cerca de una ubicacion (Mexico): cartelera completa
    (todas las peliculas con horarios) de los Cinepolis y Cinemex mas
    cercanos, para un dia. Usalo cuando el usuario NO sabe que pelicula ver
    ("que hay en el cine?"). Si ya sabe la pelicula, usa buscar_horarios.

    Args:
        lat: latitud de la ubicacion del usuario.
        lng: longitud de la ubicacion del usuario.
        fecha: fecha YYYY-MM-DD (hora de CDMX). Si se omite, usa hoy.
        desde: hora minima HH:MM (ej. "19:00"); quita funciones anteriores.
        n_cines: cuantos cines cercanos revisar por cadena (default 3).

    Cada pelicula trae "horarios" agrupados por formato/idioma, ej.
    {"2D ESPAÑOL": ["14:05", "16:30"]}.
    """
    # JSON compacto (sin sangria): la cartelera completa es grande y los
    # agentes suelen recortar resultados de tools muy largos
    return json.dumps(cli.cartelera(lat, lng, "todas", fecha, n_cines, desde), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    mcp.run()
