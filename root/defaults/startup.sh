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
mkdir -p /config/selkies-web

apply_selkies_branding() {
  local source_root="/usr/share/selkies/web"
  local source_www_root="/usr/share/selkies/www"
  local web_root="/config/selkies-web"
  local branding_root="/defaults/selkies-web"
  local index_html="${web_root}/index.html"

  [ -d "${branding_root}" ] || return 0
  [ -d "${source_root}" ] || return 0

  # A previous run may have populated web_root with files owned by root while
  # the current run is abc (or vice versa); without write access cp fails. Try
  # to normalise ownership when we have the privilege, but never let any of this
  # abort startup — branding is cosmetic and must not block the compositor.
  chown -R abc:abc "${web_root}" >/dev/null 2>&1 || true

  cp -a "${source_root}/." "${web_root}/" 2>/dev/null || \
    cp -rf "${source_root}/." "${web_root}/" 2>/dev/null || true

  cp -f "${branding_root}/agentbrowser.css" "${web_root}/agentbrowser.css" 2>/dev/null || true
  cp -f "${branding_root}/agentbrowser.js" "${web_root}/agentbrowser.js" 2>/dev/null || true
  cp -f "${branding_root}/agentbrowser-logo.png" "${web_root}/agentbrowser-logo.png" 2>/dev/null || true
  cp -f "${branding_root}/agentbrowser-start-icon.png" "${web_root}/agentbrowser-start-icon.png" 2>/dev/null || true
  if [ -d "${source_www_root}" ]; then
    cp -f "${branding_root}/agentbrowser-start-icon.png" "${source_www_root}/icon.png" 2>/dev/null || true
  fi

  python <<'PY' 2>/dev/null || true
from pathlib import Path

index = Path("/config/selkies-web/index.html")
html = index.read_text()
css = '<link rel="stylesheet" href="./agentbrowser.css">'
js = '<script defer src="./agentbrowser.js"></script>'
if css not in html:
    html = html.replace("</head>", css + "</head>")
if js not in html:
    html = html.replace("</head>", js + "</head>")
index.write_text(html)
PY

  chown -R abc:abc "${web_root}" >/dev/null 2>&1 || true
}

if [ -d /defaults/noctalia-state ]; then
  cp -an /defaults/noctalia-state/. /config/.local/state/noctalia/
  chown -R abc:abc /config/.local/state/noctalia >/dev/null 2>&1 || true
fi

if [ -d /defaults/wallpapers ]; then
  cp -an /defaults/wallpapers/. /config/wallpapers/
  chown -R abc:abc /config/wallpapers >/dev/null 2>&1 || true
fi

# Branding must never abort startup (set -e) — the compositor launch below
# depends on reaching the end of this script.
apply_selkies_branding || true

# proot-apps installs drop a *.desktop launcher into ~/Desktop, which xfce/labwc
# render as desktop icons. niri/noctalia have no desktop-icon manager, so those
# apps become unreachable. Mirror the launchers into the XDG applications dir so
# they show up in the niri launcher (Mod+D / fuzzel), noctalia, and the app list.
sync_desktop_launchers() {
  local desktop_dir="/config/Desktop"
  local apps_dir="/config/.local/share/applications"
  [ -d "${desktop_dir}" ] || return 0

  # The baseimage may create apps_dir owned by root; we run as abc. Since the
  # parent is abc-owned we can move the unwritable dir aside and recreate it.
  if [ -d "${apps_dir}" ] && ! ( : > "${apps_dir}/.w" ) 2>/dev/null; then
    mv "${apps_dir}" "${apps_dir}.root-$$" 2>/dev/null || true
  else
    rm -f "${apps_dir}/.w" 2>/dev/null || true
  fi
  mkdir -p "${apps_dir}" 2>/dev/null || true

  local f dst
  for f in "${desktop_dir}"/*.desktop; do
    [ -e "${f}" ] || continue
    dst="${apps_dir}/$(basename "${f}")"
    if [ ! -e "${dst}" ] || [ "${f}" -nt "${dst}" ]; then
      cp -f "${f}" "${dst}" 2>/dev/null || true
    fi
  done
}

case "${DESKTOP_SESSION_FLAVOR:-noctalia-niri}" in
  noctalia-niri | niri-nested)
    sync_desktop_launchers || true
    # Keep mirroring as the user installs more proot-apps at runtime.
    nohup sh -lc '
      while true; do
        sleep 8
        for f in /config/Desktop/*.desktop; do
          [ -e "$f" ] || continue
          d="/config/.local/share/applications/$(basename "$f")"
          { [ ! -e "$d" ] || [ "$f" -nt "$d" ]; } && cp -f "$f" "$d" 2>/dev/null || true
        done
      done
    ' >/dev/null 2>&1 &
    ;;
esac

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
