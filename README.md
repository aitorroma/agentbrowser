<div align="center">

  <a href="https://t.me/aitorroma">
    <img src="https://tva1.sinaimg.cn/large/008i3skNgy1gq8sv4q7cqj303k03kweo.jpg" alt="Aitor Roma" />
  </a>

  <br>

  [![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/J3J64AN17)

  <br>

  <a href="https://t.me/aitorroma">
    <img src="https://img.shields.io/badge/Telegram-informational?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Badge"/>
  </a>
</div>

# AgentBrowser

Browser automation appliance with a real visible desktop inside Docker, Arch + Selkies + Niri + Noctalia, local CDP access for agents, full desktop control, Markdown extraction, and secure Bitwarden-assisted login flows.

## Demo

![AgentBrowser demo](assets/demo.gif)

- **GIF preview:** `assets/demo.gif`
- **Video demo:** [`assets/demo.mp4`](assets/demo.mp4)
- **Static cover:** [`assets/demo-cover.jpg`](assets/demo-cover.jpg)

## Why this project exists

Most browser automation stacks force you to choose between:

- a real visible browser for manual inspection
- deterministic agent control
- full desktop automation beyond the browser
- safe handling of credentials
- remote access from a server without a local GUI

AgentBrowser combines those pieces into one appliance:

- **real visible browser, not headless-only**
- **full remote desktop streamed over Selkies/WebRTC**
- **local CDP for Playwright/agent control**
- **HTTP/MCP tools for browser and desktop actions**
- **Bitwarden-backed secure login without exposing secrets to the agent**

## What it includes

- **Arch-based Selkies image** as the desktop streaming base
- **Niri** as the primary compositor
- **Noctalia** as the desktop shell
- **Chromium and Google Chrome** inside the container
- **Persistent browser profile** in a Docker volume
- **CDP exposed only on localhost**
- **FastAPI service** for automation and support endpoints
- **Markdown extraction** from rendered pages
- **MCP endpoint** for tool-based control
- **Desktop control service** for keyboard, mouse, windows, screenshots, apps, and Niri actions
- **Secure login flow** that reuses Bitwarden state without returning credentials

## Main capabilities

### 1. Live desktop you can actually see

Open the streamed desktop in your browser and watch or interact with the running desktop session in real time.

### 2. Local agent control through CDP

Attach Playwright or any CDP-compatible client to the running browser without exposing it publicly.

### 3. MCP-compatible browser and desktop automation

Use the local MCP/API surface to drive navigation, clicks, screenshots, evaluation, app launching, keyboard typing, and window management.

### 4. Niri-aware desktop control

Control workspaces, windows, screenshots, app spawning, and desktop actions through endpoints that understand the active Niri session.

### 5. Rendered Markdown extraction

Fetch a page and convert its rendered content into cleaner Markdown for downstream agent use.

### 6. Secret-blind login flows

Authenticate to Bitwarden once, then let the service perform site logins without returning usernames, passwords, or TOTP codes to the agent.

## High-level architecture

```text
Agent / Playwright / MCP client
            |
            v
  127.0.0.1:18787  FastAPI + MCP
            |
   +--------+-------------------+
   |                            |
   v                            v
CDP / browser control      desktop + auth helpers
   |                            |
   +-------------+--------------+
                 v
   Chromium / Chrome inside Docker
                 |
                 v
 Arch Selkies base + Niri + Noctalia
                 |
                 v
        http://localhost:18080
```

## Ports

| Port | Scope | Purpose |
|---|---|---|
| `18080` | host | Selkies live desktop (HTTP) |
| `18443` | host | Selkies live desktop (HTTPS) |
| `127.0.0.1:18787` | local only | FastAPI + Markdown + MCP |
| `127.0.0.1:19222` | local only | Browser CDP proxy |
| `127.0.0.1:18082` | local only | Selkies websocket bridge |

## Requirements

- Linux host
- Docker Engine
- Docker Compose plugin
- No local GUI required on the host

## Quick start

```bash
cp .env.example .env
docker compose up -d --build
```

Then:

1. Edit `.env`
2. Change at least `SELKIES_BASIC_AUTH_PASSWORD`
3. Set a strong `BW_STATE_KEY` if you want persistent Bitwarden sessions
4. Open `http://localhost:18080`

## First-use flow

1. Copy `.env.example` to `.env`
2. Change the default auth password in `.env`
3. Start the stack with Docker Compose
4. Open the live desktop at `http://localhost:18080`
5. Optionally connect Bitwarden at `/auth/bw`
6. Use CDP, HTTP, or MCP to control the browser and desktop

## Core endpoints

### Live desktop

```text
http://localhost:18080
```

Use `SELKIES_BASIC_AUTH_USER` and `SELKIES_BASIC_AUTH_PASSWORD` from `.env`.

### Secure Bitwarden session bootstrap

```text
http://localhost:18080/auth/bw
```

Or by API:

```bash
curl -X POST http://127.0.0.1:18787/auth/bw/api \
  -H 'Content-Type: application/json' \
  -d '{"server_url":"https://vault.example.com","username":"tu-correo@example.com","password":"***"}'
```

### CDP discovery

```bash
curl http://127.0.0.1:19222/json/version
```

This stays on localhost so agents on the same machine can connect without exposing CDP to the internet.

### Markdown extraction

```bash
curl 'http://127.0.0.1:18787/markdown?url=https://example.com'
```

### MCP endpoint

```text
http://127.0.0.1:18787/mcp
```

### Browser evaluation example

```bash
curl -X POST http://127.0.0.1:18787/eval \
  -H 'Content-Type: application/json' \
  -d '{"js":"document.title"}'
```

### Desktop automation examples

Launch a terminal:

```bash
curl -X POST http://127.0.0.1:18787/desktop/apps/terminal
```

Type text:

```bash
curl -X POST http://127.0.0.1:18787/desktop/keyboard/type \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello from agentbrowser"}'
```

Take a screenshot:

```bash
curl -X POST http://127.0.0.1:18787/desktop/screenshot
```

### Niri control examples

List windows:

```bash
curl http://127.0.0.1:18787/desktop/niri/windows
```

Trigger a Niri action:

```bash
curl -X POST http://127.0.0.1:18787/desktop/niri/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"focus-workspace-down"}'
```

### Secure login execution

Example request:

```bash
curl -X POST http://127.0.0.1:18787/auth/login \
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
- `.env.*` is ignored by git except `.env.example`
- CDP is bound to localhost
- API/MCP is bound to localhost
- live desktop is protected with basic auth
- Bitwarden state can be persisted without exposing secrets in agent-visible output
- secure login returns status, not secret material

## Security and publishing notes

- `.env` must stay local
- `.env.example` contains placeholder values only and is safe to commit
- do not commit real values for:
  - `SELKIES_BASIC_AUTH_PASSWORD`
  - `BW_SESSION`
  - `BW_STATE_KEY`
  - proxy credentials in `BROWSER_PROXY_SERVER`
- if you change defaults for a public deployment, review exposed ports before publishing

### Quick pre-push check

```bash
git diff -- .env
git grep -nE 'BW_SESSION|BW_STATE_KEY|SELKIES_BASIC_AUTH_PASSWORD|Authorization:|BEGIN [A-Z ]+PRIVATE KEY'
```

`git diff -- .env` should print nothing because `.env` is ignored.

## Persistence

The browser profile is stored in the `browser_profile` Docker volume, so sessions and cookies survive restarts.

## Proxy support

The appliance can run without a proxy locally, but also supports outbound proxy configuration through environment variables such as:

```env
BROWSER_PROXY_SERVER=
BROWSER_PROXY_BYPASS=localhost,127.0.0.1
```

## Project structure

```text
app/
  browser_service.py      Browser/CDP automation and secure login logic
  desktop_service.py      Desktop control, apps, windows, screenshots, Niri helpers
  server.py               FastAPI server and HTTP/MCP surface
  requirements.txt        Python dependencies

assets/
  niri/config.kdl         Niri configuration

root/defaults/
  autostart               Selkies startup hook
  browser-launcher.sh     Main browser launcher
  nginx-default.conf      Nginx config used by the image
  startup.sh              Runtime startup hook
  startwm_wayland.sh      Main Wayland desktop startup

scripts/
  browser-launcher.sh                 Browser launcher helper
  niri-launcher.sh                    Niri startup helper
  niri-run-app.sh                     Spawn apps inside the Niri session
  noctalia-launcher.sh                Noctalia startup helper
  terminal-launcher.sh                Terminal launcher wrapper
  selkies-gstreamer-entrypoint.sh     Selkies/Nginx startup glue
  test_cdp.py                         Local validation script
  test_dogtail.py                     Dogtail accessibility smoke test
  thunar_dogtail.py                   Thunar hierarchy test

skills/
  agentbrowser-desktop-mcp/           MCP usage guidance for desktop/browser control
  browser-automation/                 Local automation CLI and usage patterns
```

## Notes

- This repository now tracks the current Arch/Niri/Noctalia implementation as the main supported version.
- The old legacy layout has been removed from the repository.
