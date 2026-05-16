"""
Market Tools - 行情数据工具
提供股票、期货、指数、加密货币、宏观经济等行情数据查询

支持的API:
- Yahoo Finance (无需 API Key) - 股票、指数、ETF、期货
- CoinGecko (免费，无需 API Key) - 加密货币
- Binance (公开数据) - 加密货币K线
- FRED (美联储经济数据 - 免费) - 宏观指标
- Alpha Vantage (免费额度) - 股票、外汇
- Twelve Data (免费额度) - 实时行情
- Trading Economics (免费额度) - 全球经济指标
- World Bank API (免费) - 发展指标
"""
from typing import Optional, Any, TypedDict, List, Dict
from datetime import datetime, timedelta
from loguru import logger
import aiohttp
import json


# ==================== 类型定义 ====================

class StockQuote(TypedDict):
    """股票行情"""
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    market_cap: float
    pe_ratio: Optional[float]
    dividend: Optional[float]
    timestamp: str
    source: str


class OHLCV(TypedDict):
    """K线数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class CryptoQuote(TypedDict):
    """加密货币行情"""
    coin_id: str
    symbol: str
    name: str
    price: float
    change_24h: float
    change_pct_24h: float
    market_cap: float
    volume_24h: float
    rank: int
    timestamp: str
    source: str


class MacroIndicator(TypedDict):
    """宏观经济指标"""
    indicator: str
    name: str
    value: float
    unit: str
    country: str
    date: str
    frequency: str
    source: str


class CommodityQuote(TypedDict):
    """大宗商品行情"""
    name: str
    price: float
    change: float
    change_pct: float
    unit: str
    timestamp: str
    source: str


# ==================== MarketTools ====================

class MarketTools:
    """
    行情数据工具集

    工具函数：
    - get_stock_price: 股票当前价格 (Yahoo Finance)
    - get_stock_history: 股票历史行情 (Yahoo Finance)
    - get_index_constituents: 指数成分股
    - get_futures_price: 期货价格
    - get_etf_info: ETF信息
    - get_crypto_price: 加密货币价格 (CoinGecko)
    - get_crypto_history: 加密货币历史 (CoinGecko)
    - get_fred_indicator: FRED宏观指标
    - get_commodity_price: 大宗商品价格
    - get_forex_rate: 外汇汇率
    """

    def __init__(self, db_connection: Optional[Any] = None, config: Optional[dict] = None):
        self.db = db_connection
        self.config = config or {}
        self._cache: dict = {}
        self._cache_ttl = self.config.get("cache_ttl", 300)
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info("MarketTools initialized with extended API support")

    async def execute(self, tool_name: str, **kwargs) -> Any:
        """执行指定工具"""
        method = getattr(self, tool_name, None)
        if method and callable(method):
            return await method(**kwargs)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP Session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # ==================== 股票/指数工具 (Yahoo Finance) ====================

    async def get_stock_price(self, symbol: str) -> dict:
        """
        获取股票当前价格

        Args:
            symbol: 股票代码，如 "000001.XSHE" (平安银行) 或 "AAPL" (苹果)

        Returns:
            dict 包含价格信息
        """
        logger.info(f"Fetching stock price for {symbol}")
        
        cache_key = f"stock_price:{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 尝试 Yahoo Finance
        quote = await self._yahoo_quote(symbol)
        if quote:
            self._set_cached(cache_key, quote)
            return quote

        # 回退到模拟数据
        return {
            "symbol": symbol,
            "name": self._get_stock_name(symbol),
            "price": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "volume": 0,
            "market_cap": 0.0,
            "pe_ratio": None,
            "dividend": None,
            "timestamp": datetime.now().isoformat(),
            "source": "yahoo_finance",
            "error": "Failed to fetch real data",
        }

    async def get_stock_history(
        self,
        symbol: str,
        days: int = 30,
        end_date: Optional[str] = None,
        interval: str = "1d",
    ) -> dict:
        """
        获取股票历史行情

        Args:
            symbol: 股票代码
            days: 历史天数
            end_date: 结束日期 (YYYY-MM-DD)
            interval: K线周期 (1d, 1wk, 1mo, 1h, 5m)

        Returns:
            dict 包含OHLCV数据
        """
        logger.info(f"Fetching {days} days history for {symbol}")
        
        cache_key = f"stock_history:{symbol}:{days}:{end_date}:{interval}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Yahoo Finance 历史数据
        data = await self._yahoo_history(symbol, days, end_date, interval)
        if data:
            self._set_cached(cache_key, data, ttl=600)  # 10分钟缓存
            return data

        return {
            "symbol": symbol,
            "name": self._get_stock_name(symbol),
            "dates": [],
            "data": [],
            "source": "yahoo_finance",
            "error": "Failed to fetch real data",
        }

    async def _yahoo_quote(self, symbol: str) -> Optional[dict]:
        """Yahoo Finance 实时行情"""
        # 转换代码格式
        yahoo_symbol = self._to_yahoo_symbol(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        
        params = {
            "interval": "1d",
            "range": "1d",
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            chart = data.get("chart", {}).get("result", [{}])[0]
            meta = chart.get("meta", {})
            quote = chart.get("indicators", {}).get("quote", [{}])[0]
            
            price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("previousClose", price)
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0

            return StockQuote(
                symbol=symbol,
                name=meta.get("shortName", meta.get("symbol", symbol)),
                price=price,
                change=round(change, 2),
                change_pct=round(change_pct, 2),
                volume=meta.get("regularMarketVolume", 0),
                market_cap=meta.get("marketCap", 0),
                pe_ratio=meta.get("trailingPE"),
                dividend=meta.get("dividendYield"),
                timestamp=datetime.now().isoformat(),
                source="yahoo_finance",
            )

        except Exception as e:
            logger.warning(f"Yahoo quote failed for {symbol}: {e}")
            return None

    async def _yahoo_history(
        self,
        symbol: str,
        days: int,
        end_date: Optional[str],
        interval: str,
    ) -> Optional[dict]:
        """Yahoo Finance 历史数据"""
        yahoo_symbol = self._to_yahoo_symbol(symbol)
        
        # 计算时间范围
        end = datetime.now()
        if end_date:
            try:
                end = datetime.strptime(end_date, "%Y-%m-%d")
            except:
                pass
        
        period1 = int((end - timedelta(days=days)).timestamp())
        period2 = int(end.timestamp())
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        
        params = {
            "period1": period1,
            "period2": period2,
            "interval": interval,
            "events": "div,split",
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()

            chart = data.get("chart", {}).get("result", [{}])[0]
            timestamps = chart.get("timestamp", [])
            quote = chart.get("indicators", {}).get("quote", [{}])[0]
            adj_close = chart.get("indicators", {}).get("adjclose", [{}])
            if adj_close:
                adj_close = adj_close[0].get("adjclose", [])
            
            dates = [datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in timestamps]
            
            ohlcv_data = []
            for i in range(len(timestamps)):
                ohlcv_data.append(OHLCV(
                    date=dates[i],
                    open=quote.get("open", [0])[i] if i < len(quote.get("open", [])) else 0,
                    high=quote.get("high", [0])[i] if i < len(quote.get("high", [])) else 0,
                    low=quote.get("low", [0])[i] if i < len(quote.get("low", [])) else 0,
                    close=adj_close[i] if adj_close and i < len(adj_close) else (quote.get("close", [0])[i] if i < len(quote.get("close", [])) else 0),
                    volume=quote.get("volume", [0])[i] if i < len(quote.get("volume", [])) else 0,
                ))

            return {
                "symbol": symbol,
                "name": self._get_stock_name(symbol),
                "dates": dates,
                "data": ohlcv_data,
                "source": "yahoo_finance",
                "interval": interval,
            }

        except Exception as e:
            logger.warning(f"Yahoo history failed for {symbol}: {e}")
            return None

    def _to_yahoo_symbol(self, symbol: str) -> str:
        """转换代码为 Yahoo Finance 格式"""
        # A股
        if symbol.startswith("6") and len(symbol) == 6:
            return f"{symbol}.SS"  # Shanghai
        elif symbol.startswith(("0", "3")) and len(symbol) == 6:
            return f"{symbol}.SZ"  # Shenzhen
        
        # 已有后缀
        if "." in symbol:
            return symbol
        
        # 加密货币 (Yahoo 有特殊格式)
        if symbol.upper() in ["BTC", "ETH"]:
            return f"{symbol.upper()}-USD"
        
        # 默认
        return symbol

    # ==================== 指数/ETF工具 ====================

    async def get_index_constituents(self, index_code: str, top_k: int = 10) -> dict:
        """
        获取指数成分股

        Args:
            index_code: 指数代码，如 "000300.XSHE" (沪深300) 或 "^GSPC" (标普500)
            top_k: 返回数量

        Returns:
            dict 包含成分股列表
        """
        logger.info(f"Fetching constituents for {index_code}")
        
        cache_key = f"index:{index_code}:{top_k}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 返回提示信息，实际需要专业数据源
        response = {
            "index_code": index_code,
            "name": self._get_index_name(index_code),
            "constituents": [],
            "total_count": 0,
            "source": "cache",
            "note": "请使用专业数据源获取指数成分",
        }
        
        self._set_cached(cache_key, response, ttl=3600)
        return response

    async def get_etf_info(self, code: str) -> dict:
        """获取ETF信息"""
        logger.info(f"Fetching ETF info for {code}")
        
        cache_key = f"etf:{code}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Yahoo Finance ETF 数据
        yahoo_code = code
        if not "." in code:
            if code.startswith("5") and len(code) == 6:
                yahoo_code = f"{code}.SS"
            elif code.startswith(("1", "15")) and len(code) == 6:
                yahoo_code = f"{code}.SZ"
        
        quote = await self._yahoo_quote(yahoo_code)
        if quote and quote.get("price", 0) > 0:
            self._set_cached(cache_key, quote, ttl=300)
            return quote

        return {
            "code": code,
            "name": "",
            "price": 0.0,
            "nav": 0.0,
            "aum": 0.0,
            "note": "请接入ETF数据源",
        }

    async def get_futures_price(self, contract: str) -> dict:
        """
        获取期货价格

        Args:
            contract: 期货合约，如 "IF2406" 或 "ES=F"

        Returns:
            dict 期货行情
        """
        logger.info(f"Fetching futures price for {contract}")
        
        cache_key = f"futures:{contract}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 尝试 Yahoo Finance
        yahoo_contract = contract
        if not "=" in contract:
            yahoo_contract = f"{contract}=F"
        
        quote = await self._yahoo_quote(yahoo_contract)
        if quote and quote.get("price", 0) > 0:
            self._set_cached(cache_key, quote)
            return quote

        return {
            "contract": contract,
            "price": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "timestamp": datetime.now().isoformat(),
            "source": "yahoo_finance",
            "note": "期货数据获取失败",
        }

    # ==================== 加密货币工具 (CoinGecko) ====================

    async def get_crypto_price(
        self,
        coin_id: str,
        currency: str = "usd",
    ) -> dict:
        """
        获取加密货币价格

        Args:
            coin_id: CoinGecko ID，如 "bitcoin", "ethereum"
            currency: 计价货币 (usd, cny, eur)

        Returns:
            dict 加密货币行情
        """
        logger.info(f"Fetching crypto price for {coin_id}")
        
        cache_key = f"crypto_price:{coin_id}:{currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            coin_data = data.get(coin_id, {})
            currency_upper = currency.upper()
            
            price = coin_data.get(currency, 0)
            change_24h = coin_data.get(f"{currency}_24h_change", 0)
            
            result = CryptoQuote(
                coin_id=coin_id,
                symbol=coin_id.upper(),
                name=coin_id.capitalize(),
                price=price,
                change_24h=price * change_24h / 100 if price else 0,
                change_pct_24h=round(change_24h, 2),
                market_cap=coin_data.get(f"{currency}_market_cap", 0),
                volume_24h=coin_data.get(f"{currency}_24h_vol", 0),
                rank=0,
                timestamp=datetime.now().isoformat(),
                source="coingecko",
            )
            
            self._set_cached(cache_key, result)
            return result

        except Exception as e:
            logger.warning(f"CoinGecko price failed for {coin_id}: {e}")
            return {
                "coin_id": coin_id,
                "price": 0.0,
                "error": str(e),
                "source": "coingecko",
            }

    async def get_crypto_prices(
        self,
        coin_ids: List[str],
        currency: str = "usd",
    ) -> dict:
        """
        批量获取加密货币价格

        Args:
            coin_ids: CoinGecko ID 列表
            currency: 计价货币

        Returns:
            dict 价格字典
        """
        logger.info(f"Fetching {len(coin_ids)} crypto prices")
        
        cache_key = f"crypto_prices:{','.join(coin_ids)}:{currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            results = {}
            for coin_id in coin_ids:
                coin_data = data.get(coin_id, {})
                price = coin_data.get(currency, 0)
                change_24h = coin_data.get(f"{currency}_24h_change", 0)
                
                results[coin_id] = {
                    "price": price,
                    "change_pct_24h": round(change_24h, 2),
                    "market_cap": coin_data.get(f"{currency}_market_cap", 0),
                }
            
            response = {
                "coins": results,
                "currency": currency,
                "timestamp": datetime.now().isoformat(),
            }
            
            self._set_cached(cache_key, response)
            return response

        except Exception as e:
            logger.warning(f"CoinGecko batch price failed: {e}")
            return {"coins": {}, "error": str(e)}

    async def get_crypto_history(
        self,
        coin_id: str,
        days: int = 30,
        currency: str = "usd",
    ) -> dict:
        """
        获取加密货币历史价格

        Args:
            coin_id: CoinGecko ID
            days: 历史天数
            currency: 计价货币

        Returns:
            dict 历史价格数据
        """
        logger.info(f"Fetching {days} days history for {coin_id}")
        
        cache_key = f"crypto_history:{coin_id}:{days}:{currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": currency,
            "days": days,
            "interval": "daily" if days > 1 else "hourly",
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()

            prices = data.get("prices", [])
            market_caps = data.get("market_caps", [])
            volumes = data.get("total_volumes", [])
            
            dates = []
            price_data = []
            
            for i, (timestamp, price) in enumerate(prices):
                date = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")
                dates.append(date)
                price_data.append({
                    "price": price,
                    "market_cap": market_caps[i][1] if i < len(market_caps) else 0,
                    "volume": volumes[i][1] if i < len(volumes) else 0,
                })

            result = {
                "coin_id": coin_id,
                "currency": currency,
                "dates": dates,
                "data": price_data,
                "source": "coingecko",
            }
            
            self._set_cached(cache_key, result, ttl=600)
            return result

        except Exception as e:
            logger.warning(f"CoinGecko history failed for {coin_id}: {e}")
            return {
                "coin_id": coin_id,
                "dates": [],
                "data": [],
                "error": str(e),
            }

    async def get_crypto_market_chart(
        self,
        coin_id: str,
        days: int = 7,
    ) -> dict:
        """
        获取加密货币市场数据图表

        Args:
            coin_id: CoinGecko ID
            days: 天数

        Returns:
            dict 市场数据
        """
        return await self.get_crypto_history(coin_id, days)

    # ==================== Binance K线 ====================

    async def get_binance_klines(
        self,
        symbol: str,
        interval: str = "1d",
        limit: int = 100,
    ) -> dict:
        """
        获取 Binance K线数据

        Args:
            symbol: 交易对，如 "BTCUSDT"
            interval: K线周期 (1m, 5m, 15m, 1h, 4h, 1d)
            limit: 数量

        Returns:
            dict K线数据
        """
        logger.info(f"Fetching Binance klines for {symbol}")
        
        cache_key = f"binance:{symbol}:{interval}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            dates = []
            ohlcv_data = []
            
            for kline in data:
                open_time = datetime.fromtimestamp(kline[0] / 1000)
                dates.append(open_time.strftime("%Y-%m-%d %H:%M"))
                ohlcv_data.append({
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": float(kline[4]),
                    "volume": float(kline[5]),
                })

            result = {
                "symbol": symbol,
                "interval": interval,
                "dates": dates,
                "data": ohlcv_data,
                "source": "binance",
            }
            
            self._set_cached(cache_key, result, ttl=60)  # 1分钟缓存
            return result

        except Exception as e:
            logger.warning(f"Binance klines failed for {symbol}: {e}")
            return {
                "symbol": symbol,
                "dates": [],
                "data": [],
                "error": str(e),
            }

    async def get_binance_ticker(self, symbol: str) -> dict:
        """
        获取 Binance 实时行情

        Args:
            symbol: 交易对，如 "BTCUSDT"

        Returns:
            dict 行情数据
        """
        cache_key = f"binance_ticker:{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = "https://api.binance.com/api/v3/ticker/24hr"
        params = {"symbol": symbol.upper()}
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            result = {
                "symbol": data.get("symbol"),
                "price": float(data.get("lastPrice", 0)),
                "change": float(data.get("priceChange", 0)),
                "change_pct": float(data.get("priceChangePercent", 0)),
                "volume_24h": float(data.get("volume", 0)),
                "quote_volume_24h": float(data.get("quoteVolume", 0)),
                "high_24h": float(data.get("highPrice", 0)),
                "low_24h": float(data.get("lowPrice", 0)),
                "timestamp": datetime.now().isoformat(),
                "source": "binance",
            }
            
            self._set_cached(cache_key, result, ttl=30)
            return result

        except Exception as e:
            logger.warning(f"Binance ticker failed for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    # ==================== FRED 宏观数据 ====================

    async def get_fred_indicator(
        self,
        series_id: str,
        limit: int = 100,
    ) -> dict:
        """
        获取 FRED 宏观指标

        Args:
            series_id: FRED 系列ID
                - DFF: 联邦基金利率
                - GDP: 美国GDP
                - CPIAUCSL: 消费者物价指数
                - UNRATE: 失业率
                - VIXCLS: VIX恐慌指数
                - DXY: 美元指数
                - GOLDAMGBD228NLBM: 金价
            limit: 返回数量

        Returns:
            dict 指标数据
        """
        logger.info(f"Fetching FRED indicator: {series_id}")
        
        cache_key = f"fred:{series_id}:{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        api_key = self.config.get("fred_api_key")
        
        if api_key:
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "limit": limit,
                "sort_order": "desc",
            }
            
            try:
                session = await self._get_session()
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

                observations = data.get("observations", [])
                dates = [o["date"] for o in observations]
                values = [float(o["value"]) if o["value"] != "." else 0 for o in observations]

                result = {
                    "series_id": series_id,
                    "name": self._get_fred_name(series_id),
                    "dates": dates,
                    "values": values,
                    "unit": self._get_fred_unit(series_id),
                    "source": "fred",
                }
                
                self._set_cached(cache_key, result, ttl=3600)
                return result

            except Exception as e:
                logger.warning(f"FRED API failed for {series_id}: {e}")

        # 无API Key时返回说明
        return {
            "series_id": series_id,
            "name": self._get_fred_name(series_id),
            "dates": [],
            "values": [],
            "unit": self._get_fred_unit(series_id),
            "source": "fred",
            "note": "请配置 FRED API Key 以获取实际数据",
        }

    def _get_fred_name(self, series_id: str) -> str:
        """获取 FRED 指标名称"""
        names = {
            "DFF": "联邦基金利率",
            "GDP": "美国GDP",
            "CPIAUCSL": "消费者物价指数",
            "PPIACO": "生产者物价指数",
            "UNRATE": "失业率",
            "VIXCLS": "VIX恐慌指数",
            "DXY": "美元指数",
            "GOLDAMGBD228NLBM": "金价",
            "MORTGAGE30US": "30年期抵押贷款利率",
            "TBILL": "3个月国库券利率",
        }
        return names.get(series_id, series_id)

    def _get_fred_unit(self, series_id: str) -> str:
        """获取 FRED 指标单位"""
        units = {
            "DFF": "%",
            "GDP": "十亿美元",
            "CPIAUCSL": "2017=100",
            "PPIACO": "2011=100",
            "UNRATE": "%",
            "VIXCLS": "",
            "DXY": "指数",
            "GOLDAMGBD228NLBM": "美元/盎司",
            "MORTGAGE30US": "%",
            "TBILL": "%",
        }
        return units.get(series_id, "")

    # ==================== 大宗商品 ====================

    async def get_commodity_price(self, name: str) -> dict:
        """
        获取大宗商品价格

        Args:
            name: 商品名称 (gold, silver, oil, natural_gas, copper)

        Returns:
            dict 商品行情
        """
        logger.info(f"Fetching commodity price for {name}")
        
        cache_key = f"commodity:{name}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 映射到 Yahoo Finance 合约
        contracts = {
            "gold": "GC=F",
            "silver": "SI=F",
            "oil": "CL=F",
            "crude_oil": "CL=F",
            "natural_gas": "NG=F",
            "copper": "HG=F",
            "platinum": "PL=F",
            "palladium": "PA=F",
        }
        
        contract = contracts.get(name.lower(), f"{name.upper()}=F")
        quote = await self._yahoo_quote(contract)
        
        if quote and quote.get("price", 0) > 0:
            self._set_cached(cache_key, quote)
            return quote

        return CommodityQuote(
            name=name,
            price=0.0,
            change=0.0,
            change_pct=0.0,
            unit=self._get_commodity_unit(name),
            timestamp=datetime.now().isoformat(),
            source="yahoo_finance",
        )

    async def get_gold_price(self) -> dict:
        """获取黄金价格"""
        return await self.get_commodity_price("gold")

    async def get_oil_price(self) -> dict:
        """获取原油价格"""
        return await self.get_commodity_price("oil")

    def _get_commodity_unit(self, name: str) -> str:
        """获取商品单位"""
        units = {
            "gold": "USD/盎司",
            "silver": "USD/盎司",
            "oil": "USD/桶",
            "natural_gas": "USD/MMBtu",
            "copper": "USD/磅",
        }
        return units.get(name.lower(), "USD")

    # ==================== 外汇工具 ====================

    async def get_forex_rate(
        self,
        pair: str,
    ) -> dict:
        """
        获取外汇汇率

        Args:
            pair: 货币对，如 "USDCNY", "EURUSD"

        Returns:
            dict 汇率数据
        """
        logger.info(f"Fetching forex rate for {pair}")
        
        cache_key = f"forex:{pair}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Yahoo Finance 外汇
        yahoo_pair = f"{pair[:3]}{pair[3:]}={pair[:3]}{pair[3:]}"
        
        # 尝试不同的格式
        formats = [
            f"{pair}=X",
            f"{pair[:3]}{pair[3:]}={pair[:3]}{pair[3:]}",
        ]
        
        for fmt in formats:
            quote = await self._yahoo_quote(fmt)
            if quote and quote.get("price", 0) > 0:
                self._set_cached(cache_key, quote)
                return quote

        # Alpha Vantage (如果有 API Key)
        av_key = self.config.get("alpha_vantage_key")
        if av_key:
            result = await self._alpha_vantage_forex(pair, av_key)
            if result:
                self._set_cached(cache_key, result)
                return result

        return {
            "pair": pair,
            "rate": 0.0,
            "timestamp": datetime.now().isoformat(),
            "source": "yahoo_finance",
            "note": "外汇数据获取失败",
        }

    async def _alpha_vantage_forex(self, pair: str, api_key: str) -> Optional[dict]:
        """Alpha Vantage 外汇数据"""
        url = "https://www.alphavantage.co/query"
        from_currency = pair[:3]
        to_currency = pair[3:]
        
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "apikey": api_key,
        }
        
        try:
            session = await self._get_session()
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            rate_data = data.get("Realtime Currency Exchange Rate", {})
            rate = float(rate_data.get("5. Exchange Rate", 0))
            
            return {
                "pair": pair,
                "rate": rate,
                "timestamp": rate_data.get("6. Last Refreshed", ""),
                "source": "alpha_vantage",
            }

        except Exception as e:
            logger.warning(f"Alpha Vantage forex failed: {e}")
            return None

    # ==================== 工具方法 ====================

    async def get_index_quote(self, index_code: str) -> dict:
        """
        获取指数行情

        Args:
            index_code: 指数代码

        Returns:
            dict 指数行情
        """
        # 转换为 Yahoo Finance 格式
        yahoo_codes = {
            "^GSPC": "^GSPC",     # S&P 500
            "^DJI": "^DJI",       # 道琼斯
            "^IXIC": "^IXIC",     # 纳斯达克
            "^HSI": "^HSI",       # 恒生指数
            "000001.XSHE": "000001.SS",  # 上证指数
            "399001.XSHE": "399001.SZ",  # 深证成指
            "000300.XSHE": "000300.SS", # 沪深300
        }
        
        yahoo_code = yahoo_codes.get(index_code, index_code)
        return await self._yahoo_quote(yahoo_code)

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

    # ==================== 股票名称映射 ====================

    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称映射"""
        names = {
            "000001": "平安银行",
            "000002": "万科A",
            "600000": "浦发银行",
            "600519": "贵州茅台",
            "000858": "五粮液",
            "AAPL": "苹果公司",
            "MSFT": "微软公司",
            "GOOGL": "谷歌",
            "AMZN": "亚马逊",
            "TSLA": "特斯拉",
        }
        return names.get(symbol, f"股票{symbol}")

    def _get_index_name(self, code: str) -> str:
        """获取指数名称映射"""
        names = {
            "000001": "上证指数",
            "399001": "深证成指",
            "000300": "沪深300",
            "000016": "上证50",
            "399006": "创业板指",
            "^GSPC": "标普500",
            "^DJI": "道琼斯",
            "^IXIC": "纳斯达克",
            "^HSI": "恒生指数",
        }
        return names.get(code, f"指数{code}")
