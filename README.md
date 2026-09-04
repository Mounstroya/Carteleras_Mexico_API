# cines-mcp

Servidor MCP con horarios de Cinepolis y Cinemex (Mexico), armado a partir
de las APIs internas de cada sitio (encontradas revisando HARs, no scraping
de HTML).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Probar sin un agente (a mano)

```bash
.venv/bin/python -c "
from cinemex_api import find_showtimes_near
print(find_showtimes_near('spider-man', lat=19.4256, lng=-99.154789, n_cinemas=3))
"
```

## Conectarlo a un agente por MCP

El servidor habla stdio. En cualquier cliente MCP (Claude Desktop, openclaw,
etc.) se registra apuntando al python del venv y a `server.py`, por ejemplo:

```json
{
  "mcpServers": {
    "cines-mx": {
      "command": "/home/yaelmontoya/cines-mcp/.venv/bin/python",
      "args": ["/home/yaelmontoya/cines-mcp/server.py"]
    }
  }
}
```

(La ruta exacta de configuracion depende de donde openclaw lea su lista de
servidores MCP; el bloque de arriba es el formato estandar que usan la
mayoria de los clientes.)

## Tools expuestas

- `buscar_horarios_cinepolis(pelicula, lat, lng, n_cines=5)`
- `buscar_horarios_cinemex(pelicula, lat, lng, fecha=None, n_cines=5)`
- `buscar_horarios(pelicula, lat, lng, fecha=None, n_cines=5)` — busca en
  ambas cadenas y regresa todo junto ordenado por distancia.

## Notas / limitaciones

- Ambas APIs son "publicas de cliente": la llave (`x-apikey` en Cinepolis,
  `X-API-Consumer-Key` en Cinemex) viene embebida en el JS de cada sitio, no
  es un token de sesion de usuario. Si algun dia dejan de responder, lo mas
  probable es que rotaron la llave — hay que capturar un `.har` nuevo
  navegando el sitio y actualizar la constante en el archivo correspondiente.
- La distancia a los cines es linea recta (haversine), no tiempo de manejo.
- La lista de cines/ciudades se cachea en disco (`cache_*.json`) por ~1
  semana para no pedirla en cada llamada.
- Cinepolis regresa horarios de los proximos ~6 dias en una sola llamada.
  Cinemex regresa un solo dia por llamada (`fecha`, default hoy).
- Solo se probo para Mexico (`country_id="MX"` / catalogo nacional de
  Cinemex).
