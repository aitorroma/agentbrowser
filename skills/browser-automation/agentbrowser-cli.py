#!/usr/bin/env python3
"""
agentbrowser-cli - Browser automation tool with Bitwarden integration
Inspired by Open Interpreter's approach to computer use

Usage:
    agentbrowser-cli login <site>              # Auto-login to a site
    agentbrowser-cli fill <selector> <value>   # Fill a form field
    agentbrowser-cli click <selector>          # Click an element
    agentbrowser-cli eval <javascript>         # Run JavaScript
    agentbrowser-cli screenshot [output]       # Take screenshot
    agentbrowser-cli snapshot                  # Get page structure
    agentbrowser-cli tabs                      # List browser tabs
    agentbrowser-cli navigate <url>            # Go to URL
    agentbrowser-cli bw <command>              # Bitwarden commands
    agentbrowser-cli desktop <command>         # Desktop control
"""

import sys
import json
import subprocess
import argparse
import os
import time
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

CDP_URL = os.getenv("CDP_URL", "http://localhost:9222")
MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8787")
CDP_CLI = os.getenv("CDP_CLI", "cdp-cli")
CONTAINER = os.getenv("CONTAINER", "agentbrowser-browser")


def run_cmd(cmd: list[str], check: bool = True) -> str:
    """Run a shell command and return output."""
    env = os.environ.copy()
    npm_global = os.path.expanduser("~/.npm-global/bin")
    if npm_global not in env.get("PATH", ""):
        env["PATH"] = f"{npm_global}:{env.get('PATH', '')}"
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def mcp_request(endpoint: str, data: dict | None = None, method: str = "GET") -> dict:
    """Make HTTP request to MCP server."""
    url = f"{MCP_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if data:
        body = json.dumps(data).encode()
        req = Request(url, data=body, headers=headers, method=method)
    else:
        req = Request(url, headers=headers, method=method)
    
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"MCP Error: {e}", file=sys.stderr)
        sys.exit(1)


def cdp_cmd(*args: str) -> str:
    """Run cdp-cli command."""
    cmd = [CDP_CLI, "--cdp-url", CDP_URL] + list(args)
    return run_cmd(cmd)


def get_active_page() -> str:
    """Get the active page ID."""
    output = cdp_cmd("tabs")
    if not output:
        print("No pages found", file=sys.stderr)
        sys.exit(1)
    
    lines = output.strip().split("\n")
    for line in lines:
        try:
            data = json.loads(line)
            if data.get("type") == "page" and data.get("url") != "about:blank":
                return data["id"]
        except json.JSONDecodeError:
            continue
    
    if lines:
        try:
            return json.loads(lines[0])["id"]
        except (json.JSONDecodeError, KeyError):
            pass
    
    print("No active page found", file=sys.stderr)
    sys.exit(1)


def docker_cp(container: str, remote_path: str, local_path: str):
    """Copy file from Docker container."""
    run_cmd(["docker", "cp", f"{container}:{remote_path}", local_path])


def get_bw_env() -> dict:
    """Get environment with Bitwarden/Node CLIs on PATH."""
    env = os.environ.copy()
    npm_global = os.path.expanduser("~/.npm-global/bin")
    if npm_global not in env.get("PATH", ""):
        env["PATH"] = f"{npm_global}:{env.get('PATH', '')}"
    return env


def get_bw_session(password: str | None = None) -> str:
    """Resolve a usable Bitwarden session."""
    session = os.environ.get("BW_SESSION", "").strip()
    if session:
        return session

    env = get_bw_env()
    result = subprocess.run(
        ["bw", "unlock", "--raw", "--nointeraction"],
        capture_output=True, text=True, env=env
    )
    session = result.stdout.strip()
    if session:
        return session

    if password:
        result = subprocess.run(
            ["bw", "unlock", password, "--raw", "--nointeraction"],
            capture_output=True, text=True, env=env
        )
        session = result.stdout.strip()
        if session:
            return session

    print("Error: Could not unlock Bitwarden vault. Use 'export BW_SESSION=...' first.", file=sys.stderr)
    sys.exit(1)


