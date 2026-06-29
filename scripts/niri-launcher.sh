#!/usr/bin/env bash
set -euo pipefail

if [ "${DESKTOP_SESSION_FLAVOR:-xfce}" != "niri-nested" ] && [ "${DESKTOP_SESSION_FLAVOR:-xfce}" != "noctalia-niri" ]; then
  exit 0
fi

export DISPLAY="${DISPLAY:-:20}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-ubuntu}"
export NIRI_CONFIG="${NIRI_CONFIG:-/opt/appliance/niri/config.kdl}"
NIRI_BIN="${NIRI_BIN:-$(command -v niri || true)}"
NIRI_WAYLAND_FILE="${NIRI_WAYLAND_FILE:-/tmp/niri-wayland-display}"
NIRI_X11_FILE="${NIRI_X11_FILE:-/tmp/niri-x-display}"
NIRI_PRIMARY_MODE="${NIRI_PRIMARY_MODE:-${PRIMARY_COMPOSITOR:-}}"

mkdir -p "${HOME}/.config/niri"

if pgrep -u "$(id -u)" -x niri >/dev/null 2>&1; then
  # A niri is already running (e.g. a racing second invocation, or a leftover).
  # We must still publish the Wayland/X11 display files — startwm_wayland.sh and
  # noctalia-launcher.sh block on them, and exiting bare strands noctalia on a
  # bogus fallback display. Recover the sockets from the running niri's IPC
  # socket name (niri.<wayland-display>.<pid>.sock) and/or its log.
  if [ ! -s "${NIRI_WAYLAND_FILE}" ]; then
    running_wayland="$(sed -n 's/.*listening on Wayland socket: //p' /tmp/niri.log 2>/dev/null | tail -n1)"
    if [ -z "${running_wayland}" ]; then
      running_wayland="$(ls "${XDG_RUNTIME_DIR}"/niri.*.sock 2>/dev/null | tail -n1 | sed -n 's#.*/niri\.\([^.]*\)\..*#\1#p')"
    fi
    if [ -n "${running_wayland}" ] && [ -S "${XDG_RUNTIME_DIR}/${running_wayland}" ]; then
      printf '%s\n' "${running_wayland}" >"${NIRI_WAYLAND_FILE}"
      running_x11="$(sed -n 's/.*listening on X11 socket: //p' /tmp/niri.log 2>/dev/null | tail -n1)"
      [ -n "${running_x11}" ] && printf '%s\n' "${running_x11}" >"${NIRI_X11_FILE}"
    fi
  fi
  exit 0
fi

if [ -z "${NIRI_BIN}" ]; then
  echo "niri binary not found in PATH" >&2
  exit 1
fi

rm -f "${NIRI_WAYLAND_FILE}" "${NIRI_X11_FILE}"
# Remove stale IPC sockets from a previous niri (we only reach here when no niri
# is running). Their PID-suffixed names would otherwise accumulate and confuse
# socket discovery.
rm -f "${XDG_RUNTIME_DIR}"/niri.*.sock 2>/dev/null || true

if [ "${NIRI_PRIMARY_MODE}" = "niri" ]; then
  unset WAYLAND_DISPLAY
  unset DISPLAY
fi

nohup "${NIRI_BIN}" >/tmp/niri.log 2>&1 &

ready=0
for _ in $(seq 1 60); do
  sleep 0.5
  if [ -s /tmp/niri.log ]; then
    niri_wayland="$(sed -n 's/.*listening on Wayland socket: //p' /tmp/niri.log | tail -n1)"
    niri_x11="$(sed -n 's/.*listening on X11 socket: //p' /tmp/niri.log | tail -n1)"
    if [ -n "${niri_wayland}" ] && [ -S "${XDG_RUNTIME_DIR}/${niri_wayland}" ]; then
      printf '%s\n' "${niri_wayland}" >"${NIRI_WAYLAND_FILE}"
      if [ -n "${niri_x11}" ]; then
        printf '%s\n' "${niri_x11}" >"${NIRI_X11_FILE}"
      fi
      ready=1
      break
    fi
  fi
done

if [ "${ready}" != "1" ]; then
  echo "niri did not publish Wayland/X11 sockets in time" >&2
  exit 1
fi

if [ "${NIRI_PRIMARY_MODE}" != "niri" ]; then
  for _ in $(seq 1 40); do
    sleep 0.5
    if wmctrl -lp 2>/dev/null | grep -i "niri" >/tmp/niri-windows.txt 2>/dev/null; then
      wid="$(awk 'NR==1{print $1}' /tmp/niri-windows.txt)"
      if [ -n "${wid}" ]; then
        wmctrl -ia "${wid}" || true
        wmctrl -i -r "${wid}" -b add,maximized_vert,maximized_horz || true
        break
      fi
    fi
  done
fi
