"""
Equity Agent - 股票分析师
专注于个股分析、行业研究、财务建模
"""
from typing import Optional
from loguru import logger

from .base_agent import BaseAgent


class EquityAgent(BaseAgent):
    """
    股票分析师智能体

    能力：
    - 个股基本面分析
    - 行业研究
    - 财务建模
    - 估值分析
    """

    def __init__(self, tools: Optional[dict] = None):
        super().__init__(
            name="股票分析师",
            description="专注于个股基本面分析和行业研究",
            tools=tools,
        )

    async def process(self, query: str, context: Optional[dict] = None) -> dict:
        """
        处理股票分析查询

        Args:
            query: 分析问题
            context: 上下文

        Returns:
            dict 包含分析结论
        """
        logger.info(f"EquityAgent processing: {query[:80]}")
        context = context or {}

        # 1. 提取股票代码
        symbol = context.get("symbol", self._extract_symbol(query))

        # 2. 分类分析类型
        analysis_type = self._classify_query(query)

        # 3. 获取数据
        data = {}
        if symbol:
            if "market_tools" in self.tools:
                data["price"] = await self.call_tool("market_tools.get_stock_price", symbol=symbol)
            if "search_tools" in self.tools:
                data["news"] = await self.call_tool("search_tools.get_company_info", ticker=symbol)

        # 4. 生成分析
        analysis = {
            "query": query,
            "symbol": symbol,
            "type": analysis_type,
            "data": data,
            "conclusion": f"基于{query}的分析结论",
            "valuation": "估值：合理/偏高/偏低",
            "recommendation": "建议：买入/持有/卖出",
        }

        return analysis

    def _extract_symbol(self, query: str) -> str:
        """从查询中提取股票代码"""
        # 简单的代码提取逻辑
        import re
        match = re.search(r'\b\d{6}\b', query)
        if match:
            return match.group(0)
        return ""

    def _classify_query(self, query: str) -> str:
        """分类查询类型"""
        q = query.lower()
        if any(k in q for k in ["估值", "价值", "贵", "便宜"]):
            return "valuation"
        elif any(k in q for k in ["业绩", "利润", "收入", "财报"]):
            return "financial"
        elif any(k in q for k in ["行业", "竞争", "市场份额"]):
            return "industry"
        elif any(k in q for k in ["技术", "走势", "趋势", "k线"]):
            return "technical"
        else:
            return "general"
