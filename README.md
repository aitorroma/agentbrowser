# AgentBrowser

Arch-first browser appliance with a visible desktop, Niri + Noctalia session, Chromium/Chrome automation, local CDP, desktop control APIs, and Bitwarden-assisted logins.

## Stack

- Arch Linux base via `ghcr.io/linuxserver/baseimage-selkies:arch`
- Selkies remote desktop
- Niri as primary compositor
- Noctalia desktop shell
- Chromium / Google Chrome inside the container
- FastAPI + MCP + desktop control

## Main URLs

- Live desktop: `http://localhost:18080`
- HTTPS desktop: `https://localhost:18443`
- Local API / MCP: `http://127.0.0.1:18787`
- Local CDP: `http://127.0.0.1:19222/json/version`

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

## Main capabilities

- Visible browser and desktop streamed over Selkies
- Full desktop control: windows, keyboard, mouse, screenshots, app launch
- Niri control endpoints and workspace/window actions
- Chromium/CDP automation for deterministic browsing
- Firefox and desktop-app control through the desktop service
- Bitwarden-backed login flows without exposing secrets to the agent
- Installed-app discovery and launch

## Important environment defaults

- `DESKTOP_SESSION_FLAVOR=noctalia-niri`
- `PRIMARY_COMPOSITOR=niri`
- `SELKIES_WEB_PORT=18080`
- `BROWSER_API_HOST_PORT=18787`
- `BROWSER_CDP_HOST_PORT=19222`

## Security and publishing notes

- `.env` is gitignored and must stay local
- `.env.example` only contains placeholder values and is safe to commit
- Do not commit real values for:
  - `SELKIES_BASIC_AUTH_PASSWORD`
  - `BW_SESSION`
  - `BW_STATE_KEY`
  - proxy credentials in `BROWSER_PROXY_SERVER`
- CDP and API ports are bound to `127.0.0.1` by default in `docker-compose.yml`
- If you change defaults for a public deployment, review exposed ports before publishing

### Quick pre-push check

```bash
git diff -- .env
git grep -nE 'BW_SESSION|BW_STATE_KEY|SELKIES_BASIC_AUTH_PASSWORD|Authorization:|BEGIN [A-Z ]+PRIVATE KEY'
```

`git diff -- .env` should print nothing because `.env` is ignored.

## Project layout

- `app/` — API, browser service, desktop service
- `scripts/` — launchers and runtime helpers
- `assets/niri/` — Niri config
- `root/defaults/` — Selkies / desktop defaults copied into the container
- `skills/agentbrowser-desktop-mcp/` — MCP usage guide for this repo

## Notes

- This repository now tracks the current Arch/Niri/Noctalia implementation as the only supported version.
- The previous legacy layout has been removed.
