"""
股票分析师 Agent
"""

from typing import Optional, Dict, Any, List
from src.agents.base import BaseAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class EquityAgent(BaseAgent):
    """
    股票分析师
    
    专注于A股、港股、美股的基本面和技术面分析
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        super().__init__(brain, mcp)
        self.role = "股票分析师"
    
    def _build_system_prompt(self) -> str:
        return """你是一位资深股票分析师，专注于：
- A股、港股、美股基本面分析
- 公司财务分析 (营收、利润、现金流)
- 行业研究和竞争格局分析
- 估值分析 (PE, PB, DCF)
- 技术分析 (趋势、支撑阻力、量价关系)
- 个股和行业配置建议

分析原则：
1. 价值投资：注重企业内在价值和长期回报
2. 风险收益：平衡收益预期和风险控制
3. 基本面为本：技术面作为辅助参考
4. 分散配置：避免过度集中单一标的

输出格式：
## 核心观点
(1-2句话概括投资逻辑)

## 基本面分析
(公司概况、竞争优势、财务数据)

## 估值分析
(当前估值、历史分位、合理区间)

## 技术面
(近期走势、关键价位、量价配合)

## 风险因素
(主要风险点)

## 投资建议
(买入/持有/卖出建议，目标价位)
"""
    
    async def process(self, query: str, **kwargs) -> str:
        """
        处理股票分析查询
        
        Args:
            query: 分析查询
            **kwargs: 其他参数 (symbol, symbols等)
        """
        symbol = kwargs.get("symbol")
        symbols = kwargs.get("symbols", [])
        days = kwargs.get("days", 30)
        
        data = {}
        
        # 获取股票数据
        if symbol:
            symbols = [symbol]
        
        if symbols:
            quotes = await self.call_mcp_tool("get_realtime_quotes", symbols=symbols)
            if isinstance(quotes, list):
                for quote in quotes:
                    symbol = quote.get("symbol")
                    if symbol:
                        data[symbol] = quote
                        # 获取历史数据
                        history = await self.call_mcp_tool(
                            "get_stock_history",
                            symbol=symbol,
                            days=days
                        )
                        if isinstance(history, list):
                            data[f"{symbol}_history"] = history[-5:]  # 最近5天
        
        # 执行分析
        return await self.analyze(query, data=data)
    
    async def analyze_stock(self, symbol: str, angle: str = "综合") -> str:
        """
        分析单只股票
        
        Args:
            symbol: 股票代码
            angle: 分析角度 (综合/基本面/技术面/估值)
        """
        # 获取数据
        quote = await self.call_mcp_tool("get_stock_price", symbol=symbol)
        history = await self.call_mcp_tool("get_stock_history", symbol=symbol, days=60)
        
        data = {
            "quote": quote,
            "history": history[-10:] if isinstance(history, list) else []
        }
        
        prompt = f"请从{angle}角度分析股票 {symbol}"
        return await self.analyze(prompt, data=data)
    
    async def compare_stocks(self, symbols: List[str]) -> str:
        """
        比较股票
        
        Args:
            symbols: 股票代码列表
        """
        quotes = await self.call_mcp_tool("get_realtime_quotes", symbols=symbols)
        
        data = {"quotes": quotes}
        
        prompt = f"请比较以下股票：{', '.join(symbols)}"
        return await self.analyze(prompt, framework="比较分析", data=data)
    
    async def analyze_sector(self, sector: str) -> str:
        """
        分析行业板块
        
        Args:
            sector: 行业名称
        """
        prompt = f"请分析{sector}行业的：\n1. 当前景气度\n2. 竞争格局\n3. 龙头公司\n4. 投资机会"
        return await self.think(prompt)
