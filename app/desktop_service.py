import asyncio
import os
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class DesktopService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.display = os.getenv("DISPLAY", ":20")
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "/data/output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def _run(
        self,
        *args: str,
        check: bool = True,
        text: bool = True,
        env: dict[str, str] | None = None,
    ) -> asyncio.subprocess.Process:
        full_env = os.environ.copy()
        full_env["DISPLAY"] = self.display
        if env:
            full_env.update(env)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
        stdout, stderr = await process.communicate()
        if check and process.returncode != 0:
            raise RuntimeError(
                f"{' '.join(args)} failed with {process.returncode}: {(stderr or b'').decode(errors='ignore')}"
            )
        process.stdout_data = stdout.decode(errors="ignore") if text else stdout  # type: ignore[attr-defined]
        process.stderr_data = stderr.decode(errors="ignore") if text else stderr  # type: ignore[attr-defined]
        return process

    async def screen_shot(
        self,
        path: str | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            if path is None:
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                path = str(self.output_dir / f"desktop-{stamp}.png")
            args = ["scrot", path]
            if region:
                args = ["scrot", "-a", region, path]
            await self._run(*args)
            return {"path": path, "display": self.display, "region": region}

    async def mouse_move(self, x: int, y: int) -> dict[str, Any]:
        async with self._lock:
            await self._run("xdotool", "mousemove", str(x), str(y))
            return {"ok": True, "x": x, "y": y}

    async def mouse_click(self, x: int, y: int, button: int = 1) -> dict[str, Any]:
        async with self._lock:
            await self._run("xdotool", "mousemove", str(x), str(y), "click", str(button))
            return {"ok": True, "x": x, "y": y, "button": button}

    async def mouse_double_click(self, x: int, y: int, button: int = 1) -> dict[str, Any]:
        async with self._lock:
            await self._run("xdotool", "mousemove", str(x), str(y), "click", "--repeat", "2", str(button))
            return {"ok": True, "x": x, "y": y, "button": button}

    async def mouse_drag(self, x1: int, y1: int, x2: int, y2: int, button: int = 1) -> dict[str, Any]:
        async with self._lock:
            await self._run(
                "xdotool",
                "mousemove",
                str(x1),
                str(y1),
                "mousedown",
                str(button),
                "mousemove",
                "--sync",
                str(x2),
                str(y2),
                "mouseup",
                str(button),
            )
            return {"ok": True, "from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}, "button": button}

    async def mouse_scroll(self, direction: str = "down", clicks: int = 3) -> dict[str, Any]:
        button_map = {"up": "4", "down": "5", "left": "6", "right": "7"}
        button = button_map.get(direction.lower())
        if button is None:
            raise ValueError("direction must be one of: up, down, left, right")
        async with self._lock:
            await self._run("xdotool", "click", "--repeat", str(clicks), button)
            return {"ok": True, "direction": direction, "clicks": clicks}

    async def key_type(self, text: str, delay_ms: int = 20) -> dict[str, Any]:
        async with self._lock:
            await self._run("xdotool", "type", "--delay", str(delay_ms), text)
            return {"ok": True, "text_length": len(text), "delay_ms": delay_ms}

    async def key_press(self, keys: str) -> dict[str, Any]:
        async with self._lock:
            await self._run("xdotool", "key", keys)
            return {"ok": True, "keys": keys}

    async def clipboard_get(self) -> dict[str, Any]:
        async with self._lock:
            result = await self._run("xclip", "-o", "-selection", "clipboard")
            return {"text": result.stdout_data}

    async def clipboard_set(self, text: str) -> dict[str, Any]:
        async with self._lock:
            process = await asyncio.create_subprocess_exec(
                "xclip",
                "-i",
                "-selection",
                "clipboard",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "DISPLAY": self.display},
            )
            _, stderr = await process.communicate(text.encode())
            if process.returncode != 0:
                raise RuntimeError(stderr.decode(errors="ignore"))
            return {"ok": True, "text_length": len(text)}

    async def window_list(self) -> dict[str, Any]:
        async with self._lock:
            result = await self._run("wmctrl", "-lp")
            windows = []
            for line in result.stdout_data.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 5:
                    windows.append(
                        {
                            "id": parts[0],
                            "desktop": parts[1],
                            "pid": parts[2],
                            "host": parts[3],
                            "title": parts[4],
                        }
                    )
            return {"windows": windows}

    async def window_focus(self, query: str) -> dict[str, Any]:
        async with self._lock:
            if query.startswith("0x"):
                await self._run("wmctrl", "-ia", query)
            else:
                await self._run("wmctrl", "-a", query)
            return {"ok": True, "query": query}

    async def app_launch(self, command: str) -> dict[str, Any]:
        async with self._lock:
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-lc",
                command,
                env={**os.environ, "DISPLAY": self.display},
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            return {"ok": True, "command": command, "pid": proc.pid}

    async def app_list(self) -> dict[str, Any]:
        known = []
        for name in ["chromium", "xfce4-terminal", "xterm", "mousepad", "thunar", "firefox"]:
            path = await self._run("sh", "-lc", f"command -v {shlex.quote(name)} || true")
            resolved = path.stdout_data.strip()
            if resolved:
                known.append({"name": name, "path": resolved})
        return {"apps": known}

    async def app_status(self, query: str) -> dict[str, Any]:
        windows = await self.window_list()
        matching = [w for w in windows["windows"] if query.lower() in w["title"].lower()]
        return {"query": query, "running": bool(matching), "windows": matching}


desktop_service = DesktopService()
