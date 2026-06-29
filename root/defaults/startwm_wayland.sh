#!/usr/bin/env bash
set -euo pipefail

# Start DE
ulimit -c 0
export XCURSOR_THEME=whiteglass
export XCURSOR_SIZE=24
export XKB_DEFAULT_LAYOUT=us
export XKB_DEFAULT_RULES=evdev
export WAYLAND_DISPLAY=wayland-1
export XDG_RUNTIME_DIR="${BROWSER_XDG_RUNTIME_DIR:-/config/.XDG}"
export PRIMARY_COMPOSITOR="${PRIMARY_COMPOSITOR:-labwc}"

# XDG_RUNTIME_DIR must be 0700 (XDG spec). The baseimage creates it 0755, which
# makes Qt/KDE (KIO) refuse to use it for sockets — dolphin et al. then spam
# "KIO: Permiso denegado". Enforce the correct mode on every start.
mkdir -p "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}" 2>/dev/null || true

if [ "${SELKIES_DESKTOP}" == "true" ]; then
  if [ "${PRIMARY_COMPOSITOR}" = "niri" ]; then
    rm -f /tmp/niri-wayland-display /tmp/niri-x-display
    # Run niri nested inside the Selkies compositor (wayland-1), not as DRM primary
    NIRI_PRIMARY_MODE=nested nohup /opt/appliance/niri-launcher.sh >/tmp/compositor.log 2>&1 &
    for _ in $(seq 1 120); do
      [ -f /tmp/niri-wayland-display ] && break
      sleep 0.5
    done
    export WAYLAND_DISPLAY="$(cat /tmp/niri-wayland-display 2>/dev/null || echo wayland-2)"
  else
    labwc >/tmp/compositor.log 2>&1 &
    sleep 1
    export WAYLAND_DISPLAY=wayland-0
  fi
  export DISPLAY=:0
  /defaults/startup.sh >/tmp/startup-hook.log 2>&1 &
  selkies-desktop
else
  /defaults/startup.sh >/tmp/startup-hook.log 2>&1 &
  if [ "${PRIMARY_COMPOSITOR}" = "niri" ]; then
    /opt/appliance/niri-launcher.sh >/tmp/compositor.log 2>&1
  else
    labwc >/tmp/compositor.log 2>&1
  fi
fi
