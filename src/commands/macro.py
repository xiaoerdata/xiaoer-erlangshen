"""
/macro 命令 - 宏观分析
"""

from typing import Optional
from src.agents.macro import MacroAgent
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class MacroCommand:
    """
    宏观分析命令处理器
    
    用法:
        /macro CPI走势
        /macro LPR利率
        /macro 美联储政策
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.agent = MacroAgent(brain, mcp)
    
    async def execute(self, args: str) -> str:
        """
        执行宏观分析
        
        Args:
            args: 分析查询
        
        Returns:
            分析结果
        """
        if not args:
            return self._help()
        
        # 解析查询，提取指标
        indicators = self._extract_indicators(args)
        
        return await self.agent.process(
            args,
            indicators=indicators if indicators else None
        )
    
    def _extract_indicators(self, query: str) -> list:
        """从查询中提取宏观指标"""
        indicator_map = {
            "gdp": "GDP",
            "国内生产总值": "GDP",
            "cpi": "CPI",
            "物价": "CPI",
            "通胀": "CPI",
            "ppi": "PPI",
            "生产物价": "PPI",
            "pmi": "PMI",
            "采购经理": "PMI",
            "社融": "社融",
            "社会融资": "社融",
            "m2": "M2",
            "货币": "M2",
            "lpr": "LPR",
            "利率": "LPR",
            "汇率": "汇率",
            "人民币": "汇率",
            "美元": "汇率",
            "出口": "出口",
            "进口": "进口",
        }
        
        query_lower = query.lower()
        found = []
        
        for keyword, indicator in indicator_map.items():
            if keyword in query_lower and indicator not in found:
                found.append(indicator)
        
        return found
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/macro - 宏观分析命令

用法:
    /macro <查询内容>

示例:
    /macro CPI走势
    /macro PPI同比环比
    /macro 制造业PMI
    /macro LPR利率
    /macro 人民币汇率
    /macro 社融数据
    /macro 美联储加息

支持的指标:
    GDP, CPI, PPI, PMI, 社融, M2, LPR, 汇率, 出口, 进口
"""
