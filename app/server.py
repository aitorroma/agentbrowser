from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from app.browser_service import browser_service
from app.cua_service import cua_service
from app.desktop_service import desktop_service


class EvalRequest(BaseModel):
    js: str


class ScreenshotRequest(BaseModel):
    path: str | None = None
    full_page: bool = True


class DesktopShotRequest(BaseModel):
    path: str | None = None
    region: str | None = None


class MouseMoveRequest(BaseModel):
    x: int
    y: int


class MouseClickRequest(BaseModel):
    x: int
    y: int
    button: int = 1


class MouseDragRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    button: int = 1


class MouseScrollRequest(BaseModel):
    direction: str = "down"
    clicks: int = 3


class KeyTypeRequest(BaseModel):
    text: str
    delay_ms: int = 20


class KeyPressRequest(BaseModel):
    keys: str


class ClipboardSetRequest(BaseModel):
    text: str


class AppLaunchRequest(BaseModel):
    command: str


class AppOpenRequest(BaseModel):
    name: str


class ThunarOpenRequest(BaseModel):
    path: str | None = None


class ThunarGoRequest(BaseModel):
    path: str


class WindowQueryRequest(BaseModel):
    query: str


class NiriActionRequest(BaseModel):
    action: str
    args: list[str] | None = None


class NiriMsgRequest(BaseModel):
    args: list[str]
    json: bool = True


class NiriSpawnRequest(BaseModel):
    command: str
    args: list[str] | None = None


class NiriTypeInWindowRequest(BaseModel):
    window_query: str
    text: str = ""
    focus_only: bool = False


class NiriClickInWindowRequest(BaseModel):
    window_query: str
    x: int
    y: int
    button: int = 1


class WevMonitorRequest(BaseModel):
    duration_sec: float = 3.0


class OpenAppRequest(BaseModel):
    app: str


class WorkspaceRequest(BaseModel):
    index: int


class SecureLoginRequest(BaseModel):
    site: str
    account: str | None = None
    username: str | None = None
    url: str | None = None
    submit: bool = True
    auto_totp: bool = True


class BitwardenConfigRequest(BaseModel):
    server_url: str
    username: str
    password: str


class CuaCallRequest(BaseModel):
    tool: str
    input: dict[str, Any] | None = None


