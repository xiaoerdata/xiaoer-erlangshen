"""
Memory - 多层记忆系统
工作记忆、情景记忆、语义记忆、程序记忆
"""
import json
import time
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
from loguru import logger


class Message(BaseModel):
    """工作记忆中的单条消息"""
    role: str  # user, assistant, system
    content: str
    timestamp: float = Field(default_factory=time.time)


class Event(BaseModel):
    """情景记忆中的事件"""
    event_id: str
    description: str
    timestamp: float
    tags: list[str] = Field(default_factory=list)
    importance: float = 0.5  # 0-1


class Memory:
    """
    多层记忆系统

    - working_memory: 当前上下文中的消息
    - episodic_memory: 重要事件记录
    - semantic_memory: 语义知识(通过KnowledgeBase)
    - procedural_memory: 能力技能注册
    """

    def __init__(self, max_working: int = 50):
        self.max_working = max_working
        self.working_memory: list[Message] = []
        self.episodic_memory: list[Event] = []
        self.procedural_memory: dict[str, Any] = {}
        logger.info("Memory initialized")

    async def add_message(self, role: str, content: str) -> None:
        """添加工作记忆消息"""
        msg = Message(role=role, content=content)
        self.working_memory.append(msg)
        if len(self.working_memory) > self.max_working:
            self.working_memory = self.working_memory[-self.max_working:]
        logger.debug(f"Added message to working memory: {role}")

    async def add_interaction(self, query: str, response: str) -> None:
        """记录一次交互"""
        await self.add_message("user", query)
        await self.add_message("assistant", response)

        # 同时记录到情景记忆
        event = Event(
            event_id=f"evt_{int(time.time()*1000)}",
            description=f"Query: {query[:100]} | Response: {response[:100]}",
            timestamp=time.time(),
            tags=["interaction"],
        )
        self.episodic_memory.append(event)
        # 保留最近100个重要事件
        if len(self.episodic_memory) > 100:
            self.episodic_memory = self.episodic_memory[-100:]

    async def get_context(self, last_n: Optional[int] = None) -> list[Message]:
        """获取工作记忆上下文"""
        if last_n:
            return self.working_memory[-last_n:]
        return self.working_memory

    async def get_recent_events(self, hours: float = 24) -> list[Event]:
        """获取最近的事件"""
        now = time.time()
        cutoff = now - hours * 3600
        return [e for e in self.episodic_memory if e.timestamp >= cutoff]

    def register_skill(self, name: str, skill: Any) -> None:
        """注册程序记忆(技能)"""
        self.procedural_memory[name] = skill

    def get_skill(self, name: str) -> Optional[Any]:
        """获取技能"""
        return self.procedural_memory.get(name)

    def list_skills(self) -> list[str]:
        """列出所有已注册技能"""
        return list(self.procedural_memory.keys())

    async def search_episodic(self, keyword: str) -> list[Event]:
        """搜索情景记忆"""
        keyword = keyword.lower()
        return [
            e for e in self.episodic_memory
            if keyword in e.description.lower()
        ]

    def export_state(self) -> dict:
        """导出记忆状态(用于持久化)"""
        return {
            "episodic": [e.model_dump() for e in self.episodic_memory],
            "procedural": list(self.procedural_memory.keys()),
            "export_time": datetime.now().isoformat(),
        }

    def import_state(self, state: dict) -> None:
        """导入记忆状态"""
        if "episodic" in state:
            self.episodic_memory = [Event(**e) for e in state["episodic"]]
        logger.info(f"Imported {len(self.episodic_memory)} events into episodic memory")
