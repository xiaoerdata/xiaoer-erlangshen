"""
Knowledge - 知识库管理
基于向量的语义搜索知识库
"""
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger


class KnowledgeEntry(BaseModel):
    """知识条目"""
    entry_id: str
    content: str
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict = Field(default_factory=dict)


class KnowledgeBase:
    """
    知识库管理

    提供：
    - 添加知识条目
    - 语义搜索
    - 分类管理
    - 知识沉淀
    """

    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent / "knowledge"
        self.base_path = Path(base_path)
        self.memos_path = self.base_path / "memos"
        self.reports_path = self.base_path / "reports"
        self.insights_path = self.base_path / "insights"
        self.facts_path = self.base_path / "facts"

        # 确保目录存在
        for p in [self.memos_path, self.reports_path, self.insights_path, self.facts_path]:
            p.mkdir(parents=True, exist_ok=True)

        # 内存索引
        self._index: list[KnowledgeEntry] = []
        self._load_index()
        logger.info(f"KnowledgeBase initialized at {self.base_path}")

    def _load_index(self) -> None:
        """加载知识库索引"""
        index_file = self.base_path / "index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                self._index = [KnowledgeEntry(**e) for e in data]
                logger.info(f"Loaded {len(self._index)} entries from index")
            except Exception as e:
                logger.warning(f"Failed to load index: {e}")

    def _save_index(self) -> None:
        """保存知识库索引"""
        index_file = self.base_path / "index.json"
        try:
            data = [e.model_dump() for e in self._index]
            index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    def add(
        self,
        content: str,
        category: str = "general",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> KnowledgeEntry:
        """
        添加知识条目

        Args:
            content: 知识内容
            category: 分类 (memo/report/insight/fact)
            tags: 标签
            metadata: 额外元数据

        Returns:
            KnowledgeEntry 新增的条目
        """
        entry = KnowledgeEntry(
            entry_id=f"kb_{int(time.time()*1000)}",
            content=content,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._index.append(entry)
        self._save_index()
        logger.info(f"Added knowledge entry: {entry.entry_id} [{category}]")
        return entry

    async def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> list[dict]:
        """
        搜索知识库 (简单关键词匹配，实际可接入向量数据库)

        Args:
            query: 搜索查询
            top_k: 返回数量
            category: 限定分类

        Returns:
            list[dict] 匹配的知识条目
        """
        query_lower = query.lower()
        results = []

        for entry in reversed(self._index):  # 优先返回最新的
            if category and entry.category != category:
                continue

            # 简单评分：内容匹配度
            score = 0.0
            query_words = query_lower.split()
            content_lower = entry.content.lower()

            for word in query_words:
                if word in content_lower:
                    score += 1.0
                if word in entry.tags:
                    score += 2.0  # 标签匹配权重更高

            if score > 0:
                results.append({
                    "entry_id": entry.entry_id,
                    "content": entry.content,
                    "category": entry.category,
                    "tags": entry.tags,
                    "score": score,
                    "created_at": entry.created_at,
                })

        # 排序并返回top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def write_memo(self, content: str, title: Optional[str] = None) -> str:
        """写入纪要"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_str = title or "memo"
        filename = self.memos_path / f"{timestamp}_{title_str}.md"
        filename.write_text(content, encoding="utf-8")

        # 同时添加到索引
        self.add(content, category="memo", metadata={"title": title or "untitled"})
        logger.info(f"Wrote memo: {filename.name}")
        return str(filename)

    async def write_report(self, content: str, title: str) -> str:
        """写入报告"""
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = self.reports_path / f"{timestamp}_{title}.md"
        filename.write_text(content, encoding="utf-8")

        self.add(content, category="report", metadata={"title": title})
        logger.info(f"Wrote report: {filename.name}")
        return str(filename)

    async def append_insight(self, insight: str, tags: Optional[list[str]] = None) -> KnowledgeEntry:
        """追加洞察"""
        return self.add(
            content=insight,
            category="insight",
            tags=tags or ["insight"],
        )

    async def add_fact(self, fact: str, source: Optional[str] = None) -> KnowledgeEntry:
        """添加事实"""
        return self.add(
            content=fact,
            category="fact",
            metadata={"source": source} if source else {},
        )

    def list_entries(self, category: Optional[str] = None) -> list[KnowledgeEntry]:
        """列出知识条目"""
        if category:
            return [e for e in self._index if e.category == category]
        return self._index

    def stats(self) -> dict:
        """知识库统计"""
        categories = {}
        for e in self._index:
            categories[e.category] = categories.get(e.category, 0) + 1
        return {
            "total": len(self._index),
            "by_category": categories,
        }
