---
name: cartelera-mx
description: Busca horarios de una pelicula en Cinepolis y/o Cinemex (Mexico) en los cines mas cercanos a una ubicacion (lat/lng).
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires": { "bins": ["python3"] },
      },
  }
---

# cartelera-mx

Busca horarios de cine en Mexico (Cinepolis y Cinemex) usando las APIs
internas de cada cadena, filtrando por cines cercanos a una ubicacion.

## When to use (trigger phrases)

Usa este skill cuando el usuario pregunte cosas como:

- "a que hora dan [pelicula] cerca de mi"
- "en que cine esta [pelicula]"
- "horarios de [pelicula]"
- "cartelera cerca de mi"
- "quiero ver [pelicula], en donde la dan"

## Antes de correrlo: necesitas una ubicacion

El script filtra por `lat`/`lng`. Si no las tienes ya:

- Si el usuario da una direccion o colonia/ciudad, resuelvela a coordenadas
  aproximadas antes de llamar al script (o pidele que comparta ubicacion).
- Si no tienes forma de ubicarlo, pregunta directamente: "¿cual es tu
  ubicacion (ciudad/colonia) o me pasas lat/lng?".

No inventes coordenadas.

## Quick start

```bash
/home/ubuntu/Carteleras_Mexico_API/.venv/bin/python \
  /home/ubuntu/Carteleras_Mexico_API/cli.py "<pelicula>" \
  --lat <lat> --lng <lng> --json
```

Opciones utiles:

- `--cadena cinepolis|cinemex|todas` (default `todas`)
- `--fecha YYYY-MM-DD` (solo afecta a Cinemex; Cinepolis siempre regresa
  ~6 dias hacia adelante de una vez; default hoy)
- `--n <numero>` cuantos cines cercanos revisar por cadena (default 5)

## Entendiendo el JSON de salida

```json
{
  "pelicula_buscada": "spider-man",
  "cinepolis_match": {"id": "...", "name": "..."},
  "cinemex_match": {"id": 71965, "name": "SPIDER-MAN: Un nuevo día"},
  "cines": [
    {
      "cadena": "Cinemex",
      "cinema": "Centro Telmex",
      "distance_km": 0.0,
      "showtimes": [
        {"date": "2026-09-04", "time": "12:50", "version": "Español Tradicional"}
      ]
    }
  ]
}
```

- `cines` ya viene ordenado por `distance_km` (mas cercano primero), mezclando
  ambas cadenas.
- Si `cinepolis_match`/`cinemex_match` es `null`, esa cadena no tiene ninguna
  pelicula que haga match con el nombre dado (recomienda pedir el nombre
  exacto o revisar ortografia).
- Los showtimes de Cinepolis traen `format` (2D/3D) y `language`
  (ESPAÑOL/SUBTITULADA). Los de Cinemex traen `version` (ya combina idioma +
  formato en un solo texto, ej. "Premium Subtitulada").
- Si una cadena fallo (red, bloqueo, etc.), viene como `cinepolis_error` /
  `cinemex_error` en vez de `_match`, y esa cadena simplemente no aporta
  cines a la lista — la otra cadena sigue funcionando normal.

## Workflow al responder al usuario

1. Si no tienes lat/lng, pidelas (ver arriba).
2. Corre el comando con `--json`.
3. Si `cines` esta vacio, dile al usuario que no encontraste esa pelicula
   cerca, y sugiere revisar el nombre.
4. Presenta, para los 2-3 cines mas cercanos, el nombre del cine, la cadena,
   distancia, y los horarios de hoy (o de la fecha pedida) agrupados de
   forma legible — no le avientes el JSON crudo al usuario.

## Notas

- Ambas APIs son publicas de cliente (llaves embebidas en el JS de cada
  sitio), no requieren login. Si un dia dejan de responder, seguramente
  rotaron la llave; hay que actualizar `cinepolis_api.py`/`cinemex_api.py`
  (ver notas en el README del repo).
- La distancia es linea recta (haversine), no tiempo de manejo.
- Cinepolis usa Cloudflare y a veces bloquea IPs de proveedores cloud/hosting
  (403 "Attention Required"). Si eso pasa, no lo trates como bug — `cli.py`
  ya lo maneja devolviendo `cinepolis_error` y sigue con Cinemex.
- Repo: https://github.com/Mounstroya/Carteleras_Mexico_API