def bw_json(args: list[str], session: str) -> dict | list:
    """Run a Bitwarden command that returns JSON."""
    env = get_bw_env()
    result = subprocess.run(
        ["bw", *args, "--session", session, "--nointeraction"],
        capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        print(f"Bitwarden error: {result.stderr or result.stdout}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Bitwarden returned invalid JSON: {result.stdout[:500]}", file=sys.stderr)
        sys.exit(1)


def get_page_state(page_id: str) -> dict:
    """Return compact page state for login automation."""
    js = """
    JSON.stringify({
      url: location.href,
      title: document.title,
      text: (document.body?.innerText || "").slice(0, 2000)
    })
    """
    result = cdp_cmd("eval", page_id, js)
    try:
        data = json.loads(result)
        return json.loads(data.get("value", "{}"))
    except json.JSONDecodeError:
        return {"url": "", "title": "", "text": ""}


def js_eval_value(page_id: str, js: str):
    """Evaluate JS and decode the returned JSON value when possible."""
    result = cdp_cmd("eval", page_id, js)
    try:
        data = json.loads(result)
        value = data.get("value")
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
    except json.JSONDecodeError:
        return result


def fill_inputs_js(page_id: str, selectors: list[str], value: str) -> int:
    """Fill all matching inputs using DOM events."""
    js = f"""
    (() => {{
      const selectors = {json.dumps(selectors)};
      const value = {json.dumps(value)};
      const seen = new Set();
      const matches = [];
      for (const selector of selectors) {{
        for (const el of document.querySelectorAll(selector)) {{
          if (!seen.has(el)) {{
            seen.add(el);
            matches.push(el);
          }}
        }}
      }}
      for (const el of matches) {{
        el.focus();
        el.value = value;
        el.dispatchEvent(new Event("input", {{ bubbles: true }}));
        el.dispatchEvent(new Event("change", {{ bubbles: true }}));
        el.dispatchEvent(new Event("blur", {{ bubbles: true }}));
      }}
      return JSON.stringify({{ count: matches.length }});
    }})()
    """
    data = js_eval_value(page_id, js)
    return int((data or {}).get("count", 0))


def click_js(page_id: str, selectors: list[str], text_patterns: list[str] | None = None) -> bool:
    """Click the first visible element matching selectors/patterns."""
    js = f"""
    (() => {{
      const selectors = {json.dumps(selectors)};
      const textPatterns = {json.dumps(text_patterns or [])};
      const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
      const matchesText = el => {{
        const text = ((el.innerText || el.value || el.textContent || "") + " " + (el.getAttribute("aria-label") || "")).trim().toLowerCase();
        return !textPatterns.length || textPatterns.some(p => text.includes(p.toLowerCase()));
      }};
      for (const selector of selectors) {{
        for (const el of document.querySelectorAll(selector)) {{
          if (visible(el) && matchesText(el)) {{
            el.click();
            return JSON.stringify({{ clicked: true, selector }});
          }}
        }}
      }}
      return JSON.stringify({{ clicked: false }});
    }})()
    """
    data = js_eval_value(page_id, js)
    return bool((data or {}).get("clicked"))


def find_login_item(site: str, session: str, account: str | None = None, username: str | None = None) -> dict | None:
    """Find the best matching Bitwarden login item for a site/account."""
    items = bw_json(["list", "items", "--search", site], session)
    if not isinstance(items, list):
        return None

    site_l = site.lower()
    account_l = (account or "").lower()
    username_l = (username or "").lower()

    def score(item: dict) -> int:
        login = item.get("login", {}) or {}
        name = (item.get("name") or "").lower()
        user = (login.get("username") or "").lower()
        uris = [((u or {}).get("uri") or "").lower() for u in (login.get("uris") or [])]
        score = 0
        if site_l and site_l in name:
            score += 20
        if any(site_l in uri for uri in uris):
            score += 40
        if username_l and user == username_l:
            score += 100
        elif username_l and username_l in user:
            score += 50
        if account_l and account_l in name:
            score += 80
        if account_l and account_l == user:
            score += 120
        if login.get("totp"):
            score += 5
        return score

    ranked = sorted(items, key=score, reverse=True)
    best = ranked[0] if ranked and score(ranked[0]) > 0 else None
    return best


# === Browser Commands ===

def cmd_google(query: str):
    """Search Google and open results."""
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    cmd_navigate(url)
    print(f"Searching Google for: {query}")


def cmd_markdown(url: str | None = None, page_id: str | None = None):
    """Get page content as markdown."""
    if not url:
        pid = page_id or get_active_page()
        result = cdp_cmd("eval", pid, "window.location.href")
        try:
            data = json.loads(result)
            url = data.get("value", "")
        except json.JSONDecodeError:
            pass
    
    if not url:
        print("No URL available", file=sys.stderr)
        return
    
    endpoint = f"/markdown?url={url}"
    try:
        result = mcp_request(endpoint)
        if "markdown" in result:
            print(result["markdown"])
        else:
            print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)


