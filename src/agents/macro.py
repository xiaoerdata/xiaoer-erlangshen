"""
宏观分析师 Agent
"""

from typing import Optional, Dict, Any
from src.agents.base import BaseAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class MacroAgent(BaseAgent):
    """
    宏观分析师
    
    专注于宏观经济分析、政策解读、大类资产配置
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        super().__init__(brain, mcp)
        self.role = "宏观分析师"
    
    def _build_system_prompt(self) -> str:
        return """你是一位资深宏观经济分析师，专注于：
- 宏观经济指标分析 (GDP, CPI, PPI, PMI等)
- 货币政策解读 (利率、存款准备金率、LPR等)
- 财政政策分析
- 大类资产配置建议
- 汇率走势分析
- 全球经济联动

分析原则：
1. 数据驱动：基于宏观经济数据进行客观分析
2. 政策导向：关注央行、财政部政策动向
3. 全球视野：关注海外主要经济体动态
4. 风险提示：明确指出潜在风险

输出格式：
## 核心观点
(1-2句话概括)

## 宏观环境
(当前经济周期、货币财政政策)

## 数据解读
(关键指标数据及含义)

## 资产配置建议
(股票、债券、商品、外汇等)

## 风险提示
(主要风险点)

## 近期关注
(即将发布的重要数据、政策事件)
"""
    
    async def process(self, query: str, **kwargs) -> str:
        """
        处理宏观分析查询
        
        Args:
            query: 分析查询
            **kwargs: 其他参数 (framework, indicators等)
        """
        framework = kwargs.get("framework")
        indicators = kwargs.get("indicators", [])
        
        # 收集相关数据
        data = {}
        
        # 获取请求的宏观指标
        if indicators:
            for indicator in indicators:
                result = await self.call_mcp_tool("get_macro_indicator", indicator_code=indicator)
                if isinstance(result, dict):
                    data[indicator] = result
        else:
            # 默认获取主要指标
            for indicator in ["GDP", "CPI", "PMI"]:
                result = await self.call_mcp_tool("get_macro_indicator", indicator_code=indicator)
                if isinstance(result, dict):
                    data[indicator] = result
            
            # 获取利率数据
            lpr_result = await self.call_mcp_tool("get_interest_rates", rate_type="LPR")
            if isinstance(lpr_result, dict):
                data["LPR"] = lpr_result
            
            # 获取汇率数据
            currency_result = await self.call_mcp_tool("get_currency_rates", base="USD")
            if isinstance(currency_result, dict):
                data["USD_CNY"] = currency_result
        
        # 执行分析
        if data:
            return await self.analyze(query, framework=framework, data=data)
        else:
            return await self.analyze(query, framework=framework)
    
    async def analyze_policy(self, policy_type: str) -> str:
        """
        分析特定政策
        
        Args:
            policy_type: 政策类型 (货币政策/财政政策/产业政策)
        """
        prompt = f"请详细分析当前{policy_type}的取向、力度和潜在影响"
        return await self.think(prompt)
    
    async def compare_economies(
        self,
        countries: list,
        indicators: list
    ) -> str:
        """
        比较多国经济
        
        Args:
            countries: 国家列表
            indicators: 指标列表
        """
        data = {}
        
        for country in countries:
            country_data = {}
            for indicator in indicators:
                result = await self.call_mcp_tool(
                    "get_macro_indicator",
                    indicator_code=indicator,
                    country=country
                )
                if isinstance(result, dict):
                    country_data[indicator] = result
            data[country] = country_data
        
        prompt = f"请比较多国经济状况：{countries}"
        return await self.analyze(prompt, framework="跨国比较", data=data)
