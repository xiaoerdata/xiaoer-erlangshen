"""
Cerebellum - 认知调度器
协调大脑(Brain)和工具(Tools)，负责任务编排、上下文管理、多跳推理
"""
import json
from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field

from .brain import Brain, AnalysisResult
from .memory import Memory
from .knowledge import KnowledgeBase


class TaskStep(BaseModel):
    """任务步骤"""
    step_id: int
    description: str
    tool: Optional[str] = None
    input_data: dict = Field(default_factory=dict)
    output: Any = None


class TaskPlan(BaseModel):
    """任务计划"""
    task_id: str
    query: str
    steps: list[TaskStep] = Field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed


class Cerebellum:
    """
    认知调度器 - 协调大脑和工具
    工作流程：
    1. 理解意图
    2. 规划任务
    3. 调用工具获取数据
    4. 大脑分析
    5. 生成回复
    6. 更新记忆
    """

    def __init__(
        self,
        brain: Optional[Brain] = None,
        memory: Optional[Memory] = None,
        knowledge: Optional[KnowledgeBase] = None,
    ):
        self.brain = brain or Brain()
        self.memory = memory or Memory()
        self.knowledge = knowledge or KnowledgeBase()
        self._tool_registry: dict[str, Any] = {}

    def register_tool(self, name: str, tool: Any) -> None:
        """注册工具到调度器"""
        self._tool_registry[name] = tool
        logger.info(f"Registered tool: {name}")

    async def _understand_intent(self, query: str) -> dict:
        """理解用户意图，返回意图结构"""
        prompt = f"""分析以下用户查询的意图：

查询：「{query}」

请返回JSON格式：
{{
  "intent": "main intent category",
  "sub_intent": "specific sub-intent",
  "entities": ["key entities mentioned"],
  "required_tools": ["needed tools to fulfill query"],
  "complexity": "low/medium/high"
}}
"""
        try:
            response = await self.brain.think(prompt)
            # 尝试解析JSON
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('{') and 'intent' in line:
                    start = response.find('{')
                    end = response.rfind('}') + 1
                    json_str = response[start:end]
                    return json.loads(json_str)
            return {"intent": "general", "sub_intent": "query", "entities": [], "required_tools": [], "complexity": "low"}
        except Exception as e:
            logger.warning(f"Intent understanding failed: {e}")
            return {"intent": "general", "sub_intent": "query", "entities": [], "required_tools": [], "complexity": "low"}

    async def _plan_tasks(self, query: str, intent: dict) -> TaskPlan:
        """规划任务步骤"""
        task_id = f"task_{hash(query) % 100000}"
        steps = []

        # 根据意图生成步骤
        if "analysis" in intent.get("intent", "").lower():
            steps.append(TaskStep(step_id=1, description="获取相关数据", tool="search"))
            steps.append(TaskStep(step_id=2, description="分析数据", tool=None))
            steps.append(TaskStep(step_id=3, description="生成结论", tool=None))
        elif "market" in intent.get("required_tools", []):
            steps.append(TaskStep(step_id=1, description="查询行情数据", tool="market"))
            steps.append(TaskStep(step_id=2, description="分析走势", tool=None))
        elif "macro" in intent.get("required_tools", []):
            steps.append(TaskStep(step_id=1, description="查询宏观数据", tool="macro"))
            steps.append(TaskStep(step_id=2, description="分析经济形势", tool=None))
        else:
            steps.append(TaskStep(step_id=1, description="搜索相关信息", tool="search"))
            steps.append(TaskStep(step_id=2, description="综合分析", tool=None))

        return TaskPlan(task_id=task_id, query=query, steps=steps)

    async def _execute_step(self, step: TaskStep) -> Any:
        """执行单个任务步骤"""
        if step.tool and step.tool in self._tool_registry:
            tool = self._tool_registry[step.tool]
            if hasattr(tool, "execute"):
                return await tool.execute(**step.input_data)
            elif callable(tool):
                return await tool(**step.input_data)
        return None

    async def process(self, query: str) -> dict:
        """
        处理用户查询的完整流程

        Args:
            query: 用户查询

        Returns:
            dict 包含结果、推理过程、置信度等
        """
        logger.info(f"Cerebellum processing: {query[:100]}")

        # 1. 理解意图
        intent = await self._understand_intent(query)

        # 2. 规划任务
        plan = await self._plan_tasks(query, intent)
        plan.status = "running"

        # 3. 执行任务步骤
        all_data = {}
        for step in plan.steps:
            logger.info(f"Executing step {step.step_id}: {step.description}")
            if step.tool:
                step.output = await self._execute_step(step)
                if step.output:
                    all_data[step.tool] = step.output
            else:
                # 分析步骤不需要工具
                pass

        # 4. 大脑分析
        analysis = await self.brain.analyze(query, data=all_data)

        # 5. 更新记忆
        await self.memory.add_interaction(query, str(analysis.conclusion))

        # 6. 返回结果
        return {
            "query": query,
            "intent": intent,
            "analysis": analysis.model_dump(),
            "plan": {
                "task_id": plan.task_id,
                "steps": [
                    {"step_id": s.step_id, "description": s.description, "tool": s.tool}
                    for s in plan.steps
                ],
            },
        }

    async def query_knowledge(self, query: str, top_k: int = 5) -> list[dict]:
        """查询知识库"""
        return await self.knowledge.search(query, top_k)
