"""
基础 Agent 类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class BaseAgent(ABC):
    """
    基础 Agent 抽象类
    
    所有专业 Agent 的基类
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.name = self.__class__.__name__
        self.role = "分析师"
        self.system_prompt = self._build_system_prompt()
    
    @abstractmethod
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        pass
    
    @abstractmethod
    async def process(self, query: str, **kwargs) -> str:
        """
        处理查询
        
        Args:
            query: 用户查询
            **kwargs: 其他参数
        
        Returns:
            处理结果
        """
        pass
    
    async def think(
        self,
        prompt: str,
        temperature: Optional[float] = None
    ) -> str:
        """
        统一思考接口
        
        Args:
            prompt: 思考提示
            temperature: 温度参数
        
        Returns:
            思考结果
        """
        return await self.brain.think(
            prompt=prompt,
            system=self.system_prompt,
            temperature=temperature
        )
    
    async def analyze(
        self,
        query: str,
        framework: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        统一分析接口
        
        Args:
            query: 分析查询
            framework: 分析框架
            data: 相关数据
        
        Returns:
            分析结果
        """
        return await self.brain.analyze(
            query=query,
            framework=framework,
            data=data
        )
    
    async def call_mcp_tool(self, tool_name: str, **kwargs) -> Any:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            工具执行结果
        """
        return await self.mcp.call_tool(tool_name, **kwargs)
    
    def get_available_tools(self) -> list:
        """获取可用工具列表"""
        return self.mcp.list_tools()
