#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

CDP_JSON = "http://127.0.0.1:9222/json/version"
API_BASE = "http://127.0.0.1:8787"
OUT = Path("output")
OUT.mkdir(exist_ok=True)
TEST_URLS = [
    ("fingerprint", "https://www.whatismybrowser.com/"),
    ("cloudflare", "https://www.cloudflare.com/"),
]


async def main() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        version = (await client.get(CDP_JSON)).json()
        print("CDP:", version["webSocketDebuggerUrl"])

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(version["webSocketDebuggerUrl"])
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        results = {}
        async with httpx.AsyncClient(timeout=60.0) as client:
            for name, url in TEST_URLS:
                response = await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                title = await page.title()
                body_text = await page.locator("body").inner_text()
                shot = OUT / f"{name}.png"
                await page.screenshot(path=str(shot), full_page=True)
                md = (await client.get(f"{API_BASE}/markdown", params={"url": url})).json()
                (OUT / f"{name}.md").write_text(md["markdown"], encoding="utf-8")
                results[name] = {
                    "url": page.url,
                    "status": response.status if response else None,
                    "title": title,
                    "navigator_webdriver": await page.evaluate("navigator.webdriver"),
                    "user_agent": await page.evaluate("navigator.userAgent"),
                    "looks_like_challenge": "challenge" in title.lower() or "verify you are human" in body_text.lower(),
                    "screenshot": str(shot),
                    "markdown": str(OUT / f"{name}.md"),
                }
        print(json.dumps(results, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
