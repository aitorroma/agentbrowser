# Agent Browser Appliance

Appliance local con navegador real *headed* dentro de Docker, display virtual sin GUI en host, control por CDP y observación por Selkies/WebRTC.

## Qué monta

- Selkies oficial como base del escritorio virtual y streaming WebRTC.
- Chromium real (no `--headless`) lanzado dentro del contenedor sobre Xvfb/Xfce.
- CDP expuesto solo en `127.0.0.1` para agentes (`connectOverCDP`).
- Perfil persistente en volumen Docker.
- Endpoint HTTP de extracción a Markdown usando Readability.
- Wrapper MCP por Streamable HTTP con herramientas: `goto`, `get_markdown`, `screenshot`, `fill`, `click`, `eval`.
- Login seguro dentro del contenedor con Bitwarden CLI vía `secure_login`, sin exponer credenciales al agente.

## Fuente de verdad Selkies usada

Se revisó la documentación/repositorio actuales de Selkies y la imagen oficial de ejemplo:

- https://selkies-project.github.io/selkies/
- `docs/start.md` y `docs/component.md` del repo actual
- `ghcr.io/selkies-project/selkies-gstreamer/gst-py-example:main-ubuntu24.04`

La documentación actual indica que `gst-py-example` es el contenedor mínimo de referencia y que, en modo contenedor, WebRTC suele requerir TURN si no se usa `hostNetwork`.

Además, se tomó como referencia la idea de SeleniumBase de lanzar un navegador del sistema y adjuntar Playwright por `connect_over_cdp()` para evitar señales típicas de `launch()` automatizado, pero manteniendo aquí la base Selkies + Chromium y sin depender de WebDriver.

## Requisitos

- Docker Engine + Docker Compose plugin
- Host Linux sin entorno gráfico
- Puertos libres:
  - `8080/tcp` live view Selkies
  - `3478/tcp+udp` y `65532-65535/tcp+udp` para TURN
  - `127.0.0.1:9222` para CDP local
  - `127.0.0.1:8787` para API Markdown local

## Arranque

```bash
cp .env.example .env
docker compose up --build
```

## Live view WebRTC

Abre `http://localhost:8080` y entra con `SELKIES_BASIC_AUTH_USER` / `SELKIES_BASIC_AUTH_PASSWORD`.

## CDP

Descubre el WebSocket:

```bash
curl http://127.0.0.1:9222/json/version
```

El host publica `127.0.0.1:9222`, y dentro del contenedor se reenvía a la escucha local real del navegador. Así el CDP queda utilizable desde tu máquina, pero no expuesto a Internet.

## Markdown renderizado / MCP

Extracción a Markdown:

```bash
curl 'http://127.0.0.1:8787/markdown?url=https://example.com'
```

Endpoint MCP Streamable HTTP:

```text
http://127.0.0.1:8787/mcp
```

## Login seguro con Bitwarden

Puedes abrir el formulario protegido por Selkies en:

```text
http://localhost:8080/auth/bw
```

Ahí introduces:

- URL self-hosted de Bitwarden
- usuario/email
- master password

La sesión queda en memoria dentro del servicio y después `secure_login` la reutiliza sin exponer credenciales al agente.

Si prefieres inyectarlo por API, usa:

```bash
curl -X POST http://127.0.0.1:8787/auth/bw/api \
  -H 'Content-Type: application/json' \
  -d '{"server_url":"https://vault.example.com","username":"tu-correo@example.com","password":"***"}'
```

Luego el agente solo necesita invocar la tool MCP/HTTP de alto nivel:

```json
{"site":"example.com","account":"default"}
```

Endpoint HTTP equivalente:

```bash
curl -X POST http://127.0.0.1:8787/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"site":"example.com","account":"default"}'
```

La respuesta devuelve solo estado (`logged_in`, `filled`, `otp_required`, etc.), nunca usuario, contraseña ni TOTP.

## Prueba

Con el stack levantado:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install playwright httpx
python scripts/test_cdp.py
```

Guarda PNG + Markdown en `output/`.

## Persistencia

El perfil vive en el volumen `browser_profile`, así que sesiones y cookies sobreviven a `docker compose down && docker compose up`.

## Proxy residencial

Por defecto no usa proxy. Para dejarlo preparado en un VPS más adelante:

```env
# BROWSER_PROXY_SERVER=http://user:pass@proxy-residencial:9000
# BROWSER_PROXY_BYPASS=<-loopback>
```

## Seguridad

- Live view expuesto en `8080` y protegido por credenciales.
- CDP y API se publican solo en `127.0.0.1`.
- No se usa `network_mode: host`, manteniendo aislamiento Docker.
- Se expone TURN porque Selkies lo necesita frecuentemente en contenedor; filtra por firewall si abres la máquina fuera de tu LAN.
