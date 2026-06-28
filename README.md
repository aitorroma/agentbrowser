# AgentBrowser

Browser automation appliance with a real headed Chromium running inside Docker, live remote desktop via Selkies/WebRTC, local CDP access for agents, Markdown extraction, and secure Bitwarden-assisted login flows.

## Why this project exists

Most browser automation stacks force you to choose between:

- a real visible browser for manual inspection
- deterministic agent control
- safe handling of credentials
- remote access from a server without a local GUI

AgentBrowser combines those pieces into one appliance:

- **real Chromium, not headless-only**
- **virtual desktop streamed over WebRTC**
- **local CDP for Playwright/agent control**
- **HTTP/MCP tools for browser actions**
- **Bitwarden-backed secure login without exposing secrets to the agent**

## What it includes

- **Selkies** as the desktop streaming base
- **Chromium headed** over Xvfb/Xfce inside the container
- **Persistent browser profile** in a Docker volume
- **CDP exposed only on localhost**
- **FastAPI service** for automation and support endpoints
- **Markdown extraction** using Readability-style processing
- **MCP endpoint** for tool-based browser control
- **Desktop control service** for full GUI workflows
- **Secure login flow** that reuses Bitwarden state without returning credentials

## Main capabilities

### 1. Live browser you can actually see

Open the streamed desktop in your browser and watch or interact with Chromium in real time.

### 2. Local agent control through CDP

Attach Playwright or any CDP-compatible client to the running browser without exposing it publicly.

### 3. MCP-compatible automation

Use the local MCP endpoint to drive navigation, clicks, screenshots, evaluation, and other flows.

### 4. Rendered Markdown extraction

Fetch a page and convert its rendered content into cleaner Markdown for downstream agent use.

### 5. Secret-blind login flows

Authenticate to Bitwarden once, then let the service perform site logins without returning usernames, passwords, or TOTP codes to the agent.

## High-level architecture

```text
Agent / Playwright / MCP client
            |
            v
   127.0.0.1:8787  FastAPI + MCP
            |
   +--------+--------+
   |                 |
   v                 v
CDP / browser    desktop tools
control          + auth helpers
   |                 |
   +--------+--------+
            v
  Headed Chromium inside Docker
            |
            v
   Selkies + Xvfb/Xfce + WebRTC
            |
            v
     http://localhost:8080
```

## Ports

| Port | Scope | Purpose |
|---|---|---|
| `8080` | host | Selkies live desktop |
| `8081` | internal | Selkies service port |
| `127.0.0.1:8787` | local only | FastAPI + Markdown + MCP |
| `127.0.0.1:9222` | local only | Chromium CDP |
| `3478` + `65532-65535` | host | TURN/WebRTC support |

## Requirements

- Linux host
- Docker Engine
- Docker Compose plugin
- No local GUI required on the host

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- **Live desktop:** `http://localhost:8080`
- **MCP / API:** `http://127.0.0.1:8787`

## First-use flow

1. Copy `.env.example` to `.env`
2. Change the default passwords in `.env`
3. Start the stack with Docker Compose
4. Open Selkies at `http://localhost:8080`
5. Optionally connect Bitwarden at `/auth/bw`
6. Use CDP, HTTP, or MCP to control the browser

## Core endpoints

### Live desktop

```text
http://localhost:8080
```

Use `SELKIES_BASIC_AUTH_USER` and `SELKIES_BASIC_AUTH_PASSWORD` from your `.env`.

### CDP discovery

```bash
curl http://127.0.0.1:9222/json/version
```

This stays on localhost so agents on the same machine can connect without exposing CDP to the internet.

### Markdown extraction

```bash
curl 'http://127.0.0.1:8787/markdown?url=https://example.com'
```

### MCP endpoint

```text
http://127.0.0.1:8787/mcp
```

### Secure Bitwarden session bootstrap

```text
http://localhost:8080/auth/bw
```

Or by API:

```bash
curl -X POST http://127.0.0.1:8787/auth/bw/api \
  -H 'Content-Type: application/json' \
  -d '{"server_url":"https://vault.example.com","username":"tu-correo@example.com","password":"***"}'
```

### Secure login execution

Example request:

```bash
curl -X POST http://127.0.0.1:8787/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"site":"example.com","account":"default"}'
```

The response returns status only, for example:

- `logged_in`
- `filled`
- `otp_required`
- `not_found`

It does **not** return credentials or TOTP values.

## Example local validation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install playwright httpx
python scripts/test_cdp.py
```

This writes screenshots and Markdown output into `output/`.

## Security model

- `.env` is ignored by git
- CDP is bound to localhost
- API/MCP is bound to localhost
- live desktop is protected with basic auth
- Bitwarden state can be persisted without exposing secrets in agent-visible output
- secure login returns status, not secret material

## Persistence

The Chromium profile is stored in the `browser_profile` Docker volume, so sessions and cookies survive restarts.

## Proxy support

The appliance can run without a proxy locally, but also supports future outbound proxy configuration through environment variables such as:

```env
BROWSER_PROXY_SERVER=
BROWSER_PROXY_BYPASS=localhost,127.0.0.1
```

## Project structure

```text
app/
  browser_service.py      Browser/CDP automation and secure login logic
  desktop_service.py      Desktop-level control helpers
  server.py               FastAPI server and HTTP/MCP surface
  requirements.txt        Python dependencies

scripts/
  browser-launcher.sh                 Chromium startup logic
  browser-supervisor.conf             Process supervision config
  nginx-default.conf                  Nginx config
  selkies-gstreamer-entrypoint.sh     Selkies/Nginx startup glue
  test_cdp.py                         Local validation script

skills/
  agentbrowser-desktop-mcp/           MCP usage guidance for desktop/browser control
  browser-automation/                 Local automation CLI and usage patterns
```

## Design choices

### Why Selkies

Selkies provides a practical remote desktop streaming layer for containerized browser sessions without requiring a local desktop on the host.

### Why headed Chromium

Some workflows need a visible browser for debugging, trust, anti-bot tuning, and manual intervention.

### Why CDP instead of WebDriver

CDP gives a clean path for Playwright attachment and lower-friction integration with agent workflows that need an already-running browser.

### Why Bitwarden-backed secure login

It allows the service to perform login tasks while keeping raw credentials outside normal agent-visible traces.

## Related local skills

- `skills/agentbrowser-desktop-mcp/SKILL.md`
- `skills/browser-automation/SKILL.md`

## Current status

AgentBrowser is a practical local appliance for:

- browser automation
- desktop-assisted web tasks
- secure credential-blind login flows
- rendered page extraction
- MCP-driven agent workflows

If you want to publish or extend it, the best next steps are usually:

1. add usage screenshots or an architecture diagram
2. document the MCP tools individually
3. add deployment notes for VPS usage
4. add CI checks for the Python service
