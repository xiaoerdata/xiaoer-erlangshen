"""
Optional local Chrome web search for the CLI.

This is deliberately optional: users who want browser-backed search install
Playwright and a Chrome/Chromium browser locally.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


INSTALL_HINT = (
    "本地 Chrome 搜索需要安装可选依赖: "
    "python3 -m pip install playwright && python3 -m playwright install chrome"
)


async def chrome_web_search(query: str, count: int = 5) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "error": "playwright_not_installed",
            "install": INSTALL_HINT,
            "results": [],
        }

    url = f"https://www.google.com/search?q={quote_plus(query)}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            items = await page.locator("a").evaluate_all(
                """
                (links) => links
                  .map((a) => ({title: (a.innerText || '').trim(), url: a.href || ''}))
                  .filter((item) => item.title && item.url.startsWith('http'))
                  .slice(0, 20)
                """
            )
            await browser.close()
    except Exception as exc:
        return {
            "error": "chrome_search_failed",
            "detail": str(exc),
            "install": INSTALL_HINT,
            "results": [],
        }

    seen = set()
    results = []
    for item in items:
        link = item.get("url", "")
        title = " ".join(str(item.get("title", "")).split())
        if not title or link in seen:
            continue
        seen.add(link)
        results.append({"title": title, "url": link, "source": "local_chrome"})
        if len(results) >= max(1, min(count, 10)):
            break
    return {"query": query, "provider": "local_chrome", "results": results, "total": len(results)}
