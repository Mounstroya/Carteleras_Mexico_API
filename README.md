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

## Usar por CLI

```bash
.venv/bin/python cli.py "spider-man" --lat 19.4256 --lng -99.154789 --json
```

Sin nombre de pelicula muestra que hay en el cine cerca ("cartelera"):

```bash
.venv/bin/python cli.py --lat 19.4256 --lng -99.154789 --fecha 2026-09-05
```

Trae todas las peliculas con horarios de los 3 cines mas cercanos de cada
cadena (`--n` para cambiarlo). Cinemex usa 1 llamada por zona; Cinepolis 1
por cine (`billboardByCinema`, la misma consulta que usa su sitio) + 1 para
los nombres de las peliculas.

Ver `python cli.py --help` para filtrar por cadena, fecha, o numero de cines
cercanos a revisar.

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
  ambas cadenas y regresa todo junto ordenado por distancia. Si una cadena
  falla, regresa la otra y marca `cinepolis_error` / `cinemex_error`.
- `cartelera_cercana(lat, lng, fecha=None, n_cines=3)` — que hay en el cine
  cerca, sin nombre de pelicula (ver el modo cartelera del CLI).

El paquete `mcp` requiere Python 3.10 o mas nuevo.

## Skill para OpenClaw

`skills/cartelera-mx/` trae un skill de [OpenClaw](https://github.com/openclaw/openclaw)
que le enseña al agente a usar `cli.py` cuando el usuario pregunte por
horarios de cine. Instalarlo:

```bash
cp -r skills/cartelera-mx ~/.openclaw/skills/
```

## Relay opcional para Cinepolis (IPs de datacenter bloqueadas)

Cinepolis usa Cloudflare y a veces bloquea IPs de proveedores cloud/hosting
con un 403 "Attention Required" (le pasa, por ejemplo, a instancias de
Oracle Cloud). Si corres esto en un servidor asi, `cinepolis_api.py` puede
enrutar sus llamadas por un relay HTTP corriendo en una IP residencial en
vez de pegarle directo a la API.

Se activa solo si defines estas dos variables (ver `.env.example`, copialo
a `.env` en la raiz del proyecto — ya esta en `.gitignore`):

```bash
CINEPOLIS_RELAY_URL=http://tu-ip-residencial:8794
CINEPOLIS_RELAY_TOKEN=<token compartido con el relay>
```

Sin esas variables, el comportamiento es identico al de siempre (llamada
directa). El codigo del relay (Flask + gunicorn en Docker, reenvia
unicamente a `api-g.cinepolis.com`, valida cada request con
`X-Worker-Token` via `hmac.compare_digest`) no vive en este repo — es
infraestructura personal, no parte de la libreria.

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
- Cinepolis regresa horarios de los proximos ~6 dias en una sola llamada
  (una por pelicula, con todos los cines cercanos juntos).
  Cinemex regresa un solo dia por llamada (`fecha`, default hoy en CDMX).
- Cinepolis limita peticiones con Cloudflare: muchas llamadas seguidas dan
  429 y bloquean la IP un rato. `cinepolis_api` reintenta con espera, pero
  evita loops de muchas consultas (p. ej. pedir `Billboard` pelicula por
  pelicula para armar una cartelera: usa `billboardByCinema`).
- Solo se probo para Mexico (`country_id="MX"` / catalogo nacional de
  Cinemex).

---

## ☕ Was it useful?

If this project saved you some time, you can buy me a coffee:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-mounstroya-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/mounstroya)

---

## License
