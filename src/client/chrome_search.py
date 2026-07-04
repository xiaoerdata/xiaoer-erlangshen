"""
Optional local Chrome web search for the CLI.

This is deliberately optional: users who want browser-backed search install
Playwright and a Chrome/Chromium browser locally.
"""

from __future__ import annotations

import base64
import os
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse


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


KNOWN_US_STOCKS = {
    "谷歌": ("GOOGL", "Alphabet/Google"),
    "google": ("GOOGL", "Alphabet/Google"),
    "alphabet": ("GOOGL", "Alphabet/Google"),
    "英伟达": ("NVDA", "NVIDIA"),
    "nvidia": ("NVDA", "NVIDIA"),
    "苹果": ("AAPL", "Apple"),
    "apple": ("AAPL", "Apple"),
    "微软": ("MSFT", "Microsoft"),
    "microsoft": ("MSFT", "Microsoft"),
    "亚马逊": ("AMZN", "Amazon"),
    "amazon": ("AMZN", "Amazon"),
    "特斯拉": ("TSLA", "Tesla"),
    "tesla": ("TSLA", "Tesla"),
    "meta": ("META", "Meta"),
    "facebook": ("META", "Meta"),
    "脸书": ("META", "Meta"),
}

KNOWN_IR_URLS = {
    "GOOGL": "https://abc.xyz/investor/",
    "GOOG": "https://abc.xyz/investor/",
    "NVDA": "https://investor.nvidia.com/financial-info/quarterly-results/default.aspx",
    "AAPL": "https://investor.apple.com/investor-relations/default.aspx",
    "MSFT": "https://www.microsoft.com/en-us/investor",
    "AMZN": "https://ir.aboutamazon.com/overview/default.aspx",
    "TSLA": "https://ir.tesla.com/",
    "META": "https://investor.fb.com/",
}


def _decode_bing_redirect_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if not parsed.netloc.lower().endswith("bing.com") or not parsed.path.lower().startswith("/ck/a"):
        return ""
    params = parse_qs(parsed.query)
    raw = (params.get("u") or params.get("url") or [""])[0]
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return unquote(raw)
    if raw.startswith("a1"):
        raw = raw[2:]
    try:
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return decoded if decoded.startswith(("http://", "https://")) else ""


def normalize_search_result_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if not parsed.scheme.startswith("http"):
        return str(url or "")
    host = parsed.netloc.lower()
    if host.endswith("bing.com") and parsed.path.lower().startswith("/ck/a"):
        decoded = _decode_bing_redirect_url(url)
        return decoded or str(url)
    if host.endswith("google.com") and parsed.path.lower().startswith("/url"):
        target = (parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("url") or [""])[0]
        if target.startswith(("http://", "https://")):
            return unquote(target)
    return str(url)


def _is_noise_search_result(title: str, url: str) -> bool:
    title_text = " ".join(str(title or "").split()).lower()
    parsed = urlparse(normalize_search_result_url(str(url or "")))
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not title_text or not parsed.scheme.startswith("http"):
        return True
    blocked_hosts = {
        "accounts.google.com",
        "policies.google.com",
        "support.google.com",
    }
    if host in blocked_hosts or host.startswith("support.google.") or host.startswith("chrome.google."):
        return True
    if host.endswith(".google.com") and path.startswith("/sorry"):
        return True
    if host.endswith("google.com") and any(part in path for part in ("/policies", "/sorry")):
        return True
    if host in {"www.google.com", "google.com", "www.google.com.hk", "google.com.hk", "www.google.cn", "google.cn"} and (
        title_text == "google" or path in {"", "/"} or path.startswith(("/intl/", "/custom", "/ig/", "/chrome"))
    ):
        return True
    if host.endswith("google.com") and title_text in {"google", "chrome", "google chrome"}:
        return True
    if host.endswith("bing.com") and not path.startswith("/ck/a"):
        return True
    noise_titles = (
        "why did this happen",
        "terms of service",
        "privacy policy",
        "learn more",
        "google search help",
    )
    return any(text in title_text for text in noise_titles)


def _extract_us_stock_identity(query: str) -> tuple[str, str]:
    text = str(query or "")
    compact = "".join(text.lower().split())
    for alias, identity in KNOWN_US_STOCKS.items():
        if alias in compact:
            return identity
    ignored = {"SEC", "EPS", "AI", "PE", "PB", "ROE", "ROIC", "ETF", "CEO", "CFO", "IPO"}
    for match in re_find_us_tickers(text):
        ticker = match.upper()
        if ticker not in ignored:
            return ticker, ticker
    return "", ""


