"""
/search 命令 - 搜索
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class SearchCommand:
    """
    搜索命令处理器
    
    用法:
        /search 茅台
        /search 宏观研报
        /search 量化策略
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.knowledge_dir = None
    
    async def execute(self, args: str) -> str:
        """
        执行搜索
        
        Args:
            args: 搜索关键词
        
        Returns:
            搜索结果
        """
        if not args:
            return self._help()
        
        # 优先搜索本地知识库
        local_results = await self._search_local(args)
        
        # 如果本地没有，生成综合回答
        if not local_results:
            result = await self._generate_answer(args)
            return result
        
        return self._format_results(local_results)
    
    async def _search_local(self, query: str) -> List[Dict[str, Any]]:
        """搜索本地知识库"""
        knowledge_base = Path("~/.openclaw-agent-06/workspace/erlangshen/knowledge").expanduser()
        
        if not knowledge_base.exists():
            return []
        
        results = []
        
        # 搜索纪要
        memos_dir = knowledge_base / "memos"
        if memos_dir.exists():
            for file in memos_dir.glob("*.md"):
                if self._matches_query(file, query):
                    results.append({
                        "type": "memo",
                        "title": file.stem,
                        "path": str(file),
                        "content": self._get_preview(file, query)
                    })
        
        # 搜索报告
        reports_dir = knowledge_base / "reports"
        if reports_dir.exists():
            for file in reports_dir.glob("*.md"):
                if self._matches_query(file, query):
                    results.append({
                        "type": "report",
                        "title": file.stem,
                        "path": str(file),
                        "content": self._get_preview(file, query)
                    })
        
        # 搜索洞察
        insights_dir = knowledge_base / "insights"
        if insights_dir.exists():
            for file in insights_dir.glob("*.md"):
                if self._matches_query(file, query):
                    results.append({
                        "type": "insight",
                        "title": file.stem,
                        "path": str(file),
                        "content": self._get_preview(file, query)
                    })
        
        return results
    
    def _matches_query(self, file: Path, query: str) -> bool:
        """检查文件是否匹配查询"""
        try:
            content = file.read_text(encoding="utf-8").lower()
            query_lower = query.lower()
            
            # 简单的关键词匹配
            keywords = query_lower.split()
            for kw in keywords:
                if kw in content:
                    return True
            
            return False
        except Exception:
            return False
    
    def _get_preview(self, file: Path, query: str, max_lines: int = 5) -> str:
        """获取匹配内容预览"""
        try:
            content = file.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            preview = []
            query_lower = query.lower()
            
            for line in lines:
                if query_lower in line.lower():
                    preview.append(line.strip())
                
                if len(preview) >= max_lines:
                    break
            
            return "\n".join(preview) if preview else content[:200]
        except Exception:
            return ""
    
    async def _generate_answer(self, query: str) -> str:
        """生成综合回答"""
        prompt = f"""请回答以下问题：

问题：{query}

请提供：
1. 简洁直接的回答
2. 相关背景信息
3. 可能的行动建议

如果你不知道，请明确说明。
"""
        
        return await self.brain.think(
            prompt,
            system="你是一个知识渊博的投资顾问。请简洁、专业地回答问题。"
        )
    
    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化搜索结果"""
        output = f"找到 {len(results)} 条相关结果：\n\n"
        
        for i, result in enumerate(results, 1):
            output += f"{i}. 【{result['type']}】{result['title']}\n"
            output += f"   {result['content'][:100]}...\n"
            output += f"   📁 {result['path']}\n\n"
        
        return output
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/search - 搜索命令

用法:
    /search <关键词>

示例:
    /search 茅台
    /search 宏观
    /search 量化策略
    /search 美联储

搜索范围:
    - 本地知识库 (纪要、报告、洞察)
    - 实时生成回答

说明:
    搜索会优先查找本地已保存的纪要和报告，
    如果没有找到相关记录，会基于LLM生成回答。
"""
