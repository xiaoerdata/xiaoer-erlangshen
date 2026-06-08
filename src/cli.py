#!/usr/bin/env python3
"""
二郎神 CLI - 服务端优先的投资分析智能体命令行入口
"""

import asyncio
import importlib
import os
import sys

from src.auth.session import load_auth_session
from src.config import get_config


class CLI:
    """二郎神 CLI 主类"""

    COMMANDS = {
        "analyze": "src.commands.analyze.AnalyzeCommand",
        "macro": "src.commands.macro.MacroCommand",
        "stock": "src.commands.stock.StockCommand",
        "report": "src.commands.report.ReportCommand",
        "search": "src.commands.search.SearchCommand",
        "portfolio": "src.commands.portfolio.PortfolioCommand",
        "risk": "src.commands.risk.RiskCommand",
        "memo": "src.commands.memo.MemoCommand",
        "invest": "src.commands.invest.InvestCommand",
        "omniscient": "src.commands.omniscient.OmniscientCommand",
        "god": "src.commands.omniscient.OmniscientCommand",
        "cognition": "src.commands.cognition.CognitionCommand",
        "auth": "src.commands.auth.AuthCommand",
        "server": "src.commands.server.ServerCommand",
    }
    CLIENT_COMMANDS = {"auth", "server"}

    ALIASES = {
        "login": ("auth", "login"),
        "logout": ("auth", "logout"),
        "status": ("auth", "status"),
        "whoami": ("auth", "status"),
        "me": ("server", "me"),
        "service": ("server", "status"),
        "health": ("server", "health"),
        "map": ("server", "map"),
        "advice": ("server", "advice"),
    }

    def __init__(self):
        self.brain = None
        self.mcp = None
        self.hooks = None

    async def dispatch(self, user_input: str) -> str:
        """把交互输入或一次性参数分发到对应命令。"""
        user_input = (user_input or "").strip()
        if not user_input:
            return ""
        if user_input.startswith("/"):
            parts = user_input[1:].split(maxsplit=1)
            command = parts[0].strip()
            args = parts[1].strip() if len(parts) > 1 else ""
            command, args = self._resolve_alias(command, args)
            return await self.run_command(command, args)
        return await self.run_command("server", f"advice {user_input}")

    def _resolve_alias(self, command: str, args: str) -> tuple[str, str]:
        alias = self.ALIASES.get(command)
        if not alias:
            return command, args
        target_command, prefix = alias
        merged_args = f"{prefix} {args}".strip()
        return target_command, merged_args

    async def run_command(self, command: str, args: str) -> str:
        """执行命令"""
        if command in self.COMMANDS:
            try:
                command_class = self._load_command_class(command)
                brain, mcp = self._command_context(command)
            except ModuleNotFoundError as exc:
                return self._missing_local_module_message(command, exc)
            cmd = command_class(brain, mcp)
            return await cmd.execute(args)
        aliases = ", ".join(f"/{name}" for name in sorted(self.ALIASES))
        return f"未知命令: /{command}\n\n常用命令: {aliases}\n输入 /help 查看完整帮助。"

    def _load_command_class(self, command: str):
        path = self.COMMANDS[command]
        module_name, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)

    def _command_context(self, command: str):
        if command in self.CLIENT_COMMANDS:
            return None, None
        if self.brain is None or self.mcp is None:
            from src.brain import Brain
            from src.mcp.registry import MCPRegistry

            self.brain = Brain()
            self.mcp = MCPRegistry()
        return self.brain, self.mcp

    def _missing_local_module_message(self, command: str, exc: ModuleNotFoundError) -> str:
        return (
            f"当前安装包不包含 /{command} 的本地分析模块: {exc.name}。\n"
            "用户端默认作为瘦客户端运行，请使用 /auth 登录后调用 /server map 或 /server advice。"
        )

    def _init_hooks(self) -> bool:
        if self.hooks is not None:
            return True
        try:
            self._command_context("analyze")
            from src.hooks.session_start import SessionStartHook
            from src.hooks.session_end import SessionEndHook
        except ModuleNotFoundError:
            self.hooks = {}
            return False

        self.hooks = {
            "session_start": SessionStartHook(self.brain, self.mcp),
            "session_end": SessionEndHook(self.brain, self.mcp),
        }
        return True

    async def interactive_mode(self):
        """交互模式"""
        self.print_header()

        # Session start hook
        if self._init_hooks():
            await self.hooks["session_start"].run()

        while True:
            try:
                user_input = input(self.prompt()).strip()

                if not user_input:
                    continue

                if user_input in ["/exit", "/quit", "/q"]:
                    print("再见!")
                    break

                if user_input == "/help":
                    self.print_help()
                    continue

                if user_input == "/clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.print_header()
                    continue

                result = await self.dispatch(user_input)
                if result:
                    print(f"\n{result}\n")

            except KeyboardInterrupt:
                print("\n\n再见!")
                break
            except Exception as e:
                print(f"\n错误: {e}\n")

        # Session end hook
        if self.hooks and "session_end" in self.hooks:
            await self.hooks["session_end"].run()

    def print_header(self) -> None:
        session = load_auth_session()
        base_url = session.get("base_url") or get_config().erlangshen_api_base_url
        user = session.get("user") or {}
        username = user.get("username") or user.get("email") or user.get("id")
        auth_text = username or ("已保存 token" if session.get("token") else "未登录")
        print("二郎神 v0.1.2 - 服务端 CLI")
        print(f"服务端: {base_url}")
        print(f"会话: {auth_text}")
        print("输入自然语言会默认请求 /advice；输入 /help 查看命令，/exit 退出。\n")

    def prompt(self) -> str:
        session = load_auth_session()
        user = session.get("user") or {}
        name = user.get("username") or user.get("email") or user.get("id") or "guest"
        if len(name) > 24:
            name = name[:21] + "..."
        return f"erlangshen:{name}> "

    def print_help(self):
        """打印帮助信息"""
        print("""
二郎神 - 服务端优先 CLI

常用命令:
  /login [xwab|xczt] [账号]    登录核心服务端
  /logout                     清除本地登录状态
  /status                     查看登录状态
  /service                    查看服务端状态
  /health                     服务端健康检查
  /map <问题>                 映射服务端认知场景
  /advice <问题>              生成受保护投资建议
  <自然语言问题>              等同于 /advice <问题>
  /clear                      清屏
  /exit                       退出

完整命令:
  /auth <cmd>                 登录、账号、服务端地址
  /server <cmd>               调用核心服务端 API

本地开发命令:
  /analyze <query>            综合分析
  /macro <query>              宏观分析
  /stock <query>              股票分析
  /report <query>             报告生成
  /search <query>             搜索
  /portfolio <query>          组合分析
  /risk <query>               风险分析
  /memo <query>               纪要管理
  /invest [option]            投资分析

示例:
  erlangshen /auth server https://xiaoerdata.site/api/erlangshen
  erlangshen /login xwab user@example.com
  erlangshen /status
  erlangshen /map 全球流动性转向时风险资产怎么看
  erlangshen /advice 利率下行时A股红利资产怎么看
  erlangshen 利率下行时A股红利资产怎么看
""")


def main():
    """主入口"""
    cli = CLI()

    if len(sys.argv) > 1:
        raw = " ".join(sys.argv[1:]).strip()

        if raw in {"--help", "-h"}:
            cli.print_help()
            return

        result = asyncio.run(cli.dispatch(raw))
        print(result)
    else:
        # 交互模式
        asyncio.run(cli.interactive_mode())


if __name__ == "__main__":
    main()
