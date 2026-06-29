#!/usr/bin/env bash
set -euo pipefail

app="${1:-}"
shift || true
app_key="$(basename "${app}")"
app_key="${app_key,,}"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export DISPLAY="${DISPLAY:-:0}"

if [ "${DESKTOP_SESSION_FLAVOR:-}" = "noctalia-niri" ] && [ -f /tmp/niri-wayland-display ]; then
  export WAYLAND_DISPLAY="$(cat /tmp/niri-wayland-display)"
fi

if [ "${DESKTOP_SESSION_FLAVOR:-}" = "noctalia-niri" ] && [ -f /tmp/niri-x-display ]; then
  export DISPLAY="$(cat /tmp/niri-x-display)"
fi

case "${app_key}" in
  firefox)
    exec env MOZ_ENABLE_WAYLAND=0 GDK_BACKEND=x11 DISPLAY="${DISPLAY}" firefox "$@"
    ;;
  chromium|chrome)
    chrome_bin="$(
      /opt/appliance/venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
PY
    )"
    exec "${chrome_bin}" \
      --ozone-platform=x11 \
      --disable-dev-shm-usage \
      "$@"
    ;;
  thunar)
    exec env GDK_BACKEND=x11 DISPLAY="${DISPLAY}" thunar "$@"
    ;;
  foot|fuzzel)
    exec "${app_key}" "$@"
    ;;
  "")
    echo "usage: niri-run-app.sh <app> [args...]" >&2
    exit 64
    ;;
  *)
    exec "${app}" "$@"
    ;;
esac