def cmd_close_blank():
    """Close all about:blank tabs."""
    output = cdp_cmd("tabs")
    closed = 0
    for line in output.strip().split("\n"):
        try:
            tab = json.loads(line)
            if tab.get("url") == "about:blank":
                cdp_cmd("close", tab["id"])
                closed += 1
        except json.JSONDecodeError:
            continue
    print(f"Closed {closed} blank tab(s)")


def cmd_tabs():
    """List all browser tabs."""
    output = cdp_cmd("tabs")
    for line in output.strip().split("\n"):
        try:
            tab = json.loads(line)
            if tab.get("type") == "page":
                print(f"{tab['id'][:12]}  {tab['title'][:50]}  {tab['url'][:60]}")
        except json.JSONDecodeError:
            continue


def cmd_navigate(url: str, page_id: str | None = None):
    """Navigate to URL."""
    pid = page_id or get_active_page()
    result = cdp_cmd("go", pid, url)
    print(f"Navigated to {url}")


def cmd_fill(selector: str, value: str, page_id: str | None = None):
    """Fill an input field."""
    pid = page_id or get_active_page()
    result = cdp_cmd("fill", pid, value, selector)
    print(f"Filled {selector}")


def cmd_click(selector: str, page_id: str | None = None):
    """Click an element."""
    pid = page_id or get_active_page()
    result = cdp_cmd("click", pid, selector)
    print(f"Clicked {selector}")


def cmd_eval(js: str, page_id: str | None = None):
    """Evaluate JavaScript."""
    pid = page_id or get_active_page()
    result = cdp_cmd("eval", pid, js)
    try:
        data = json.loads(result)
        if "result" in data:
            print(json.dumps(data["result"], indent=2, ensure_ascii=False))
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(result)


def cmd_screenshot(output: str | None = None, page_id: str | None = None):
    """Take screenshot."""
    pid = page_id or get_active_page()
    output = output or f"/tmp/screenshot-{pid[:8]}.png"
    result = cdp_cmd("screenshot", pid, output)
    
    try:
        docker_cp(CONTAINER, output, output)
        print(f"Screenshot saved to {output}")
    except Exception:
        print(f"Screenshot taken (in container): {output}")


def cmd_snapshot(page_id: str | None = None):
    """Get page snapshot (accessibility tree)."""
    pid = page_id or get_active_page()
    result = cdp_cmd("snapshot", pid, "--format", "ax")
    
    try:
        data = json.loads(result)
        if "nodes" in data:
            for node in data["nodes"][:50]:
                role = node.get("role", {}).get("value", "unknown")
                name = node.get("name", {}).get("value", "")
                if name and role not in ["none", "generic"]:
                    print(f"  [{role}] {name[:80]}")
        else:
            print(json.dumps(data, indent=2)[:2000])
    except json.JSONDecodeError:
        print(result[:2000])


# === Login Automation ===

