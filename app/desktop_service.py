import asyncio
import configparser
import json
import os
import shlex
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class DesktopService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "/data/output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_display(self) -> str:
        if os.getenv("DESKTOP_SESSION_FLAVOR") == "noctalia-niri":
            niri_x_display = Path("/tmp/niri-x-display")
            try:
                value = niri_x_display.read_text(encoding="utf-8").strip()
                if value:
                    return value
            except FileNotFoundError:
                pass
        return os.getenv("DISPLAY", ":20")

    def _resolve_niri_wayland_display(self) -> str | None:
        if os.getenv("DESKTOP_SESSION_FLAVOR") != "noctalia-niri":
            return None
        niri_wayland = Path("/tmp/niri-wayland-display")
        try:
            value = niri_wayland.read_text(encoding="utf-8").strip()
            if value:
                return value
        except FileNotFoundError:
            return None
        return None

    def _resolve_niri_socket(self, runtime_dir: str, wayland_display: str) -> str | None:
        socket_dir = Path(runtime_dir)
        candidates = list(socket_dir.glob(f"niri.{wayland_display}.*.sock"))
        if not candidates:
            candidates = list(socket_dir.glob("niri.*.sock"))
        if not candidates:
            return None
        # Socket names embed niri's PID, so a stale socket from a previous niri
        # can linger. Pick the most recently created one (the live compositor) —
        # never a lexical sort, which would rank "niri.…357" above "niri.…1200".
        newest = max(candidates, key=lambda p: p.stat().st_mtime)
        return str(newest)

    def _is_niri(self) -> bool:
        return os.getenv("DESKTOP_SESSION_FLAVOR") == "noctalia-niri"

    def _niri_env(self) -> dict[str, str] | None:
        """Build an environment that can talk to the nested niri compositor:
        the right Wayland socket plus the niri IPC socket. Returns None when
        niri is not the active session or its socket is not up yet."""
        if not self._is_niri():
            return None
        wayland_display = self._resolve_niri_wayland_display()
        if not wayland_display:
            return None
        runtime_dir = os.getenv("XDG_RUNTIME_DIR", "/config/.XDG")
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = runtime_dir
        env["WAYLAND_DISPLAY"] = wayland_display
        niri_socket = self._resolve_niri_socket(runtime_dir, wayland_display)
        if niri_socket:
            env["NIRI_SOCKET"] = niri_socket
        return env

    async def _run_wayland(self, *args: str, stdin: bytes | None = None) -> str:
        """Run a Wayland-native tool (niri msg, wtype, wl-copy, wl-paste)
        against the nested niri compositor. The API process already runs as the
        `abc` user, which is what niri's virtual-keyboard/IPC requires."""
        env = self._niri_env()
        if env is None:
            raise RuntimeError("niri session not available")
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        out, err = await process.communicate(stdin)
        if process.returncode != 0:
            raise RuntimeError(
                f"{' '.join(args)} failed with {process.returncode}: {err.decode(errors='ignore')}"
            )
        return out.decode(errors="ignore")

    async def _wl_copy(self, text: str) -> None:
        """Set the Wayland clipboard. wl-copy double-forks a daemon that holds
        the selection; that child inherits our pipes, so capturing stdout/stderr
        would make communicate() block forever. Send to DEVNULL instead and wait
        only for the foreground process to exit."""
        env = self._niri_env()
        if env is None:
            raise RuntimeError("niri session not available")
        process = await asyncio.create_subprocess_exec(
            "wl-copy",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        await process.communicate(text.encode())

    async def niri_action(self, action: str, args: list[str] | None = None) -> dict[str, Any]:
        """Perform any niri compositor action (the full `niri msg action` set):
        window/column focus and movement, workspaces, monitors, fullscreen,
        floating, overview, screenshots, spawn, etc."""
        argv = ["niri", "msg", "action", action, *(args or [])]
        await self._run_wayland(*argv)
        return {"ok": True, "action": action, "args": args or []}

    async def niri_msg(self, args: list[str], json: bool = True) -> dict[str, Any]:
        """Run an arbitrary `niri msg` introspection/control subcommand
        (windows, workspaces, outputs, focused-window, action, output, ...)."""
        argv = ["niri", "msg"]
        if json:
            argv.append("--json")
        argv.extend(args)
        try:
            out = await self._run_wayland(*argv)
        except RuntimeError as exc:
            return {"ok": False, "error": str(exc), "args": args}
        if json:
            try:
                import json as _json

                return {"ok": True, "args": args, "data": _json.loads(out)}
            except ValueError:
                return {"ok": True, "args": args, "raw": out}
        return {"ok": True, "args": args, "raw": out}

    async def niri_windows(self) -> dict[str, Any]:
        return await self.niri_msg(["windows"])

    async def niri_workspaces(self) -> dict[str, Any]:
        return await self.niri_msg(["workspaces"])

    async def niri_outputs(self) -> dict[str, Any]:
        return await self.niri_msg(["outputs"])

    async def niri_focused_window(self) -> dict[str, Any]:
        return await self.niri_msg(["focused-window"])

    async def _niri_focused_app_id(self) -> str:
        """Return the App ID of the focused niri window (empty string if none)."""
        try:
            out = await self._run_wayland("niri", "msg", "--json", "focused-window")
            import json as _json

            data = _json.loads(out)
            if isinstance(data, dict):
                return (data.get("app_id") or "").lower()
        except (RuntimeError, ValueError):
            pass
        return ""

    # Named desktop launchers, mirroring the Super+key binds in
    # assets/niri/config.kdl. Each value is the argv spawned via niri.
    _NIRI_APPS: dict[str, list[str]] = {
        "launcher": ["/opt/appliance/niri-run-app.sh", "fuzzel"],
        "fuzzel": ["/opt/appliance/niri-run-app.sh", "fuzzel"],
        "terminal": ["/opt/appliance/terminal-launcher.sh"],
        "foot": ["/opt/appliance/terminal-launcher.sh"],
        "firefox": ["/opt/appliance/niri-run-app.sh", "firefox"],
        "dolphin": ["/opt/appliance/niri-run-app.sh", "dolphin"],
        # Dolphin is the default file manager: it works, whereas thunar crashes
        # under niri (its GTK4/glycin SVG loader needs a bwrap sandbox that the
        # container forbids). "thunar" stays available explicitly.
        "files": ["/opt/appliance/niri-run-app.sh", "dolphin"],
        "thunar": ["/opt/appliance/niri-run-app.sh", "thunar"],
        "chromium": ["/opt/appliance/niri-run-app.sh", "chromium"],
    }

    async def niri_spawn(self, command: str, args: list[str] | None = None) -> dict[str, Any]:
        """Spawn a command as a child of the niri compositor so it inherits the
        correct Wayland session — the reliable way to launch desktop apps under
        niri (xdotool/X11 spawning does not work for native Wayland clients)."""
        argv = ["niri", "msg", "action", "spawn", "--", command, *(args or [])]
        try:
            await self._run_wayland(*argv)
        except RuntimeError as exc:
            return {"ok": False, "command": command, "args": args or [], "error": str(exc)}
        return {"ok": True, "command": command, "args": args or []}

    async def open_app(self, app: str) -> dict[str, Any]:
        """Launch a known desktop app by name (launcher/fuzzel, terminal/foot,
        firefox, thunar/files, chromium) via niri."""
        key = app.strip().lower()
        argv = self._NIRI_APPS.get(key)
        if argv is None:
            return {
                "ok": False,
                "app": app,
                "error": f"unknown app '{app}'",
                "available": sorted(self._NIRI_APPS),
            }
        result = await self.niri_spawn(argv[0], argv[1:])
        result["app"] = key
        return result

    async def open_launcher(self) -> dict[str, Any]:
        """Open the fuzzel application launcher (same as Super+D)."""
        return await self.open_app("fuzzel")

    async def open_terminal(self) -> dict[str, Any]:
        """Open a foot terminal (same as Super+T)."""
        return await self.open_app("terminal")

    async def open_firefox(self) -> dict[str, Any]:
        """Open Firefox (same as Super+B)."""
        return await self.open_app("firefox")

    async def open_files(self) -> dict[str, Any]:
        """Open the default file manager (Dolphin)."""
        return await self.open_app("files")

    async def open_dolphin(self) -> dict[str, Any]:
        """Open the Dolphin file manager."""
        return await self.open_app("dolphin")

    async def workspace_goto(self, reference: int | str) -> dict[str, Any]:
        """Switch to a workspace by 1-based index or by name."""
        return await self.niri_action("focus-workspace", [str(reference)])

    async def workspace_set_name(self, name: str) -> dict[str, Any]:
        """Name the focused workspace (enables switching to it by name)."""
        return await self.niri_action("set-workspace-name", [name])

    async def move_window_to_workspace_named(self, reference: int | str) -> dict[str, Any]:
        """Move the focused window to a workspace by 1-based index or name."""
        return await self.niri_action("move-window-to-workspace", [str(reference)])

    async def workspace_next(self) -> dict[str, Any]:
        """Switch to the next workspace (down)."""
        return await self.niri_action("focus-workspace-down")

    async def workspace_prev(self) -> dict[str, Any]:
        """Switch to the previous workspace (up)."""
        return await self.niri_action("focus-workspace-up")

    async def move_window_to_workspace(self, index: int) -> dict[str, Any]:
        """Move the focused window to the workspace with the given 1-based index."""
        return await self.niri_action("move-window-to-workspace", [str(index)])

    # Mirrors the binds defined in assets/niri/config.kdl. Niri keybinds are
    # handled at the Wayland compositor level, so xdotool (X11/xwayland) cannot
    # trigger them; we forward them through `niri msg action` instead. Each
    # value is the argv passed after `niri msg action`.
    _NIRI_HOTKEYS: dict[str, list[str]] = {
        "super+t": ["spawn", "--", "/opt/appliance/terminal-launcher.sh"],
        "super+return": ["spawn", "--", "/opt/appliance/terminal-launcher.sh"],
        "super+d": ["spawn", "--", "/opt/appliance/niri-run-app.sh", "fuzzel"],
        "super+b": ["spawn", "--", "/opt/appliance/niri-run-app.sh", "firefox"],
        "super+e": ["spawn", "--", "/opt/appliance/niri-run-app.sh", "thunar"],
        "super+q": ["close-window"],
        "super+left": ["focus-column-left"],
        "super+h": ["focus-column-left"],
        "super+right": ["focus-column-right"],
        "super+l": ["focus-column-right"],
        "super+down": ["focus-window-down"],
        "super+j": ["focus-window-down"],
        "super+up": ["focus-window-up"],
        "super+k": ["focus-window-up"],
        "super+ctrl+left": ["move-column-left"],
        "super+ctrl+h": ["move-column-left"],
        "super+ctrl+right": ["move-column-right"],
        "super+ctrl+l": ["move-column-right"],
        "super+ctrl+down": ["move-window-down"],
        "super+ctrl+j": ["move-window-down"],
        "super+ctrl+up": ["move-window-up"],
        "super+ctrl+k": ["move-window-up"],
        "super+m": ["maximize-column"],
        "super+f": ["fullscreen-window"],
        "super+r": ["switch-preset-column-width"],
        "super+shift+r": ["switch-preset-window-height"],
    }

    # Terminals paste with Ctrl+Shift+V; everything else with Ctrl+V.
    _TERMINAL_APP_IDS = {"foot", "footclient", "alacritty", "kitty", "xterm", "org.wezfurlong.wezterm"}

    async def _maybe_handle_niri_hotkey(self, keys: str) -> dict[str, Any] | None:
        if self._niri_env() is None:
            return None
        normalized = keys.strip().lower().replace("win+", "super+").replace("windows+", "super+")
        action = self._NIRI_HOTKEYS.get(normalized)
        if action is None:
            return None
        await self._run_wayland("niri", "msg", "action", *action)
        return {"ok": True, "keys": keys, "handled_by": "niri-ipc"}

    @staticmethod
    def _wtype_modifier_args(combo: str) -> list[str] | None:
        """Translate a chord like "ctrl+shift+v" into wtype argv. Returns None
        if any token is not a plain modifier+single-key combo wtype handles."""
        mod_map = {
            "ctrl": "ctrl", "control": "ctrl",
            "shift": "shift",
            "alt": "alt", "meta": "logo", "super": "logo", "win": "logo", "cmd": "logo",
        }
        key_map = {
            "return": "Return", "enter": "Return", "tab": "Tab", "esc": "Escape",
            "escape": "Escape", "space": "space", "backspace": "BackSpace",
            "delete": "Delete", "home": "Home", "end": "End", "up": "Up",
            "down": "Down", "left": "Left", "right": "Right", "pageup": "Prior",
            "pagedown": "Next", "insert": "Insert",
        }
        parts = combo.strip().lower().split("+")
        mods, key = parts[:-1], parts[-1]
        mod_tokens = []
        for m in mods:
            if m not in mod_map:
                return None
            mod_tokens.append(mod_map[m])
        if key in key_map:
            key_token = key_map[key]
        elif len(key) == 1:
            key_token = key
        else:
            return None
        argv: list[str] = []
        for m in mod_tokens:
            argv += ["-M", m]
        argv += ["-k", key_token]
        for m in reversed(mod_tokens):
            argv += ["-m", m]
        return argv

    async def _run(
        self,
        *args: str,
        check: bool = True,
        text: bool = True,
        env: dict[str, str] | None = None,
    ) -> asyncio.subprocess.Process:
        full_env = os.environ.copy()
        full_env["DISPLAY"] = self._resolve_display()
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
            if self._niri_env() is not None:
                return await self._screen_shot_niri(path)
            args = ["scrot", path]
            if region:
                args = ["scrot", "-a", region, path]
            await self._run(*args)
            return {"path": path, "display": self._resolve_display(), "region": region}

    async def _screen_shot_niri(self, path: str) -> dict[str, Any]:
        """Capture the niri desktop. scrot/X11 only sees the empty Xwayland root
        (black), so use niri's own screenshot: it copies a PNG of the focused
        screen to the Wayland clipboard, which we then write to disk."""
        await self._run_wayland("niri", "msg", "action", "screenshot-screen")
        size = await self._niri_clipboard_png_to_file(path)
        return {"path": path, "method": "niri-screenshot", "bytes": size}

    async def _niri_clipboard_png_to_file(self, path: str) -> int:
        env = self._niri_env()
        # niri encodes the screenshot and populates the clipboard asynchronously,
        # so the PNG may not be there the instant the action returns. Poll.
        out = b""
        err = b""
        for _ in range(25):
            process = await asyncio.create_subprocess_exec(
                "wl-paste", "--type", "image/png",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            out, err = await process.communicate()
            if process.returncode == 0 and out:
                break
            await asyncio.sleep(0.2)
        if not out:
            raise RuntimeError(
                f"niri screenshot failed: {err.decode(errors='ignore') or 'empty clipboard'}"
            )
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(out)
        return len(out)

    async def screen_shot_window(self, query: str | None = None, path: str | None = None) -> dict[str, Any]:
        """Screenshot a single window (the focused one, or the one matching
        `query` by id/title/app_id) using niri's screenshot-window."""
        async with self._lock:
            if self._niri_env() is None:
                raise RuntimeError("screen_shot_window requires the niri session")
            if path is None:
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                path = str(self.output_dir / f"window-{stamp}.png")
            window = None
            if query:
                window = await self._find_window_unlocked(query)
                await self._run_wayland("niri", "msg", "action", "focus-window", "--id", str(window["id"]))
            await self._run_wayland("niri", "msg", "action", "screenshot-window")
            size = await self._niri_clipboard_png_to_file(path)
            return {"path": path, "method": "niri-screenshot-window", "bytes": size, "window": window}

    # ydotool injects input at the uinput/evdev level, so it reaches native
    # Wayland apps too (xdotool only reaches Xwayland/X11 clients). It requires
    # /dev/uinput (mapped from the host) and a running ydotoold. When those are
    # absent we fall back to xdotool, which still drives X11/Xwayland apps.
    _YDOTOOL_BUTTONS = {1: "0xC0", 2: "0xC2", 3: "0xC1"}  # left, middle, right

    def _ydotool_env(self) -> dict[str, str] | None:
        if not os.path.exists("/dev/uinput") or shutil.which("ydotool") is None:
            return None
        socket = os.getenv("YDOTOOL_SOCKET", "/tmp/.ydotool_socket")
        if not os.path.exists(socket):
            return None
        env = os.environ.copy()
        env["YDOTOOL_SOCKET"] = socket
        return env

    async def _run_ydotool(self, *args: str) -> None:
        env = self._ydotool_env()
        process = await asyncio.create_subprocess_exec(
            "ydotool", *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _, err = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"ydotool {' '.join(args)} failed: {err.decode(errors='ignore')}")

    async def mouse_move(self, x: int, y: int) -> dict[str, Any]:
        async with self._lock:
            if self._ydotool_env() is not None:
                await self._run_ydotool("mousemove", "--absolute", "-x", str(x), "-y", str(y))
                return {"ok": True, "x": x, "y": y, "backend": "ydotool"}
            await self._run("xdotool", "mousemove", str(x), str(y))
            return {"ok": True, "x": x, "y": y}

    async def mouse_click(self, x: int, y: int, button: int = 1) -> dict[str, Any]:
        async with self._lock:
            if self._ydotool_env() is not None:
                await self._run_ydotool("mousemove", "--absolute", "-x", str(x), "-y", str(y))
                await self._run_ydotool("click", self._YDOTOOL_BUTTONS.get(button, "0xC0"))
                return {"ok": True, "x": x, "y": y, "button": button, "backend": "ydotool"}
            await self._run("xdotool", "mousemove", str(x), str(y), "click", str(button))
            return {"ok": True, "x": x, "y": y, "button": button}

    async def mouse_double_click(self, x: int, y: int, button: int = 1) -> dict[str, Any]:
        async with self._lock:
            if self._ydotool_env() is not None:
                code = self._YDOTOOL_BUTTONS.get(button, "0xC0")
                await self._run_ydotool("mousemove", "--absolute", "-x", str(x), "-y", str(y))
                await self._run_ydotool("click", code, code)
                return {"ok": True, "x": x, "y": y, "button": button, "backend": "ydotool"}
            await self._run("xdotool", "mousemove", str(x), str(y), "click", "--repeat", "2", str(button))
            return {"ok": True, "x": x, "y": y, "button": button}

    async def mouse_drag(self, x1: int, y1: int, x2: int, y2: int, button: int = 1) -> dict[str, Any]:
        async with self._lock:
            if self._ydotool_env() is not None:
                down = {1: "0x40", 2: "0x44", 3: "0x42"}.get(button, "0x40")
                up = {1: "0x80", 2: "0x84", 3: "0x82"}.get(button, "0x80")
                await self._run_ydotool("mousemove", "--absolute", "-x", str(x1), "-y", str(y1))
                await self._run_ydotool("click", down)
                await self._run_ydotool("mousemove", "--absolute", "-x", str(x2), "-y", str(y2))
                await self._run_ydotool("click", up)
                return {"ok": True, "from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}, "button": button, "backend": "ydotool"}
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
            if self._ydotool_env() is not None:
                step = {"up": ("0", "-15"), "down": ("0", "15"), "left": ("-15", "0"), "right": ("15", "0")}[direction.lower()]
                for _ in range(clicks):
                    await self._run_ydotool("mousemove", "--wheel", "-x", step[0], "-y", step[1])
                return {"ok": True, "direction": direction, "clicks": clicks, "backend": "ydotool"}
            await self._run("xdotool", "click", "--repeat", str(clicks), button)
            return {"ok": True, "direction": direction, "clicks": clicks}

    async def key_type(self, text: str, delay_ms: int = 20) -> dict[str, Any]:
        async with self._lock:
            if self._niri_env() is not None:
                return await self._key_type_niri(text)
            await self._run("xdotool", "type", "--delay", str(delay_ms), text)
            return {"ok": True, "text_length": len(text), "delay_ms": delay_ms}

    async def _key_type_niri(self, text: str) -> dict[str, Any]:
        """Type arbitrary text into the focused Wayland window. Pure ASCII is
        sent directly with wtype; anything with special characters (@, ñ, €, …)
        goes through the clipboard, which is fully keymap-independent and the
        only reliable way to inject those characters under niri."""
        if text and all(0x20 <= ord(c) <= 0x7E for c in text) and "\n" not in text:
            await self._run_wayland("wtype", text)
            return {"ok": True, "text_length": len(text), "method": "wtype"}
        # Special characters: copy to the Wayland clipboard and paste.
        await self._wl_copy(text)
        app_id = await self._niri_focused_app_id()
        paste = "ctrl+shift+v" if app_id in self._TERMINAL_APP_IDS else "ctrl+v"
        argv = self._wtype_modifier_args(paste)
        await self._run_wayland("wtype", *argv)
        return {"ok": True, "text_length": len(text), "method": "clipboard-paste", "paste": paste}

    async def key_press(self, keys: str) -> dict[str, Any]:
        async with self._lock:
            niri_result = await self._maybe_handle_niri_hotkey(keys)
            if niri_result is not None:
                return niri_result
            if self._niri_env() is not None:
                argv = self._wtype_modifier_args(keys)
                if argv is not None:
                    await self._run_wayland("wtype", *argv)
                    return {"ok": True, "keys": keys, "handled_by": "wtype"}
            await self._run("xdotool", "key", keys)
            return {"ok": True, "keys": keys}

    async def clipboard_get(self) -> dict[str, Any]:
        async with self._lock:
            if self._niri_env() is not None:
                # Force a text type: the clipboard may hold an image (e.g. after
                # a screenshot), and an unfiltered wl-paste would return raw
                # binary. If there is no text offer, report empty.
                try:
                    text = await self._run_wayland(
                        "wl-paste", "--no-newline", "--type", "text/plain"
                    )
                except RuntimeError:
                    try:
                        text = await self._run_wayland("wl-paste", "--no-newline", "--type", "text")
                    except RuntimeError:
                        return {"text": "", "note": "clipboard holds no text (e.g. an image)"}
                return {"text": text}
            result = await self._run("xclip", "-o", "-selection", "clipboard")
            return {"text": result.stdout_data}

    async def clipboard_set(self, text: str) -> dict[str, Any]:
        async with self._lock:
            if self._niri_env() is not None:
                await self._wl_copy(text)
                return {"ok": True, "text_length": len(text)}
            process = await asyncio.create_subprocess_exec(
                "xclip",
                "-i",
                "-selection",
                "clipboard",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "DISPLAY": self._resolve_display()},
            )
            _, stderr = await process.communicate(text.encode())
            if process.returncode != 0:
                raise RuntimeError(stderr.decode(errors="ignore"))
            return {"ok": True, "text_length": len(text)}

    async def window_list(self) -> dict[str, Any]:
        async with self._lock:
            return {"windows": await self._window_list_unlocked()}

    async def _window_list_unlocked(self) -> list[dict[str, Any]]:
        if self._niri_env() is not None:
            return await self._niri_window_list()
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
        return windows

    async def _niri_window_list(self) -> list[dict[str, Any]]:
        try:
            out = await self._run_wayland("niri", "msg", "--json", "windows")
            import json as _json

            data = _json.loads(out)
        except (RuntimeError, ValueError):
            return []
        windows = []
        for w in data if isinstance(data, list) else []:
            windows.append(
                {
                    "id": str(w.get("id")),
                    "title": w.get("title") or "",
                    "app_id": w.get("app_id") or "",
                    "pid": w.get("pid"),
                    "workspace_id": w.get("workspace_id"),
                    "is_focused": w.get("is_focused", False),
                }
            )
        return windows

    async def _find_window_unlocked(self, query: str) -> dict[str, Any]:
        windows = await self._window_list_unlocked()
        lowered = query.lower()
        for window in windows:
            wid = str(window.get("id", "")).lower()
            if wid == lowered:
                return window
            if query.startswith("0x") and wid == lowered:
                return window
            if lowered in window.get("title", "").lower():
                return window
            if lowered in window.get("app_id", "").lower():
                return window
        raise RuntimeError(f"No window matched query: {query}")

    async def window_focus(self, query: str) -> dict[str, Any]:
        async with self._lock:
            window = await self._find_window_unlocked(query)
            if self._niri_env() is not None:
                await self._run_wayland("niri", "msg", "action", "focus-window", "--id", str(window["id"]))
                return {"ok": True, "query": query, "window": window}
            await self._run("wmctrl", "-ia", window["id"])
            return {"ok": True, "query": query, "window": window}

    async def window_maximize(self, query: str) -> dict[str, Any]:
        async with self._lock:
            window = await self._find_window_unlocked(query)
            if self._niri_env() is not None:
                await self._run_wayland("niri", "msg", "action", "focus-window", "--id", str(window["id"]))
                await self._run_wayland("niri", "msg", "action", "maximize-column")
                return {"ok": True, "query": query, "window": window, "state": "maximized"}
            await self._run("wmctrl", "-ia", window["id"])
            await self._run("wmctrl", "-i", "-r", window["id"], "-b", "add,maximized_vert,maximized_horz")
            return {"ok": True, "query": query, "window": window, "state": "maximized"}

    async def window_minimize(self, query: str) -> dict[str, Any]:
        async with self._lock:
            window = await self._find_window_unlocked(query)
            if self._niri_env() is not None:
                # niri is a scrolling WM with no minimize; the closest is to make
                # the window floating and move it off the active workspace.
                await self._run_wayland("niri", "msg", "action", "focus-window", "--id", str(window["id"]))
                await self._run_wayland("niri", "msg", "action", "move-window-to-workspace-down")
                return {"ok": True, "query": query, "window": window, "state": "moved-to-workspace-down"}
            await self._run("wmctrl", "-i", "-r", window["id"], "-b", "add,hidden")
            return {"ok": True, "query": query, "window": window, "state": "minimized"}

    async def window_restore(self, query: str) -> dict[str, Any]:
        async with self._lock:
            window = await self._find_window_unlocked(query)
            if self._niri_env() is not None:
                await self._run_wayland("niri", "msg", "action", "focus-window", "--id", str(window["id"]))
                await self._run_wayland("niri", "msg", "action", "switch-preset-column-width")
                return {"ok": True, "query": query, "window": window, "state": "restored"}
            await self._run("wmctrl", "-i", "-r", window["id"], "-b", "remove,maximized_vert,maximized_horz")
            await self._run("wmctrl", "-i", "-r", window["id"], "-b", "remove,hidden", check=False)
            await self._run("wmctrl", "-ia", window["id"], check=False)
            return {"ok": True, "query": query, "window": window, "state": "restored"}

    async def app_launch(self, command: str) -> dict[str, Any]:
        async with self._lock:
            launch_command = self._wrap_command_for_desktop_session(command)
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-lc",
                launch_command,
                env={**os.environ, "DISPLAY": self._resolve_display()},
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            return {"ok": True, "command": command, "launch_command": launch_command, "pid": proc.pid}

    def _desktop_entry_dirs(self) -> list[Path]:
        dirs = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local/share/applications",
        ]
        return [directory for directory in dirs if directory.exists()]

    def _parse_desktop_entry(self, path: Path) -> dict[str, Any] | None:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except Exception:
            return None
        if "Desktop Entry" not in parser:
            return None
        entry = parser["Desktop Entry"]
        if entry.get("Type") != "Application":
            return None
        if entry.get("NoDisplay", "").lower() == "true":
            return None
        name = (entry.get("Name") or "").strip()
        exec_value = (entry.get("Exec") or "").strip()
        if not name or not exec_value:
            return None
        command = self._sanitize_exec(exec_value)
        if not command:
            return None
        return {
            "name": name,
            "command": command,
            "desktop_file": str(path),
            "icon": (entry.get("Icon") or "").strip() or None,
            "source": "desktop",
        }

    def _sanitize_exec(self, exec_value: str) -> str:
        tokens = []
        for token in shlex.split(exec_value):
            if token.startswith("%"):
                continue
            tokens.append(token)
        return " ".join(tokens).strip()

    def _desktop_session_flavor(self) -> str:
        return os.getenv("DESKTOP_SESSION_FLAVOR", "xfce")

    def _wrap_command_for_desktop_session(self, command: str) -> str:
        if self._desktop_session_flavor() not in {"niri-nested", "noctalia-niri"}:
            return command
        try:
            tokens = shlex.split(command)
        except ValueError:
            return command
        if not tokens:
            return command
        wrapped = ["/opt/appliance/niri-run-app.sh", tokens[0], *tokens[1:]]
        return shlex.join(wrapped)

    def _discover_desktop_apps(self) -> list[dict[str, Any]]:
        apps: dict[str, dict[str, Any]] = {}
        for directory in self._desktop_entry_dirs():
            for desktop_file in sorted(directory.glob("*.desktop")):
                entry = self._parse_desktop_entry(desktop_file)
                if not entry:
                    continue
                key = (entry["name"].lower(), entry["command"].lower())
                apps.setdefault(key, entry)
        return sorted(apps.values(), key=lambda item: item["name"].lower())

    def _discover_path_apps(self) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        path_dirs = [Path(part) for part in os.getenv("PATH", "").split(os.pathsep) if part]
        for directory in path_dirs:
            if not directory.exists() or not directory.is_dir():
                continue
            try:
                entries = sorted(directory.iterdir())
            except Exception:
                continue
            for entry in entries:
                try:
                    if not entry.is_file() or not os.access(entry, os.X_OK):
                        continue
                except Exception:
                    continue
                name = entry.name
                seen.setdefault(
                    name.lower(),
                    {
                        "name": name,
                        "command": name,
                        "path": str(entry),
                        "source": "path",
                    },
                )
        return sorted(seen.values(), key=lambda item: item["name"].lower())

    def _normalize_apps(self, apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for app in apps:
            key = app["name"].lower()
            existing = merged.get(key)
            if existing is None or existing.get("source") == "path":
                merged[key] = app
        return sorted(merged.values(), key=lambda item: item["name"].lower())

    async def app_list(self) -> dict[str, Any]:
        async with self._lock:
            desktop_apps = self._discover_desktop_apps()
            path_apps = self._discover_path_apps()
            apps = self._normalize_apps(desktop_apps + path_apps)
            return {
                "apps": apps,
                "counts": {
                    "desktop_entries": len(desktop_apps),
                    "path_binaries": len(path_apps),
                    "merged": len(apps),
                },
            }

    async def app_open(self, name: str) -> dict[str, Any]:
        async with self._lock:
            discovered = self._normalize_apps(self._discover_desktop_apps() + self._discover_path_apps())
            lowered = name.lower()
            match = next((app for app in discovered if lowered == app["name"].lower()), None)
            if match is None:
                match = next((app for app in discovered if lowered in app["name"].lower()), None)
            if match is None:
                binary = shutil.which(name)
                if binary:
                    match = {"name": name, "command": shlex.quote(binary), "path": binary, "source": "path-direct"}
            if match is None:
                raise RuntimeError(f"Installed app not found: {name}")

            launch_command = self._wrap_command_for_desktop_session(match["command"])
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-lc",
                launch_command,
                env={**os.environ, "DISPLAY": self._resolve_display()},
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            return {"ok": True, "app": match, "launch_command": launch_command, "pid": proc.pid}

    async def app_status(self, query: str) -> dict[str, Any]:
        windows = await self.window_list()
        matching = [w for w in windows["windows"] if query.lower() in w["title"].lower()]
        return {"query": query, "running": bool(matching), "windows": matching}

    async def _run_json(self, *args: str) -> dict[str, Any]:
        result = await self._run(*args)
        output = result.stdout_data.strip()
        if not output:
            return {"ok": True}
        try:
            return json.loads(output)
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON output from {' '.join(args)}: {output}") from exc

    async def thunar_open(self, path: str | None = None) -> dict[str, Any]:
        command = "thunar"
        if path:
            command = f"thunar {shlex.quote(path)}"
        launched = await self.app_launch(command)
        await asyncio.sleep(1.2)
        await self.window_focus("Thunar")
        return {"ok": True, "command": command, "launched": launched}

    async def thunar_go(self, path: str) -> dict[str, Any]:
        target = str(Path(path))
        status = await self.app_status("Thunar")
        if not status["running"]:
            await self.thunar_open(target)
            await asyncio.sleep(1.0)
        else:
            await self.window_focus("Thunar")
            await self.key_press("ctrl+l")
            await asyncio.sleep(0.2)
            await self.key_type(target)
            await asyncio.sleep(0.1)
            await self.key_press("Return")
        await asyncio.sleep(0.5)
        return {"ok": True, "path": target}

    async def thunar_action(self, action: str) -> dict[str, Any]:
        status = await self.app_status("Thunar")
        if not status["running"]:
            await self.thunar_open()
            await asyncio.sleep(1.0)
        else:
            await self.window_focus("Thunar")
        return await self._run_json("/usr/bin/python3", "/opt/appliance/scripts/thunar_dogtail.py", "action", action)

    async def thunar_tree(self, max_depth: int = 5, max_children: int = 40) -> dict[str, Any]:
        status = await self.app_status("Thunar")
        if not status["running"]:
            await self.thunar_open()
            await asyncio.sleep(1.0)
        else:
            await self.window_focus("Thunar")
        return await self._run_json(
            "/usr/bin/python3",
            "/opt/appliance/scripts/thunar_dogtail.py",
            "tree",
            "--max-depth",
            str(max_depth),
            "--max-children",
            str(max_children),
        )

    async def firefox_maximize(self) -> dict[str, Any]:
        return await self.window_maximize("Firefox")

    async def chrome_maximize(self) -> dict[str, Any]:
        return await self.window_maximize("Chrome")

    async def thunar_maximize(self) -> dict[str, Any]:
        return await self.window_maximize("Thunar")

    async def niri_start(self) -> dict[str, Any]:
        async with self._lock:
            proc = await asyncio.create_subprocess_exec(
                "/opt/appliance/niri-launcher.sh",
                env={**os.environ, "DISPLAY": self._resolve_display()},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "ok": proc.returncode == 0,
                "desktop_session_flavor": os.getenv("DESKTOP_SESSION_FLAVOR", "xfce"),
                "stdout": stdout.decode(errors="ignore"),
                "stderr": stderr.decode(errors="ignore"),
            }

    async def niri_status(self) -> dict[str, Any]:
        result = await self._run("sh", "-lc", "pgrep -a -x niri || true")
        status = await self.app_status("niri")
        return {
            "running": bool(result.stdout_data.strip()),
            "processes": [line for line in result.stdout_data.splitlines() if line.strip()],
            "windows": status["windows"],
            "desktop_session_flavor": os.getenv("DESKTOP_SESSION_FLAVOR", "xfce"),
        }

    async def noctalia_start(self) -> dict[str, Any]:
        async with self._lock:
            proc = await asyncio.create_subprocess_exec(
                "/opt/appliance/noctalia-launcher.sh",
                env={**os.environ, "DISPLAY": self._resolve_display()},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "ok": proc.returncode == 0,
                "desktop_session_flavor": os.getenv("DESKTOP_SESSION_FLAVOR", "xfce"),
                "stdout": stdout.decode(errors="ignore"),
                "stderr": stderr.decode(errors="ignore"),
            }

    async def noctalia_status(self) -> dict[str, Any]:
        result = await self._run("sh", "-lc", "pgrep -a -x noctalia || true")
        return {
            "running": bool(result.stdout_data.strip()),
            "processes": [line for line in result.stdout_data.splitlines() if line.strip()],
            "desktop_session_flavor": os.getenv("DESKTOP_SESSION_FLAVOR", "xfce"),
            "wayland_display": os.getenv("WAYLAND_DISPLAY", "wayland-1"),
        }


desktop_service = DesktopService()
