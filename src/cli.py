#!/usr/bin/env python3
"""
二郎神 CLI - 投资分析智能体命令行入口
"""

import sys
import asyncio
import os
from typing import Optional

from src.brain import Brain
from src.mcp.registry import MCPRegistry
from src.commands.analyze import AnalyzeCommand
from src.commands.macro import MacroCommand
from src.commands.stock import StockCommand
from src.commands.report import ReportCommand
from src.commands.search import SearchCommand
from src.commands.portfolio import PortfolioCommand
from src.commands.risk import RiskCommand
from src.commands.memo import MemoCommand
from src.hooks.session_start import SessionStartHook
from src.hooks.session_end import SessionEndHook


class CLI:
    """二郎神 CLI 主类"""
    
    COMMANDS = {
        "analyze": AnalyzeCommand,
        "macro": MacroCommand,
        "stock": StockCommand,
        "report": ReportCommand,
        "search": SearchCommand,
        "portfolio": PortfolioCommand,
        "risk": RiskCommand,
        "memo": MemoCommand,
    }
    
    def __init__(self):
        self.brain = Brain()
        self.mcp = MCPRegistry()
        self.hooks = {
            "session_start": SessionStartHook(self.brain, self.mcp),
            "session_end": SessionEndHook(self.brain, self.mcp),
        }
    
    async def run_command(self, command: str, args: str) -> str:
        """执行命令"""
        if command in self.COMMANDS:
            cmd = self.COMMANDS[command](self.brain, self.mcp)
            return await cmd.execute(args)
        else:
            return f"未知命令: /{command}\n\n可用命令:\n" + "\n".join(f"  /{cmd}" for cmd in self.COMMANDS.keys())
    
    async def interactive_mode(self):
        """交互模式"""
        print("二郎神 v0.1.0 - 投资分析智能体")
        print("输入 /help 查看帮助，输入 /exit 退出\n")
        
        # Session start hook
        await self.hooks["session_start"].run()
        
        while True:
            try:
                user_input = input("二郎神> ").strip()
                
                if not user_input:
                    continue
                
                if user_input in ["/exit", "/quit", "/q"]:
                    print("再见!")
                    break
                
                if user_input == "/help":
                    self.print_help()
                    continue
                
                # 处理斜杠命令
                if user_input.startswith("/"):
                    parts = user_input[1:].split(maxsplit=1)
                    command = parts[0]
                    args = parts[1] if len(parts) > 1 else ""
                    result = await self.run_command(command, args)
                else:
                    # 默认执行分析
                    result = await self.run_command("analyze", user_input)
                
                print(f"\n{result}\n")
                
            except KeyboardInterrupt:
                print("\n\n再见!")
                break
            except Exception as e:
                print(f"\n错误: {e}\n")
        
        # Session end hook
        await self.hooks["session_end"].run()
    
    def print_help(self):
        """打印帮助信息"""
        print("""
二郎神 - 投资分析智能体

可用命令:
  /analyze <query>   综合分析 (默认)
  /macro <query>     宏观分析
  /stock <query>     股票分析
  /report <query>    报告生成
  /search <query>    搜索
  /portfolio <query> 组合分析
  /risk <query>      风险分析
  /memo <query>      纪要管理

示例:
  二郎神 /analyze A股当前走势
  二郎神 /macro CPI走势
  二郎神 /stock 茅台
  二郎神 /report 月度报告
""")


def main():
    """主入口"""
    cli = CLI()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--help" or command == "-h":
            cli.print_help()
            return
        
        if command.startswith("/"):
            # 斜杠命令格式
            cmd_parts = command[1:].split(maxsplit=1)
            cmd = cmd_parts[0]
            args = cmd_parts[1] if len(cmd_parts) > 1 else ""
            if len(sys.argv) > 2:
                args = (args + " " + " ".join(sys.argv[2:])).strip() if args else " ".join(sys.argv[2:])
            result = asyncio.run(cli.run_command(cmd, args))
        else:
            # 非斜杠命令格式
            args = " ".join(sys.argv[1:])
            result = asyncio.run(cli.run_command("analyze", args))
        
        print(result)
    else:
        # 交互模式
        asyncio.run(cli.interactive_mode())


if __name__ == "__main__":
    main()