def cmd_login(
    site: str,
    password: str | None = None,
    account: str | None = None,
    username: str | None = None,
    page_id: str | None = None,
    submit: bool = True,
    auto_totp: bool = True,
):
    """Auto-login to a website using Bitwarden credentials."""
    print(f"Looking up credentials for {site}...")
    session = get_bw_session(password)
    matching = find_login_item(site, session, account=account, username=username)
    if not matching:
        print(f"No credentials found for {site}", file=sys.stderr)
        return

    login = matching.get("login", {}) or {}
    login_username = login.get("username", "")
    login_password = login.get("password", "")
    has_totp = bool(login.get("totp"))
    print(f"Found: {matching.get('name')} ({login_username})")

    page_id = page_id or get_active_page()
    state = get_page_state(page_id)
    if site.lower() not in (state.get("url") or "").lower():
        cmd_eval(f'window.location.href = "https://{site}"; "navigating"', page_id)
        time.sleep(3)

    username_selectors = [
        "input[name='LoginUserName']",
        "input[type='email']",
        "input[name='email']",
        "input[name='username']",
        "input[name='login']",
        "input[id='email']",
        "input[id='username']",
        "input[placeholder*='mail' i]",
        "input[placeholder*='user' i]",
        "input[autocomplete='username']",
        "input[type='text']",
    ]
    password_selectors = [
        "input[name='LoginPassword']",
        "input[type='password']",
        "input[name='password']",
        "input[name='passwd']",
        "input[id='password']",
        "input[autocomplete='current-password']",
    ]

    user_count = fill_inputs_js(page_id, username_selectors, login_username)
    pass_count = fill_inputs_js(page_id, password_selectors, login_password)
    print(f"Filled username fields: {user_count}")
    print(f"Filled password fields: {pass_count}")

    if not submit:
        print("Login form filled. Submission skipped by --no-submit.")
        return

    clicked = click_js(
        page_id,
        [
            "button[type='submit']",
            "input[type='submit']",
            "button",
        ],
        ["sign in", "log in", "login", "submit", "continue"],
    )
    print("Submitted login form." if clicked else "Could not find a submit button automatically.")

    if has_totp and auto_totp:
        env = get_bw_env()
        for _ in range(10):
            time.sleep(1)
            state = get_page_state(page_id)
            blob = " ".join([state.get("url", ""), state.get("title", ""), state.get("text", "")]).lower()
            if any(key in blob for key in ["otp", "two-factor", "two factor", "authentication code", "verification code"]):
                result = subprocess.run(
                    ["bw", "get", "totp", matching.get("id"), "--session", session, "--nointeraction"],
                    capture_output=True, text=True, env=env
                )
                totp_code = result.stdout.strip()
                if not totp_code:
                    print("TOTP required but could not generate a code.", file=sys.stderr)
                    return
                otp_selectors = [
                    "input[placeholder*='otp' i]",
                    "input[placeholder*='code' i]",
                    "input[name*='otp' i]",
                    "input[name*='code' i]",
                    "input[id*='otp' i]",
                    "input[id*='code' i]",
                    "input[type='tel']",
                    "input[type='number']",
                    "input[type='text']",
                ]
                otp_count = fill_inputs_js(page_id, otp_selectors, totp_code)
                otp_clicked = click_js(
                    page_id,
                    ["button[type='submit']", "input[type='submit']", "button"],
                    ["submit", "verify", "continue", "sign in"],
                )
                print(f"Filled OTP fields: {otp_count}")
                print("Submitted OTP form." if otp_clicked else "Filled OTP, but could not auto-submit.")
                return

    print("Login flow completed or waiting for next step.")


# === Bitwarden Commands ===

def cmd_bw_list(search: str | None = None):
    """List Bitwarden vault items."""
    env = get_bw_env()
    session = get_bw_session()
    # List items
    cmd = ["bw", "list", "items", "--session", session, "--nointeraction"]
    if search:
        cmd.extend(["--search", search])
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    try:
        items = json.loads(result.stdout)
        for item in items[:20]:
            name = item.get("name", "unnamed")
            login = item.get("login", {})
            username = login.get("username", "")
            uris = login.get("uris", []) or []
            uri = uris[0].get("uri", "") if uris else ""
            has_totp = "✓" if login.get("totp") else " "
            print(f"  {has_totp} {name[:40]:40} {username[:30]:30} {uri[:50]}")
    except json.JSONDecodeError:
        print(result)


def cmd_bw_get(item_name: str):
    """Get item details from Bitwarden."""
    env = get_bw_env()
    session = get_bw_session()
    # Search for item
    result = subprocess.run(
        ["bw", "list", "items", "--session", session, "--search", item_name, "--nointeraction"],
        capture_output=True, text=True, env=env
    )
    
    try:
        items = json.loads(result.stdout)
        for item in items:
            if item_name.lower() in item.get("name", "").lower():
                login = item.get("login", {})
                print(f"Name: {item.get('name')}")
                print(f"Username: {login.get('username')}")
                print(f"Password: {login.get('password')}")
                if login.get("totp"):
                    print(f"TOTP: {login.get('totp')}")
                    # Generate current TOTP
                    result = subprocess.run(
                        ["bw", "get", "totp", item.get("id"), "--session", session, "--nointeraction"],
                        capture_output=True, text=True, env=env
                    )
                    if result.stdout:
                        print(f"Current TOTP: {result.stdout}")
                return
        print(f"No item found matching '{item_name}'", file=sys.stderr)
    except json.JSONDecodeError:
        print(f"Error: {result.stdout}", file=sys.stderr)


