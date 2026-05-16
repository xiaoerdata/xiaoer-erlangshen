"""
SessionStart 钩子 - 会话开始时执行
"""

from datetime import datetime
from typing import Any
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class SessionStartHook:
    """
    会话开始钩子
    
    在新会话开始时执行，用于：
    - 加载市场快照
    - 检查重要数据更新
    - 初始化会话上下文
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
    
    async def run(self) -> None:
        """执行会话开始钩子"""
        try:
            # 获取市场快照
            snapshot = await self._get_market_snapshot()
            
            # 显示欢迎信息
            self._print_welcome(snapshot)
            
        except Exception as e:
            print(f"会话初始化完成 (部分数据加载失败: {e})")
    
    async def _get_market_snapshot(self) -> dict:
        """获取市场快照"""
        snapshot = {
            "indices": [],
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 尝试获取主要指数
        try:
            index_codes = ["000001.SH", "399001.SZ", "399006.SZ", "000300.SH"]
            for code in index_codes:
                result = await self.mcp.call_tool("get_index_quote", index_code=code)
                if isinstance(result, dict) and result.get("price"):
                    snapshot["indices"].append(result)
        except Exception:
            pass
        
        return snapshot
    
    def _print_welcome(self, snapshot: dict) -> None:
        """打印欢迎信息"""
        print(f"\n{'='*50}")
        print(f"  二郎神投资分析智能体")
        print(f"{'='*50}")
        print(f"  时间: {snapshot['time']}")
        
        if snapshot["indices"]:
            print(f"\n  市场快照:")
            for index in snapshot["indices"]:
                name = index.get("name", "")
                price = index.get("price", 0)
                change = index.get("change_pct", 0)
                arrow = "▲" if change >= 0 else "▼"
                color = "" if not hasattr(self, '_has_color') else ("\033[92m" if change >= 0 else "\033[91m")
                reset = "" if not hasattr(self, '_has_color') else "\033[0m"
                print(f"    {name}: {price:.2f} {arrow} {abs(change):.2f}%")
        
        print(f"\n  输入 /help 查看可用命令")
        print(f"{'='*50}\n")
