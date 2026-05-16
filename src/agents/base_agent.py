"""
Base Agent - 基础智能体
所有智能体的基类
"""
from abc import ABC, abstractmethod
from typing import Optional, Any
from loguru import logger


class BaseAgent(ABC):
    """
    基础智能体抽象类

    提供：
    - 名称和描述
    - 工具绑定
    - 消息处理
    - 日志记录
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        tools: Optional[dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.tools = tools or {}
        logger.info(f"Agent '{name}' initialized")

    def bind_tool(self, name: str, tool: Any) -> None:
        """绑定工具"""
        self.tools[name] = tool

    async def call_tool(self, name: str, **kwargs) -> Any:
        """调用工具 - 支持 dotted 格式如 'market_tools.get_stock_price'"""
        # 支持 dotted 格式：tool_instance.method_name
        if "." in name:
            parts = name.split(".", 1)
            tool_key = parts[0]
            method_name = parts[1]
            
            if tool_key not in self.tools:
                return {"error": f"Tool '{tool_key}' not found"}
            
            tool = self.tools[tool_key]
            method = getattr(tool, method_name, None)
            if method is None:
                return {"error": f"Method '{method_name}' not found on tool '{tool_key}'"}
            if callable(method):
                return await method(**kwargs)
            return {"error": f"Method '{method_name}' on '{tool_key}' is not callable"}
        
        # 直接格式
        if name not in self.tools:
            return {"error": f"Tool '{name}' not found"}

        tool = self.tools[name]
        if hasattr(tool, "execute"):
            return await tool.execute(**kwargs)
        elif callable(tool):
            return await tool(**kwargs)
        return {"error": f"Tool '{name}' is not callable"}

    @abstractmethod
    async def process(self, query: str, context: Optional[dict] = None) -> dict:
        """
        处理查询 - 子类必须实现

        Args:
            query: 输入查询
            context: 上下文

        Returns:
            dict 处理结果
        """
        pass

    def get_info(self) -> dict:
        """获取智能体信息"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": list(self.tools.keys()),
        }
