"""
Required local Chrome/Chromium web search for evidence-backed CLI analysis.

The npm installer installs Playwright and a bundled Chromium browser by default.
If a user has Google Chrome available, the search path uses it first and then
falls back to Playwright's Chromium.
"""

from __future__ import annotations

import base64
import os
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse


INSTALL_HINT = (
    "web_search 是财报、公告、新闻和事件验证的关键能力；请安装依赖: "
    "python -m pip install playwright && python -m playwright install chromium"
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
        _add_result(
            results,
            seen,
            f"Nasdaq {ticker} earnings/forecast",
            f"https://www.nasdaq.com/market-activity/stocks/{ticker_lower}/earnings",
            "professional_source/nasdaq",
            "用于核对 earnings、consensus estimate 和 surprise。",
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


def _build_web_search_results(
    items: list[dict[str, str]],
    query: str,
    *,
    count: int,
    browser_label: str,
    engine: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    seen = set()
    results = []
    for item in items:
        link = normalize_search_result_url(item.get("url", ""))
        title = " ".join(str(item.get("title", "")).split())
        snippet = " ".join(str(item.get("snippet", "")).split())
        if not title:
            parsed = urlparse(str(link))
            title = parsed.netloc.replace("www.", "") if parsed.netloc else ""
        if not title or link in seen or _is_noise_search_result(title, link):
            continue
        seen.add(link)
        result = {"title": title, "url": link, "source": f"local_{browser_label}/{engine}"}
        if snippet:
            result["snippet"] = snippet[:500]
        results.append(result)
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
    return results, fallback_results


def _finance_page_snippet(text: str, query: str, *, max_len: int = 900) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return ""
    keywords = [
        "基本面摘要",
        "市盈率",
        "每股收益",
        "市值",
        "52周",
        "成交量",
        "财报",
        "营收",
        "现金流",
        "目标价",
        "评级",
        "分析师",
        "Revenues",
        "revenue",
        "Operating income",
        "Net income",
        "Diluted earnings per share",
        "earnings per share",
        "capital expenditures",
        "CapEx",
        "buyback",
        "repurchase",
        "Google Cloud",
        "advertising",
        "Search",
    ]
    ticker, company = _extract_us_stock_identity(query)
    for token in (ticker, company.split("/", 1)[0] if company else ""):
        if token:
            keywords.append(token)
    lower = clean.lower()
    windows: list[str] = []
    for keyword in keywords:
        needle = keyword.lower()
        idx = lower.find(needle)
        if idx < 0:
            continue
        start = max(0, idx - 180)
        end = min(len(clean), idx + 520)
        window = clean[start:end].strip(" ，。；|")
        if window and not any(window in item or item in window for item in windows):
            windows.append(window)
        if len("；".join(windows)) >= max_len:
            break
    if not windows and _looks_like_finance_research_query(query):
        windows.append(clean[:max_len])
    snippet = "；".join(windows)
    return snippet[:max_len].strip()


async def _extract_page_text_snippet(browser: Any, url: str, query: str) -> tuple[str, list[dict[str, str]]]:
    if not url or url.lower().endswith((".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "", []
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host.endswith("eastmoney.com") and "/web/s" in path:
        return "", []
    if host == "cn.investing.com" and path.startswith("/search"):
        return "", []
    if host.endswith("sec.gov") and "/edgar/browse" in path:
        return "", []
    page = await browser.new_page(
        locale="zh-CN",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
    )
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=12000)
        await page.wait_for_timeout(1800 if parsed.netloc.lower().endswith("finance.sina.com.cn") else 800)
        text = await page.locator("body").inner_text(timeout=5000)
        snippet = _finance_page_snippet(text, query)
        related_links: list[dict[str, str]] = []
        if parsed.netloc.lower().endswith("abc.xyz"):
            related_links = await page.locator("a").evaluate_all(
                """
                (links) => links
                  .map((a) => ({
                    title: (a.innerText || a.textContent || a.getAttribute('aria-label') || '').trim(),
                    url: a.href || ''
                  }))
                  .filter((item) => item.title && item.url && /earnings|10-q|10-k|quarter|results|financials|sec/i.test(item.title + ' ' + item.url))
                  .slice(0, 10)
                """
            )
        return snippet, related_links
    except Exception:
        return "", []
    finally:
        await page.close()


async def _enrich_finance_results_with_page_snippets(browser: Any, results: list[dict[str, str]], query: str) -> bool:
    if not _looks_like_finance_research_query(query) or not results:
        return False
    enriched = False
    checked = 0
    preferred_hosts = (
        "finance.sina.com.cn",
        "nasdaq.com",
        "abc.xyz",
        "finance.yahoo.co.jp",
    )
    for item in results:
        if checked >= 2:
            break
        url = str(item.get("url") or "")
        host = urlparse(url).netloc.lower()
        if not any(marker in host for marker in preferred_hosts):
            continue
        checked += 1
        snippet, related_links = await _extract_page_text_snippet(browser, url, query)
        if snippet:
            existing = str(item.get("snippet") or "")
            if len(snippet) > len(existing):
                item["snippet"] = snippet
                item["content_status"] = "page_snippet_extracted"
                enriched = True
        if related_links:
            item["related_links"] = related_links
            enriched = True
    return enriched


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
    browser_label = "chrome"
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=True)
            except Exception:
                browser = await p.chromium.launch(headless=True)
                browser_label = "chromium"
            try:
                page = await browser.new_page(
                    locale="zh-CN",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                if engine == "bing":
                    items = await page.locator("li.b_algo").evaluate_all(
                        """
                        (nodes) => nodes
                          .map((node) => {
                            const a = node.querySelector('h2 a');
                            const snippet = node.querySelector('.b_caption p, p');
                            return {
                              title: ((a && (a.innerText || a.textContent || a.getAttribute('aria-label') || a.getAttribute('title'))) || '').trim(),
                              url: (a && a.href) || '',
                              snippet: ((snippet && (snippet.innerText || snippet.textContent)) || '').trim()
                            };
                          })
                          .filter((item) => item.title && item.url.startsWith('http'))
                          .slice(0, 20)
                        """
                    )
                else:
                    items = await page.locator("a").evaluate_all(
                        """
                        (links) => links
                          .map((a) => ({
                            title: (a.innerText || a.textContent || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim(),
                            url: a.href || '',
                            snippet: ''
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
                            url: a.href || '',
                            snippet: ''
                          }))
                          .filter((item) => item.title && item.url.startsWith('http'))
                          .slice(0, 30)
                        """
                    )
                results, fallback_results = _build_web_search_results(
                    items,
                    query,
                    count=count,
                    browser_label=browser_label,
                    engine=engine,
                )
                enriched = await _enrich_finance_results_with_page_snippets(browser, results, query)
                return {
                    "query": query,
                    "provider": "local_chrome" + ("+professional_source_fallback" if fallback_results else ""),
                    "engine": engine,
                    "results": results,
                    "total": len(results),
                    "quality": (
                        "fallback_source_entries_with_page_snippets"
                        if fallback_results and enriched
                        else "fallback_source_entries"
                        if fallback_results
                        else "search_results_with_page_snippets"
                        if enriched
                        else "search_results"
                    ),
                    "fallback_reason": "search_results_missing_or_low_quality" if fallback_results else "",
                }
            finally:
                await browser.close()
    except Exception as exc:
        return {
            "error": "chrome_search_failed",
            "detail": str(exc),
            "install": INSTALL_HINT,
            "results": [],
        }
