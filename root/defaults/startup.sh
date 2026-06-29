#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/config}"
export BROWSER_API_HOST="${BROWSER_API_HOST:-0.0.0.0}"
export BROWSER_API_PORT="${BROWSER_API_PORT:-8787}"
export BROWSER_CDP_PROXY_PORT="${BROWSER_CDP_PROXY_PORT:-9223}"
export BROWSER_CDP_PORT="${BROWSER_CDP_PORT:-9222}"
export BROWSER_CDP_BIND="${BROWSER_CDP_BIND:-127.0.0.1}"
export BROWSER_PROFILE_DIR="${BROWSER_PROFILE_DIR:-/data/profile/chromium}"
export OUTPUT_DIR="${OUTPUT_DIR:-/data/output}"
export XDG_RUNTIME_DIR="${BROWSER_XDG_RUNTIME_DIR:-/config/.XDG}"
export WAYLAND_DISPLAY="${BROWSER_WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:1}"

cd /opt/appliance
mkdir -p "$BROWSER_PROFILE_DIR" "$OUTPUT_DIR" /tmp/runtime-abc
# XDG_RUNTIME_DIR must be 0700 or Qt/KDE (KIO) refuses to use it for sockets.
chmod 700 "$XDG_RUNTIME_DIR" /tmp/runtime-abc 2>/dev/null || true
mkdir -p /config/.local/state/noctalia
mkdir -p /config/wallpapers

if [ -d /defaults/noctalia-state ]; then
  cp -an /defaults/noctalia-state/. /config/.local/state/noctalia/
  chown -R abc:abc /config/.local/state/noctalia >/dev/null 2>&1 || true
fi

if [ -d /defaults/wallpapers ]; then
  cp -an /defaults/wallpapers/. /config/wallpapers/
  chown -R abc:abc /config/wallpapers >/dev/null 2>&1 || true
fi

# ydotoold provides uinput-level input injection that reaches native Wayland
# apps (xdotool only reaches Xwayland). Needs /dev/uinput mapped from the host
# (map it in docker-compose if you need host-level uinput). No-op when the device is absent.
if [ -e /dev/uinput ] && command -v ydotoold >/dev/null 2>&1 && ! pgrep -x ydotoold >/dev/null 2>&1; then
  nohup ydotoold --socket-path "${YDOTOOL_SOCKET:-/tmp/.ydotool_socket}" --socket-own "$(id -u):$(id -g)" \
    >/tmp/ydotoold.log 2>&1 &
fi

start_browser_launcher() {
  nohup sh -lc '
    sleep 2
    exec /opt/appliance/browser-launcher.sh
  ' >/tmp/chromium.log 2>&1 &
}

if ! pgrep -f "uvicorn app.server:app" >/dev/null 2>&1; then
  nohup /opt/appliance/venv/bin/uvicorn app.server:app \
    --host "${BROWSER_API_HOST}" \
    --port "${BROWSER_API_PORT}" \
    >/tmp/browser-api.log 2>&1 &
fi

if ! pgrep -f "socat TCP-LISTEN:${BROWSER_CDP_PROXY_PORT}" >/dev/null 2>&1; then
  nohup socat \
    "TCP-LISTEN:${BROWSER_CDP_PROXY_PORT},bind=0.0.0.0,fork,reuseaddr" \
    "TCP:127.0.0.1:${BROWSER_CDP_PORT}" \
    >/tmp/cdp-proxy.log 2>&1 &
fi

if ! pgrep -f "chrome-linux64/chrome.*--remote-debugging-port=${BROWSER_CDP_PORT}" >/dev/null 2>&1; then
  start_browser_launcher
fi

if [ "${DESKTOP_SESSION_FLAVOR:-noctalia-niri}" = "niri-nested" ]; then
  if [ "${PRIMARY_COMPOSITOR:-labwc}" != "niri" ] && command -v niri >/dev/null 2>&1 && ! pgrep -x niri >/dev/null 2>&1; then
    nohup /opt/appliance/niri-launcher.sh >/tmp/niri-launcher.log 2>&1 &
  fi
fi

if [ "${DESKTOP_SESSION_FLAVOR:-noctalia-niri}" = "noctalia-niri" ]; then
  if [ "${PRIMARY_COMPOSITOR:-labwc}" != "niri" ] && command -v niri >/dev/null 2>&1 && ! pgrep -x niri >/dev/null 2>&1; then
    nohup /opt/appliance/niri-launcher.sh >/tmp/niri-launcher.log 2>&1 &
    for _ in $(seq 1 40); do
      if [ -f /tmp/niri-wayland-display ]; then
        break
      fi
      sleep 0.5
    done
  fi
  if command -v noctalia >/dev/null 2>&1 && ! pgrep -x noctalia >/dev/null 2>&1; then
    nohup /opt/appliance/noctalia-launcher.sh >/tmp/noctalia-launcher.log 2>&1 &
  else
    echo "Noctalia not installed in this image" >/tmp/noctalia.log
  fi
fi

nohup sh -lc '
  sleep 10
  if ! curl -fsS "http://127.0.0.1:${BROWSER_API_PORT}/healthz" | grep -q "\"ok\":true"; then
    pkill -f "chrome-linux64/chrome.*--remote-debugging-port=${BROWSER_CDP_PORT}" >/dev/null 2>&1 || true
    exec /opt/appliance/browser-launcher.sh
  fi
' >/tmp/browser-watchdog.log 2>&1 &
