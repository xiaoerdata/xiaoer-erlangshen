"""
Optional local Chrome web search for the CLI.

This is deliberately optional: users who want browser-backed search install
Playwright and a Chrome/Chromium browser locally.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus, urlparse


INSTALL_HINT = (
    "本地 Chrome 搜索需要安装可选依赖: "
    "python3 -m pip install playwright && python3 -m playwright install chrome"
)


def search_engine() -> str:
    engine = os.environ.get("ERLANGSHEN_SEARCH_ENGINE", "bing").strip().lower()
    return engine if engine in {"bing", "google"} else "bing"


def build_search_url(query: str, engine: str | None = None) -> str:
    selected = (engine or search_engine()).strip().lower()
    if selected == "google":
        return f"https://www.google.com/search?q={quote_plus(query)}"
    return f"https://www.bing.com/search?q={quote_plus(query)}&mkt=zh-CN"


def _is_noise_search_result(title: str, url: str) -> bool:
    title_text = " ".join(str(title or "").split()).lower()
    parsed = urlparse(str(url or ""))
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not title_text or not parsed.scheme.startswith("http"):
        return True
    blocked_hosts = {
        "accounts.google.com",
        "policies.google.com",
        "support.google.com",
    }
    if host in blocked_hosts or host.endswith(".google.com") and path.startswith("/sorry"):
        return True
    if host.endswith("google.com") and any(part in path for part in ("/policies", "/sorry")):
        return True
    if host.endswith("bing.com") and path in {"/search", "/images/search", "/videos/search"}:
        return True
    noise_titles = (
        "why did this happen",
        "terms of service",
        "privacy policy",
        "learn more",
        "google search help",
    )
    return any(text in title_text for text in noise_titles)


async def chrome_web_search(query: str, count: int = 5) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "error": "playwright_not_installed",
            "install": INSTALL_HINT,
            "results": [],
        }

    engine = search_engine()
    url = build_search_url(query, engine)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=True)
            page = await browser.new_page(
                locale="zh-CN",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            selector = "li.b_algo a" if engine == "bing" else "a"
            items = await page.locator(selector).evaluate_all(
                """
                (links) => links
                  .map((a) => ({title: (a.innerText || '').trim(), url: a.href || ''}))
                  .filter((item) => item.title && item.url.startsWith('http'))
                  .slice(0, 20)
                """
            )
            if not items:
                items = await page.locator("a").evaluate_all(
                    """
                    (links) => links
                      .map((a) => ({title: (a.innerText || '').trim(), url: a.href || ''}))
                      .filter((item) => item.title && item.url.startsWith('http'))
                      .slice(0, 30)
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
        if not title or link in seen or _is_noise_search_result(title, link):
            continue
        seen.add(link)
        results.append({"title": title, "url": link, "source": f"local_chrome/{engine}"})
        if len(results) >= max(1, min(count, 10)):
            break
    return {
        "query": query,
        "provider": "local_chrome",
        "engine": engine,
        "results": results,
        "total": len(results),
    }
