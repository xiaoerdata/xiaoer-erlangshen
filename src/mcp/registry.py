"""
MCP 注册表 - 统一管理所有MCP工具
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    mcp_name: str
    handler: Callable[..., Awaitable[Any]]
    parameters: Dict[str, Any]


class MCPRegistry:
    """
    MCP 注册表
    
    统一管理所有 MCP 工具的注册和调用
    """
    
    def __init__(self):
        self._mcps: Dict[str, Any] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._register_default_mcps()
    
    def _register_default_mcps(self):
        """注册默认 MCP"""
        # Market MCP
        try:
            from src.mcp.market import MarketMCP
            self.register_mcp("market", MarketMCP())
        except Exception as e:
            logger.warning(f"Market MCP 注册失败: {e}")
        
        # Macro MCP
        try:
            from src.mcp.macro import MacroMCP
            self.register_mcp("macro", MacroMCP())
        except Exception as e:
            logger.warning(f"Macro MCP 注册失败: {e}")
        
        # Feishu MCP
        try:
            from src.mcp.feishu import FeishuMCP
            self.register_mcp("feishu", FeishuMCP())
        except Exception as e:
            logger.warning(f"Feishu MCP 注册失败: {e}")
        
        # Fund MCP
        try:
            from src.mcp.fund_tools import FundMCP
            self.register_mcp("fund", FundMCP())
        except Exception as e:
            logger.warning(f"Fund MCP 注册失败: {e}")
    
    def register_mcp(self, name: str, mcp_instance: Any):
        """
        注册 MCP 实例
        
        Args:
            name: MCP 名称
            mcp_instance: MCP 实例
        """
        self._mcps[name] = mcp_instance
        
        # 自动注册 MCP 的工具
        if hasattr(mcp_instance, "list_tools"):
            for tool in mcp_instance.list_tools():
                tool_name = tool["name"]
                handler = getattr(mcp_instance, tool_name, None)
                
                if handler and callable(handler):
                    self._tools[tool_name] = MCPTool(
                        name=tool_name,
                        description=tool["description"],
                        mcp_name=name,
                        handler=handler,
                        parameters=tool.get("parameters", {})
                    )
        
        logger.info(f"MCP '{name}' 已注册，包含 {len([t for t in self._tools.values() if t.mcp_name == name])} 个工具")
    
    def get_mcp(self, name: str) -> Optional[Any]:
        """
        获取 MCP 实例
        
        Args:
            name: MCP 名称
        
        Returns:
            MCP 实例
        """
        return self._mcps.get(name)
    
    def list_mcps(self) -> List[Dict[str, Any]]:
        """列出所有已注册的 MCP"""
        return [
            {
                "name": name,
                "tools": len([t for t in self._tools.values() if t.mcp_name == name])
            }
            for name, mcp in self._mcps.items()
        ]
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "mcp": tool.mcp_name,
                "parameters": tool.parameters
            }
            for tool in self._tools.values()
        ]
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            工具执行结果
        """
        tool = self._tools.get(tool_name)
        
        if not tool:
            return {
                "success": False,
                "error": f"未知工具: {tool_name}",
                "available_tools": list(self._tools.keys())
            }
        
        try:
            result = await tool.handler(**kwargs)
            return result
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        tool = self._tools.get(tool_name)
        
        if not tool:
            return None
        
        return {
            "name": tool.name,
            "description": tool.description,
            "mcp": tool.mcp_name,
            "parameters": tool.parameters
        }
