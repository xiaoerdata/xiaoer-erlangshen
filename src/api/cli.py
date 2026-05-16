"""
CLI - 二郎神命令行界面
参考 Claude Code 的 UI 设计优化版本
"""
import sys
import asyncio
import os
import time
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger

from src.core.brain import Brain
from src.core.memory import Memory
from src.core.knowledge import KnowledgeBase
from src.tools.market_tools import MarketTools
from src.tools.macro_tools import MacroTools
from src.tools.search_tools import SearchTools
from src.tools.file_tools import FileTools
from src.agents.erlang import 二郎神


# ============================================================
# ANSI 颜色定义
# ============================================================
@dataclass
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # 亮色
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"
    
    # 背景色
    BG_BLACK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"


def c(color: str, text: str) -> str:
    """彩色输出辅助函数"""
    return f"{color}{text}{Colors.RESET}"


# ============================================================
# Spinner 进度指示器
# ============================================================
class Spinner:
    """优雅的加载动画"""
    
    FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self, message: str = "二郎神正在思考"):
        self.message = message
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self):
        """启动 spinner"""
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
    
    def stop(self, final_message: Optional[str] = None):
        """停止 spinner"""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.5)
        
        # 清除当前行
        sys.stdout.write('\r' + ' ' * (len(self.message) + 20) + '\r')
        sys.stdout.flush()
        
        if final_message:
            print(c(Colors.BRIGHT_GREEN, f"✓ {final_message}"))
    
    def _spin(self):
        """Spinner 动画循环"""
        idx = 0
        while self.running and not self._stop_event.is_set():
            frame = self.FRAMES[idx % len(self.FRAMES)]
            msg = f"{frame} {self.message}..."
            sys.stdout.write('\r' + msg)
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)
        
        if self.running:
            sys.stdout.write('\r' + ' ' * (len(self.message) + 20) + '\r')
            sys.stdout.flush()


# ============================================================
# 打字机效果
# ============================================================
async def typewriter_effect(
    text: str,
    delay: float = 0.01,
    color: str = Colors.WHITE
):
    """模拟打字机效果输出"""
    # 检测是否启用（终端宽度足够且不是太长的文本）
    if not sys.stdout.isatty() or len(text) > 2000:
        print(c(color, text))
        return
    
    for char in text:
        print(c(color, char), end='', flush=True)
        await asyncio.sleep(delay)
    print()


# ============================================================
# UI 组件
# ============================================================
class UI:
    """UI 组件库"""
    
    @staticmethod
    def banner():
        """现代 ASCII 艺术横幅"""
        banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║{Colors.RESET}                                                                  {Colors.CYAN}║
║{Colors.RESET}   {Colors.BRIGHT_CYAN}{Colors.BOLD}  ▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀  {Colors.RESET}   {Colors.CYAN}║
║{Colors.RESET}   {Colors.BRIGHT_CYAN}{Colors.BOLD}  █  二  郎  神  -  AI  投  资  智  能  体  █  {Colors.RESET}   {Colors.CYAN}║
║{Colors.RESET}   {Colors.BRIGHT_CYAN}{Colors.BOLD}  ▀▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄  {Colors.RESET}   {Colors.CYAN}║
║{Colors.RESET}                                                                  {Colors.CYAN}║
║{Colors.RESET}   {Colors.DIM}  全知全能 · 天眼洞察 · 投资决策 · 风险评估  {Colors.RESET}        {Colors.CYAN}║
║{Colors.RESET}                                                                  {Colors.CYAN}║
╚══════════════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}
{Colors.WHITE}  输入你的问题，二郎神将为你分析投资机会和风险{Colors.RESET}
{Colors.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}
"""
        print(banner)
    
    @staticmethod
    def help_panel():
        """帮助面板"""
        help_text = f"""
{Colors.CYAN}╭─────────────────────────────────────────────────────────╮{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}                    {Colors.BOLD}快捷命令{Colors.RESET}                      {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}├─────────────────────────────────────────────────────────┤{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}/help{Colors.RESET}      显示帮助信息                          {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}/market{Colors.RESET}    查询股票行情  例: /market 000001       {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}/macro{Colors.RESET}     查询宏观数据  例: /macro CPI          {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}/report{Colors.RESET}    生成报告      例: /report 周报         {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}/status{Colors.RESET}   查看状态                                {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.GREEN}/clear{Colors.RESET}    清除对话历史                          {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}│{Colors.RESET}  {Colors.RED}/quit{Colors.RESET}     退出程序                                {Colors.CYAN}│{Colors.RESET}
{Colors.CYAN}╰─────────────────────────────────────────────────────────╯{Colors.RESET}