def cmd_bw_generate(length: int = 16):
    """Generate a password."""
    result = run_cmd(["bw", "generate", "--length", str(length), "--nointeraction"], check=False)
    print(f"Generated: {result}")


def cmd_bw_status():
    """Check Bitwarden status."""
    result = run_cmd(["bw", "status", "--nointeraction"], check=False)
    print(result)


# === Desktop Commands ===

def cmd_desktop_click(x: int, y: int):
    """Click at coordinates."""
    mcp_request("/desktop/mouse/click", {"x": x, "y": y}, "POST")
    print(f"Clicked at ({x}, {y})")


def cmd_desktop_type(text: str, delay: int = 20):
    """Type text via desktop control."""
    mcp_request("/desktop/keyboard/type", {"text": text, "delay_ms": delay}, "POST")
    print(f"Typed: {text[:50]}...")


def cmd_desktop_key(key: str):
    """Press a key."""
    mcp_request("/desktop/keyboard/press", {"keys": key}, "POST")
    print(f"Pressed: {key}")


def cmd_desktop_screenshot(output: str | None = None):
    """Take desktop screenshot."""
    output = output or "/tmp/desktop-screenshot.png"
    result = mcp_request("/desktop/screenshot", {"path": output}, "POST")
    
    try:
        docker_cp(CONTAINER, output, output)
        print(f"Screenshot saved to {output}")
    except Exception:
        print(f"Screenshot taken (in container): {output}")


def cmd_desktop_windows():
    """List desktop windows."""
    result = mcp_request("/desktop/windows")
    if isinstance(result, list):
        for win in result:
            if win.get("title"):
                print(f"  {win.get('id', '')[:12]}  {win['title'][:60]}")
    else:
        print(json.dumps(result, indent=2))


def cmd_desktop_focus(query: str):
    """Focus a window by name."""
    mcp_request("/desktop/windows/focus", query, "POST")
    print(f"Focused: {query}")


# === Main ===

