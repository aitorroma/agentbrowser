#!/usr/bin/env bash
set -euo pipefail

if [ "${DESKTOP_SESSION_FLAVOR:-xfce}" != "noctalia-niri" ]; then
  exit 0
fi

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export GDK_BACKEND="${GDK_BACKEND:-wayland}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"
export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-Noctalia}"
export XDG_SESSION_DESKTOP="${XDG_SESSION_DESKTOP:-Noctalia}"

if [ -f /tmp/niri-wayland-display ]; then
  WAYLAND_DISPLAY="$(cat /tmp/niri-wayland-display)"
  export WAYLAND_DISPLAY
fi

if [ -f /tmp/niri-x-display ]; then
  DISPLAY="$(cat /tmp/niri-x-display)"
  export DISPLAY
fi

if pgrep -u "$(id -u)" -x noctalia >/dev/null 2>&1; then
  exit 0
fi

for _ in $(seq 1 60); do
  if [ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ]; then
    break
  fi
  sleep 0.5
done

if [ ! -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ]; then
  echo "Wayland socket ${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY} not ready" >&2
  exit 1
fi

NOCTALIA_BIN="${NOCTALIA_BIN:-$(command -v noctalia || true)}"
if [ -z "${NOCTALIA_BIN}" ]; then
  echo "noctalia binary not found in PATH" >&2
  exit 1
fi

nohup "${NOCTALIA_BIN}" >/tmp/noctalia.log 2>&1 &