def re_find_us_tickers(text: str) -> list[str]:
    import re

    return [
        match.group(1)
        for match in re.finditer(r"(?<![A-Za-z])([A-Z]{2,5})(?:\.(?:US|O|N))?(?![A-Za-z])", text or "")
    ]


def _looks_like_finance_research_query(query: str) -> bool:
    text = "".join(str(query or "").lower().split())
    markers = (
        "股票",
        "美股",
        "港股",
        "a股",
        "财报",
        "财务",
        "估值",
        "eps",
        "营收",
        "现金流",
        "分析师",
        "目标价",
        "研报",
        "评级",
        "基金",
        "基金经理",
        "持仓",
        "净值",
        "东方财富",
        "新浪财经",
        "英为财情",
        "investing",
        "sec",
        "investorrelations",
    )
    return any(marker in text for marker in markers) or bool(_extract_us_stock_identity(query)[0])


def _looks_like_fund_manager_query(query: str) -> bool:
    text = "".join(str(query or "").lower().split())
    return "基金经理" in text or ("基金" in text and any(word in text for word in ("管理", "任职", "持仓", "旗下")))


def _is_relevant_finance_result(query: str, item: dict[str, str]) -> bool:
    title = str(item.get("title") or "")
    url = str(item.get("url") or "")
    combined = f"{title} {url}".lower()
    if _looks_like_fund_manager_query(query):
        compact_query = "".join(str(query or "").split())
        manager_names = [
            part
            for part in re_find_chinese_terms(compact_query)
            if 2 <= len(part) <= 6 and part not in {"基金经理", "基金公司", "东方财富", "天天基金", "同花顺"}
        ]
        return any(name in title or name.lower() in combined for name in manager_names) or any(
            marker in combined
            for marker in (
                "基金经理",
                "fund",
                "eastmoney",
                "tiantianfund",
                "iwencai",
                "10jqka",
                "gelonghui",
                "持仓",
                "净值",
                "公募",
                "私募",
            )
        )
    ticker, company = _extract_us_stock_identity(query)
    source_markers = (
        "eastmoney",
        "finance.sina.com.cn",
        "finance.yahoo.com",
        "investing.com",
        "xueqiu.com",
        "futunn",
        "itiger",
        "nasdaq.com",
        "sec.gov",
        "cnbc.com",
    )
    if ticker:
        import re

        if re.search(rf"(?<![a-z0-9]){re.escape(ticker.lower())}(?![a-z0-9])", combined):
            return True
    if company and company.lower().split("/", 1)[0] in combined and "investor" in combined:
        return True
    return any(marker in combined for marker in source_markers)


def re_find_chinese_terms(text: str) -> list[str]:
    import re

    return re.findall(r"[\u4e00-\u9fff]{2,12}", text or "")


def _add_result(results: list[dict[str, str]], seen: set[str], title: str, url: str, source: str, snippet: str = "") -> None:
    if not url or url in seen or _is_noise_search_result(title, url):
        return
    seen.add(url)
    item = {"title": title, "url": url, "source": source}
    if snippet:
        item["snippet"] = snippet
    results.append(item)