def main():
    parser = argparse.ArgumentParser(
        description="AgentBrowser CLI - Browser automation with Bitwarden",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentbrowser-cli login example.com       # Auto-login with Bitwarden
  agentbrowser-cli tabs                    # List browser tabs
  agentbrowser-cli navigate https://...    # Go to URL
  agentbrowser-cli fill "#email" "user@.." # Fill field
  agentbrowser-cli click "button"          # Click element
  agentbrowser-cli eval "document.title"   # Run JavaScript
  agentbrowser-cli screenshot              # Take screenshot
  agentbrowser-cli bw list                 # List Bitwarden items
  agentbrowser-cli bw get example          # Get credentials
  agentbrowser-cli desktop click 100 200   # Click at coordinates
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Browser commands
    login = subparsers.add_parser("login", help="Auto-login with Bitwarden")
    login.add_argument("site", help="Site name to login")
    login.add_argument("-a", "--account", help="Prefer a Bitwarden item/account name")
    login.add_argument("-u", "--username", help="Prefer a specific username")
    login.add_argument("-p", "--page", help="Page ID")
    login.add_argument("--no-submit", action="store_true", help="Fill only, do not submit")
    login.add_argument("--no-totp", action="store_true", help="Do not auto-handle TOTP")
    
    google = subparsers.add_parser("google", help="Search Google")
    google.add_argument("query", help="Search query")
    
    subparsers.add_parser("tabs", help="List browser tabs")
    
    nav = subparsers.add_parser("navigate", help="Navigate to URL")
    nav.add_argument("url", help="URL to navigate to")
    nav.add_argument("-p", "--page", help="Page ID")
    
    fill = subparsers.add_parser("fill", help="Fill an input field")
    fill.add_argument("selector", help="CSS selector")
    fill.add_argument("value", help="Value to fill")
    fill.add_argument("-p", "--page", help="Page ID")
    
    click = subparsers.add_parser("click", help="Click an element")
    click.add_argument("selector", help="CSS selector")
    click.add_argument("-p", "--page", help="Page ID")
    
    ev = subparsers.add_parser("eval", help="Evaluate JavaScript")
    ev.add_argument("js", help="JavaScript code")
    ev.add_argument("-p", "--page", help="Page ID")
    
    ss = subparsers.add_parser("screenshot", help="Take screenshot")
    ss.add_argument("output", nargs="?", help="Output file path")
    ss.add_argument("-p", "--page", help="Page ID")
    
    subparsers.add_parser("snapshot", help="Get page snapshot")
    
    md = subparsers.add_parser("markdown", help="Get page as markdown")
    md.add_argument("url", nargs="?", help="URL to convert")
    md.add_argument("-p", "--page", help="Page ID")
    
    subparsers.add_parser("close-blank", help="Close all blank tabs")
    
    # Bitwarden commands
    bwc = subparsers.add_parser("bw", help="Bitwarden commands")
    bwc_sub = bwc.add_subparsers(dest="bw_action", help="Bitwarden action")
    
    bwc_list = bwc_sub.add_parser("list", help="List vault items")
    bwc_list.add_argument("-s", "--search", help="Search term")
    
    bwc_get = bwc_sub.add_parser("get", help="Get item details")
    bwc_get.add_argument("name", help="Item name to search")
    
    bwc_gen = bwc_sub.add_parser("generate", help="Generate password")
    bwc_gen.add_argument("-l", "--length", type=int, default=16, help="Password length")
    
    bwc_sub.add_parser("status", help="Show status")
    
    # Desktop commands
    desktop = subparsers.add_parser("desktop", help="Desktop control")
    desktop_sub = desktop.add_subparsers(dest="desktop_action", help="Desktop action")
    
    dc = desktop_sub.add_parser("click", help="Click at coordinates")
    dc.add_argument("x", type=int, help="X coordinate")
    dc.add_argument("y", type=int, help="Y coordinate")
    
    dt = desktop_sub.add_parser("type", help="Type text")
    dt.add_argument("text", help="Text to type")
    dt.add_argument("-d", "--delay", type=int, default=20, help="Delay between chars (ms)")
    
    dk = desktop_sub.add_parser("key", help="Press a key")
    dk.add_argument("key", help="Key to press")
    
    dss = desktop_sub.add_parser("screenshot", help="Take desktop screenshot")
    dss.add_argument("output", nargs="?", help="Output file path")
    
    desktop_sub.add_parser("windows", help="List windows")
    
    dwf = desktop_sub.add_parser("focus", help="Focus a window")
    dwf.add_argument("query", help="Window name to focus")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Ensure CDP CLI is in PATH
    global CDP_CLI
    if not os.path.isfile(CDP_CLI):
        npm_global = os.path.expanduser("~/.npm-global/bin")
        if os.path.isfile(f"{npm_global}/cdp-cli"):
            CDP_CLI = f"{npm_global}/cdp-cli"
    
    # Dispatch commands
    if args.command == "google":
        cmd_google(args.query)
    elif args.command == "login":
        cmd_login(
            args.site,
            account=getattr(args, "account", None),
            username=getattr(args, "username", None),
            page_id=getattr(args, "page", None),
            submit=not getattr(args, "no_submit", False),
            auto_totp=not getattr(args, "no_totp", False),
        )
    elif args.command == "tabs":
        cmd_tabs()
    elif args.command == "navigate":
        cmd_navigate(args.url, args.page)
    elif args.command == "fill":
        cmd_fill(args.selector, args.value, args.page)
    elif args.command == "click":
        cmd_click(args.selector, args.page)
    elif args.command == "eval":
        cmd_eval(args.js, args.page)
    elif args.command == "screenshot":
        cmd_screenshot(args.output, args.page)
    elif args.command == "snapshot":
        cmd_snapshot()
    elif args.command == "bw":
        if args.bw_action == "list":
            cmd_bw_list(args.search)
        elif args.bw_action == "get":
            cmd_bw_get(args.name)
        elif args.bw_action == "generate":
            cmd_bw_generate(args.length)
        elif args.bw_action == "status":
            cmd_bw_status()
        else:
            print("Usage: agentbrowser-cli bw {list|get|generate|status}")
    elif args.command == "desktop":
        if args.desktop_action == "click":
            cmd_desktop_click(args.x, args.y)
        elif args.desktop_action == "type":
            cmd_desktop_type(args.text, args.delay)
        elif args.desktop_action == "key":
            cmd_desktop_key(args.key)
        elif args.desktop_action == "screenshot":
            cmd_desktop_screenshot(args.output)
        elif args.desktop_action == "windows":
            cmd_desktop_windows()
        elif args.desktop_action == "focus":
            cmd_desktop_focus(args.query)
        else:
            print("Usage: agentbrowser-cli desktop {click|type|key|screenshot|windows|focus}")


if __name__ == "__main__":
    main()
