"""wdotool MCP tool for agentbrowser.

This module provides mouse and keyboard control using wdotool,
which works on Wayland via wlr-protocols (virtual-keyboard, virtual-pointer).
"""

import asyncio
import os
from typing import Any


class WdotoolTool:
    """Tool for controlling mouse and keyboard using wdotool."""
    
    def __init__(self):
        self._env = {
            "WAYLAND_DISPLAY": os.getenv("WAYLAND_DISPLAY", "wayland-2"),
            "XDG_RUNTIME_DIR": os.getenv("XDG_RUNTIME_DIR", "/config/.XDG"),
        }
    
    async def _run_wdotool(self, *args: str) -> dict[str, Any]:
        """Run a wdotool command and return the result."""
        try:
            process = await asyncio.create_subprocess_exec(
                "wdotool", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._env,
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return {
                    "ok": False,
                    "error": stderr.decode(errors="ignore"),
                    "command": " ".join(args),
                }
            
            return {
                "ok": True,
                "output": stdout.decode(errors="ignore").strip(),
                "command": " ".join(args),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "command": " ".join(args)}
    
    async def mousemove(self, x: int, y: int, relative: bool = False) -> dict[str, Any]:
        """Move mouse to absolute or relative position."""
        if relative:
            result = await self._run_wdotool("mousemove", "--relative", str(x), str(y))
        else:
            result = await self._run_wdot("mousemove", str(x), str(y))
        return result
    
    async def click(self, button: int = 1) -> dict[str, Any]:
        """Click mouse button (1=left, 2=middle, 3=right)."""
        return await self._run_wdotool("click", str(button))
    
    async def mousedown(self, button: int = 1) -> dict[str, Any]:
        """Press mouse button."""
        return await self._run_wdotool("mousedown", str(button))
    
    async def mouseup(self, button: int = 1) -> dict[str, Any]:
        """Release mouse button."""
        return await self._run_wdotool("mouseup", str(button))
    
    async def scroll(self, dx: int = 0, dy: int = 3) -> dict[str, Any]:
        """Scroll mouse wheel."""
        return await self._run_wdotool("scroll", str(dx), str(dy))
    
    async def type_text(self, text: str) -> dict[str, Any]:
        """Type text."""
        return await self._run_wdotool("type", text)
    
    async def key(self, keys: str) -> dict[str, Any]:
        """Press key combination (e.g., 'ctrl+c')."""
        return await self._run_wdotool("key", keys)
    
    async def keydown(self, keys: str) -> dict[str, Any]:
        """Press and hold key."""
        return await self._run_wdotool("keydown", keys)
    
    async def keyup(self, keys: str) -> dict[str, Any]:
        """Release key."""
        return await self._run_wdotool("keyup", keys)
    
    async def search(self, name: str = "", app_id: str = "", pid: int = 0) -> dict[str, Any]:
        """Search for windows."""
        args = ["search"]
        if name:
            args.extend(["--name", name])
        if app_id:
            args.extend(["--class", app_id])
        if pid:
            args.extend(["--pid", str(pid)])
        return await self._run_wdotool(*args)
    
    async def getactivewindow(self) -> dict[str, Any]:
        """Get active window ID."""
        return await self._run_wdotool("getactivewindow")
    
    async def windowactivate(self, window_id: str) -> dict[str, Any]:
        """Activate (focus) a window."""
        return await self._run_wdotool("windowactivate", window_id)
    
    async def windowclose(self, window_id: str) -> dict[str, Any]:
        """Close a window."""
        return await self._run_wdotool("windowclose", window_id)
    
    async def info(self) -> dict[str, Any]:
        """Get wdotool backend info."""
        return await self._run_wdotool("info")


# Singleton instance
_wdotool_tool = None


def get_wdotool_tool() -> WdotoolTool:
    """Get or create wdotool tool instance."""
    global _wdotool_tool
    if _wdotool_tool is None:
        _wdotool_tool = WdotoolTool()
    return _wdotool_tool
