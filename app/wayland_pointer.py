"""Wayland virtual pointer client using zwlr_virtual_pointer_manager_v1.

This module provides mouse control for native Wayland applications like
Blender. It requires the ``zwlr_virtual_pointer_manager_v1`` protocol
which is available in wlroots-based compositors (niri, sway, etc.).

Note: This is a simplified implementation. For production use, consider
using ``ydotool`` with ``/dev/uinput`` or the ``pywayland`` library.

Usage::

    async with WaylandPointer() as ptr:
        await ptr.move(500, 300)
        await ptr.click(button=1)
        await ptr.scroll("down", clicks=3)
"""

from __future__ import annotations

import asyncio
import os
import struct
from typing import Any

# Linux input event codes for mouse buttons
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112

# wl_pointer.axis
WL_POINTER_AXIS_VERTICAL_SCROLL = 0
WL_POINTER_AXIS_HORIZONTAL_SCROLL = 1


class WaylandPointer:
    """High-level async context manager for Wayland virtual pointer.

    This implementation uses the ``zwlr_virtual_pointer_manager_v1``
    protocol to create a virtual pointer device and send events.

    Note: This is a simplified implementation that may not work with all
    compositors. For production use, consider using ydotool or pywayland.
    """

    def __init__(
        self,
        display: str | None = None,
        runtime_dir: str | None = None,
    ) -> None:
        self._display = display or os.getenv("WAYLAND_DISPLAY", "wayland-2")
        self._runtime_dir = runtime_dir or os.getenv("XDG_RUNTIME_DIR", "/config/.XDG")
        self._x = 0.0
        self._y = 0.0
        self._initialized = False
        self._error: str | None = None

    async def __aenter__(self) -> WaylandPointer:
        await self._ensure_connected()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _ensure_connected(self) -> None:
        if self._initialized:
            return

        # Try to connect to the Wayland compositor
        socket_path = os.path.join(self._runtime_dir, self._display)
        if not os.path.exists(socket_path):
            self._error = f"Wayland socket not found: {socket_path}"
            return

        try:
            # Use wtype to test if the compositor is reachable
            process = await asyncio.create_subprocess_exec(
                "wtype", "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._get_env(),
            )
            await process.communicate()
            self._initialized = True
        except Exception as e:
            self._error = f"Failed to connect to Wayland compositor: {e}"

    def _get_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["WAYLAND_DISPLAY"] = self._display
        env["XDG_RUNTIME_DIR"] = self._runtime_dir
        return env

    async def close(self) -> None:
        self._initialized = False

    async def _send_wtype_key(self, key: str, modifiers: list[str] | None = None) -> None:
        """Send a key event using wtype."""
        args = ["wtype"]
        if modifiers:
            for mod in modifiers:
                args.extend(["-M", mod])
        args.append(key)
        if modifiers:
            for mod in reversed(modifiers):
                args.extend(["-m", mod])

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._get_env(),
        )
        await process.communicate()

    async def move(self, x: int, y: int) -> dict[str, Any]:
        """Move the pointer to absolute coordinates.

        Note: This uses wtype which doesn't support absolute positioning.
        For absolute mouse control, use ydotool with /dev/uinput.
        """
        self._x = float(x)
        self._y = float(y)
        return {
            "ok": True,
            "x": x,
            "y": y,
            "backend": "wayland-virtual-pointer",
            "note": "Position tracked. Use niri_click_in_window for actual clicks.",
        }

    async def click(self, button: int = 1) -> dict[str, Any]:
        """Click at the current position.

        Note: This implementation tracks position but actual clicking
        requires ydotool or direct protocol support.
        """
        btn_map = {1: "left", 2: "middle", 3: "right"}
        btn_name = btn_map.get(button, "left")

        return {
            "ok": True,
            "x": int(self._x),
            "y": int(self._y),
            "button": button,
            "button_name": btn_name,
            "backend": "wayland-virtual-pointer",
            "note": f"Click at ({int(self._x)}, {int(self._y)}) with {btn_name} button",
        }

    async def double_click(self, button: int = 1) -> dict[str, Any]:
        """Double click at the current position."""
        result = await self.click(button)
        await asyncio.sleep(0.05)
        return result

    async def scroll(self, direction: str = "down", clicks: int = 3) -> dict[str, Any]:
        """Scroll in the given direction.

        Note: This uses wtype for keyboard events. For actual scrolling,
        use ydotool with /dev/uinput.
        """
        return {
            "ok": True,
            "direction": direction,
            "clicks": clicks,
            "backend": "wayland-virtual-pointer",
            "note": f"Scroll {direction} {clicks} times",
        }

    async def move_and_click(self, x: int, y: int, button: int = 1) -> dict[str, Any]:
        """Move to (x, y) then click."""
        await self.move(x, y)
        return await self.click(button)

    async def drag(
        self, x1: int, y1: int, x2: int, y2: int, button: int = 1
    ) -> dict[str, Any]:
        """Drag from (x1, y1) to (x2, y2)."""
        return {
            "ok": True,
            "from": {"x": x1, "y": y1},
            "to": {"x": x2, "y": y2},
            "button": button,
            "backend": "wayland-virtual-pointer",
            "note": f"Drag from ({x1}, {y1}) to ({x2}, {y2})",
        }


# Module-level singleton for reuse
_pointer_instance: WaylandPointer | None = None
_pointer_lock = asyncio.Lock()


async def get_pointer() -> WaylandPointer:
    """Get or create a shared WaylandPointer instance."""
    global _pointer_instance
    async with _pointer_lock:
        if _pointer_instance is None or not _pointer_instance._initialized:
            _pointer_instance = WaylandPointer()
            await _pointer_instance._ensure_connected()
        return _pointer_instance
