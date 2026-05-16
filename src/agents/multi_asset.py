"""
多资产分析师 Agent
"""

from typing import Optional, Dict, Any, List
from src.agents.base import BaseAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class MultiAssetAgent(BaseAgent):
    """
    多资产分析师
    
    专注于跨资产配置、组合优化、风险预算
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        super().__init__(brain, mcp)
        self.role = "多资产分析师"
    
    def _build_system_prompt(self) -> str:
        return """你是一位资深多资产分析师，专注于：
- 大类资产配置 (股票、债券、商品、现金)
- 跨资产相关性分析
- 组合构建和优化
- 风险预算管理
- 因子暴露分析
- 绝对收益策略

分析原则：
1. 风险分散：通过多资产配置降低组合风险
2. 风险预算：基于风险预算进行资产配置
3. 动态调整：根据市场环境动态调整配置
4. 成本控制：关注交易成本和滑点

输出格式：
## 核心观点
(当前资产配置的主要观点)

## 资产配置
(各类资产配置比例及逻辑)

## 相关性分析
(资产间相关性变化)

## 风险分析
(组合整体风险暴露)

## 业绩归因
(收益来源分析)

## 调整建议
(近期配置调整建议)
"""
    
    async def process(self, query: str, **kwargs) -> str:
        """
        处理多资产分析查询
        
        Args:
            query: 分析查询
            **kwargs: 其他参数 (assets等)
        """
        assets = kwargs.get("assets", [])
        
        data = {}
        
        # 获取各类资产数据
        for asset in assets:
            asset_type = asset.get("type")
            symbol = asset.get("symbol")
            
            if asset_type == "stock":
                result = await self.call_mcp_tool("get_stock_price", symbol=symbol)
                data[f"stock_{symbol}"] = result
            elif asset_type == "index":
                result = await self.call_mcp_tool("get_index_quote", index_code=symbol)
                data[f"index_{symbol}"] = result
            elif asset_type == "futures":
                result = await self.call_mcp_tool("get_futures_price", contract=symbol)
                data[f"futures_{symbol}"] = result
        
        return await self.analyze(query, data=data)
    
    async def analyze_allocation(
        self,
        portfolio: Dict[str, float],
        benchmark: Optional[Dict[str, float]] = None
    ) -> str:
        """
        分析资产配置
        
        Args:
            portfolio: 当前组合配置 (asset: percentage)
            benchmark: 基准配置 (可选)
        """
        data = {
            "portfolio": portfolio,
            "benchmark": benchmark
        }
        
        prompt = "请分析当前资产配置"
        return await self.analyze(prompt, framework="资产配置", data=data)
    
    async def rebalance_suggestion(
        self,
        current_allocation: Dict[str, float],
        target_allocation: Dict[str, float],
        threshold: float = 0.05
    ) -> str:
        """
        生成再平衡建议
        
        Args:
            current_allocation: 当前配置
            target_allocation: 目标配置
            threshold: 再平衡阈值
        """
        data = {
            "current": current_allocation,
            "target": target_allocation,
            "threshold": threshold
        }
        
        prompt = "请基于以下数据提供再平衡建议"
        return await self.analyze(prompt, framework="再平衡分析", data=data)
    
    async def risk_analysis(
        self,
        portfolio: Dict[str, float],
        confidence_level: float = 0.95
    ) -> str:
        """
        组合风险分析
        
        Args:
            portfolio: 组合配置
            confidence_level: 置信水平
        """
        data = {
            "portfolio": portfolio,
            "confidence_level": confidence_level
        }
        
        prompt = f"请进行组合风险分析 (置信水平: {confidence_level})"
        return await self.analyze(prompt, framework="风险分析", data=data)
