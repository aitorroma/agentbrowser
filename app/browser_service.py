import asyncio
import base64
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from markdownify import markdownify as md
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from readabilipy import simple_json_from_html_string


class BrowserService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser: Browser | None = None
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "/data/output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cdp_port = int(os.getenv("BROWSER_CDP_PORT", "9222"))
        self.cdp_bind = os.getenv("BROWSER_CDP_CONNECT_HOST", "127.0.0.1")
        self.browser_locale = os.getenv("BROWSER_LOCALE", "es-ES")
        self.browser_timezone = os.getenv("BROWSER_TIMEZONE", "Europe/Madrid")
        self.bw_cli = os.getenv("BW_CLI", "bw")
        self._bw_session_token: str | None = None
        self._bw_server_url: str | None = None
        self._bw_username: str | None = None
        self._bw_state_lock = asyncio.Lock()
        self.bw_appdata_dir = Path(os.getenv("BW_APPDATA_DIR", "/dev/shm/agentbrowser-bw"))
        self.bw_appdata_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.bw_appdata_dir, 0o700)
        except PermissionError:
            pass
        self.bw_state_dir = Path(os.getenv("BW_STATE_DIR", "/data/profile/bitwarden-state"))
        self.bw_state_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.bw_state_dir, 0o700)
        except PermissionError:
            pass
        self.bw_state_file = self.bw_state_dir / "session.enc"
        self._bw_persistence_secret = os.getenv("BW_STATE_KEY", "").strip()
        self._bw_restore_state()
        # WebAuthn / passkeys via a CDP virtual authenticator
        self._webauthn_authenticator_id: str | None = None
        self.webauthn_state_dir = Path(os.getenv("WEBAUTHN_STATE_DIR", "/data/profile/webauthn"))
        self.webauthn_state_dir.mkdir(parents=True, exist_ok=True)
        self.webauthn_state_file = self.webauthn_state_dir / "credentials.json"

    async def _fetch_ws_endpoint(self) -> str:
        url = f"http://{self.cdp_bind}:{self.cdp_port}/json/version"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()["webSocketDebuggerUrl"]

    async def _connect(self) -> Browser:
        if self._browser and self._browser.is_connected():
            return self._browser
        ws_endpoint = await self._fetch_ws_endpoint()
        if not self._playwright:
            self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(ws_endpoint)
        return self._browser

    async def _context(self) -> BrowserContext:
        browser = await self._connect()
        if browser.contexts:
            return browser.contexts[0]
        return await browser.new_context(viewport={"width": 1366, "height": 768})

    async def _page(self) -> Page:
        context = await self._context()
        pages = [page for page in context.pages if not page.url.startswith("chrome://")]
        page = pages[0] if pages else await context.new_page()
        await self._apply_overrides(page)
        return page

    async def _apply_overrides(self, page: Page) -> None:
        session = await page.context.new_cdp_session(page)
        try:
            await session.send("Emulation.setTimezoneOverride", {"timezoneId": self.browser_timezone})
        except Exception as exc:
            if "timezone override is already in effect" not in str(exc).lower():
                raise
        try:
            await session.send("Emulation.setLocaleOverride", {"locale": self.browser_locale})
        except Exception as exc:
            if "locale override is already in effect" not in str(exc).lower():
                raise

    async def health(self) -> dict[str, Any]:
        ws_endpoint = ""
        try:
            ws_endpoint = await self._fetch_ws_endpoint()
        except Exception as exc:
            ws_error = str(exc)
        else:
            ws_error = ""
        try:
            page = await self._page()
            current_url = page.url
        except Exception as exc:
            current_url = ""
            return {
                "ok": False,
                "ws_endpoint": ws_endpoint,
                "current_url": current_url,
                "reason": str(exc),
                "ws_error": ws_error,
                "bitwarden_configured": bool(self._bw_session_token or os.getenv("BW_SESSION")),
            }
        return {
            "ok": True,
            "ws_endpoint": ws_endpoint,
            "current_url": current_url,
            "ws_error": ws_error,
            "bitwarden_configured": bool(self._bw_session_token or os.getenv("BW_SESSION")),
        }

    def _bw_available(self) -> bool:
        return shutil.which(self.bw_cli) is not None

    def _bw_persistence_enabled(self) -> bool:
        return bool(self._bw_persistence_secret)

    def _bw_fernet(self) -> Fernet:
        secret = self._bw_persistence_secret.encode("utf-8")
        digest = hashlib.sha256(secret).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def _bw_restore_state(self) -> None:
        if not self._bw_persistence_enabled() or not self.bw_state_file.exists():
            return
        try:
            payload = self._bw_fernet().decrypt(self.bw_state_file.read_bytes())
            data = json.loads(payload.decode("utf-8"))
        except (OSError, InvalidToken, json.JSONDecodeError, ValueError):
            return
        self._bw_session_token = (data.get("session") or "").strip() or None
        self._bw_server_url = (data.get("server_url") or "").strip() or None
        self._bw_username = (data.get("username") or "").strip() or None

    def _bw_persist_state(self) -> None:
        if not self._bw_persistence_enabled():
            return
        if not self._bw_session_token:
            self._bw_clear_persisted_state()
            return
        data = {
            "session": self._bw_session_token,
            "server_url": self._bw_server_url,
            "username": self._bw_username,
            "saved_at": datetime.now(UTC).isoformat(),
        }
        token = self._bw_fernet().encrypt(json.dumps(data, separators=(",", ":")).encode("utf-8"))
        self.bw_state_file.write_bytes(token)
        os.chmod(self.bw_state_file, 0o600)

    def _bw_clear_persisted_state(self) -> None:
        try:
            self.bw_state_file.unlink(missing_ok=True)
        except OSError:
            pass

    def _bw_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.bw_appdata_dir)
        env["BITWARDENCLI_APPDATA_DIR"] = str(self.bw_appdata_dir / ".config" / "Bitwarden CLI")
        env["NODE_OPTIONS"] = " ".join(
            part for part in [env.get("NODE_OPTIONS", "").strip(), "--experimental-global-webcrypto"] if part
        )
        Path(env["BITWARDENCLI_APPDATA_DIR"]).mkdir(parents=True, exist_ok=True)
        if extra:
            env.update(extra)
        return env

    async def _bw_session(self) -> str:
        session = (self._bw_session_token or "").strip()
        if session:
            return session
        session = os.getenv("BW_SESSION", "").strip()
        if session:
            return session
        raise RuntimeError("bitwarden_not_configured")

    async def _bw_exec(self, *args: str, include_session: bool = True, extra_env: dict[str, str] | None = None) -> str:
        if not self._bw_available():
            raise RuntimeError("bitwarden_cli_missing")
        cmd = [self.bw_cli, *args]
        if include_session:
            session = await self._bw_session()
            cmd.extend(["--session", session])
        cmd.append("--nointeraction")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._bw_env(extra_env),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError((stderr or stdout).decode().strip() or "bitwarden_error")
        return stdout.decode().strip()

    async def configure_bitwarden(self, server_url: str, username: str, password: str) -> dict[str, Any]:
        async with self._bw_state_lock:
            if not self._bw_available():
                return {"ok": False, "stage": "config_error", "reason": "bitwarden_cli_missing"}
            if not username or not password:
                return {"ok": False, "stage": "config_error", "reason": "missing_credentials"}

            extra_env = {"BW_PASSWORD": password}
            try:
                try:
                    await self._bw_exec("logout", include_session=False)
                except RuntimeError:
                    pass

                target = (server_url or "https://vault.bitwarden.com").strip()
                await self._bw_exec("config", "server", target, include_session=False)
                session = await self._bw_exec(
                    "login",
                    username,
                    "--passwordenv",
                    "BW_PASSWORD",
                    "--raw",
                    include_session=False,
                    extra_env=extra_env,
                )
                self._bw_session_token = session.strip()
                self._bw_server_url = target
                self._bw_username = username
                self._bw_persist_state()
                try:
                    await self._bw_exec("sync")
                except RuntimeError:
                    pass
                return {
                    "ok": True,
                    "stage": "connected",
                    "server_url": target,
                    "username_hint": f"{username[:2]}***" if len(username) > 2 else "***",
                }
            except RuntimeError as exc:
                return {"ok": False, "stage": "connect_failed", "reason": str(exc)}

    async def logout_bitwarden(self) -> dict[str, Any]:
        async with self._bw_state_lock:
            try:
                await self._bw_exec("logout")
            except RuntimeError:
                try:
                    await self._bw_exec("logout", include_session=False)
                except RuntimeError:
                    pass
            self._bw_session_token = None
            self._bw_server_url = None
            self._bw_username = None
            self._bw_clear_persisted_state()
            return {"ok": True, "stage": "logged_out"}

    def bitwarden_status(self) -> dict[str, Any]:
        return {
            "configured": bool(self._bw_session_token or os.getenv("BW_SESSION")),
            "server_url": self._bw_server_url,
            "persisted": bool(self._bw_persistence_enabled() and self.bw_state_file.exists()),
            "username_hint": (
                f"{self._bw_username[:2]}***" if self._bw_username and len(self._bw_username) > 2 else None
            ),
        }

    async def _bw_list_items(self, search: str) -> list[dict[str, Any]]:
        raw = await self._bw_exec("list", "items", "--search", search)
        data = json.loads(raw)
        return data if isinstance(data, list) else []

    async def _bw_get_totp(self, item_id: str) -> str:
        return (await self._bw_exec("get", "totp", item_id)).strip()

    async def list_accounts(self, search: str | None = None) -> dict[str, Any]:
        async with self._lock:
            try:
                if search:
                    items = await self._bw_list_items(search)
                else:
                    raw = await self._bw_exec("list", "items")
                    items = json.loads(raw) if isinstance(json.loads(raw), list) else []
            except RuntimeError as exc:
                return {"ok": False, "reason": str(exc)}
            accounts = []
            seen = set()
            for item in items:
                login = item.get("login", {}) or {}
                name = item.get("name", "")
                username = login.get("username", "")
                key = f"{name}|{username}"
                if key in seen:
                    continue
                seen.add(key)
                uris = [u.get("uri", "") for u in (login.get("uris") or []) if u.get("uri")]
                accounts.append({
                    "name": name,
                    "username": username,
                    "has_totp": bool(login.get("totp")),
                    "uris": uris[:3],
                })
            return {"ok": True, "count": len(accounts), "accounts": accounts}

    async def get_totp(self, site: str, account: str | None = None) -> dict[str, Any]:
        async with self._lock:
            try:
                items = await self._bw_list_items(site)
            except RuntimeError as exc:
                return {"ok": False, "reason": str(exc)}
            item = self._pick_login_item(items, site=site, account=account)
            if not item:
                return {"ok": False, "reason": "credential_not_found", "site": site}
            login = item.get("login", {}) or {}
            if not login.get("totp"):
                return {"ok": False, "reason": "no_totp", "site": site, "username": login.get("username")}
            try:
                totp = await self._bw_get_totp(item["id"])
            except RuntimeError as exc:
                return {"ok": False, "reason": str(exc)}
            return {"ok": True, "totp": totp, "site": site, "username": login.get("username")}

    def _pick_login_item(
        self,
        items: list[dict[str, Any]],
        *,
        site: str,
        account: str | None = None,
        username: str | None = None,
    ) -> dict[str, Any] | None:
        site_l = site.lower()
        account_l = (account or "").lower()
        username_l = (username or "").lower()

        def score(item: dict[str, Any]) -> int:
            login = item.get("login", {}) or {}
            name = (item.get("name") or "").lower()
            user = (login.get("username") or "").lower()
            uris = [((u or {}).get("uri") or "").lower() for u in (login.get("uris") or [])]
            value = 0
            if site_l in name:
                value += 20
            if any(site_l in uri for uri in uris):
                value += 50
            if account_l and account_l in name:
                value += 80
            if account_l and account_l == user:
                value += 120
            if username_l and username_l == user:
                value += 100
            elif username_l and username_l in user:
                value += 40
            if login.get("totp"):
                value += 5
            return value

        ranked = sorted(items, key=score, reverse=True)
        if not ranked or score(ranked[0]) <= 0:
            return None
        return ranked[0]

    async def _fill_first(self, page: Page, selectors: list[str], value: str) -> int:
        selectors_js = json.dumps(selectors)
        value_js = json.dumps(value)
        return await page.evaluate(
            f"""
            (() => {{
              const selectors = {selectors_js};
              const value = {value_js};
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
              return matches.length;
            }})()
            """
        )

    async def _click_submit(self, page: Page, labels: list[str]) -> bool:
        labels_js = json.dumps([label.lower() for label in labels])
        return await page.evaluate(
            f"""
            (() => {{
              const labels = {labels_js};
              const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
              const passwordInput = document.querySelector("input[type='password']");
              const usernameInput = document.querySelector("input[name='LoginUserName'], input[type='email'], input[name='email'], input[name='username'], input[autocomplete='username'], input[type='text']");
              const roots = [];
              const addRoot = root => {{ if (root && !roots.includes(root)) roots.push(root); }};
              addRoot(passwordInput?.form);
              addRoot(usernameInput?.form);
              addRoot(passwordInput?.closest("form,[role='form'],section,article,main,div"));
              addRoot(usernameInput?.closest("form,[role='form'],section,article,main,div"));
              addRoot(document);

              const controls = [];
              const seen = new Set();
              for (const root of roots) {{
                for (const el of root.querySelectorAll("button, input[type='submit'], input[type='button'], [role='button']")) {{
                  if (!seen.has(el)) {{
                    seen.add(el);
                    controls.push(el);
                  }}
                }}
              }}
              for (const el of controls) {{
                const text = ((el.innerText || el.value || el.textContent || "") + " " + (el.getAttribute("aria-label") || "")).trim().toLowerCase();
                if (visible(el) && labels.some(label => text.includes(label))) {{
                  el.click();
                  return true;
                }}
              }}
              if (passwordInput?.form && typeof passwordInput.form.requestSubmit === "function") {{
                passwordInput.form.requestSubmit();
                return true;
              }}
              if (passwordInput?.form && typeof passwordInput.form.submit === "function") {{
                passwordInput.form.submit();
                return true;
              }}
              if (passwordInput) {{
                passwordInput.focus();
                for (const type of ["keydown", "keypress", "keyup"]) {{
                  passwordInput.dispatchEvent(new KeyboardEvent(type, {{ key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }}));
                }}
                return true;
              }}
              return false;
            }})()
            """
        )

    async def _page_text(self, page: Page, limit: int = 4000) -> str:
        try:
            return (await page.locator("body").inner_text())[:limit]
        except Exception:
            return ""

    async def _otp_context(self, page: Page) -> dict[str, Any]:
        return await page.evaluate(
            """
            (() => {
              const body = (document.body?.innerText || '').toLowerCase();
              const otpInputs = Array.from(document.querySelectorAll(
                "input[placeholder*='otp' i], input[placeholder*='code' i], input[name*='otp' i], input[name*='code' i], input[id*='otp' i], input[id*='code' i], input[type='tel'], input[type='number']"
              )).filter(el => (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
              const textInputs = Array.from(document.querySelectorAll("input[type='text']")).filter(
                el => (el.offsetWidth || el.offsetHeight || el.getClientRects().length)
              );
              return {
                looksOtp:
                  otpInputs.length > 0 ||
                  body.includes("otp") ||
                  body.includes("two-factor") ||
                  body.includes("two factor") ||
                  body.includes("authentication code") ||
                  body.includes("verification code") ||
                  body.includes("enter otp code"),
                otpInputs: otpInputs.length,
                textInputs: textInputs.length,
              };
            })()
            """
        )

    async def _submit_otp(self, page: Page, code: str) -> dict[str, Any]:
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
        otp_count = await self._fill_first(page, otp_selectors, code)
        if not otp_count:
            return {"ok": False, "stage": "otp_required", "url": page.url}
        await self._click_submit(page, ["submit", "verify", "continue", "sign in", "log in"])
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1500)
        return {"ok": True, "stage": "otp_submitted", "url": page.url}

    async def secure_login(
        self,
        site: str,
        account: str | None = None,
        username: str | None = None,
        url: str | None = None,
        submit: bool = True,
        auto_totp: bool = True,
    ) -> dict[str, Any]:
        async with self._lock:
            try:
                items = await self._bw_list_items(site)
            except RuntimeError as exc:
                return {"ok": False, "stage": "config_error", "reason": str(exc)}

            item = self._pick_login_item(items, site=site, account=account, username=username)
            if not item:
                return {"ok": False, "stage": "credential_not_found", "site": site}

            login = item.get("login", {}) or {}
            login_username = login.get("username") or ""
            login_password = login.get("password") or ""
            if not login_username or not login_password:
                return {"ok": False, "stage": "credential_incomplete", "site": site}

            page = await self._page()
            target_url = url or f"https://{site}"
            if site.lower() not in page.url.lower():
                await page.goto(target_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")

            otp_ctx = await self._otp_context(page)
            if auto_totp and login.get("totp") and otp_ctx.get("looksOtp"):
                try:
                    totp = await self._bw_get_totp(item["id"])
                except RuntimeError as exc:
                    return {"ok": False, "stage": "otp_failed", "reason": str(exc), "site": site, "url": page.url}
                otp_result = await self._submit_otp(page, totp)
                if not otp_result.get("ok"):
                    return {"ok": False, "stage": "otp_required", "site": site, "url": page.url}
                current_url = page.url
                current_title = await page.title()
                current_text = (await self._page_text(page, 1600)).lower()
                if any(key in current_text for key in ["enter otp code", "two-factor", "verification code", "authentication code"]):
                    return {"ok": False, "stage": "otp_required", "site": site, "url": current_url, "title": current_title}
                return {"ok": True, "stage": "logged_in", "site": site, "url": current_url, "title": current_title}

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

            user_count = await self._fill_first(page, username_selectors, login_username)
            pass_count = await self._fill_first(page, password_selectors, login_password)
            if not user_count or not pass_count:
                return {
                    "ok": False,
                    "stage": "form_not_found",
                    "site": site,
                    "url": page.url,
                    "username_fields": user_count,
                    "password_fields": pass_count,
                }

            if not submit:
                return {"ok": True, "stage": "filled", "site": site, "url": page.url}

            await self._click_submit(page, ["sign in", "log in", "login", "submit", "continue"])
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1500)

            if auto_totp and login.get("totp"):
                blob = f"{page.url}\n{await page.title()}\n{await self._page_text(page)}"
                if any(key in blob.lower() for key in ["otp", "two-factor", "two factor", "authentication code", "verification code"]):
                    try:
                        totp = await self._bw_get_totp(item["id"])
                    except RuntimeError as exc:
                        return {"ok": False, "stage": "otp_failed", "reason": str(exc), "site": site, "url": page.url}
                    otp_result = await self._submit_otp(page, totp)
                    if not otp_result.get("ok"):
                        return {"ok": False, "stage": "otp_required", "site": site, "url": page.url}

            current_url = page.url
            current_title = await page.title()
            current_text = (await self._page_text(page, 1200)).lower()
            if any(key in current_text for key in ["otp code is required", "enter otp", "two-factor", "verification code"]):
                return {"ok": False, "stage": "otp_required", "site": site, "url": current_url, "title": current_title}
            if site.lower() in current_url.lower() or "account" in current_text or "dashboard" in current_text:
                return {"ok": True, "stage": "logged_in", "site": site, "url": current_url, "title": current_title}
            return {"ok": True, "stage": "submitted", "site": site, "url": current_url, "title": current_title}

    async def goto(self, url: str) -> dict[str, Any]:
        async with self._lock:
            page = await self._page()
            response = await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            return {"url": page.url, "status": response.status if response else None, "title": await page.title()}

    async def screenshot(self, path: str | None = None, full_page: bool = True) -> dict[str, Any]:
        async with self._lock:
            page = await self._page()
            if path is None:
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                path = str(self.output_dir / f"screenshot-{stamp}.png")
            await page.screenshot(path=path, full_page=full_page)
            return {"path": path, "url": page.url}

    async def fill(self, selector: str, text: str) -> dict[str, Any]:
        async with self._lock:
            page = await self._page()
            await page.locator(selector).fill(text)
            return {"ok": True, "selector": selector, "text_length": len(text), "url": page.url}

    async def click(self, selector: str) -> dict[str, Any]:
        async with self._lock:
            page = await self._page()
            await page.locator(selector).click()
            return {"ok": True, "selector": selector, "url": page.url}

    async def evaluate(self, js: str) -> dict[str, Any]:
        async with self._lock:
            page = await self._page()
            return {"result": await page.evaluate(js), "url": page.url}

    async def get_markdown(self, url: str | None = None) -> dict[str, Any]:
        async with self._lock:
            page = await self._page()
            if url:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
            html = await page.content()
            article = simple_json_from_html_string(html, use_readability=True)
            content_html = article.get("content") or html
            markdown = md(content_html, heading_style="ATX")
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            md_path = self.output_dir / f"page-{stamp}.md"
            md_path.write_text(markdown, encoding="utf-8")
            return {
                "url": page.url,
                "title": article.get("title") or await page.title(),
                "byline": article.get("byline"),
                "markdown": markdown,
                "path": str(md_path),
            }

    # --- WebAuthn / passkeys -------------------------------------------------
    # A CDP virtual authenticator lets the agent register and use passkeys fully
    # in software (the same mechanism Playwright uses to test WebAuthn). There is
    # no biometric hardware in the container, so this is the only way to drive
    # passkey flows. Credentials are software-backed and persisted to the profile.

    async def _webauthn_cdp(self):
        page = await self._page()
        session = await page.context.new_cdp_session(page)
        await session.send("WebAuthn.enable", {"enableUI": False})
        return session

    async def webauthn_enable(
        self,
        resident_key: bool = True,
        user_verification: bool = True,
        transport: str = "internal",
    ) -> dict[str, Any]:
        """Attach a virtual authenticator so the browser can create and use
        passkeys. Restores any previously persisted credentials."""
        async with self._lock:
            session = await self._webauthn_cdp()
            result = await session.send(
                "WebAuthn.addVirtualAuthenticator",
                {
                    "options": {
                        "protocol": "ctap2",
                        "transport": transport,
                        "hasResidentKey": resident_key,
                        "hasUserVerification": user_verification,
                        "isUserVerified": True,
                        "automaticPresenceSimulation": True,
                    }
                },
            )
            self._webauthn_authenticator_id = result["authenticatorId"]
            restored = await self._webauthn_restore(session)
            return {
                "ok": True,
                "authenticator_id": self._webauthn_authenticator_id,
                "resident_key": resident_key,
                "user_verification": user_verification,
                "restored_credentials": restored,
            }

    async def _webauthn_require(self):
        if not self._webauthn_authenticator_id:
            raise RuntimeError("WebAuthn not enabled — call webauthn_enable first")
        return await self._webauthn_cdp()

    async def webauthn_status(self) -> dict[str, Any]:
        async with self._lock:
            if not self._webauthn_authenticator_id:
                return {"enabled": False, "credentials": 0, "persisted": self.webauthn_state_file.exists()}
            session = await self._webauthn_cdp()
            try:
                result = await session.send(
                    "WebAuthn.getCredentials",
                    {"authenticatorId": self._webauthn_authenticator_id},
                )
                creds = result.get("credentials", [])
            except Exception:
                # authenticator went away (browser restart); mark disabled
                self._webauthn_authenticator_id = None
                return {"enabled": False, "credentials": 0, "persisted": self.webauthn_state_file.exists()}
            return {
                "enabled": True,
                "authenticator_id": self._webauthn_authenticator_id,
                "credentials": len(creds),
                "rp_ids": sorted({c.get("rpId") for c in creds if c.get("rpId")}),
                "persisted": self.webauthn_state_file.exists(),
            }

    async def webauthn_list_credentials(self) -> dict[str, Any]:
        async with self._lock:
            session = await self._webauthn_require()
            result = await session.send(
                "WebAuthn.getCredentials",
                {"authenticatorId": self._webauthn_authenticator_id},
            )
            creds = result.get("credentials", [])
            # Never return private keys to the agent; surface safe metadata only.
            safe = [
                {
                    "credentialId": c.get("credentialId"),
                    "rpId": c.get("rpId"),
                    "userHandle": c.get("userHandle"),
                    "signCount": c.get("signCount"),
                    "isResidentCredential": c.get("isResidentCredential"),
                }
                for c in creds
            ]
            return {"ok": True, "count": len(safe), "credentials": safe}

    async def webauthn_save(self) -> dict[str, Any]:
        """Persist the current credentials (incl. private keys) to the profile so
        passkeys survive a browser/container restart."""
        async with self._lock:
            session = await self._webauthn_require()
            result = await session.send(
                "WebAuthn.getCredentials",
                {"authenticatorId": self._webauthn_authenticator_id},
            )
            creds = result.get("credentials", [])
            self.webauthn_state_file.write_text(json.dumps(creds), encoding="utf-8")
            try:
                os.chmod(self.webauthn_state_file, 0o600)
            except PermissionError:
                pass
            return {"ok": True, "saved": len(creds), "path": str(self.webauthn_state_file)}

    async def _webauthn_restore(self, session) -> int:
        if not self.webauthn_state_file.exists():
            return 0
        try:
            creds = json.loads(self.webauthn_state_file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return 0
        restored = 0
        for c in creds:
            try:
                await session.send(
                    "WebAuthn.addCredential",
                    {"authenticatorId": self._webauthn_authenticator_id, "credential": c},
                )
                restored += 1
            except Exception:
                continue
        return restored

    async def webauthn_disable(self) -> dict[str, Any]:
        async with self._lock:
            if not self._webauthn_authenticator_id:
                return {"ok": True, "note": "already disabled"}
            session = await self._webauthn_cdp()
            try:
                await session.send(
                    "WebAuthn.removeVirtualAuthenticator",
                    {"authenticatorId": self._webauthn_authenticator_id},
                )
            except Exception:
                pass
            self._webauthn_authenticator_id = None
            return {"ok": True}


browser_service = BrowserService()
