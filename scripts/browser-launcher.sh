#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:20}"
export HOME="${HOME:-/home/ubuntu}"
PROFILE_DIR="${BROWSER_PROFILE_DIR:-/data/profile/chromium}"
OUTPUT_DIR="${OUTPUT_DIR:-/data/output}"
CDP_BIND="${BROWSER_CDP_BIND:-127.0.0.1}"
CDP_PORT="${BROWSER_CDP_PORT:-9222}"
WINDOW_SIZE="${BROWSER_WINDOW_SIZE:-1366,768}"
START_URL="${BROWSER_START_URL:-about:blank}"
LOCALE="${BROWSER_LOCALE:-es-ES}"
LANG_LIST="${BROWSER_ACCEPT_LANGS:-${LOCALE},es}"
DISABLE_SANDBOX="${BROWSER_DISABLE_SANDBOX:-false}"

mkdir -p "$PROFILE_DIR" "$OUTPUT_DIR"

rm -f \
  "$PROFILE_DIR/SingletonLock" \
  "$PROFILE_DIR/SingletonSocket" \
  "$PROFILE_DIR/SingletonCookie"

python3 - <<PY
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

until [ -S "/tmp/.X11-unix/X${DISPLAY#*:}" ]; do
  sleep 0.5
done

CHROME_BIN="$(
/opt/appliance/venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
PY
)"

args=(
  "$CHROME_BIN"
  "--user-data-dir=${PROFILE_DIR}"
  "--remote-debugging-address=${CDP_BIND}"
  "--remote-debugging-port=${CDP_PORT}"
  "--password-store=basic"
  "--no-first-run"
  "--no-default-browser-check"
  "--disable-dev-shm-usage"
  "--disable-gpu"
  "--disable-features=Translate,AcceptCHFrame,MediaRouter,OptimizationHints,ProcessPerSiteUpToMainFrameThreshold"
  "--window-size=${WINDOW_SIZE}"
  "--lang=${LOCALE}"
  "--ozone-platform=x11"
)

if [ "${DISABLE_SANDBOX}" = "true" ]; then
  args+=("--no-sandbox")
fi

if [ -n "${BROWSER_PROXY_SERVER:-}" ]; then
  args+=("--proxy-server=${BROWSER_PROXY_SERVER}")
  if [ -n "${BROWSER_PROXY_BYPASS:-}" ]; then
    args+=("--proxy-bypass-list=${BROWSER_PROXY_BYPASS}")
  fi
fi

args+=("${START_URL}")

echo "Launching Chromium with CDP at ${CDP_BIND}:${CDP_PORT}"
exec "${args[@]}"
