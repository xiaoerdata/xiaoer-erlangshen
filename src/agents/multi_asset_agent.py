"""
Multi Asset Agent - 多资产分析师
跨资产类别分析、相对价值分析
"""
from typing import Optional
from loguru import logger

from .base_agent import BaseAgent


class MultiAssetAgent(BaseAgent):
    """
    多资产分析师智能体

    能力：
    - 跨资产类别分析
    - 相对价值比较
    - 多资产组合分析
    - 风险收益特征分析
    """

    def __init__(self, tools: Optional[dict] = None):
        super().__init__(
            name="多资产分析师",
            description="专注于跨资产分析和相对价值比较",
            tools=tools,
        )

    async def process(self, query: str, context: Optional[dict] = None) -> dict:
        """
        处理多资产分析查询

        Args:
            query: 分析问题
            context: 上下文

        Returns:
            dict 包含分析结论
        """
        logger.info(f"MultiAssetAgent processing: {query[:80]}")
        context = context or {}

        # 1. 确定涉及的资产类别
        asset_classes = self._identify_assets(query)

        # 2. 获取各类资产数据
        data = {}
        for asset_class in asset_classes:
            if asset_class == "stock":
                if "market_tools" in self.tools:
                    data["stocks"] = await self.call_tool("market_tools.get_stock_history", symbol="000001", days=30)
            elif asset_class == "bond":
                pass  # 债券数据
            elif asset_class == "gold":
                pass  # 黄金数据
            elif asset_class == "fx":
                if "macro_tools" in self.tools:
                    data["fx"] = await self.call_tool("macro_tools.get_currency_rates")

        # 3. 相对价值分析
        analysis = {
            "query": query,
            "asset_classes": asset_classes,
            "data": data,
            "relative_value": "相对价值分析结论",
            "recommendation": "配置建议",
        }

        return analysis

    def _identify_assets(self, query: str) -> list[str]:
        """识别查询中涉及的资产类别"""
        q = query.lower()
        assets = []
        if any(k in q for k in ["股票", "a股", "美股", "港股"]):
            assets.append("stock")
        if any(k in q for k in ["债券", "国债", "信用债"]):
            assets.append("bond")
        if any(k in q for k in ["黄金", "贵金属"]):
            assets.append("gold")
        if any(k in q for k in ["外汇", "汇率", "美元", "人民币"]):
            assets.append("fx")
        if any(k in q for k in ["原油", "大宗商品", "商品"]):
            assets.append("commodity")
        if not assets:
            assets = ["stock", "bond", "gold", "fx"]  # 默认全品类
        return assets
