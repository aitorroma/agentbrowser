#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/config}"
export XDG_RUNTIME_DIR="${BROWSER_XDG_RUNTIME_DIR:-/config/.XDG}"
export WAYLAND_DISPLAY="${BROWSER_WAYLAND_DISPLAY:-${WAYLAND_DISPLAY:-wayland-0}}"
export DISPLAY="${DISPLAY:-:1}"
PROFILE_DIR="${BROWSER_PROFILE_DIR:-/data/profile/chromium}"
OUTPUT_DIR="${OUTPUT_DIR:-/data/output}"
CDP_BIND="${BROWSER_CDP_BIND:-127.0.0.1}"
CDP_PORT="${BROWSER_CDP_PORT:-9222}"
WINDOW_SIZE="${BROWSER_WINDOW_SIZE:-1366,768}"
START_URL="${BROWSER_START_URL:-about:blank}"
LOCALE="${BROWSER_LOCALE:-es-ES}"
LANG_LIST="${BROWSER_ACCEPT_LANGS:-${LOCALE},es}"
DISABLE_SANDBOX="${BROWSER_DISABLE_SANDBOX:-false}"
FORCE_RENDERER_ACCESSIBILITY="${BROWSER_FORCE_RENDERER_ACCESSIBILITY:-false}"
OZONE_PLATFORM="${BROWSER_OZONE_PLATFORM:-x11}"
BROWSER_BINARY="${BROWSER_BINARY:-}"

mkdir -p "$PROFILE_DIR" "$OUTPUT_DIR"

rm -f \
  "$PROFILE_DIR/SingletonLock" \
  "$PROFILE_DIR/SingletonSocket" \
  "$PROFILE_DIR/SingletonCookie"

python <<PY
import json
from pathlib import Path

profile_dir = Path(${PROFILE_DIR@Q})
locale = ${LOCALE@Q}
lang_list = ${LANG_LIST@Q}

targets = [
    (profile_dir / "Local State", {"intl": {"app_locale": locale}}),
    (profile_dir / "Default" / "Preferences", {"intl": {"selected_languages": lang_list}}),
]

for path, patch in targets:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except Exception:
            data = {}
    for key, value in patch.items():
        node = data.setdefault(key, {})
        if isinstance(node, dict) and isinstance(value, dict):
            node.update(value)
        else:
            data[key] = value
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
PY

for _ in $(seq 1 120); do
  if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ]; then
    break
  fi
  if [ -n "${DISPLAY:-}" ] && [ -S "/tmp/.X11-unix/X${DISPLAY#*:}" ]; then
    break
  fi
  sleep 0.5
done

gsettings set org.gnome.desktop.interface toolkit-accessibility true >/dev/null 2>&1 || true

if [ -n "${BROWSER_BINARY}" ]; then
  case "${BROWSER_BINARY}" in
    chrome|google-chrome|google-chrome-stable)
      CHROME_BIN="$(command -v google-chrome-stable)"
      ;;
    chromium)
      CHROME_BIN="$(command -v chromium)"
      ;;
    playwright)
      CHROME_BIN="$(
      /opt/appliance/venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
PY
      )"
      ;;
    *)
      CHROME_BIN="${BROWSER_BINARY}"
      ;;
  esac
elif command -v google-chrome-stable >/dev/null 2>&1; then
  CHROME_BIN="$(command -v google-chrome-stable)"
else
  CHROME_BIN="$(
  /opt/appliance/venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
PY
  )"
fi

args=(
  "$CHROME_BIN"
  "--user-data-dir=${PROFILE_DIR}"
  "--remote-debugging-address=${CDP_BIND}"
  "--remote-debugging-port=${CDP_PORT}"
  "--remote-allow-origins=*"
  "--password-store=basic"
  "--no-first-run"
  "--no-default-browser-check"
  "--disable-dev-shm-usage"
  "--disable-gpu"
  "--disable-features=Translate,AcceptCHFrame,MediaRouter,OptimizationHints,ProcessPerSiteUpToMainFrameThreshold"
  "--window-size=${WINDOW_SIZE}"
  "--lang=${LOCALE}"
  "--ozone-platform=${OZONE_PLATFORM}"
)

if [ "${DISABLE_SANDBOX}" = "true" ]; then
  args+=("--no-sandbox")
fi

if [ "${FORCE_RENDERER_ACCESSIBILITY}" = "true" ]; then
  args+=("--force-renderer-accessibility")
fi

if [ -n "${BROWSER_PROXY_SERVER:-}" ]; then
  args+=("--proxy-server=${BROWSER_PROXY_SERVER}")
  if [ -n "${BROWSER_PROXY_BYPASS:-}" ]; then
    args+=("--proxy-bypass-list=${BROWSER_PROXY_BYPASS}")
  fi
fi

args+=("${START_URL}")

exec "${args[@]}"