{Colors.DIM}示例：{Colors.RESET}
  {Colors.WHITE}→{Colors.RESET}  分析美联储加息对A股的影响
  {Colors.WHITE}→{Colors.RESET}  茅台现在值得买入吗？
  {Colors.WHITE}→{Colors.RESET}  当前应该怎么配置资产？
  {Colors.WHITE}→{Colors.RESET}  分析半导体行业前景
"""
        print(help_text)
    
    @staticmethod
    def status_bar():
        """底部状态栏"""
        # 获取终端宽度
        try:
            size = os.get_terminal_size()
            width = size.columns
        except:
            width = 80
        
        bar = "─" * (width - 6)
        print(f"\n{Colors.DIM}┌{bar}┐{Colors.RESET}")
        print(f"{Colors.DIM}│{Colors.RESET}  {Colors.DIM}Ctrl+L: 清屏{Colors.RESET}  |  {Colors.DIM}Ctrl+C: 中断{Colors.RESET}  |  {Colors.DIM}Tab: 自动补全{Colors.RESET}  {Colors.DIM}│{Colors.RESET}")
        print(f"{Colors.DIM}└{bar}┘{Colors.RESET}")

    @staticmethod
    def thinking_indicator():
        """思考中指示"""
        return f"{Colors.YELLOW}⏳ 二郎神正在思考...{Colors.RESET}"

    @staticmethod
    def success(msg: str):
        """成功消息"""
        print(c(Colors.BRIGHT_GREEN, f"✓ {msg}"))

    @staticmethod
    def error(msg: str):
        """错误消息"""
        print(c(Colors.BRIGHT_RED, f"✗ {msg}"))

    @staticmethod
    def warning(msg: str):
        """警告消息"""
        print(c(Colors.YELLOW, f"⚠ {msg}"))

    @staticmethod
    def info(msg: str):
        """信息消息"""
        print(c(Colors.CYAN, f"ℹ {msg}"))


# ============================================================
# CLI 主类
# ============================================================
class CLI:
    """二郎神命令行界面 - 优化版"""

    def __init__(self):
        self.erlangshen = self._init_erlangshen()
        self.running = True
        self.spinner = Spinner()
        self.ui = UI()
        logger.info("CLI initialized")

    def _init_erlangshen(self) -> 二郎神:
        """初始化二郎神"""
        logger.info("Initializing 二郎神...")
        
        # 加载配置
        try:
            from src.config import load_config
            config = load_config()
            deepseek_key = config.deepseek_api_key if config.deepseek_api_key else os.getenv("DEEPSEEK_API_KEY")
            if deepseek_key:
                os.environ["DEEPSEEK_API_KEY"] = deepseek_key
        except Exception as e:
            logger.warning(f"Config load failed: {e}, using env var")

        brain = Brain()
        memory = Memory()
        knowledge = KnowledgeBase()

        tools = {
            "market_tools": MarketTools(),
            "macro_tools": MacroTools(),
            "search_tools": SearchTools(),
            "file_tools": FileTools(),
        }

        return 二郎神(
            brain=brain,
            memory=memory,
            knowledge=knowledge,
            tools=tools,
        )

    def _format_result(self, result: dict) -> str:
        """美化输出格式"""
        lines = []
        
        # 标题框
        lines.append(f"\n{Colors.CYAN}╭{'─' * 58}╮{Colors.RESET}")
        lines.append(f"{Colors.CYAN}│{Colors.RESET}{Colors.BOLD}{Colors.BRIGHT_CYAN}  二郎神分析结果{Colors.RESET}{' ' * 38}{Colors.CYAN}│{Colors.RESET}")
        lines.append(f"{Colors.CYAN}╰{'─' * 58}╯{Colors.RESET}\n")

        # 核心结论
        if "conclusion" in result:
            lines.append(f"{Colors.BOLD}📊 核心结论{Colors.RESET}")
            lines.append(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
            lines.append(f"{Colors.WHITE}{result['conclusion'][:500]}{Colors.RESET}")
            lines.append("")

        # 分析结论
        if "analysis" in result:
            analysis = result["analysis"]
            if "conclusion" in analysis:
                lines.append(f"{Colors.BOLD}📈 分析结论{Colors.RESET}")
                lines.append(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
                lines.append(f"{Colors.WHITE}{analysis['conclusion'][:500]}{Colors.RESET}")
                lines.append("")
            
            # 置信度
            if "confidence" in analysis:
                conf = analysis["confidence"]
                stars = "★" * int(conf * 5) + "☆" * (5 - int(conf * 5))
                conf_color = Colors.GREEN if conf > 0.7 else Colors.YELLOW if conf > 0.4 else Colors.RED
                lines.append(f"{Colors.BOLD}🎯 置信度{Colors.RESET}  {c(conf_color, f'{stars} ({conf:.0%})')}")
                lines.append("")

        # 二郎神洞察
        if "erlangshen_insight" in result:
            lines.append(f"{Colors.BOLD}💡 二郎神洞察{Colors.RESET}")
            lines.append(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
            lines.append(f"{Colors.CYAN}{result['erlangshen_insight'][:300]}{Colors.RESET}")
            lines.append("")

        # 建议
        if "recommendation" in result:
            lines.append(f"{Colors.BOLD}📋 建议{Colors.RESET}")
            lines.append(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
            lines.append(f"{Colors.WHITE}{result['recommendation'][:300]}{Colors.RESET}")
            lines.append("")

        # 底部边框
        lines.append(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")
        
        return "\n".join(lines)

    async def process_command(self, cmd: str) -> Optional[str]:
        """处理命令"""
        cmd = cmd.strip()

        if not cmd:
            return None

        # 命令处理
        if cmd == "/quit":
            self.running = False
            return c(Colors.CYAN, "\n👋 再见！二郎神退下了。\n")

        if cmd == "/help":
            self.ui.help_panel()
            return None

        if cmd == "/clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            self.ui.banner()
            return None

        if cmd == "/status":
            stats = self.erlangshen.knowledge.stats()
            return f"\n{Colors.CYAN}📊 知识库状态{Colors.RESET}\n{stats}"

        if cmd.startswith("/market "):
            symbol = cmd.split()[1]
            try:
                result = await self.erlangshen.tools["market_tools"].get_stock_price(symbol)
                return f"\n{Colors.GREEN}📈 {symbol} 行情:{Colors.RESET}\n{result}"
            except Exception as e:
                return c(Colors.RED, f"查询失败: {e}")

        if cmd.startswith("/macro "):
            indicator = cmd.split()[1]
            try:
                result = await self.erlangshen.tools["macro_tools"].get_macro_indicator(indicator)
                return f"\n{Colors.GREEN}📊 {indicator} 数据:{Colors.RESET}\n{result}"
            except Exception as e:
                return c(Colors.RED, f"查询失败: {e}")

        if cmd.startswith("/report "):
            title = cmd[8:].strip()
            if not title:
                return c(Colors.YELLOW, "请提供报告标题: /report <标题>")
            return c(Colors.YELLOW, f"报告功能开发中: /report {title}")

        # 默认作为分析查询处理
        print(f"\n{self.ui.thinking_indicator()}")
        self.spinner.message = "二郎神正在思考"
        self.spinner.start()
        
        try:
            result = await self.erlangshen.process(cmd)
            self.spinner.stop("分析完成")
            return self._format_result(result)
        except Exception as e:
            self.spinner.stop()
            logger.error(f"Error processing query: {e}")
            return c(Colors.RED, f"\n❌ 处理出错: {e}")

    async def run(self):
        """运行CLI"""
        os.system('cls' if os.name == 'nt' else 'clear')
        self.ui.banner()
        self.ui.help_panel()

        while self.running:
            try:
                # 显示状态栏
                self.ui.status_bar()
                
                # 获取输入
                try:
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: input(f"{Colors.BRIGHT_CYAN}❓ 你:{Colors.RESET} ").strip()
                    )
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print(c(Colors.YELLOW, "\n\n⚠ 使用 /quit 退出"))
                    continue

                if not user_input:
                    continue

                # 处理命令/查询
                result = await self.process_command(user_input)
                if result:
                    print(result)

            except KeyboardInterrupt:
                print(c(Colors.YELLOW, "\n\n⚠ 使用 /quit 退出"))
                continue
            except Exception as e:
                logger.error(f"CLI error: {e}")
                print(c(Colors.RED, f"\n❌ 错误: {e}"))

        print(c(Colors.CYAN, "\n👋 二郎神已退出。再见！\n"))


async def main():
    """主入口"""
    print(f"{Colors.DIM}启动二郎神CLI...{Colors.RESET}")
    cli = CLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
