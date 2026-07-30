"""
MCP 注册表 - 统一管理所有MCP工具
"""

import inspect
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
import logging

from src.mcp.protocol import normalize_tool_definition

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    mcp_name: str
    handler: Callable[..., Awaitable[Any]]
    parameters: Dict[str, Any]
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    annotations: Optional[Dict[str, Any]] = None
    icons: Optional[List[Dict[str, Any]]] = None


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

        # Super-66 MCP
        try:
            from src.mcp.super66 import Super66MCP
            self.register_mcp("super66", Super66MCP())
        except Exception as e:
            logger.warning(f"Super66 MCP 注册失败: {e}")
    
    def register_mcp(self, name: str, mcp_instance: Any):
        """
        注册 MCP 实例
        
        Args:
            name: MCP 名称
            mcp_instance: MCP 实例
        """
        self._mcps[name] = mcp_instance
        
        # 自动注册 MCP 的工具。部分远程 MCP 的 list_tools 是异步探测接口，
        # registry 需要使用同步清单，避免初始化时误触发网络调用。
        for tool in self._get_registry_tool_defs(mcp_instance):
            tool_name = tool["name"]
            handler_name = tool.get("handler", tool_name)
            handler = getattr(mcp_instance, handler_name, None)

            if handler and callable(handler):
                tool = normalize_tool_definition(tool, handler)
                self._register_tool_alias(
                    public_name=tool_name,
                    mcp_name=name,
                    handler=handler,
                    description=tool["description"],
                    parameters=tool.get("parameters", {}),
                    input_schema=tool["inputSchema"],
                    output_schema=tool.get("outputSchema"),
                    title=tool.get("title"),
                    annotations=tool.get("annotations"),
                    icons=tool.get("icons"),
                )

                # 同时注册带 MCP 前缀的别名，解决不同 MCP 工具重名问题。
                prefixed_name = tool.get("alias") or f"{name}_{tool_name}"
                if prefixed_name != tool_name:
                    self._register_tool_alias(
                        public_name=prefixed_name,
                        mcp_name=name,
                        handler=handler,
                        description=f"{name}: {tool['description']}",
                        parameters=tool.get("parameters", {}),
                        input_schema=tool["inputSchema"],
                        output_schema=tool.get("outputSchema"),
                        title=tool.get("title"),
                        annotations=tool.get("annotations"),
                        icons=tool.get("icons"),
                        overwrite=False,
                    )
        
        logger.info(f"MCP '{name}' 已注册，包含 {len([t for t in self._tools.values() if t.mcp_name == name])} 个工具")

    def _get_registry_tool_defs(self, mcp_instance: Any) -> List[Dict[str, Any]]:
        """获取可同步注册到本地 registry 的工具定义。"""
        if hasattr(mcp_instance, "list_registry_tools"):
            return mcp_instance.list_registry_tools()

        list_tools = getattr(mcp_instance, "list_tools", None)
        if not callable(list_tools):
            return []

        if inspect.iscoroutinefunction(list_tools):
            logger.debug(
                "跳过异步 list_tools 注册；如需注册请提供 list_registry_tools"
            )
            return []

        tools = list_tools()
        if inspect.isawaitable(tools):
            close = getattr(tools, "close", None)
            if callable(close):
                close()
            logger.debug(
                "跳过 awaitable list_tools 注册；如需注册请提供 list_registry_tools"
            )
            return []
        return list(tools or [])

    def _register_tool_alias(
        self,
        public_name: str,
        mcp_name: str,
        handler: Callable[..., Awaitable[Any]],
        description: str,
        parameters: Dict[str, Any],
        input_schema: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        annotations: Optional[Dict[str, Any]] = None,
        icons: Optional[List[Dict[str, Any]]] = None,
        overwrite: bool = True,
    ) -> None:
        """注册工具名或别名，默认不让跨 MCP 重名工具悄悄覆盖。"""
        existing = self._tools.get(public_name)
        if existing and existing.mcp_name != mcp_name and not overwrite:
            return
        if existing and existing.mcp_name != mcp_name and overwrite:
            logger.info(
                "工具名 %s 已由 MCP '%s' 注册，保留原工具；请使用带前缀别名",
                public_name,
                existing.mcp_name,
            )
            return

        self._tools[public_name] = MCPTool(
            name=public_name,
            description=description,
            mcp_name=mcp_name,
            handler=handler,
            parameters=parameters,
            input_schema=input_schema,
            output_schema=output_schema,
            title=title,
            annotations=annotations,
            icons=icons,
        )
    
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
        """列出所有可用工具，兼容旧字段并提供标准 MCP Tool schema。"""
        tools = []
        for tool in self._tools.values():
            item = {
                "name": tool.name,
                "description": tool.description,
                "mcp": tool.mcp_name,
                "parameters": tool.parameters,
                "inputSchema": tool.input_schema,
            }
            if tool.output_schema is not None:
                item["outputSchema"] = tool.output_schema
            if tool.title:
                item["title"] = tool.title
            if tool.annotations:
                item["annotations"] = tool.annotations
            if tool.icons:
                item["icons"] = tool.icons
            tools.append(item)
        return tools
    
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
        
        item = {
            "name": tool.name,
            "description": tool.description,
            "mcp": tool.mcp_name,
            "parameters": tool.parameters,
            "inputSchema": tool.input_schema,
        }
        if tool.output_schema is not None:
            item["outputSchema"] = tool.output_schema
        if tool.title:
            item["title"] = tool.title
        if tool.annotations:
            item["annotations"] = tool.annotations
        if tool.icons:
            item["icons"] = tool.icons
        return item
