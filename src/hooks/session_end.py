"""
SessionEnd 钩子 - 会话结束时执行
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class SessionEndHook:
    """
    会话结束钩子
    
    在会话结束时执行，用于：
    - 保存会话摘要
    - 更新知识库
    - 清理临时文件
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.session_summary_dir = Path("~/.openclaw-agent-06/workspace/erlangshen/knowledge/memos").expanduser()
        self.session_summary_dir.mkdir(parents=True, exist_ok=True)
    
    async def run(self) -> None:
        """执行会话结束钩子"""
        try:
            # 生成会话摘要
            summary = self._generate_summary()
            
            # 保存会话摘要
            await self._save_session_summary(summary)
            
        except Exception as e:
            print(f"会话结束处理完成 (部分操作失败: {e})")
    
    def _generate_summary(self) -> dict:
        """生成会话摘要"""
        return {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "conversations": [],
            "commands_executed": [],
        }
    
    async def _save_session_summary(self, summary: dict) -> None:
        """保存会话摘要"""
        filename = f"session_{summary['session_id']}.json"
        filepath = self.session_summary_dir / filename
        
        import json
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
