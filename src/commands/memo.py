"""
/memo 命令 - 纪要管理
"""

from typing import Optional, List
from datetime import datetime
from pathlib import Path
import json
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class MemoCommand:
    """
    纪要管理命令处理器
    
    用法:
        /memo 记录今天的会议
        /memo 列表
        /memo 查看 20240101
        /memo 搜索 茅台
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.memos_dir = Path("~/.openclaw-agent-06/workspace/erlangshen/knowledge/memos").expanduser()
        self.memos_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute(self, args: str) -> str:
        """
        执行纪要操作
        
        Args:
            args: 操作类型和内容
        
        Returns:
            操作结果
        """
        if not args:
            return self._help()
        
        args = args.strip()
        parts = args.split(maxsplit=1)
        action = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        
        if action in ["记", "记录", "add", "create"]:
            return await self._create_memo(content)
        elif action in ["列表", "list"]:
            return self._list_memos()
        elif action in ["查看", "show", "read"]:
            return await self._read_memo(content)
        elif action in ["搜索", "search"]:
            return await self._search_memos(content)
        elif action in ["删除", "delete"]:
            return self._delete_memo(content)
        else:
            # 默认为记录
            return await self._create_memo(args)
    
    async def _create_memo(self, content: str) -> str:
        """创建纪要"""
        if not content:
            return "请提供纪要内容"
        
        # 生成文件名
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{date_str}.md"
        filepath = self.memos_dir / filename
        
        # 构建纪要内容
        memo_content = f"""# 纪要 - {datetime.now().strftime("%Y年%m月%d日 %H:%M")}

## 内容

{content}

---
*由二郎神自动生成*
"""
        
        # 保存
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(memo_content)
        
        return f"✅ 纪要已保存: {filepath.name}"
    
    def _list_memos(self) -> str:
        """列出所有纪要"""
        memos = list(self.memos_dir.glob("*.md"))
        
        if not memos:
            return "暂无纪要"
        
        memos.sort(key=lambda x: x.stem, reverse=True)
        
        output = f"📝 共 {len(memos)} 条纪要：\n\n"
        
        for memo in memos[:20]:  # 最多显示20条
            try:
                content = memo.read_text(encoding="utf-8")
                # 获取标题
                title_line = content.split("\n")[0].replace("#", "").strip()
                # 获取前50字符
                preview = content[content.find("## 内容"):].replace("## 内容", "").strip()[:50]
                
                date_str = memo.stem[:8]
                date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                output += f"- **{date_formatted}** {title_line}\n"
                output += f"  {preview}...\n\n"
            except Exception:
                continue
        
        if len(memos) > 20:
            output += f"\n... 还有 {len(memos) - 20} 条纪要"
        
        return output
    
    async def _read_memo(self, identifier: str) -> str:
        """读取指定纪要"""
        if not identifier:
            return "请提供纪要标识"
        
        # 尝试按日期或文件名查找
        if identifier.isdigit() and len(identifier) == 8:
            # 按日期查找
            pattern = f"{identifier}*"
            matches = list(self.memos_dir.glob(f"{pattern}.md"))
        else:
            # 按文件名或内容搜索
            matches = list(self.memos_dir.glob("*.md"))
            matches = [m for m in matches if identifier in m.stem or identifier in m.read_text()]
        
        if not matches:
            return f"未找到纪要: {identifier}"
        
        # 返回最新的
        memo = sorted(matches, key=lambda x: x.stem, reverse=True)[0]
        content = memo.read_text(encoding="utf-8")
        
        return f"📝 **{memo.stem}**\n\n{content}"
    
    async def _search_memos(self, keyword: str) -> str:
        """搜索纪要"""
        if not keyword:
            return "请提供搜索关键词"
        
        matches = []
        
        for memo in self.memos_dir.glob("*.md"):
            try:
                content = memo.read_text(encoding="utf-8")
                if keyword.lower() in content.lower():
                    matches.append({
                        "file": memo,
                        "content": content[:200]
                    })
            except Exception:
                continue
        
        if not matches:
            return f"未找到包含'{keyword}'的纪要"
        
        output = f"🔍 找到 {len(matches)} 条相关纪要：\n\n"
        
        for match in matches[:10]:
            output += f"- **{match['file'].stem}**\n"
            output += f"  {match['content'][:100]}...\n\n"
        
        return output
    
    def _delete_memo(self, identifier: str) -> str:
        """删除纪要"""
        if not identifier:
            return "请提供要删除的纪要标识"
        
        # 查找纪要
        pattern = f"*{identifier}*" if identifier.isdigit() else f"*{identifier}*.md"
        matches = list(self.memos_dir.glob(pattern))
        
        if not matches:
            return f"未找到纪要: {identifier}"
        
        # 删除第一个匹配
        memo = matches[0]
        memo.unlink()
        
        return f"✅ 已删除: {memo.name}"
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/memo - 纪要管理命令

用法:
    /memo <内容>         - 快速记录
    /memo 记录 <内容>    - 记录新纪要
    /memo 列表           - 查看所有纪要
    /memo 查看 <标识>    - 查看指定纪要
    /memo 搜索 <关键词>  - 搜索纪要
    /memo 删除 <标识>    - 删除纪要

示例:
    /memo 今天讨论了量化策略
    /memo 列表
    /memo 查看 20240101
    /memo 搜索 茅台
    /memo 删除 20240101

说明:
    - 纪要自动保存到本地知识库
    - 支持按日期或关键词搜索
    - 自动生成时间戳
"""
