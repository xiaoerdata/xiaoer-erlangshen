"""
Macro Agent - 宏观分析师
专注于宏观经济分析、政策解读、大类资产配置
"""
from typing import Optional
from loguru import logger

from .base_agent import BaseAgent


class MacroAgent(BaseAgent):
    """
    宏观分析师智能体

    能力：
    - 宏观经济指标分析
    - 货币政策解读
    - 大类资产配置建议
    - 宏观风险识别
    """

    def __init__(self, tools: Optional[dict] = None):
        super().__init__(
            name="宏观分析师",
            description="专注于宏观经济分析、政策解读和大类资产配置",
            tools=tools,
        )

    async def process(self, query: str, context: Optional[dict] = None) -> dict:
        """
        处理宏观分析查询

        Args:
            query: 分析问题
            context: 上下文

        Returns:
            dict 包含分析结论和建议
        """
        logger.info(f"MacroAgent processing: {query[:80]}")
        context = context or {}

        # 1. 解析分析类型
        analysis_type = self._classify_query(query)

        # 2. 获取相关数据
        data = {}
        if "indicator" in analysis_type:
            # 获取宏观指标
            indicator = context.get("indicator", "CPI")
            if "macro_tools" in self.tools:
                data["macro"] = await self.call_tool("macro_tools.get_macro_indicator", code=indicator)
            if "search_tools" in self.tools:
                data["news"] = await self.call_tool("search_tools.news_search", query=f"{indicator} 宏观 经济")

        # 3. 生成分析
        analysis = {
            "query": query,
            "type": analysis_type,
            "data": data,
            "conclusion": f"基于{query}的分析结论",
            "recommendation": "建议配置...",
        }

        return analysis

    def _classify_query(self, query: str) -> str:
        """分类查询类型"""
        q = query.lower()
        if any(k in q for k in ["gdp", "增长", "经济"]):
            return "economic_growth"
        elif any(k in q for k in ["通胀", "cpi", "ppi", "物价"]):
            return "inflation"
        elif any(k in q for k in ["利率", "美联储", "央行", "货币政策"]):
            return "monetary_policy"
        elif any(k in q for k in ["汇率", "外汇", "人民币", "美元"]):
            return "fx_rate"
        elif any(k in q for k in ["配置", "资产"]):
            return "asset_allocation"
        else:
            return "general_macro"
