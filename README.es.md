# AgentBrowser

Documentación en español para AgentBrowser, un appliance de automatización de navegador y escritorio con entorno visible dentro de Docker usando **Arch + Selkies + Niri + Noctalia**.

**Idiomas:** [🇪🇸 Español](README.es.md) · [🇬🇧 English](README.md)

## Resumen

AgentBrowser combina en una sola stack:

- navegador real visible
- control local por **CDP**
- control completo del escritorio
- endpoint **MCP/HTTP**
- integración segura con **Bitwarden**
- extracción de contenido en **Markdown**

## Demo

![AgentBrowser demo](assets/demo.gif)

- **GIF:** `assets/demo.gif`
- **Vídeo:** [`assets/demo.mp4`](assets/demo.mp4)
- **Imagen estática:** [`assets/demo-cover.jpg`](assets/demo-cover.jpg)

## Qué incluye

- **Selkies** para streaming del escritorio
- **Niri** como compositor principal
- **Noctalia** como shell visual
- **Chromium y Google Chrome** dentro del contenedor
- **FastAPI + MCP** para automatización
- control de ventanas, teclado, ratón, screenshots y apps
- acciones específicas para **Niri**
- flujo de login seguro sin exponer credenciales al agente

## Puertos principales

| Puerto | Alcance | Uso |
|---|---|---|
| `18080` | host | escritorio web Selkies (HTTP) |
| `18443` | host | escritorio web Selkies (HTTPS) |
| `127.0.0.1:18787` | local | API + Markdown + MCP |
| `127.0.0.1:19222` | local | proxy CDP del navegador |
| `127.0.0.1:18082` | local | websocket bridge de Selkies |

## Inicio rápido

```bash
cp .env.example .env
docker compose up -d --build
```

Después:

1. edita `.env`
2. cambia al menos `SELKIES_BASIC_AUTH_PASSWORD`
3. define un `BW_STATE_KEY` fuerte si quieres persistencia de Bitwarden
4. abre `http://localhost:18080`

## Flujo inicial recomendado

1. Copia `.env.example` a `.env`
2. Cambia la contraseña de acceso web
3. Arranca la stack con Docker Compose
4. Abre el escritorio en `http://localhost:18080`
5. Si quieres, conecta Bitwarden en `/auth/bw`
6. Usa CDP, HTTP o MCP para controlar navegador y escritorio

## URLs importantes

- **Escritorio web:** `http://localhost:18080`
- **API / MCP:** `http://127.0.0.1:18787`
- **CDP:** `http://127.0.0.1:19222/json/version`
- **Bootstrap de Bitwarden:** `http://localhost:18080/auth/bw`

## Ejemplos rápidos

### Obtener el título de la página actual

```bash
curl -X POST http://127.0.0.1:18787/eval \
  -H 'Content-Type: application/json' \
  -d '{"js":"document.title"}'
```

### Abrir una terminal

```bash
curl -X POST http://127.0.0.1:18787/desktop/apps/terminal
```

### Escribir texto en el escritorio

```bash
curl -X POST http://127.0.0.1:18787/desktop/keyboard/type \
  -H 'Content-Type: application/json' \
  -d '{"text":"hola desde agentbrowser"}'
```

### Hacer una captura

```bash
curl -X POST http://127.0.0.1:18787/desktop/screenshot
```

### Listar ventanas de Niri

```bash
curl http://127.0.0.1:18787/desktop/niri/windows
```

### Lanzar una acción de Niri

```bash
curl -X POST http://127.0.0.1:18787/desktop/niri/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"focus-workspace-down"}'
```

## Seguridad

- `.env` y `.env.*` están ignorados por git, excepto `.env.example`
- CDP y API quedan publicados solo en `127.0.0.1`
- el escritorio web usa autenticación básica
- Bitwarden puede persistirse sin devolver secretos al agente
- no subas valores reales de `BW_SESSION`, `BW_STATE_KEY` o contraseñas

### Comprobación rápida antes de hacer push

```bash
git diff -- .env
git grep -nE 'BW_SESSION|BW_STATE_KEY|SELKIES_BASIC_AUTH_PASSWORD|Authorization:|BEGIN [A-Z ]+PRIVATE KEY'
```

## Estructura del proyecto

```text
app/
  browser_service.py      Automatización del navegador/CDP y login seguro
  desktop_service.py      Control de escritorio, apps, ventanas, screenshots y Niri
  server.py               Servidor FastAPI y superficie HTTP/MCP

assets/
  niri/config.kdl         Configuración de Niri

root/defaults/
  autostart               Hook de arranque
  browser-launcher.sh     Launcher principal del navegador
  nginx-default.conf      Configuración de nginx
  startup.sh              Hook de arranque en runtime
  startwm_wayland.sh      Arranque principal del escritorio Wayland

scripts/
  niri-launcher.sh        Helper de arranque de Niri
  niri-run-app.sh         Lanzamiento de apps dentro de Niri
  noctalia-launcher.sh    Helper de arranque de Noctalia
  terminal-launcher.sh    Wrapper para abrir terminal
```

## Nota

La documentación más completa y detallada en inglés está en [`README.md`](README.md).
