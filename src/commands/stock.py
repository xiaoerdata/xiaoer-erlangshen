"""
/stock 命令 - 股票分析
"""

from typing import Optional, List
import re
from src.agents.equity import EquityAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class StockCommand:
    """
    股票分析命令处理器
    
    用法:
        /stock 贵州茅台
        /stock 000001
        /stock 腾讯 阿里巴巴
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.agent = EquityAgent(brain, mcp)
    
    async def execute(self, args: str) -> str:
        """
        执行股票分析
        
        Args:
            args: 分析查询
        
        Returns:
            分析结果
        """
        if not args:
            return self._help()
        
        # 提取股票代码或名称
        symbols = self._extract_symbols(args)
        
        if len(symbols) == 1:
            return await self.agent.analyze_stock(symbols[0])
        elif len(symbols) > 1:
            return await self.agent.compare_stocks(symbols)
        else:
            # 无法识别股票，分析查询意图
            return await self.agent.analyze_sector(args)
    
    def _extract_symbols(self, query: str) -> List[str]:
        """从查询中提取股票代码"""
        # A股代码模式 (6位数字)
        a_stock_pattern = r'\b(\d{6})\b'
        a_stocks = re.findall(a_stock_pattern, query)
        
        # 常见股票名称映射
        name_to_symbol = {
            "茅台": "600519.SH",
            "贵州茅台": "600519.SH",
            "平安": "601318.SH",
            "中国平安": "601318.SH",
            "招商": "600036.SH",
            "招商银行": "600036.SH",
            "平安银行": "000001.SZ",
            "万科": "000002.SZ",
            "平安好医生": "1833.HK",
            "腾讯": "0700.HK",
            "阿里巴巴": "9988.HK",
            "美团": "3690.HK",
            "比亚迪": "002594.SZ",
            "美的": "000333.SZ",
            "美的集团": "000333.SZ",
            "恒瑞": "600276.SH",
            "恒瑞医药": "600276.SH",
            "中信": "600030.SH",
            "中芯": "688981.SH",
            "中芯国际": "688981.SH",
            "宁德": "300750.SZ",
            "宁德时代": "300750.SZ",
            "隆基": "601012.SH",
            "隆基绿能": "601012.SH",
        }
        
        symbols = []
        
        # 检查名称
        for name, symbol in name_to_symbol.items():
            if name in query:
                symbols.append(symbol)
        
        # 添加数字代码
        for code in a_stocks:
            # 判断交易所
            if code.startswith(('0', '3')):
                symbol = f"{code}.SZ"
            else:
                symbol = f"{code}.SH"
            
            if symbol not in symbols:
                symbols.append(symbol)
        
        return symbols
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/stock - 股票分析命令

用法:
    /stock <股票名称或代码>
    /stock <股票1> <股票2> ... (比较)

示例:
    /stock 贵州茅台
    /stock 600519
    /stock 腾讯 阿里巴巴 美团
    /stock 比亚迪

支持:
    - A股代码 (自动识别沪深)
    - 港股代码
    - 股票名称 (部分支持)
"""
