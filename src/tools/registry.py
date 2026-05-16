"""
Tool Registry - 工具注册表
管理所有可用工具的注册和调用

工具分类:
- market: 行情数据 (股票、期货、ETF、加密货币、宏观指标)
- search: 搜索工具 (网络搜索、新闻、学术搜索、公司信息)
- macro: 宏观数据 (FRED指标、中国宏观、央行数据)
- file: 文件工具 (读取、写入、搜索)
"""
from typing import Any, Optional, Dict, List
from loguru import logger
import aiohttp


class ToolRegistry:
    """
    工具注册表

    提供工具的注册、发现和调用
    """

    def __init__(self, config: Optional[Dict] = None):
        self._tools: Dict[str, Any] = {}
        self._categories: Dict[str, List[str]] = {}
        self._instances: Dict[str, Any] = {}
        self._config = config or {}
        self._http_session: Optional[aiohttp.ClientSession] = None
        logger.info("ToolRegistry initialized")

    def register(
        self,
        name: str,
        tool_class: type,
        category: str = "general",
        description: str = "",
        **init_kwargs,
    ) -> None:
        """
        注册工具

        Args:
            name: 工具名称
            tool_class: 工具类
            category: 分类
            description: 描述
            **init_kwargs: 工具类初始化参数
        """
        # 实例化工具
        try:
            instance = tool_class(**init_kwargs)
        except TypeError:
            # 如果不需要参数
            instance = tool_class()

        self._tools[name] = {
            "instance": instance,
            "class": tool_class,
            "category": category,
            "description": description,
            "init_kwargs": init_kwargs,
        }

        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)

        self._instances[name] = instance
        logger.info(f"Registered tool: {name} [{category}]")

    def register_instance(
        self,
        name: str,
        instance: Any,
        category: str = "general",
        description: str = "",
    ) -> None:
        """
        注册已有工具实例

        Args:
            name: 工具名称
            instance: 工具实例
            category: 分类
            description: 描述
        """
        self._tools[name] = {
            "instance": instance,
            "category": category,
            "description": description,
        }

        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)

        self._instances[name] = instance
        logger.info(f"Registered instance: {name} [{category}]")

    def get(self, name: str) -> Optional[Any]:
        """获取工具实例"""
        tool_info = self._tools.get(name)
        if tool_info:
            return tool_info["instance"]
        return None

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """列出工具"""
        if category:
            return self._categories.get(category, [])
        return list(self._tools.keys())

    def list_categories(self) -> List[str]:
        """列出分类"""
        return list(self._categories.keys())

    def get_info(self, name: str) -> Optional[dict]:
        """获取工具信息"""
        info = self._tools.get(name)
        if info:
            return {
                "name": name,
                "category": info["category"],
                "description": info.get("description", ""),
            }
        return None

    def get_category_tools(self, category: str) -> Dict[str, dict]:
        """获取某个分类的所有工具信息"""
        tools = {}
        for name in self._categories.get(category, []):
            info = self.get_info(name)
            if info:
                tools[name] = info
        return tools

    async def execute(self, name: str, **kwargs) -> Any:
        """执行工具"""
        tool_info = self._tools.get(name)
        if not tool_info:
            return {"error": f"Tool not found: {name}"}

        tool = tool_info["instance"]
        if hasattr(tool, "execute"):
            return await tool.execute(**kwargs)
        elif callable(tool):
            return await tool(**kwargs)
        return {"error": f"Tool {name} is not callable"}

    async def get_http_session(self) -> aiohttp.ClientSession:
        """获取HTTP Session"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    def close(self) -> None:
        """关闭资源"""
        if self._http_session and not self._http_session.closed:
            # 异步关闭需要用 asyncio
            pass
        logger.info("ToolRegistry closed")


# ==================== 工具初始化函数 ====================

def create_registry(config: Optional[Dict] = None) -> ToolRegistry:
    """
    创建并初始化工具注册表

    Args:
        config: 配置字典

    Returns:
        ToolRegistry: 初始化后的工具注册表
    """
    from .market_tools import MarketTools
    from .search_tools import SearchTools
    from .file_tools import FileTools

    registry = ToolRegistry(config)

    # 注册市场工具
    market_config = config or {}
    registry.register(
        "market",
        MarketTools,
        category="market",
        description="行情数据工具: 股票、期货、ETF、加密货币、宏观指标",
        db_connection=None,
        config=market_config,
    )

    # 注册搜索工具
    search_config = {
        "serpapi_key": config.get("serpapi_key") if config else None,
        "cache_ttl": config.get("cache_ttl", 300) if config else 300,
    }
    registry.register(
        "search",
        SearchTools,
        category="search",
        description="搜索工具: 网络搜索、新闻搜索、学术搜索、公司信息",
        config=search_config,
    )

    # 注册文件工具
    registry.register(
        "file",
        FileTools,
        category="file",
        description="文件工具: 读取、写入、搜索知识库",
    )

    # 注册快捷方法
    _register_shortcut_methods(registry)

    return registry


def _register_shortcut_methods(registry: ToolRegistry) -> None:
    """注册快捷调用方法"""
    market = registry.get("market")
    search = registry.get("search")

    if market:
        # 股票工具
        registry.register_instance(
            "get_stock_price",
            _create_shortcut(market, "get_stock_price"),
            category="market",
            description="获取股票价格",
        )
        registry.register_instance(
            "get_stock_history",
            _create_shortcut(market, "get_stock_history"),
            category="market",
            description="获取股票历史",
        )
        registry.register_instance(
            "get_index_quote",
            _create_shortcut(market, "get_index_quote"),
            category="market",
            description="获取指数行情",
        )
        registry.register_instance(
            "get_etf_info",
            _create_shortcut(market, "get_etf_info"),
            category="market",
            description="获取ETF信息",
        )
        registry.register_instance(
            "get_futures_price",
            _create_shortcut(market, "get_futures_price"),
            category="market",
            description="获取期货价格",
        )

        # 加密货币工具
        registry.register_instance(
            "get_crypto_price",
            _create_shortcut(market, "get_crypto_price"),
            category="market",
            description="获取加密货币价格",
        )
        registry.register_instance(
            "get_crypto_prices",
            _create_shortcut(market, "get_crypto_prices"),
            category="market",
            description="批量获取加密货币价格",
        )
        registry.register_instance(
            "get_crypto_history",
            _create_shortcut(market, "get_crypto_history"),
            category="market",
            description="获取加密货币历史",
        )
        registry.register_instance(
            "get_binance_klines",
            _create_shortcut(market, "get_binance_klines"),
            category="market",
            description="获取Binance K线",
        )
        registry.register_instance(
            "get_binance_ticker",
            _create_shortcut(market, "get_binance_ticker"),
            category="market",
            description="获取Binance实时行情",
        )

        # 宏观工具
        registry.register_instance(
            "get_fred_indicator",
            _create_shortcut(market, "get_fred_indicator"),
            category="market",
            description="获取FRED宏观指标",
        )
        registry.register_instance(
            "get_commodity_price",
            _create_shortcut(market, "get_commodity_price"),
            category="market",
            description="获取大宗商品价格",
        )
        registry.register_instance(
            "get_gold_price",
            _create_shortcut(market, "get_gold_price"),
            category="market",
            description="获取黄金价格",
        )
        registry.register_instance(
            "get_oil_price",
            _create_shortcut(market, "get_oil_price"),
            category="market",
            description="获取原油价格",
        )
        registry.register_instance(
            "get_forex_rate",
            _create_shortcut(market, "get_forex_rate"),
            category="market",
            description="获取外汇汇率",
        )

    if search:
        # 搜索工具
        registry.register_instance(
            "web_search",
            _create_shortcut(search, "web_search"),
            category="search",
            description="网络搜索",
        )
        registry.register_instance(
            "news_search",
            _create_shortcut(search, "news_search"),
            category="search",
            description="新闻搜索",
        )
        registry.register_instance(
            "academic_search",
            _create_shortcut(search, "academic_search"),
            category="search",
            description="学术搜索",
        )
        registry.register_instance(
            "company_search",
            _create_shortcut(search, "company_search"),
            category="search",
            description="公司信息搜索",
        )
        registry.register_instance(
            "get_financial_news",
            _create_shortcut(search, "get_financial_news"),
            category="search",
            description="财经新闻",
        )
        registry.register_instance(
            "get_macro_news",
            _create_shortcut(search, "get_macro_news"),
            category="search",
            description="宏观新闻",
        )
        registry.register_instance(
            "get_industry_news",
            _create_shortcut(search, "get_industry_news"),
            category="search",
            description="行业新闻",
        )


def _create_shortcut(instance: Any, method_name: str):
    """创建快捷调用函数"""
    async def shortcut(**kwargs):
        method = getattr(instance, method_name)
        if callable(method):
            return await method(**kwargs)
        return {"error": f"Method {method_name} not callable"}
    return shortcut


# ==================== 全局注册表 ====================

_global_registry: Optional[ToolRegistry] = None


def get_registry(config: Optional[Dict] = None) -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = create_registry(config)
    return _global_registry


def reset_registry() -> None:
    """重置全局注册表"""
    global _global_registry
    if _global_registry:
        _global_registry.close()
    _global_registry = None
