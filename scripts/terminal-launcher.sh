#!/usr/bin/env bash
set -euo pipefail

for term in foot alacritty kitty xterm; do
  if command -v "${term}" >/dev/null 2>&1; then
    exec "${term}" "$@"
  fi
done

echo "No terminal emulator found (tried: foot, alacritty, kitty, xterm)" >&2
exit 127
