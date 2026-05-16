"""
Search Tools - 搜索工具
提供网络搜索、新闻搜索、公司信息查询、学术搜索

支持多种搜索源:
- MiniMax MCP (已有联网能力)
- DuckDuckGo (无需 API Key)
- SerpAPI (可选付费API)
"""
from typing import Optional, Any, TypedDict, List
from datetime import datetime
from loguru import logger
import aiohttp
import asyncio
import json


class SearchResult(TypedDict):
    """搜索结果类型"""
    title: str
    url: str
    snippet: str
    source: str
    date: Optional[str]


class NewsResult(TypedDict):
    """新闻结果类型"""
    title: str
    url: str
    snippet: str
    source: str
    date: str


class AcademicResult(TypedDict):
    """学术结果类型"""
    title: str
    url: str
    authors: List[str]
    abstract: str
    year: Optional[int]
    venue: Optional[str]


class CompanyInfo(TypedDict):
    """公司信息类型"""
    name: str
    ticker: str
    exchange: str
    industry: str
    sector: Optional[str]
    market_cap: float
    pe_ratio: Optional[float]
    description: str
    website: Optional[str]
    headquarters: Optional[str]


class SearchTools:
    """
    搜索工具集

    工具函数：
    - web_search: 网络搜索 (支持中英文)
    - news_search: 新闻搜索 (支持时间范围过滤)
    - academic_search: 学术搜索 (论文、研报)
    - company_search: 公司信息搜索
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._ddg_session: Optional[aiohttp.ClientSession] = None
        self._cache: dict = {}
        self._cache_ttl = self.config.get("cache_ttl", 300)  # 5分钟缓存
        logger.info("SearchTools initialized with global search support")

    async def execute(self, tool_name: str, **kwargs) -> Any:
        """执行指定工具"""
        method = getattr(self, tool_name, None)
        if method and callable(method):
            return await method(**kwargs)
        return {"error": f"Unknown tool: {tool_name}"}

    # ==================== 网络搜索 ====================

    async def web_search(
        self,
        query: str,
        language: str = "zh",
        count: int = 10,
        provider: str = "duckduckgo",
    ) -> dict:
        """
        网络搜索

        Args:
            query: 搜索关键词
            language: 语言偏好 (zh/en/auto)
            count: 返回结果数量 (1-20)
            provider: 搜索提供商 (duckduckgo/serpapi/minimax)

        Returns:
            dict 搜索结果，包含 title, url, snippet, source, date
        """
        logger.info(f"Web search: {query} (provider={provider}, lang={language})")
        
        # 检查缓存
        cache_key = f"web:{provider}:{language}:{query}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            if provider == "duckduckgo":
                results = await self._duckduckgo_search(query, language, count)
            elif provider == "serpapi":
                results = await self._serpapi_search(query, language, count)
            elif provider == "minimax":
                results = await self._minimax_search(query, language, count)
            else:
                # 默认使用 DuckDuckGo
                results = await self._duckduckgo_search(query, language, count)

            response = {
                "query": query,
                "language": language,
                "provider": provider,
                "results": results,
                "total": len(results),
                "timestamp": datetime.now().isoformat(),
            }
            
            self._set_cached(cache_key, response)
            return response

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {
                "query": query,
                "results": [],
                "error": str(e),
                "total": 0,
            }

    async def _duckduckgo_search(
        self,
        query: str,
        language: str,
        count: int,
    ) -> List[SearchResult]:
        """使用 DuckDuckGo HTML 搜索 (无需 API Key)"""
        import urllib.parse
        
        # DuckDuckGo HTML search
        params = {
            "q": query,
            "kl": "wt-wt" if language == "en" else "cn-zh",
            "ia": "news" if "news" in query.lower() else "web",
        }
        
        url = f"https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    html = await resp.text()
                    
            results = self._parse_ddg_html(html, count)
            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}, trying alternative...")
            return await self._duckduckgolite_search(query, language, count)

    async def _duckduckgolite_search(
        self,
        query: str,
        language: str,
        count: int,
    ) -> List[SearchResult]:
        """DuckDuckGo Lite 搜索 (备选方案)"""
        import urllib.parse
        
        params = {
            "q": query,
            "format": "json",
        }
        
        url = f"https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode(params)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    text = await resp.text()
                    
            results = self._parse_ddg_lite(text, count)
            return results
        except Exception as e:
            logger.error(f"DuckDuckGo Lite failed: {e}")
            return []

    def _parse_ddg_html(self, html: str, count: int) -> List[SearchResult]:
        """解析 DuckDuckGo HTML 结果"""
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            for result in soup.select(".result")[:count]:
                title_elem = result.select_one(".result__title a")
                snippet_elem = result.select_one(".result__snippet")
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get("href", "")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="DuckDuckGo",
                        date=None,
                    ))
        except ImportError:
            logger.warning("BeautifulSoup not installed, using regex parsing")
            results = self._parse_ddg_regex(html, count)
        except Exception as e:
            logger.error(f"Failed to parse DDG HTML: {e}")
            
        return results

    def _parse_ddg_regex(self, text: str, count: int) -> List[SearchResult]:
        """使用正则表达式解析 DuckDuckGo 结果 (备选)"""
        import re
        results = []
        
        # 简单正则匹配
        pattern = r'<a class="result__a" href="([^"]+)">([^<]+)</a>'
        matches = re.findall(pattern, text)
        
        for url, title in matches[:count]:
            results.append(SearchResult(
                title=title.strip(),
                url=url,
                snippet="",
                source="DuckDuckGo",
                date=None,
            ))
        
        return results

    def _parse_ddg_lite(self, text: str, count: int) -> List[SearchResult]:
        """解析 DuckDuckGo Lite JSON 结果"""
        results = []
        try:
            import re
            
            # 匹配 <a href="URL">TITLE</a> 模式
            pattern = r'<a href="(https?://[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, text)
            
            seen = set()
            for url, title in matches:
                if url not in seen and len(results) < count:
                    if not any(x in url.lower() for x in ['duckduckgo', 'duck.com']):
                        seen.add(url)
                        results.append(SearchResult(
                            title=title.strip(),
                            url=url,
                            snippet="",
                            source="DuckDuckGo",
                            date=None,
                        ))
        except Exception as e:
            logger.error(f"Failed to parse DDG Lite: {e}")
            
        return results

    async def _serpapi_search(
        self,
        query: str,
        language: str,
        count: int,
    ) -> List[SearchResult]:
        """使用 SerpAPI 搜索 (需要 API Key)"""
        api_key = self.config.get("serpapi_key")
        if not api_key:
            logger.warning("SerpAPI key not configured")
            return []

        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": count,
        }
        
        if language == "zh":
            params["gl"] = "cn"
            params["hl"] = "zh-cn"
        elif language == "en":
            params["gl"] = "us"
            params["hl"] = "en"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://serpapi.com/search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

            results = []
            for item in data.get("organic_results", [])[:count]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="Google",
                    date=item.get("date", None),
                ))
            return results

        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return []

    async def _minimax_search(
        self,
        query: str,
        language: str,
        count: int,
    ) -> List[SearchResult]:
        """使用 MiniMax MCP 搜索 (如果可用)"""
        # 尝试使用 MiniMax 的联网能力
        # 这需要 mcporter minimax 配置
        try:
            # 预留接口，实际通过 MCP 调用
            logger.info("MiniMax search - via MCP interface")
            return []
        except Exception as e:
            logger.warning(f"MiniMax search not available: {e}")
            return []

    # ==================== 新闻搜索 ====================

    async def news_search(
        self,
        query: str,
        days: int = 7,
        language: str = "zh",
        count: int = 10,
    ) -> dict:
        """
        新闻搜索

        Args:
            query: 搜索关键词
            days: 最近天数
            language: 语言 (zh/en)
            count: 返回数量

        Returns:
            dict 新闻结果列表
        """
        logger.info(f"News search: {query} (days={days})")
        
        cache_key = f"news:{query}:{days}:{language}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            # 使用 DuckDuckGo 新闻
            news = await self._duckduckgo_news(query, language, count)
            
            # 过滤日期
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            filtered = []
            for item in news:
                if item.get("date"):
                    try:
                        item_date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                        if item_date > cutoff:
                            filtered.append(item)
                    except:
                        filtered.append(item)
                else:
                    filtered.append(item)

            response = {
                "query": query,
                "days": days,
                "news": filtered,
                "total": len(filtered),
                "timestamp": datetime.now().isoformat(),
            }
            
            self._set_cached(cache_key, response)
            return response

        except Exception as e:
            logger.error(f"News search failed: {e}")
            return {
                "query": query,
                "news": [],
                "error": str(e),
            }

    async def _duckduckgo_news(
        self,
        query: str,
        language: str,
        count: int,
    ) -> List[NewsResult]:
        """DuckDuckGo 新闻搜索"""
        import urllib.parse
        
        params = {
            "q": query,
            "ia": "news",
            "kl": "wt-wt" if language == "en" else "cn-zh",
        }
        
        url = f"https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(params)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    html = await resp.text()
                    
            return self._parse_ddg_news(html, count)
        except Exception as e:
            logger.error(f"DuckDuckGo news failed: {e}")
            return []

    def _parse_ddg_news(self, html: str, count: int) -> List[NewsResult]:
        """解析 DuckDuckGo 新闻结果"""
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            for item in soup.select(".result")[:count]:
                title_elem = item.select_one(".result__title a")
                snippet_elem = item.select_one(".result__snippet")
                
                # 尝试获取日期
                date_elem = item.select_one(".result__timestamp")
                date_text = date_elem.get_text(strip=True) if date_elem else None
                
                if title_elem:
                    results.append(NewsResult(
                        title=title_elem.get_text(strip=True),
                        url=title_elem.get("href", ""),
                        snippet=snippet_elem.get_text(strip=True) if snippet_elem else "",
                        source="DuckDuckGo",
                        date=date_text,
                    ))
        except Exception as e:
            logger.error(f"Failed to parse news: {e}")
            
        return results

    # ==================== 学术搜索 ====================

    async def academic_search(
        self,
        query: str,
        count: int = 10,
        domain: Optional[str] = None,
    ) -> dict:
        """
        学术搜索

        Args:
            query: 搜索关键词
            count: 返回数量
            domain: 领域筛选 (cs/econ/fin)

        Returns:
            dict 学术论文/研报列表
        """
        logger.info(f"Academic search: {query} (domain={domain})")
        
        cache_key = f"academic:{query}:{domain}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        results = []
        
        # 尝试 Google Scholar (通过 SerpAPI)
        if self.config.get("serpapi_key"):
            scholar_results = await self._serpapi_scholar(query, count)
            results.extend(scholar_results)
        
        # 尝试 Semantic Scholar (免费)
        ss_results = await self._semantic_scholar(query, count)
        results.extend(ss_results)
        
        # 去重
        seen_urls = set()
        unique_results = []
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(r)

        response = {
            "query": query,
            "domain": domain,
            "papers": unique_results[:count],
            "total": len(unique_results),
            "timestamp": datetime.now().isoformat(),
        }
        
        self._set_cached(cache_key, response, ttl=3600)  # 学术结果缓存1小时
        return response

    async def _semantic_scholar(
        self,
        query: str,
        count: int,
    ) -> List[AcademicResult]:
        """Semantic Scholar 免费学术搜索"""
        import urllib.parse
        
        params = {
            "query": query,
            "limit": count,
            "fields": "title,authors,abstract,year,venue,openAccessPdf",
        }
        
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
        
        headers = {
            "Accept": "application/json",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()

            results = []
            for paper in data.get("data", []):
                authors = [a.get("name", "") for a in paper.get("authors", [])]
                
                results.append(AcademicResult(
                    title=paper.get("title", ""),
                    url=f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}",
                    authors=authors[:5],  # 最多5个作者
                    abstract=paper.get("abstract", "")[:500],
                    year=paper.get("year"),
                    venue=paper.get("venue"),
                ))
            return results

        except Exception as e:
            logger.error(f"Semantic Scholar failed: {e}")
            return []

    async def _serpapi_scholar(
        self,
        query: str,
        count: int,
    ) -> List[AcademicResult]:
        """SerpAPI Google Scholar 搜索"""
        api_key = self.config.get("serpapi_key")
        if not api_key:
            return []

        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google_scholar",
            "num": count,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://serpapi.com/search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

            results = []
            for item in data.get("organic_results", []):
                results.append(AcademicResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    authors=[item.get("publication_info", {}).get("authors", [])],
                    abstract=item.get("snippet", ""),
                    year=None,
                    venue=item.get("publication_info", {}).get("summary", None),
                ))
            return results

        except Exception as e:
            logger.error(f"SerpAPI Scholar failed: {e}")
            return []

    # ==================== 公司信息 ====================

    async def company_search(self, name: str) -> dict:
        """
        公司信息搜索

        Args:
            name: 公司名称或股票代码

        Returns:
            dict 公司基本信息、财务数据、新闻
        """
        logger.info(f"Company search: {name}")
        
        cache_key = f"company:{name}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 尝试多个数据源
        info = await self._search_company_basic(name)
        
        response = {
            "query": name,
            "info": info,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._set_cached(cache_key, response, ttl=3600)  # 1小时缓存
        return response

    async def _search_company_basic(self, name: str) -> CompanyInfo:
        """搜索公司基本信息"""
        # 使用 DuckDuckGo 搜索公司信息
        results = await self._duckduckgo_search(f"{name} 公司 简介", "zh", 5)
        
        if results:
            first_result = results[0]
            return CompanyInfo(
                name=name,
                ticker="",
                exchange="",
                industry="",
                sector=None,
                market_cap=0.0,
                pe_ratio=None,
                description=first_result.get("snippet", ""),
                website=None,
                headquarters=None,
            )
        
        return CompanyInfo(
            name=name,
            ticker="",
            exchange="",
            industry="",
            sector=None,
            market_cap=0.0,
            pe_ratio=None,
            description="",
            website=None,
            headquarters=None,
        )

    # ==================== 缓存管理 ====================

    def _get_cached(self, key: str) -> Optional[dict]:
        """获取缓存"""
        import time
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["time"] < entry["ttl"]:
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        import time
        self._cache[key] = {
            "data": data,
            "time": time.time(),
            "ttl": ttl or self._cache_ttl,
        }
        # 限制缓存大小
        if len(self._cache) > 1000:
            self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """清理过期缓存"""
        import time
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v["time"] >= v["ttl"]]
        for k in expired:
            del self._cache[k]

    # ==================== 财经新闻快捷方法 ====================

    async def get_financial_news(
        self,
        tickers: Optional[list[str]] = None,
        days: int = 7,
    ) -> dict:
        """
        获取财经新闻

        Args:
            tickers: 关注的股票代码列表
            days: 最近天数

        Returns:
            dict 新闻列表
        """
        query = " ".join(tickers) if tickers else "股票 财经"
        return await self.news_search(query, days=days, language="zh")

    async def get_macro_news(
        self,
        keywords: Optional[list[str]] = None,
        days: int = 7,
    ) -> dict:
        """
        获取宏观新闻

        Args:
            keywords: 关键词列表
            days: 最近天数

        Returns:
            dict 宏观新闻列表
        """
        query = " ".join(keywords) if keywords else "宏观经济 货币政策"
        return await self.news_search(query, days=days, language="zh")

    async def get_industry_news(
        self,
        industry: str,
        days: int = 7,
    ) -> dict:
        """
        获取行业新闻

        Args:
            industry: 行业名称
            days: 最近天数

        Returns:
            dict 行业新闻
        """
        return await self.news_search(f"{industry}行业 动态", days=days, language="zh")
