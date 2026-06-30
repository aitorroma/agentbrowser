#!/usr/bin/with-contenv bash

# Restore persistent components
/opt/appliance/restore-all.sh 2>/dev/null || true

# wayland entrypoint
if [[ "${PIXELFLUX_WAYLAND}" == "true" ]]; then
  SOCKET_PATH="${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY:-wayland-1}"
  echo "[svc-de] Wayland mode: Waiting for socket at ${SOCKET_PATH}..."
  while [ ! -e "${SOCKET_PATH}" ]; do
    sleep 0.5
  done
  echo "[svc-de] ${SOCKET_PATH} found launching de"
  cd $HOME
  exec s6-setuidgid abc \
    /bin/bash /defaults/startwm_wayland.sh &
  PID=$!
  echo "$PID" > /de-pid
  wait "$PID"
  exit 1
fi
