# Carteleras Mexico API

Cliente en Python para las APIs de cartelera/horarios de **Cinepolis** y
**Cinemex** en Mexico: cartelera de peliculas, catalogo de cines con
ubicacion, y horarios por cine. Se puede usar como libreria en cualquier
script o proyecto, o exponerse via MCP para que un agente de IA lo llame.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usar como libreria

```python
from cinemex_api import find_showtimes_near as cinemex_near
from cinepolis_api import find_showtimes_near as cinepolis_near

cinemex_near("spider-man", lat=19.4256, lng=-99.154789, n_cinemas=3)
cinepolis_near("coyote vs acme", lat=19.335388, lng=-99.157622, n_cinemas=3)
```

Cada modulo (`cinepolis_api.py`, `cinemex_api.py`) tambien expone funciones
por separado si solo necesitas una parte: `get_cinemas()`, `get_movies()`,
`find_movie()`, `nearest_cinemas()`, etc.

## Usar via MCP

`server.py` expone las mismas busquedas como tools MCP, para que un agente
de IA (Claude Desktop, openclaw, o cualquier cliente MCP) las llame directo
sin tener que escribir codigo. El servidor habla stdio; se registra
apuntando al python del venv y a `server.py`:

```json
{
  "mcpServers": {
    "cines-mx": {
      "command": "/ruta/a/Carteleras_Mexico_API/.venv/bin/python",
      "args": ["/ruta/a/Carteleras_Mexico_API/server.py"]
    }
  }
}
```

Tools expuestas:

- `buscar_horarios_cinepolis(pelicula, lat, lng, n_cines=5)`
- `buscar_horarios_cinemex(pelicula, lat, lng, fecha=None, n_cines=5)`
- `buscar_horarios(pelicula, lat, lng, fecha=None, n_cines=5)` — busca en
  ambas cadenas y regresa todo junto ordenado por distancia.

## Notas / limitaciones

- Ambas APIs son "publicas de cliente": la llave (`x-apikey` en Cinepolis,
  `X-API-Consumer-Key` en Cinemex) viene embebida en el JS de cada sitio, no
  es un token de sesion de usuario. Si algun dia dejan de responder, lo mas
  probable es que rotaron la llave — hay que revisar las peticiones de red
  del sitio (pestana Network del navegador) y actualizar la constante en el
  archivo correspondiente.
- La distancia a los cines es linea recta (haversine), no tiempo de manejo.
- La lista de cines/ciudades se cachea en disco (`cache_*.json`) por ~1
  semana para no pedirla en cada llamada.
- Cinepolis regresa horarios de los proximos ~6 dias en una sola llamada.
  Cinemex regresa un solo dia por llamada (`fecha`, default hoy).
- Solo se probo para Mexico (`country_id="MX"` / catalogo nacional de
  Cinemex).
