"""Captcha resolver service using direct CDP commands.

Clicks the Turnstile checkbox using Chrome DevTools Protocol directly,
bypassing PyAutoGUI which doesn't work on Wayland.
"""

import asyncio
import json
import logging
import os
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class CaptchaService:
    def __init__(self):
        self._cdp_port = int(os.getenv("BROWSER_CDP_PORT", "9222"))
        self._cdp_host = os.getenv("BROWSER_CDP_BIND", "127.0.0.1")

    async def solve_turnstile(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        return await self._run_solve(url, timeout)

    async def solve_recaptcha(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        return await self._run_solve(url, timeout)

    async def solve_cloudflare(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        return await self._run_solve(url, timeout)

    async def solve_captcha(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        return await self._run_solve(url, timeout)

    async def _run_solve(self, url: str | None, timeout: int) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._solve_blocking, url, timeout)

    def _get_page_ws(self) -> str:
        resp = urllib.request.urlopen(
            f"http://{self._cdp_host}:{self._cdp_port}/json", timeout=5
        )
        for p in json.loads(resp.read()):
            if p.get("type") == "page":
                return p["webSocketDebuggerUrl"]
        raise RuntimeError("No page found")

    def _solve_blocking(self, url: str | None, timeout: int) -> dict[str, Any]:
        try:
            import websocket

            page_ws = self._get_page_ws()
            ws = websocket.create_connection(page_ws, timeout=10)
            msg_id = 0

            def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                cmd = {"id": msg_id, "method": method}
                if params:
                    cmd["params"] = params
                ws.send(json.dumps(cmd))
                while True:
                    r = json.loads(ws.recv())
                    if r.get("id") == msg_id:
                        return r.get("result", {})

            def eval_js(expr):
                r = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
                return r.get("result", {}).get("value")

            # Navigate if URL provided
            if url:
                send("Page.navigate", {"url": url})
                time.sleep(5)

            # Find the Turnstile iframe and get its position
            click_result = eval_js("""
            (function() {
                // Find turnstile container
                var container = document.querySelector('.cf-turnstile, [id*="turnstile"]');
                if (!container) return JSON.stringify({error: 'no_container'});

                var rect = container.getBoundingClientRect();
                // Click at center-left where the checkbox is
                var clickX = rect.left + 25;
                var clickY = rect.top + rect.height / 2;
                return JSON.stringify({x: clickX, y: clickY, w: rect.width, h: rect.height});
            })()
            """)

            if not click_result or '"error"' in str(click_result):
                # Try iframe approach
                click_result = eval_js("""
                (function() {
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        var src = iframes[i].src || '';
                        if (src.includes('turnstile') || src.includes('challenges.cloudflare')) {
                            var rect = iframes[i].getBoundingClientRect();
                            return JSON.stringify({x: rect.left + 25, y: rect.top + rect.height / 2, w: rect.width, h: rect.height});
                        }
                    }
                    return JSON.stringify({error: 'no_iframe'});
                })()
                """)

            if click_result and '"error"' not in str(click_result):
                coords = json.loads(click_result)
                x, y = coords["x"], coords["y"]
                logger.info("Clicking Turnstile at (%s, %s)", x, y)

                # Dispatch mouse events via CDP
                send("Input.dispatchMouseEvent", {
                    "type": "mouseMoved", "x": x, "y": y
                })
                time.sleep(0.1)
                send("Input.dispatchMouseEvent", {
                    "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1
                })
                time.sleep(0.05)
                send("Input.dispatchMouseEvent", {
                    "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1
                })

                # Wait for resolution
                time.sleep(8)

            # Check success
            solved = eval_js("""
            (function() {
                var s = document.querySelector('img#captcha-success');
                if (s && s.style.display !== 'none') return true;
                var r = document.querySelector('[name="cf-turnstile-response"]');
                if (r && r.value) return true;
                return false;
            })()
            """)

            final_url = eval_js("location.href") or ""
            final_title = eval_js("document.title") or ""

            ws.close()

            return {
                "ok": bool(solved),
                "captcha_type": "turnstile",
                "url": final_url,
                "title": final_title,
            }

        except Exception as e:
            logger.error("Captcha solve failed: %s", e)
            return {"ok": False, "error": str(e), "captcha_type": "turnstile"}


captcha_service = CaptchaService()
