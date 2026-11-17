#!/usr/bin/env python3
"""
CLI unificado: busca horarios de una pelicula en Cinepolis y/o Cinemex,
en los cines mas cercanos a una ubicacion.

Ejemplos:
    python cli.py "spider-man" --lat 19.4256 --lng -99.154789
    python cli.py "coyote vs acme" --lat 19.335 --lng -99.157 --cadena cinepolis
    python cli.py "spider-man" --lat 19.4256 --lng -99.154789 --fecha 2026-09-05 --json

Sin nombre de pelicula muestra la cartelera completa de los cines cercanos:
    python cli.py --lat 19.4256 --lng -99.154789
    python cli.py --lat 19.4256 --lng -99.154789 --fecha 2026-09-05 --n 3 --json
"""
from __future__ import annotations

import argparse
import json

import cinemex_api
import cinepolis_api


def buscar(movie: str, lat: float, lng: float, cadena: str, fecha: str | None, n: int) -> dict:
    resultado: dict = {"pelicula_buscada": movie, "cines": []}

    if cadena in ("todas", "cinepolis"):
        try:
            r = cinepolis_api.find_showtimes_near(movie, lat, lng, n_cinemas=n)
            resultado["cinepolis_match"] = r.get("movie")
            for c in r.get("cinemas", []):
                resultado["cines"].append({**c, "cadena": "Cinepolis"})
        except Exception as e:
            resultado["cinepolis_error"] = str(e)

    if cadena in ("todas", "cinemex"):
        try:
            r = cinemex_api.find_showtimes_near(movie, lat, lng, target_date=fecha, n_cinemas=n)
            resultado["cinemex_match"] = r.get("movie")
            for c in r.get("cinemas", []):
                resultado["cines"].append({**c, "cadena": "Cinemex"})
        except Exception as e:
            resultado["cinemex_error"] = str(e)

    resultado["cines"].sort(key=lambda c: c["distance_km"])
    return resultado


def _compactar(cadena: str, movies: list[dict], desde: str | None) -> list[dict]:
    """
    Agrupa los horarios de cada pelicula por formato/idioma
    ({"2D ESPAÑOL": ["14:05", "16:30"]}) y quita funciones antes de `desde`
    (HH:MM). La cartelera completa sin compactar pesa ~40k caracteres, mas de
    lo que un agente recibe completo de una tool.
    """
    out = []
    for m in movies:
        grupos: dict[str, list[str]] = {}
        for st in m["showtimes"]:
            if desde and st["time"] < desde:
                continue
            label = f"{st['format']} {st['language']}" if cadena == "Cinepolis" else st["version"]
            grupos.setdefault(label, []).append(st["time"])
        if grupos:
            out.append({"name": m["name"], "horarios": grupos})
    return out


def cartelera(
    lat: float, lng: float, cadena: str, fecha: str | None, n: int, desde: str | None = None
) -> dict:
    """
    Cartelera completa (todas las peliculas con horarios) de los n cines mas
    cercanos de cada cadena, compacta. `desde` (HH:MM) quita funciones antes de esa hora.
    """
    resultado: dict = {"fecha": fecha or cinemex_api.today_mx(), "cines": []}
    if desde:
        resultado["desde"] = desde

    if cadena in ("todas", "cinepolis"):
        try:
            r = cinepolis_api.cartelera_near(lat, lng, target_date=resultado["fecha"], n_cinemas=n)
            for c in r.get("cinemas", []):
                resultado["cines"].append(
                    {**c, "cadena": "Cinepolis", "movies": _compactar("Cinepolis", c["movies"], desde)}
                )
        except Exception as e:
            resultado["cinepolis_error"] = str(e)

    if cadena in ("todas", "cinemex"):
        try:
            r = cinemex_api.cartelera_near(lat, lng, target_date=resultado["fecha"], n_cinemas=n)
            for c in r.get("cinemas", []):
                resultado["cines"].append(
                    {**c, "cadena": "Cinemex", "movies": _compactar("Cinemex", c["movies"], desde)}
                )
        except Exception as e:
            resultado["cinemex_error"] = str(e)

    resultado["cines"].sort(key=lambda c: c["distance_km"])
    return resultado


def imprimir_cartelera(resultado: dict) -> None:
    desde = f" desde las {resultado['desde']}" if resultado.get("desde") else ""
    print(f"Cartelera del {resultado['fecha']}{desde}")
    for key, name in (("cinepolis_error", "Cinepolis"), ("cinemex_error", "Cinemex")):
        if resultado.get(key):
            print(f"  [{name} fallo: {resultado[key]}]")
    print()
    for c in resultado["cines"]:
        print(f"== [{c['cadena']}] {c['cinema']} - {c['distance_km']} km ==")
        if not c["movies"]:
            print("  (sin funciones ese dia)")
        for m in c["movies"]:
            print(f"  {m['name']}: " + " | ".join(f"{k}: {' '.join(v)}" for k, v in m["horarios"].items()))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Horarios de cine (Cinepolis/Cinemex) cerca de una ubicacion")
    parser.add_argument(
        "movie", nargs="?", default=None,
        help="Nombre (aproximado) de la pelicula. Si se omite, muestra la cartelera completa.",
    )
    parser.add_argument("--lat", type=float, required=True, help="Latitud")
    parser.add_argument("--lng", type=float, required=True, help="Longitud")
    parser.add_argument("--cadena", choices=["todas", "cinepolis", "cinemex"], default="todas")
    parser.add_argument(
        "--fecha", default=None,
        help="YYYY-MM-DD (default hoy). Con pelicula solo afecta a Cinemex; en modo cartelera filtra ambas.",
    )
    parser.add_argument(
        "--n", type=int, default=None,
        help="Cines cercanos a revisar por cadena (default 5 con pelicula, 3 en modo cartelera)",
    )
    parser.add_argument("--desde", default=None, help="HH:MM: en modo cartelera, quita funciones antes de esa hora")
    parser.add_argument("--json", action="store_true", help="Imprimir salida en JSON crudo")
    args = parser.parse_args()

    if args.movie is None:
        resultado = cartelera(args.lat, args.lng, args.cadena, args.fecha, args.n or 3, args.desde)
        if args.json:
            print(json.dumps(resultado, indent=2, ensure_ascii=False))
        else:
            imprimir_cartelera(resultado)
        return

    resultado = buscar(args.movie, args.lat, args.lng, args.cadena, args.fecha, args.n or 5)

    if args.json:
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return

    print(f"Pelicula buscada: {args.movie}")
    if resultado.get("cinepolis_match"):
        print(f"  Match Cinepolis: {resultado['cinepolis_match']['name']}")
    if resultado.get("cinemex_match"):
        print(f"  Match Cinemex:   {resultado['cinemex_match']['name']}")
    if resultado.get("cinepolis_error"):
        print(f"  [Cinepolis fallo: {resultado['cinepolis_error']}]")
    if resultado.get("cinemex_error"):
        print(f"  [Cinemex fallo: {resultado['cinemex_error']}]")
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
