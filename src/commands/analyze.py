"""
/analyze 命令 - 综合分析
"""

from typing import Optional
from src.agents.macro import MacroAgent
from src.agents.equity import EquityAgent
from src.agents.multi_asset import MultiAssetAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class AnalyzeCommand:
    """
    综合分析命令处理器
    
    用法:
        /analyze A股当前走势
        /analyze 茅台投资价值
        /analyze 黄金避险情绪
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.macro_agent = MacroAgent(brain, mcp)
        self.equity_agent = EquityAgent(brain, mcp)
        self.multi_asset_agent = MultiAssetAgent(brain, mcp)
    
    async def execute(self, args: str) -> str:
        """
        执行分析
        
        Args:
            args: 分析查询
        
        Returns:
            分析结果
        """
        if not args:
            return self._help()
        
        # 意图识别
        intent = self._classify_intent(args)
        
        if intent == "macro":
            return await self.macro_agent.process(args)
        elif intent == "equity":
            return await self.equity_agent.process(args)
        elif intent == "multi_asset":
            return await self.multi_asset_agent.process(args)
        else:
            # 默认综合分析
            return await self._comprehensive_analysis(args)
    
    def _classify_intent(self, query: str) -> str:
        """
        分类查询意图
        
        Returns:
            intent: macro/equity/multi_asset
        """
        query_lower = query.lower()
        
        # 宏观关键词
        macro_keywords = ["宏观", "经济", "gdp", "cpi", "ppi", "pmi", "利率", "汇率", 
                         "货币", "财政", "政策", "出口", "进口", "社融", "m2"]
        
        # 股票关键词
        equity_keywords = ["股票", "股价", "茅台", "腾讯", "苹果", "估值", "财报",
                          "营收", "利润", "板块", "行业", "涨停", "跌停"]
        
        # 多资产关键词
        multi_asset_keywords = ["配置", "组合", "分散", "风险", "收益", "再平衡",
                               "仓位", "持仓", "资产配置"]
        
        scores = {"macro": 0, "equity": 0, "multi_asset": 0}
        
        for kw in macro_keywords:
            if kw in query_lower:
                scores["macro"] += 1
        
        for kw in equity_keywords:
            if kw in query_lower:
                scores["equity"] += 1
        
        for kw in multi_asset_keywords:
            if kw in query_lower:
                scores["multi_asset"] += 1
        
        max_score = max(scores.values())
        if max_score == 0:
            return "macro"  # 默认宏观
        
        for intent, score in scores.items():
            if score == max_score:
                return intent
        
        return "macro"
    
    async def _comprehensive_analysis(self, query: str) -> str:
        """综合分析"""
        prompt = f"""请对以下主题进行全面综合分析：

主题：{query}

请从以下维度进行分析：
1. 宏观背景
2. 市场现状
3. 关键因素
4. 风险提示
5. 投资建议
"""
        return await self.brain.analyze(prompt, framework="综合分析框架")
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/analyze - 综合分析命令

用法:
    /analyze <查询内容>

示例:
    /analyze A股当前走势
    /analyze 茅台投资价值
    /analyze 黄金避险情绪
    /analyze 当前宏观经济形势

系统会自动识别查询意图并调用相应的分析师Agent。
"""
