from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from app.browser_service import browser_service
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
          <div><strong>Configurado:</strong> {configured}</div>
          <div><strong>Persistido:</strong> {persisted}</div>
          <div><strong>Server:</strong> {server}</div>
          <div><strong>Usuario:</strong> {user}</div>
        </div>
        """
    flash = f'<div class="flash {"error" if error else "ok"}">{message}</div>' if message else ""
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Bitwarden Login</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; }}
    .wrap {{ max-width: 560px; margin: 48px auto; padding: 24px; }}
    .card {{ background:#111827; border:1px solid #334155; border-radius:16px; padding:24px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }}
    h1 {{ margin-top:0; font-size: 28px; }}
    p {{ color:#94a3b8; }}
    label {{ display:block; margin:16px 0 6px; font-weight:600; }}
    input {{ width:100%; box-sizing:border-box; padding:12px 14px; border-radius:10px; border:1px solid #475569; background:#020617; color:#e2e8f0; }}
    button {{ margin-top:20px; width:100%; padding:12px 14px; border:0; border-radius:10px; background:#2563eb; color:white; font-weight:700; cursor:pointer; }}
    .flash {{ margin:16px 0; padding:12px 14px; border-radius:10px; }}
    .flash.ok {{ background:#052e16; color:#bbf7d0; border:1px solid #166534; }}
    .flash.error {{ background:#450a0a; color:#fecaca; border:1px solid #991b1b; }}
    .status-card {{ margin:16px 0; padding:12px 14px; border-radius:10px; background:#0b1220; border:1px solid #334155; color:#cbd5e1; }}
    .hint {{ font-size:12px; color:#94a3b8; margin-top:8px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Conectar Bitwarden</h1>
      <p>La API guardará la sesión en memoria dentro del servicio y la usará para `secure_login` sin exponer credenciales al agente.</p>
      {flash}
      {status_html}
      <form method="post" action="/auth/bw">
        <label for="server_url">URL self-hosted</label>
        <input id="server_url" name="server_url" type="url" placeholder="https://vault.tudominio.com" required />
        <label for="username">Usuario / email</label>
        <input id="username" name="username" type="text" autocomplete="username" required />
        <label for="password">Master password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">Iniciar sesión en Bitwarden</button>
        <div class="hint">Después podrás usar `/auth/login` o la tool MCP `secure_login` sin volver a pasar las credenciales.</div>
      </form>
    </div>
  </div>
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
async def app_list() -> dict[str, Any]:
    return await desktop_service.app_list()


@mcp.tool()
async def app_launch(command: str) -> dict[str, Any]:
    return await desktop_service.app_launch(command)


@mcp.tool()
async def app_status(query: str) -> dict[str, Any]:
    return await desktop_service.app_status(query)


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


@app.get("/desktop/apps")
async def desktop_apps_http() -> dict[str, Any]:
    return await desktop_service.app_list()


@app.post("/desktop/apps/launch")
async def desktop_app_launch_http(request: AppLaunchRequest) -> dict[str, Any]:
    return await desktop_service.app_launch(request.command)


@app.get("/desktop/apps/status")
async def desktop_app_status_http(query: str = Query(...)) -> dict[str, Any]:
    return await desktop_service.app_status(query)


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
