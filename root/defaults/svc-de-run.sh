#!/bin/bash

echo "=== Iniciando sistema completo ==="

# Fix permissions
chmod 666 /tmp/*.log 2>/dev/null || true

# Clean stale files
rm -f /tmp/niri-wayland-display /tmp/niri-x-display
rm -f /config/.XDG/niri.*.sock 2>/dev/null || true

# Start niri (only if not running)
if ! pgrep -x niri >/dev/null 2>&1; then
  echo "[1/6] Iniciando niri..."
  sudo -u abc env DISPLAY=:1 WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/config/.XDG /usr/sbin/niri &>/tmp/niri.log &
  sleep 5
else
  echo "[1/6] niri ya está corriendo"
fi

# Create display files
echo "wayland-2" > /tmp/niri-wayland-display
echo ":2" > /tmp/niri-x-display

# Start xwayland-satellite (only if not running)
if ! pgrep -x xwayland-satellite >/dev/null 2>&1; then
  echo "[2/6] Iniciando xwayland-satellite..."
  sudo -u abc WAYLAND_DISPLAY=wayland-2 XDG_RUNTIME_DIR=/config/.XDG xwayland-satellite :2 &>/tmp/xwayland.log &
  sleep 2
else
  echo "[2/6] xwayland-satellite ya está corriendo"
fi

# Start selkies-desktop FIRST (only if not running)
if ! pgrep -x selkies-desktop >/dev/null 2>&1; then
  echo "[3/6] Iniciando selkies-desktop..."
  sudo -u abc WAYLAND_DISPLAY=wayland-2 XDG_RUNTIME_DIR=/config/.XDG /usr/sbin/selkies-desktop &>/tmp/selkies-desktop.log &
  sleep 2
else
  echo "[3/6] selkies-desktop ya está corriendo"
fi

# Start Chrome (only if not running)
if ! pgrep -f "chrome.*remote-debugging" >/dev/null 2>&1; then
  echo "[4/6] Iniciando Chrome..."
  sudo -u abc DISPLAY=:2 /opt/playwright/chromium-1228/chrome-linux64/chrome --ozone-platform=x11 --disable-dev-shm-usage --no-sandbox --remote-debugging-port=9222 &>/tmp/chrome.log &
  sleep 3
else
  echo "[4/6] Chrome ya está corriendo"
fi

# Start noctalia (only if not running)
if ! pgrep -x noctalia >/dev/null 2>&1; then
  echo "[5/6] Iniciando noctalia..."
  sudo -u abc WAYLAND_DISPLAY=wayland-2 XDG_RUNTIME_DIR=/config/.XDG /usr/sbin/noctalia &>/tmp/noctalia.log &
  sleep 1
else
  echo "[5/6] noctalia ya está corriendo"
fi

# Start uvicorn (only if not running)
if ! pgrep -f uvicorn >/dev/null 2>&1; then
  echo "[6/6] Iniciando servidor MCP..."
  cd /opt/appliance
  /opt/appliance/venv/bin/uvicorn app.server:app --host 0.0.0.0 --port 8787 &>/tmp/browser-api.log &
  sleep 2
else
  echo "[6/6] uvicorn ya está corriendo"
fi

echo "=== Sistema iniciado ==="
sleep 3
echo "niri: $(pgrep -x niri | head -1)"
echo "chrome: $(pgrep -f 'chrome.*remote-debugging' | head -1)"
echo "uvicorn: $(pgrep -f uvicorn | head -1)"
echo "noctalia: $(pgrep -x noctalia | head -1)"
echo "selkies-desktop: $(pgrep -x selkies-desktop | head -1)"