def bw_auth_page(message: str = "", error: bool = False, status: dict[str, Any] | None = None) -> str:
    status = status or {}
    status_html = ""
    if status:
        configured = "sí" if status.get("configured") else "no"
        server = status.get("server_url") or "—"
        user = status.get("username_hint") or "—"
        persisted = "sí" if status.get("persisted") else "no"
        status_html = f"""
        <div class="status-card">
          <div><span>Configurado</span><strong>{configured}</strong></div>
          <div><span>Persistido</span><strong>{persisted}</strong></div>
          <div><span>Servidor</span><strong>{server}</strong></div>
          <div><span>Usuario</span><strong>{user}</strong></div>
        </div>
        """
    flash = f'<div class="flash {"error" if error else "ok"}">{message}</div>' if message else ""
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Iniciar sesión | Bitwarden</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet" />
  <style>
    :root {{ --bw-blue:#175ddc; --bw-blue-hover:#1252be; }}
    * {{ box-sizing:border-box; }}
    body {{
      font-family:'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background:#f7f8fa; color:#1b2029; margin:0; min-height:100vh;
      display:flex; flex-direction:column; align-items:center;
    }}
    .brand {{ margin:56px 0 28px; display:flex; align-items:center; gap:12px; }}
    .brand svg {{ display:block; }}
    .brand .word {{ font-size:30px; font-weight:700; letter-spacing:-.5px; color:#175ddc; }}
    .card {{
      width:min(92vw,420px); background:#fff; border:1px solid #e3e6ec; border-radius:8px;
      padding:32px; box-shadow:0 1px 3px rgba(0,0,0,.08), 0 8px 24px rgba(23,93,220,.06);
    }}
    h1 {{ margin:0 0 6px; font-size:20px; font-weight:700; }}
    .sub {{ margin:0 0 20px; font-size:13px; color:#6b7280; line-height:1.5; }}
    label {{ display:block; margin:14px 0 5px; font-weight:700; font-size:13px; color:#28303f; }}
    input {{
      width:100%; padding:11px 13px; font-size:14px; font-family:inherit;
      border:1px solid #ced4dc; border-radius:6px; background:#fff; color:#1b2029; transition:border-color .15s, box-shadow .15s;
    }}
    input:focus {{ outline:none; border-color:var(--bw-blue); box-shadow:0 0 0 3px rgba(23,93,220,.15); }}
    button {{
      margin-top:22px; width:100%; padding:12px 14px; font-size:15px; font-weight:700; font-family:inherit;
      border:0; border-radius:6px; background:var(--bw-blue); color:#fff; cursor:pointer; transition:background .15s;
      display:flex; align-items:center; justify-content:center; gap:8px;
    }}
    button:hover {{ background:var(--bw-blue-hover); }}
    .flash {{ margin:0 0 18px; padding:11px 13px; border-radius:6px; font-size:13px; display:flex; gap:8px; align-items:flex-start; }}
    .flash.ok {{ background:#e9f6ee; color:#1c7e3f; border:1px solid #b7e2c6; }}
    .flash.error {{ background:#fdecec; color:#c12f2f; border:1px solid #f5c2c2; }}
    .status-card {{ margin:0 0 18px; border:1px solid #e3e6ec; border-radius:6px; overflow:hidden; }}
    .status-card div {{ display:flex; justify-content:space-between; padding:9px 13px; font-size:13px; border-top:1px solid #eef0f4; }}
    .status-card div:first-child {{ border-top:0; }}
    .status-card span {{ color:#6b7280; }}
    .status-card strong {{ color:#28303f; }}
    .hint {{ font-size:12px; color:#9aa1ad; margin-top:16px; text-align:center; line-height:1.5; }}
    .footer {{ margin:24px 0 40px; font-size:12px; color:#9aa1ad; }}
  </style>
</head>
<body>
  <div class="brand">
    <svg width="42" height="42" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#175ddc" d="M12 1.5 3.4 4.2v7.1c0 5.2 3.9 9.9 8.6 11.2 4.7-1.3 8.6-6 8.6-11.2V4.2L12 1.5z"/>
      <path fill="#fff" d="M12 4.1v15.4c-3.3-1.2-5.9-4.8-5.9-8.4V5.9L12 4.1zm1.6 3.2v2.1h2.7v1.8h-2.7v3.3c0 .6.3.9.9.9h1.8v1.8h-2.1c-1.5 0-2.4-.9-2.4-2.4V7.3h1.8z"/>
    </svg>
    <span class="word">bitwarden</span>
  </div>
  <div class="card">
    <h1>Inicia sesión en tu bóveda</h1>
    <p class="sub">La sesión se guarda en el servicio y se usa para <code>secure_login</code> sin exponer credenciales al agente.</p>
    {flash}
    {status_html}
    <form method="post" action="/auth/bw">
      <label for="server_url">URL del servidor</label>
      <input id="server_url" name="server_url" type="url" placeholder="https://vault.tudominio.com" required />
      <label for="username">Dirección de correo</label>
      <input id="username" name="username" type="text" autocomplete="username" placeholder="nombre@ejemplo.com" required />
      <label for="password">Contraseña maestra</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required />
      <button type="submit">Iniciar sesión</button>
      <div class="hint">Después podrás usar <code>/auth/login</code> o la tool <code>secure_login</code> sin volver a introducir las credenciales.</div>
    </form>
  </div>
  <div class="footer">AgentBrowser · sesión Bitwarden gestionada por el servicio</div>
</body>
</html>"""


mcp = FastMCP("browser-appliance", streamable_http_path="/")


@mcp.tool()
async def goto(url: str) -> dict[str, Any]:
    return await browser_service.goto(url)


@mcp.tool()
async def get_markdown(url: str) -> dict[str, Any]:
    return await browser_service.get_markdown(url)


@mcp.tool()
async def screenshot() -> dict[str, Any]:
    return await browser_service.screenshot()


@mcp.tool()
async def fill(selector: str, text: str) -> dict[str, Any]:
    return await browser_service.fill(selector, text)


@mcp.tool()
async def click(selector: str) -> dict[str, Any]:
    return await browser_service.click(selector)


@mcp.tool()
async def eval(js: str) -> dict[str, Any]:
    return await browser_service.evaluate(js)


@mcp.tool()
async def screen_shot(path: str | None = None, region: str | None = None) -> dict[str, Any]:
    return await desktop_service.screen_shot(path=path, region=region)


@mcp.tool()
async def mouse_move(x: int, y: int) -> dict[str, Any]:
    return await desktop_service.mouse_move(x, y)


@mcp.tool()
async def mouse_click(x: int, y: int, button: int = 1) -> dict[str, Any]:
    return await desktop_service.mouse_click(x, y, button)


@mcp.tool()
async def mouse_double_click(x: int, y: int, button: int = 1) -> dict[str, Any]:
    return await desktop_service.mouse_double_click(x, y, button)


@mcp.tool()
async def mouse_drag(x1: int, y1: int, x2: int, y2: int, button: int = 1) -> dict[str, Any]:
    return await desktop_service.mouse_drag(x1, y1, x2, y2, button)


@mcp.tool()
async def mouse_scroll(direction: str = "down", clicks: int = 3) -> dict[str, Any]:
    return await desktop_service.mouse_scroll(direction, clicks)


@mcp.tool()
async def key_type(text: str, delay_ms: int = 20) -> dict[str, Any]:
    return await desktop_service.key_type(text, delay_ms)


@mcp.tool()
async def key_press(keys: str) -> dict[str, Any]:
    return await desktop_service.key_press(keys)


@mcp.tool()
async def clipboard_get() -> dict[str, Any]:
    return await desktop_service.clipboard_get()


@mcp.tool()
async def clipboard_set(text: str) -> dict[str, Any]:
    return await desktop_service.clipboard_set(text)


@mcp.tool()
async def window_list() -> dict[str, Any]:
    return await desktop_service.window_list()


@mcp.tool()
async def window_focus(query: str) -> dict[str, Any]:
    return await desktop_service.window_focus(query)


@mcp.tool()
async def window_maximize(query: str) -> dict[str, Any]:
    return await desktop_service.window_maximize(query)


@mcp.tool()
async def window_minimize(query: str) -> dict[str, Any]:
    return await desktop_service.window_minimize(query)


@mcp.tool()
async def window_restore(query: str) -> dict[str, Any]:
    return await desktop_service.window_restore(query)


@mcp.tool()
async def app_list() -> dict[str, Any]:
    return await desktop_service.app_list()


@mcp.tool()
async def app_launch(command: str) -> dict[str, Any]:
    return await desktop_service.app_launch(command)


@mcp.tool()
async def app_open(name: str) -> dict[str, Any]:
    return await desktop_service.app_open(name)


@mcp.tool()
async def app_status(query: str) -> dict[str, Any]:
    return await desktop_service.app_status(query)


@mcp.tool()
async def thunar_open(path: str | None = None) -> dict[str, Any]:
    return await desktop_service.thunar_open(path)


@mcp.tool()
async def thunar_go(path: str) -> dict[str, Any]:
    return await desktop_service.thunar_go(path)


@mcp.tool()
async def thunar_action(action: str) -> dict[str, Any]:
    return await desktop_service.thunar_action(action)


@mcp.tool()
async def thunar_tree(max_depth: int = 5, max_children: int = 40) -> dict[str, Any]:
    return await desktop_service.thunar_tree(max_depth=max_depth, max_children=max_children)


@mcp.tool()
async def firefox_maximize() -> dict[str, Any]:
    return await desktop_service.firefox_maximize()


@mcp.tool()
async def chrome_maximize() -> dict[str, Any]:
    return await desktop_service.chrome_maximize()


@mcp.tool()
async def thunar_maximize() -> dict[str, Any]:
    return await desktop_service.thunar_maximize()


@mcp.tool()
async def niri_start() -> dict[str, Any]:
    return await desktop_service.niri_start()


@mcp.tool()
async def niri_status() -> dict[str, Any]:
    return await desktop_service.niri_status()


@mcp.tool()
async def noctalia_start() -> dict[str, Any]:
    return await desktop_service.noctalia_start()


@mcp.tool()
async def noctalia_status() -> dict[str, Any]:
    return await desktop_service.noctalia_status()


@mcp.tool()
async def niri_action(action: str, args: list[str] | None = None) -> dict[str, Any]:
    """Perform any niri compositor action (full `niri msg action` set): focus or
    move windows/columns, switch workspaces and monitors, fullscreen, floating,
    overview, column widths, screenshots, spawn, etc."""
    return await desktop_service.niri_action(action, args)


@mcp.tool()
async def niri_msg(args: list[str], json: bool = True) -> dict[str, Any]:
    """Run an arbitrary `niri msg` subcommand (windows, workspaces, outputs,
    focused-window, action, output, ...) and return its JSON output."""
    return await desktop_service.niri_msg(args, json)


@mcp.tool()
async def niri_windows() -> dict[str, Any]:
    return await desktop_service.niri_windows()


@mcp.tool()
async def niri_workspaces() -> dict[str, Any]:
    return await desktop_service.niri_workspaces()


@mcp.tool()
async def niri_outputs() -> dict[str, Any]:
    return await desktop_service.niri_outputs()


@mcp.tool()
async def niri_focused_window() -> dict[str, Any]:
    return await desktop_service.niri_focused_window()


@mcp.tool()
async def niri_type_in_window(window_query: str, text: str = "", focus_only: bool = False) -> dict[str, Any]:
    """Focus a Wayland window and optionally type text into it.  Handles
    the focus-then-type sequence atomically so that wtype events land in
    the correct window (especially important for Blender and other native
    Wayland apps)."""
    return await desktop_service.niri_type_in_window(window_query, text, focus_only)


@mcp.tool()
async def niri_click_in_window(window_query: str, x: int, y: int, button: int = 1) -> dict[str, Any]:
    """Focus a Wayland window and click at (x, y) using the virtual pointer
    protocol.  Works on native Wayland apps (Blender, Foot, etc.) without
    /dev/uinput."""
    return await desktop_service.niri_click_in_window(window_query, x, y, button)


@mcp.tool()
async def wev_monitor(duration_sec: float = 3.0) -> dict[str, Any]:
    """Monitor Wayland keyboard events for `duration_sec` seconds using wev.
    Returns the list of key events that arrived at the focused client.
    Useful for debugging keyboard input issues with Wayland apps."""
    return await desktop_service.wev_monitor(duration_sec)


@mcp.tool()
async def niri_spawn(command: str, args: list[str] | None = None) -> dict[str, Any]:
    """Spawn any command as a child of the niri compositor (correct Wayland
    session). Use this to launch arbitrary desktop apps under niri."""
    return await desktop_service.niri_spawn(command, args)


@mcp.tool()
async def open_app(app: str) -> dict[str, Any]:
    """Launch a known desktop app by name: launcher/fuzzel, terminal/foot,
    firefox, thunar/files, chromium."""
    return await desktop_service.open_app(app)


@mcp.tool()
async def open_launcher() -> dict[str, Any]:
    """Open the fuzzel application launcher (same as Super+D)."""
    return await desktop_service.open_launcher()


@mcp.tool()
async def open_terminal() -> dict[str, Any]:
    """Open a foot terminal (same as Super+T)."""
    return await desktop_service.open_terminal()


@mcp.tool()
async def open_firefox() -> dict[str, Any]:
    """Open Firefox (same as Super+B)."""
    return await desktop_service.open_firefox()


@mcp.tool()
async def open_files() -> dict[str, Any]:
    """Open the default file manager (Dolphin)."""
    return await desktop_service.open_files()


@mcp.tool()
async def open_dolphin() -> dict[str, Any]:
    """Open the Dolphin file manager."""
    return await desktop_service.open_dolphin()


@mcp.tool()
async def workspace_goto(reference: str) -> dict[str, Any]:
    """Switch to a workspace by 1-based index or by name."""
    return await desktop_service.workspace_goto(reference)


@mcp.tool()
async def workspace_next() -> dict[str, Any]:
    """Switch to the next workspace (down)."""
    return await desktop_service.workspace_next()


@mcp.tool()
async def workspace_prev() -> dict[str, Any]:
    """Switch to the previous workspace (up)."""
    return await desktop_service.workspace_prev()


@mcp.tool()
async def move_window_to_workspace(index: int) -> dict[str, Any]:
    """Move the focused window to the workspace with the given 1-based index."""
    return await desktop_service.move_window_to_workspace(index)


@mcp.tool()
async def workspace_set_name(name: str) -> dict[str, Any]:
    """Name the focused workspace so it can be switched to by name."""
    return await desktop_service.workspace_set_name(name)


@mcp.tool()
async def screenshot_window(query: str | None = None) -> dict[str, Any]:
    """Screenshot a single window (focused, or matched by id/title/app_id)."""
    return await desktop_service.screen_shot_window(query)


@mcp.tool()
async def cua_status() -> dict[str, Any]:
    return await cua_service.status()


@mcp.tool()
async def cua_doctor() -> dict[str, Any]:
    return await cua_service.doctor()


@mcp.tool()
async def cua_list_tools() -> dict[str, Any]:
    return await cua_service.list_tools()


@mcp.tool()
async def cua_call(tool: str, input: dict[str, Any] | None = None) -> dict[str, Any]:
    return await cua_service.call(tool, input)


@mcp.tool()
async def cua_windows() -> dict[str, Any]:
    return await cua_service.windows()


@mcp.tool()
async def cua_apps() -> dict[str, Any]:
    return await cua_service.apps()


@mcp.tool()
async def cua_accessibility_tree() -> dict[str, Any]:
    return await cua_service.accessibility_tree()


@mcp.tool()
async def list_accounts(search: str | None = None) -> dict[str, Any]:
    return await browser_service.list_accounts(search=search)


@mcp.tool()
async def get_totp(site: str, account: str | None = None) -> dict[str, Any]:
    return await browser_service.get_totp(site=site, account=account)


@mcp.tool()
async def secure_login(
    site: str,
    account: str | None = None,
    username: str | None = None,
    url: str | None = None,
    submit: bool = True,
    auto_totp: bool = True,
) -> dict[str, Any]:
    return await browser_service.secure_login(
        site=site,
        account=account,
        username=username,
        url=url,
        submit=submit,
        auto_totp=auto_totp,
    )


@mcp.tool()
async def configure_bitwarden(server_url: str, username: str, password: str) -> dict[str, Any]:
    return await browser_service.configure_bitwarden(server_url, username, password)


@mcp.tool()
async def logout_bitwarden() -> dict[str, Any]:
    return await browser_service.logout_bitwarden()


@mcp.tool()
async def webauthn_enable(resident_key: bool = True, user_verification: bool = True) -> dict[str, Any]:
    """Attach a software (virtual) authenticator so the browser can register and
    use passkeys / WebAuthn. Restores previously persisted credentials."""
    return await browser_service.webauthn_enable(resident_key, user_verification)


@mcp.tool()
async def webauthn_status() -> dict[str, Any]:
    """Report whether the virtual authenticator is active and how many passkeys it holds."""
    return await browser_service.webauthn_status()


@mcp.tool()
async def webauthn_list_credentials() -> dict[str, Any]:
    """List passkey metadata (rpId, userHandle, signCount) — never private keys."""
    return await browser_service.webauthn_list_credentials()


@mcp.tool()
async def webauthn_save() -> dict[str, Any]:
    """Persist current passkeys to the profile so they survive a restart."""
    return await browser_service.webauthn_save()


@mcp.tool()
async def webauthn_disable() -> dict[str, Any]:
    """Detach the virtual authenticator."""
    return await browser_service.webauthn_disable()


@asynccontextmanager
async def lifespan(application: FastAPI):
    async with mcp.session_manager.run():
        yield


mcp_http_app = mcp.streamable_http_app()
app = FastAPI(title="browser-appliance", lifespan=lifespan)
app.mount("/mcp", mcp_http_app.routes[0].endpoint)


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return await browser_service.health()


@app.get("/auth/bw", response_class=HTMLResponse)
async def bitwarden_auth_page() -> str:
    return bw_auth_page(status=browser_service.bitwarden_status())


@app.post("/auth/bw", response_class=HTMLResponse)
async def bitwarden_auth_submit(
    server_url: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
) -> str:
    result = await browser_service.configure_bitwarden(server_url, username, password)
    return bw_auth_page(
        message="Bitwarden conectado correctamente." if result.get("ok") else f"Error: {result.get('reason', 'login_failed')}",
        error=not result.get("ok"),
        status=browser_service.bitwarden_status(),
    )


@app.get("/auth/bw/status")
async def bitwarden_auth_status() -> dict[str, Any]:
    return browser_service.bitwarden_status()


@app.post("/auth/bw/api")
async def bitwarden_auth_api(request: BitwardenConfigRequest) -> dict[str, Any]:
    return await browser_service.configure_bitwarden(request.server_url, request.username, request.password)


@app.post("/auth/bw/logout")
async def bitwarden_auth_logout() -> dict[str, Any]:
    return await browser_service.logout_bitwarden()


@app.post("/webauthn/enable")
async def webauthn_enable_http(
    resident_key: bool = Query(True),
    user_verification: bool = Query(True),
) -> dict[str, Any]:
    return await browser_service.webauthn_enable(resident_key, user_verification)


@app.get("/webauthn/status")
async def webauthn_status_http() -> dict[str, Any]:
    return await browser_service.webauthn_status()


@app.get("/webauthn/credentials")
async def webauthn_credentials_http() -> dict[str, Any]:
    return await browser_service.webauthn_list_credentials()


@app.post("/webauthn/save")
async def webauthn_save_http() -> dict[str, Any]:
    return await browser_service.webauthn_save()


@app.post("/webauthn/disable")
async def webauthn_disable_http() -> dict[str, Any]:
    return await browser_service.webauthn_disable()


@app.get("/markdown")
async def markdown(url: str = Query(...)) -> dict[str, Any]:
    return await browser_service.get_markdown(url)


@app.post("/screenshot")
async def screenshot_http(request: ScreenshotRequest) -> dict[str, Any]:
    return await browser_service.screenshot(path=request.path, full_page=request.full_page)


@app.post("/eval")
async def eval_http(request: EvalRequest) -> dict[str, Any]:
    return await browser_service.evaluate(request.js)


@app.post("/desktop/screenshot")
async def desktop_screenshot_http(request: DesktopShotRequest) -> dict[str, Any]:
    return await desktop_service.screen_shot(path=request.path, region=request.region)


@app.post("/desktop/mouse/move")
async def desktop_mouse_move_http(request: MouseMoveRequest) -> dict[str, Any]:
    return await desktop_service.mouse_move(request.x, request.y)


@app.post("/desktop/mouse/click")
async def desktop_mouse_click_http(request: MouseClickRequest) -> dict[str, Any]:
    return await desktop_service.mouse_click(request.x, request.y, request.button)


@app.post("/desktop/mouse/double-click")
async def desktop_mouse_double_click_http(request: MouseClickRequest) -> dict[str, Any]:
    return await desktop_service.mouse_double_click(request.x, request.y, request.button)


@app.post("/desktop/mouse/drag")
async def desktop_mouse_drag_http(request: MouseDragRequest) -> dict[str, Any]:
    return await desktop_service.mouse_drag(request.x1, request.y1, request.x2, request.y2, request.button)


@app.post("/desktop/mouse/scroll")
async def desktop_mouse_scroll_http(request: MouseScrollRequest) -> dict[str, Any]:
    return await desktop_service.mouse_scroll(request.direction, request.clicks)


@app.post("/desktop/keyboard/type")
async def desktop_key_type_http(request: KeyTypeRequest) -> dict[str, Any]:
    return await desktop_service.key_type(request.text, request.delay_ms)


@app.post("/desktop/keyboard/press")
async def desktop_key_press_http(request: KeyPressRequest) -> dict[str, Any]:
    return await desktop_service.key_press(request.keys)


@app.get("/desktop/clipboard")
async def desktop_clipboard_get_http() -> dict[str, Any]:
    return await desktop_service.clipboard_get()


@app.post("/desktop/clipboard")
async def desktop_clipboard_set_http(request: ClipboardSetRequest) -> dict[str, Any]:
    return await desktop_service.clipboard_set(request.text)


@app.get("/desktop/windows")
async def desktop_windows_http() -> dict[str, Any]:
    return await desktop_service.window_list()


@app.post("/desktop/windows/focus")
async def desktop_window_focus_http(query: str = Query(...)) -> dict[str, Any]:
    return await desktop_service.window_focus(query)


@app.post("/desktop/windows/maximize")
async def desktop_window_maximize_http(request: WindowQueryRequest) -> dict[str, Any]:
    return await desktop_service.window_maximize(request.query)


@app.post("/desktop/windows/minimize")
async def desktop_window_minimize_http(request: WindowQueryRequest) -> dict[str, Any]:
    return await desktop_service.window_minimize(request.query)


@app.post("/desktop/windows/restore")
async def desktop_window_restore_http(request: WindowQueryRequest) -> dict[str, Any]:
    return await desktop_service.window_restore(request.query)


@app.get("/desktop/apps")
async def desktop_apps_http() -> dict[str, Any]:
    return await desktop_service.app_list()


@app.post("/desktop/apps/launch")
async def desktop_app_launch_http(request: AppLaunchRequest) -> dict[str, Any]:
    return await desktop_service.app_launch(request.command)


@app.post("/desktop/apps/open")
async def desktop_app_open_http(request: AppOpenRequest) -> dict[str, Any]:
    return await desktop_service.app_open(request.name)


@app.get("/desktop/apps/status")
async def desktop_app_status_http(query: str = Query(...)) -> dict[str, Any]:
    return await desktop_service.app_status(query)


@app.post("/desktop/thunar/open")
async def desktop_thunar_open_http(request: ThunarOpenRequest) -> dict[str, Any]:
    return await desktop_service.thunar_open(path=request.path)


@app.post("/desktop/thunar/go")
async def desktop_thunar_go_http(request: ThunarGoRequest) -> dict[str, Any]:
    return await desktop_service.thunar_go(request.path)


@app.post("/desktop/thunar/action")
async def desktop_thunar_action_http(action: str = Query(...)) -> dict[str, Any]:
    return await desktop_service.thunar_action(action)


@app.get("/desktop/thunar/tree")
async def desktop_thunar_tree_http(
    max_depth: int = Query(5, ge=1, le=10),
    max_children: int = Query(40, ge=1, le=200),
) -> dict[str, Any]:
    return await desktop_service.thunar_tree(max_depth=max_depth, max_children=max_children)


@app.post("/desktop/firefox/maximize")
async def desktop_firefox_maximize_http() -> dict[str, Any]:
    return await desktop_service.firefox_maximize()


@app.post("/desktop/chrome/maximize")
async def desktop_chrome_maximize_http() -> dict[str, Any]:
    return await desktop_service.chrome_maximize()


@app.post("/desktop/thunar/maximize")
async def desktop_thunar_maximize_http() -> dict[str, Any]:
    return await desktop_service.thunar_maximize()


@app.post("/desktop/niri/start")
async def desktop_niri_start_http() -> dict[str, Any]:
    return await desktop_service.niri_start()


@app.get("/desktop/niri/status")
async def desktop_niri_status_http() -> dict[str, Any]:
    return await desktop_service.niri_status()


@app.post("/desktop/noctalia/start")
async def desktop_noctalia_start_http() -> dict[str, Any]:
    return await desktop_service.noctalia_start()


@app.get("/desktop/noctalia/status")
async def desktop_noctalia_status_http() -> dict[str, Any]:
    return await desktop_service.noctalia_status()


@app.post("/desktop/niri/action")
async def desktop_niri_action_http(request: NiriActionRequest) -> dict[str, Any]:
    return await desktop_service.niri_action(request.action, request.args)


@app.post("/desktop/niri/msg")
async def desktop_niri_msg_http(request: NiriMsgRequest) -> dict[str, Any]:
    return await desktop_service.niri_msg(request.args, request.json)


@app.get("/desktop/niri/windows")
async def desktop_niri_windows_http() -> dict[str, Any]:
    return await desktop_service.niri_windows()


@app.get("/desktop/niri/workspaces")
async def desktop_niri_workspaces_http() -> dict[str, Any]:
    return await desktop_service.niri_workspaces()


@app.get("/desktop/niri/outputs")
async def desktop_niri_outputs_http() -> dict[str, Any]:
    return await desktop_service.niri_outputs()


@app.get("/desktop/niri/focused-window")
async def desktop_niri_focused_window_http() -> dict[str, Any]:
    return await desktop_service.niri_focused_window()


@app.post("/desktop/niri/type-in-window")
async def desktop_niri_type_in_window_http(request: NiriTypeInWindowRequest) -> dict[str, Any]:
    return await desktop_service.niri_type_in_window(
        request.window_query, request.text, request.focus_only
    )


@app.post("/desktop/niri/click-in-window")
async def desktop_niri_click_in_window_http(request: NiriClickInWindowRequest) -> dict[str, Any]:
    return await desktop_service.niri_click_in_window(
        request.window_query, request.x, request.y, request.button
    )


@app.post("/desktop/wev/monitor")
async def desktop_wev_monitor_http(request: WevMonitorRequest) -> dict[str, Any]:
    return await desktop_service.wev_monitor(request.duration_sec)


@app.post("/desktop/niri/spawn")
async def desktop_niri_spawn_http(request: NiriSpawnRequest) -> dict[str, Any]:
    return await desktop_service.niri_spawn(request.command, request.args)


@app.post("/desktop/apps/open-named")
async def desktop_open_app_http(request: OpenAppRequest) -> dict[str, Any]:
    return await desktop_service.open_app(request.app)


@app.post("/desktop/apps/launcher")
async def desktop_open_launcher_http() -> dict[str, Any]:
    return await desktop_service.open_launcher()


@app.post("/desktop/apps/terminal")
async def desktop_open_terminal_http() -> dict[str, Any]:
    return await desktop_service.open_terminal()


@app.post("/desktop/apps/firefox")
async def desktop_open_firefox_http() -> dict[str, Any]:
    return await desktop_service.open_firefox()


@app.post("/desktop/apps/files")
async def desktop_open_files_http() -> dict[str, Any]:
    return await desktop_service.open_files()


@app.post("/desktop/apps/dolphin")
async def desktop_open_dolphin_http() -> dict[str, Any]:
    return await desktop_service.open_dolphin()


@app.post("/desktop/niri/workspace/goto")
async def desktop_workspace_goto_http(request: WorkspaceRequest) -> dict[str, Any]:
    return await desktop_service.workspace_goto(request.index)


@app.post("/desktop/niri/workspace/next")
async def desktop_workspace_next_http() -> dict[str, Any]:
    return await desktop_service.workspace_next()


@app.post("/desktop/niri/workspace/prev")
async def desktop_workspace_prev_http() -> dict[str, Any]:
    return await desktop_service.workspace_prev()


@app.post("/desktop/niri/workspace/move-window")
async def desktop_move_window_to_workspace_http(request: WorkspaceRequest) -> dict[str, Any]:
    return await desktop_service.move_window_to_workspace(request.index)


@app.post("/desktop/niri/workspace/set-name")
async def desktop_workspace_set_name_http(name: str = Query(...)) -> dict[str, Any]:
    return await desktop_service.workspace_set_name(name)


@app.post("/desktop/screenshot/window")
async def desktop_screenshot_window_http(query: str | None = Query(None)) -> dict[str, Any]:
    return await desktop_service.screen_shot_window(query)


@app.get("/desktop/cua/status")
async def desktop_cua_status_http() -> dict[str, Any]:
    return await cua_service.status()


@app.get("/desktop/cua/doctor")
async def desktop_cua_doctor_http() -> dict[str, Any]:
    return await cua_service.doctor()


@app.get("/desktop/cua/tools")
async def desktop_cua_tools_http() -> dict[str, Any]:
    return await cua_service.list_tools()


@app.get("/desktop/cua/describe")
async def desktop_cua_describe_http(tool: str = Query(...)) -> dict[str, Any]:
    return await cua_service.describe(tool)


@app.post("/desktop/cua/call")
async def desktop_cua_call_http(request: CuaCallRequest) -> dict[str, Any]:
    return await cua_service.call(request.tool, request.input)


@app.get("/desktop/cua/windows")
async def desktop_cua_windows_http() -> dict[str, Any]:
    return await cua_service.windows()


@app.get("/desktop/cua/apps")
async def desktop_cua_apps_http() -> dict[str, Any]:
    return await cua_service.apps()


@app.get("/desktop/cua/accessibility-tree")
async def desktop_cua_accessibility_tree_http() -> dict[str, Any]:
    return await cua_service.accessibility_tree()


@app.get("/auth/accounts")
async def list_accounts_http(search: str | None = Query(None)) -> dict[str, Any]:
    return await browser_service.list_accounts(search=search)


@app.get("/auth/totp")
async def get_totp_http(site: str = Query(...), account: str | None = Query(None)) -> dict[str, Any]:
    return await browser_service.get_totp(site=site, account=account)


@app.post("/auth/login")
async def secure_login_http(request: SecureLoginRequest) -> dict[str, Any]:
    return await browser_service.secure_login(
        site=request.site,
        account=request.account,
        username=request.username,
        url=request.url,
        submit=request.submit,
        auto_totp=request.auto_totp,
    )
