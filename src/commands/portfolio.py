"""
/portfolio 命令 - 组合分析
"""

from typing import Optional, Dict, List
from src.agents.multi_asset import MultiAssetAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class PortfolioCommand:
    """
    组合分析命令处理器
    
    用法:
        /portfolio 分析
        /portfolio 再平衡
        /portfolio 风险
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.agent = MultiAssetAgent(brain, mcp)
    
    async def execute(self, args: str) -> str:
        """
        执行组合分析
        
        Args:
            args: 分析类型
        
        Returns:
            分析结果
        """
        if not args:
            return self._help()
        
        args_lower = args.lower()
        
        if "分析" in args or "查看" in args:
            return await self._analyze_portfolio()
        elif "再平衡" in args or "rebalance" in args_lower:
            return await self._rebalance_suggestion()
        elif "风险" in args:
            return await self._risk_analysis()
        elif "收益" in args or "业绩" in args:
            return await self._performance_analysis()
        else:
            return await self._general_analysis(args)
    
    async def _analyze_portfolio(self) -> str:
        """分析组合"""
        # 默认组合配置
        default_portfolio = {
            "沪深300": 0.30,
            "中证500": 0.15,
            "恒生科技": 0.10,
            "纳斯达克": 0.10,
            "黄金": 0.10,
            "债券": 0.15,
            "现金": 0.10,
        }
        
        return await self.agent.analyze_allocation(default_portfolio)
    
    async def _rebalance_suggestion(self) -> str:
        """再平衡建议"""
        current = {
            "沪深300": 0.32,
            "中证500": 0.14,
            "恒生科技": 0.12,
            "纳斯达克": 0.08,
            "黄金": 0.08,
            "债券": 0.16,
            "现金": 0.10,
        }
        
        target = {
            "沪深300": 0.30,
            "中证500": 0.15,
            "恒生科技": 0.10,
            "纳斯达克": 0.10,
            "黄金": 0.10,
            "债券": 0.15,
            "现金": 0.10,
        }
        
        return await self.agent.rebalance_suggestion(current, target)
    
    async def _risk_analysis(self) -> str:
        """风险分析"""
        portfolio = {
            "沪深300": 0.30,
            "中证500": 0.15,
            "恒生科技": 0.10,
            "纳斯达克": 0.10,
            "黄金": 0.10,
            "债券": 0.15,
            "现金": 0.10,
        }
        
        return await self.agent.risk_analysis(portfolio)
    
    async def _performance_analysis(self) -> str:
        """业绩分析"""
        prompt = """请分析以下组合的历史业绩表现：

组合配置:
- 沪深300: 30%
- 中证500: 15%
- 恒生科技: 10%
- 纳斯达克: 10%
- 黄金: 10%
- 债券: 15%
- 现金: 10%

请从以下维度进行分析：
1. 收益表现 (YTD, 1Y, 3Y)
2. 风险指标 (波动率, 最大回撤)
3. 风险调整收益 (夏普比率, 卡玛比率)
4. 业绩归因
"""
        
        return await self.brain.analyze(prompt, framework="业绩归因框架")
    
    async def _general_analysis(self, args: str) -> str:
        """通用分析"""
        return await self.brain.analyze(
            f"关于组合管理的问题：{args}",
            framework="多资产配置框架"
        )
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/portfolio - 组合分析命令

用法:
    /portfolio 分析     - 分析当前组合配置
    /portfolio 再平衡   - 提供再平衡建议
    /portfolio 风险     - 组合风险分析
    /portfolio 业绩     - 业绩表现分析

示例:
    /portfolio 分析
    /portfolio 再平衡
    /portfolio 风险
    /portfolio 业绩归因

说明:
    系统使用默认的参考组合配置进行分析。
    如需分析自定义组合，请提供具体的配置比例。
"""
