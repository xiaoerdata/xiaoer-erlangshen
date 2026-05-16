"""
二郎神 - 二郎神主智能体
全知全能的投资智能体，整合所有能力
"""
from typing import Optional
from loguru import logger

from .base_agent import BaseAgent
from .macro_agent import MacroAgent
from .equity_agent import EquityAgent
from .multi_asset_agent import MultiAssetAgent


class 二郎神(BaseAgent):
    """
    二郎神 - 主智能体

    整合所有分析师能力，提供全品类、全方位的投资分析

    架构：
    - Brain: LLM大脑
    - Cerebellum: 认知调度
    - Agents: 专业分析师团队
    - Tools: 工具集
    - Memory: 记忆系统
    """

    def __init__(
        self,
        brain=None,
        memory=None,
        knowledge=None,
        tools: Optional[dict] = None,
    ):
        super().__init__(
            name="二郎神",
            description="全知全能的投资智能体，具有天眼般全方位洞察能力",
            tools=tools,
        )

        self.brain = brain
        self.memory = memory
        self.knowledge = knowledge

        # 初始化专业分析师团队
        self.macro_agent = MacroAgent(tools=tools)
        self.equity_agent = EquityAgent(tools=tools)
        self.multi_asset_agent = MultiAssetAgent(tools=tools)

        logger.info("二郎神 (二郎神) fully initialized")

    async def process(self, query: str, context: Optional[dict] = None) -> dict:
        """
        处理用户查询

        Args:
            query: 用户查询
            context: 上下文

        Returns:
            dict 包含完整分析结果
        """
        logger.info(f"二郎神 processing: {query[:100]}")
        context = context or {}

        # 1. 确定查询类型
        query_type = self._classify_query(query)

        # 2. 路由到对应分析师
        result = {}
        if query_type == "macro":
            result = await self.macro_agent.process(query, context)
        elif query_type == "equity":
            result = await self.equity_agent.process(query, context)
        elif query_type == "multi_asset":
            result = await self.multi_asset_agent.process(query, context)
        else:
            # 综合分析
            result = await self._comprehensive_analysis(query, context)

        # 3. 添加二郎神特色结论
        result["erlangshen_insight"] = self._generate_insight(query, result)

        # 4. 记录到记忆
        if self.memory:
            await self.memory.add_interaction(query, str(result.get("conclusion", "")))

        # 5. 沉淀到知识库
        if self.knowledge and result.get("conclusion"):
            await self.knowledge.append_insight(
                result["conclusion"],
                tags=["analysis", query_type],
            )

        return result

    async def _comprehensive_analysis(self, query: str, context: dict) -> dict:
        """综合分析 - 多维度分析"""
        logger.info("Running comprehensive analysis")

        # 并行调用多个分析师
        import asyncio
        try:
            results = await asyncio.gather(
                self.macro_agent.process(query, context),
                self.equity_agent.process(query, context),
                self.multi_asset_agent.process(query, context),
                return_exceptions=True,
            )
        except Exception:
            results = []

        return {
            "query": query,
            "type": "comprehensive",
            "macro_analysis": results[0] if len(results) > 0 else {},
            "equity_analysis": results[1] if len(results) > 1 else {},
            "multi_asset_analysis": results[2] if len(results) > 2 else {},
        }

    def _classify_query(self, query: str) -> str:
        """分类查询类型"""
        q = query.lower()
        if any(k in q for k in ["宏观", "经济", "gdp", "通胀", "利率", "政策"]):
            return "macro"
        elif any(k in q for k in ["股票", "个股", "茅台", "估值", "行业"]):
            return "equity"
        elif any(k in q for k in ["配置", "资产", "组合", "多资产", "黄金", "债券"]):
            return "multi_asset"
        else:
            return "comprehensive"

    def _generate_insight(self, query: str, result: dict) -> str:
        """生成二郎神洞察"""
        return (
            "【二郎神天眼观察】"
            f"针对「{query[:30]}...」的分析已完成。"
            "建议结合宏观周期、资产配置和个人风险偏好综合决策。"
        )

    async def analyze_market(self, market: str = "A股") -> dict:
        """分析市场整体状况"""
        logger.info(f"Analyzing {market}")
        return await self.process(f"分析当前{market}市场走势和投资机会")

    async def analyze_stock(self, symbol: str) -> dict:
        """分析个股"""
        logger.info(f"Analyzing stock {symbol}")
        return await self.process(f"分析股票{symbol}的投资价值", {"symbol": symbol})

    async def analyze_macro(self, topic: str) -> dict:
        """分析宏观经济"""
        logger.info(f"Analyzing macro: {topic}")
        return await self.process(f"分析{topic}对投资的影响")

    async def generate_report(
        self,
        title: str,
        content: str,
    ) -> dict:
        """生成报告并沉淀到知识库"""
        if self.knowledge:
            filepath = await self.knowledge.write_report(content, title)
            return {"status": "success", "path": filepath}
        return {"status": "skipped", "reason": "knowledge not available"}