def professional_source_fallback_results(query: str, count: int = 5) -> list[dict[str, str]]:
    """Return deterministic finance research entry points when search pages degrade."""
    if not _looks_like_finance_research_query(query):
        return []
    limit = max(1, min(count, 10))
    encoded_query = quote_plus(query)
    ticker, company = _extract_us_stock_identity(query)
    ticker_lower = ticker.lower()
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    base_snippet = "搜索通道质量不足时的专业来源入口；需打开来源核对事实后再写结论。"

    if _looks_like_fund_manager_query(query):
        _add_result(
            results,
            seen,
            f"东方财富基金经理检索: {query[:24]}",
            f"https://so.eastmoney.com/web/s?keyword={encoded_query}",
            "professional_source/eastmoney",
            base_snippet,
        )
        _add_result(
            results,
            seen,
            "天天基金基金经理列表入口",
            "https://fund.eastmoney.com/manager/default.html",
            "professional_source/tiantianfund",
            "用于核对基金经理归属、在管产品和任职历史。",
        )
        _add_result(
            results,
            seen,
            f"同花顺问财基金经理检索: {query[:24]}",
            f"https://www.iwencai.com/unifiedwap/result?w={encoded_query}",
            "professional_source/iwencai",
            base_snippet,
        )

    _add_result(
        results,
        seen,
        f"东方财富财经检索: {query[:24]}",
        f"https://so.eastmoney.com/web/s?keyword={encoded_query}",
        "professional_source/eastmoney",
        base_snippet,
    )
    if ticker:
        _add_result(
            results,
            seen,
            f"新浪财经美股 {ticker} 行情/财务入口",
            f"https://stock.finance.sina.com.cn/usstock/quotes/{ticker}.html",
            "professional_source/sina_finance",
            "中国网络环境下较常用的美股行情、财务和新闻入口。",
        )
        _add_result(
            results,
            seen,
            f"英为财情 {ticker} 财报/预测检索",
            f"https://cn.investing.com/search/?q={quote_plus(ticker)}",
            "professional_source/investing",
            "用于核对 EPS、营收、分析师预测和目标价口径。",
        )
        _add_result(
            results,
            seen,
            f"SEC EDGAR {ticker} 官方披露入口",
            f"https://www.sec.gov/edgar/browse/?CIK={ticker}&owner=exclude",
            "official_source/sec",
            "官方 10-Q/10-K/8-K 披露入口，用于交叉验证财报事实。",
        )
        _add_result(
            results,
            seen,
            f"Nasdaq {ticker} earnings/forecast",
            f"https://www.nasdaq.com/market-activity/stocks/{ticker_lower}/earnings",
            "professional_source/nasdaq",
            "用于核对 earnings、consensus estimate 和 surprise。",
        )
        ir_url = KNOWN_IR_URLS.get(ticker)
        if ir_url:
            _add_result(
                results,
                seen,
                f"{company} Investor Relations 官方入口",
                ir_url,
                "official_source/investor_relations",
                "公司官方投资者关系页面，用于核对财报新闻稿、电话会材料和回购/CapEx 信息。",
            )
    else:
        _add_result(
            results,
            seen,
            f"英为财情检索: {query[:24]}",
            f"https://cn.investing.com/search/?q={encoded_query}",
            "professional_source/investing",
            base_snippet,
        )

    return results[:limit]


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
            selector = "li.b_algo h2 a, .b_algo h2 a" if engine == "bing" else "a"
            items = await page.locator(selector).evaluate_all(
                """
                (links) => links
                  .map((a) => ({
                    title: (a.innerText || a.textContent || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim(),
                    url: a.href || ''
                  }))
                  .filter((item) => item.title && item.url.startsWith('http'))
                  .slice(0, 20)
                """
            )
            if not items:
                items = await page.locator("a").evaluate_all(
                    """
                    (links) => links
                      .map((a) => ({
                        title: (a.innerText || a.textContent || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim(),
                        url: a.href || ''
                      }))
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
        link = normalize_search_result_url(item.get("url", ""))
        title = " ".join(str(item.get("title", "")).split())
        if not title:
            parsed = urlparse(str(link))
            title = parsed.netloc.replace("www.", "") if parsed.netloc else ""
        if not title or link in seen or _is_noise_search_result(title, link):
            continue
        seen.add(link)
        results.append({"title": title, "url": link, "source": f"local_chrome/{engine}"})
        if len(results) >= max(1, min(count, 10)):
            break
    fallback_results: list[dict[str, str]] = []
    if _looks_like_finance_research_query(query):
        relevant_results = [item for item in results if _is_relevant_finance_result(query, item)]
        if len(relevant_results) < len(results):
            results = relevant_results
            seen = {item.get("url", "") for item in results}
    if _looks_like_finance_research_query(query) and len(results) < min(max(1, count), 5):
        fallback_results = professional_source_fallback_results(query, count=max(1, min(count, 10)))
        for item in fallback_results:
            link = item.get("url", "")
            if link in seen:
                continue
            seen.add(link)
            results.append(item)
            if len(results) >= max(1, min(count, 10)):
                break
    return {
        "query": query,
        "provider": "local_chrome" + ("+professional_source_fallback" if fallback_results else ""),
        "engine": engine,
        "results": results,
        "total": len(results),
        "quality": "fallback_source_entries" if fallback_results else "search_results",
        "fallback_reason": "search_results_missing_or_low_quality" if fallback_results else "",
    }
