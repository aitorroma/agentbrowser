"""Captcha resolver service using SeleniumBase CDP Mode.

Connects to the existing Chrome instance via CDP and uses SeleniumBase's
built-in captcha solvers for Turnstile, reCAPTCHA, Cloudflare, etc.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CaptchaService:
    """Resolve captchas using SeleniumBase CDP Mode against the running Chrome."""

    def __init__(self):
        import os
        self._cdp_port = int(os.getenv("BROWSER_CDP_PORT", "9222"))

    async def solve_turnstile(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        """Solve a Cloudflare Turnstile captcha on the current or given page."""
        return await self._run_solve("turnstile", url, timeout)

    async def solve_recaptcha(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        """Solve a Google reCAPTCHA on the current or given page."""
        return await self._run_solve("recaptcha", url, timeout)

    async def solve_cloudflare(self, url: str | None = None, timeout: int = 30) -> Any:
        """Solve a Cloudflare challenge (Turnstile or JS challenge)."""
        return await self._run_solve("cloudflare", url, timeout)

    async def solve_captcha(self, url: str | None = None, timeout: int = 30) -> dict[str, Any]:
        """Auto-detect and solve any supported captcha."""
        return await self._run_solve("auto", url, timeout)

    async def _run_solve(self, captcha_type: str, url: str | None, timeout: int) -> dict[str, Any]:
        """Run captcha solver in a thread to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._solve_blocking,
            captcha_type,
            url,
            timeout,
        )

    def _solve_blocking(self, captcha_type: str, url: str | None, timeout: int) -> dict[str, Any]:
        """Synchronous captcha solving using sb_cdp.Chrome() connected to existing CDP."""
        try:
            from seleniumbase import sb_cdp

            # Connect to existing Chrome via CDP on the configured port
            sb = sb_cdp.Chrome(cdp_port=self._cdp_port)

            try:
                # Navigate to URL if provided
                if url:
                    sb.goto(url)
                    sb.sleep(3)

                # Wait for captcha widget to appear
                sb.sleep(1)

                # Detect captcha type and solve
                solved = False
                detected_type = "unknown"

                # Try Turnstile
                if captcha_type in ("turnstile", "auto"):
                    try:
                        sb.wait_for_element(
                            '[class*="cf-turnstile"], [id*="turnstile"], iframe[src*="turnstile"]',
                            timeout=5,
                        )
                        detected_type = "turnstile"
                        sb.solve_captcha()
                        solved = True
                    except Exception:
                        pass

                # Try reCAPTCHA
                if not solved and captcha_type in ("recaptcha", "auto"):
                    try:
                        sb.wait_for_element(
                            'iframe[src*="recaptcha"], .g-recaptcha, [class*="recaptcha"]',
                            timeout=5,
                        )
                        detected_type = "recaptcha"
                        sb.solve_captcha()
                        solved = True
                    except Exception:
                        pass

                # Try Cloudflare challenge
                if not solved and captcha_type in ("cloudflare", "auto"):
                    try:
                        sb.wait_for_element(
                            '[class*="challenge"], [id*="challenge-widget"]',
                            timeout=5,
                        )
                        detected_type = "cloudflare"
                        sb.sleep(2)
                        sb.solve_captcha()
                        solved = True
                    except Exception:
                        pass

                # Generic solve attempt
                if not solved and captcha_type == "auto":
                    try:
                        detected_type = "generic"
                        sb.solve_captcha()
                        solved = True
                    except Exception as e:
                        return {
                            "ok": False,
                            "error": str(e),
                            "captcha_type": "unknown",
                        }

                # Check for success indicators
                success = False
                try:
                    sb.wait_for_element(
                        'img#captcha-success, [class*="success"], [class*="verified"]',
                        timeout=5,
                    )
                    success = True
                except Exception:
                    # No explicit success element - check if page advanced
                    success = not sb.is_element_present(
                        '[class*="error"], [class*="failed"], img#captcha-failure'
                    )

                return {
                    "ok": success,
                    "captcha_type": detected_type,
                    "url": sb.get_current_url(),
                    "title": sb.get_title(),
                }

            finally:
                # Do NOT close the browser - we don't own it
                # Just release the CDP connection
                pass

        except Exception as e:
            logger.error("Captcha solve failed: %s", e)
            return {
                "ok": False,
                "error": str(e),
                "captcha_type": captcha_type,
            }


captcha_service = CaptchaService()
