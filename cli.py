#!/usr/bin/env python3
"""
CLI unificado: busca horarios de una pelicula en Cinepolis y/o Cinemex,
en los cines mas cercanos a una ubicacion.

Ejemplos:
    python cli.py "spider-man" --lat 19.4256 --lng -99.154789
    python cli.py "coyote vs acme" --lat 19.335 --lng -99.157 --cadena cinepolis
    python cli.py "spider-man" --lat 19.4256 --lng -99.154789 --fecha 2026-09-05 --json
"""
from __future__ import annotations

import argparse
import json

import cinemex_api
import cinepolis_api


def buscar(movie: str, lat: float, lng: float, cadena: str, fecha: str | None, n: int) -> dict:
    resultado: dict = {"pelicula_buscada": movie, "cines": []}

    if cadena in ("todas", "cinepolis"):
        r = cinepolis_api.find_showtimes_near(movie, lat, lng, n_cinemas=n)
        resultado["cinepolis_match"] = r.get("movie")
        for c in r.get("cinemas", []):
            resultado["cines"].append({**c, "cadena": "Cinepolis"})

    if cadena in ("todas", "cinemex"):
        r = cinemex_api.find_showtimes_near(movie, lat, lng, target_date=fecha, n_cinemas=n)
        resultado["cinemex_match"] = r.get("movie")
        for c in r.get("cinemas", []):
            resultado["cines"].append({**c, "cadena": "Cinemex"})

    resultado["cines"].sort(key=lambda c: c["distance_km"])
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description="Horarios de cine (Cinepolis/Cinemex) cerca de una ubicacion")
    parser.add_argument("movie", help="Nombre (aproximado) de la pelicula")
    parser.add_argument("--lat", type=float, required=True, help="Latitud")
    parser.add_argument("--lng", type=float, required=True, help="Longitud")
    parser.add_argument("--cadena", choices=["todas", "cinepolis", "cinemex"], default="todas")
    parser.add_argument("--fecha", default=None, help="YYYY-MM-DD (solo afecta a Cinemex; default hoy)")
    parser.add_argument("--n", type=int, default=5, help="Cines cercanos a revisar por cadena")
    parser.add_argument("--json", action="store_true", help="Imprimir salida en JSON crudo")
    args = parser.parse_args()

    resultado = buscar(args.movie, args.lat, args.lng, args.cadena, args.fecha, args.n)

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return

    print(f"Pelicula buscada: {args.movie}")
    if resultado.get("cinepolis_match"):
        print(f"  Match Cinepolis: {resultado['cinepolis_match']['name']}")
    if resultado.get("cinemex_match"):
        print(f"  Match Cinemex:   {resultado['cinemex_match']['name']}")
    print()

    if not resultado["cines"]:
        print("No hay horarios en los cines cercanos revisados.")
        return

    for c in resultado["cines"]:
        print(f"== [{c['cadena']}] {c['cinema']} - {c['distance_km']} km ==")
        by_date: dict[str, list[str]] = {}
        for st in c["showtimes"]:
            if c["cadena"] == "Cinepolis":
                label = f"{st['time']} ({st['format']}, {st['language']})"
            else:
                label = f"{st['time']} ({st['version']})"
            by_date.setdefault(st["date"], []).append(label)
        for date, times in by_date.items():
            print(f"  {date}: " + " | ".join(times))
        print()


if __name__ == "__main__":
    main()
