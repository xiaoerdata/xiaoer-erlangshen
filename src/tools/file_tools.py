"""
File Tools - 文件/报告工具
知识沉淀、纪要写入、报告生成
"""
import os
from pathlib import Path
from typing import Optional
from datetime import datetime
from loguru import logger


class FileTools:
    """
    文件工具集

    工具函数：
    - write_memo: 写入纪要
    - write_report: 写入报告
    - search_knowledge: 搜索知识库
    - append_insight: 追加洞察
    """

    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            base_path = Path.home() / ".openclaw-agent-06" / "workspace" / "erlangshen" / "knowledge"
        self.base_path = Path(base_path)
        self.memos_path = self.base_path / "memos"
        self.reports_path = self.base_path / "reports"
        self.insights_path = self.base_path / "insights"

        for p in [self.memos_path, self.reports_path, self.insights_path]:
            p.mkdir(parents=True, exist_ok=True)

        logger.info(f"FileTools initialized at {self.base_path}")

    async def execute(self, tool_name: str, **kwargs) -> any:
        """执行指定工具"""
        method = getattr(self, tool_name, None)
        if method and callable(method):
            return await method(**kwargs)
        return {"error": f"Unknown tool: {tool_name}"}

    async def write_memo(
        self,
        content: str,
        title: Optional[str] = None,
    ) -> dict:
        """
        写入纪要

        Args:
            content: 纪要内容
            title: 标题

        Returns:
            dict 操作结果
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_str = title or "memo"
        filename = f"{timestamp}_{title_str}.md"
        filepath = self.memos_path / filename

        try:
            filepath.write_text(content, encoding="utf-8")
            logger.info(f"Wrote memo: {filename}")
            return {
                "status": "success",
                "filename": filename,
                "path": str(filepath),
            }
        except Exception as e:
            logger.error(f"Failed to write memo: {e}")
            return {"status": "error", "message": str(e)}

    async def write_report(
        self,
        content: str,
        title: str,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """
        写入报告

        Args:
            content: 报告内容
            title: 标题
            tags: 标签

        Returns:
            dict 操作结果
        """
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{timestamp}_{title}.md"
        filepath = self.reports_path / filename

        try:
            # 添加元数据头
            header = f"""---
title: {title}
date: {datetime.now().isoformat()}
tags: {tags or []}
---

"""
            filepath.write_text(header + content, encoding="utf-8")
            logger.info(f"Wrote report: {filename}")
            return {
                "status": "success",
                "filename": filename,
                "path": str(filepath),
            }
        except Exception as e:
            logger.error(f"Failed to write report: {e}")
            return {"status": "error", "message": str(e)}

    async def append_insight(
        self,
        insight: str,
        category: str = "general",
    ) -> dict:
        """
        追加洞察到洞察文件

        Args:
            insight: 洞察内容
            category: 分类

        Returns:
            dict 操作结果
        """
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"insights_{timestamp}.md"
        filepath = self.insights_path / filename

        try:
            content = f"""# 洞察 {datetime.now().strftime("%Y-%m-%d %H:%M")}

**分类**: {category}

{insight}

---
"""
            filepath.write_text(content, encoding="utf-8")
            logger.info(f"Appended insight: {filename}")
            return {
                "status": "success",
                "filename": filename,
                "path": str(filepath),
            }
        except Exception as e:
            logger.error(f"Failed to append insight: {e}")
            return {"status": "error", "message": str(e)}

    async def search_knowledge(
        self,
        query: str,
        path: Optional[str] = None,
    ) -> list[str]:
        """
        搜索知识库文件

        Args:
            query: 搜索关键词
            path: 搜索路径

        Returns:
            list[str] 匹配的文件列表
        """
        search_path = Path(path) if path else self.base_path
        results = []
        query_lower = query.lower()

        try:
            for filepath in search_path.rglob("*.md"):
                try:
                    content = filepath.read_text(encoding="utf-8").lower()
                    if query_lower in content:
                        results.append(str(filepath))
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Search failed: {e}")

        return results

    async def list_memos(self) -> list[dict]:
        """列出所有纪要"""
        memos = []
        for f in sorted(self.memos_path.glob("*.md"), reverse=True):
            memos.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return memos

    async def list_reports(self) -> list[dict]:
        """列出所有报告"""
        reports = []
        for f in sorted(self.reports_path.glob("*.md"), reverse=True):
            reports.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return reports
