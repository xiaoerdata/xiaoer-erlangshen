"""
二郎神CLI增强版
参考 Claude Code 的设计理念，添加更多高级功能
"""
import sys
import asyncio
import os
import time
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, AsyncGenerator
from collections import deque

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
# ANSI 颜色和格式化
# ============================================================
@dataclass
class C:
    """颜色常量"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    
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
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


def c(color: str, text: str) -> str:
    """彩色输出"""
    return f"{color}{text}{C.RESET}"


def is_terminal_closed_error(exc: BaseException) -> bool:
    if isinstance(exc, (EOFError, BrokenPipeError)):
        return True
    if isinstance(exc, OSError):
        args = getattr(exc, "args", ())
        return (
            getattr(exc, "errno", None) == 5
            or 5 in args
            or "Input/output error" in str(exc)
        )
    message = str(exc)
    return "Input/output error" in message or "(5," in message


def clear_line():
    """清除当前行"""
    sys.stdout.write('\r' + ' ' * 100 + '\r')
    sys.stdout.flush()


# ============================================================
# Spinner 增强版
# ============================================================
class Spinner:
    """带消息的加载动画"""
    
    FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self, message: str = "处理中"):
        self.message = message
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self):
        """启动"""
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
    
    def stop(self, final_msg: Optional[str] = None):
        """停止"""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=0.3)
        clear_line()
        if final_msg:
            print(c(C.BRIGHT_GREEN, f"✓ {final_msg}"))
    
    def _spin(self):
        """动画循环"""
        idx = 0
        while self.running and not self._stop_event.is_set():
            frame = self.FRAMES[idx % len(self.FRAMES)]
            msg = f"{frame} {self.message}..."
            sys.stdout.write('\r' + msg)
            sys.stdout.flush()
            idx += 1
            time.sleep(0.08)
        clear_line()


# ============================================================
# 打字机效果（流式输出）
# ============================================================
async def typewriter_stream(
    text: str,
    delay: float = 0.005,
    prefix: str = "",
    color: str = C.WHITE
) -> str:
    """
    流式输出效果
    
    Args:
        text: 要输出的文本
        delay: 每个字符的延迟
        prefix: 每行前缀
        color: 颜色
    
    Returns:
        完整文本
    """
    # 非TTY或文本太长，直接输出
    if not sys.stdout.isatty() or len(text) > 3000:
        print(c(color, text))
        return text
    
    result = []
    for i, char in enumerate(text):
        if char == '\n':
            result.append(char)
            print(c(color, ''.join(result)), end='', flush=True)
            result = []
        else:
            result.append(char)
            if len(result) >= 50 or i == len(text) - 1:
                print(c(color, ''.join(result)), end='', flush=True)
                result = []
        await asyncio.sleep(delay)
    
    if result:
        print(c(color, ''.join(result)), end='', flush=True)
    
    print()  # 换行
    return text


# ============================================================
# Markdown 简单渲染
# ============================================================
class MarkdownRenderer:
    """简单的 Markdown 渲染器"""
    
    @staticmethod
    def render(text: str) -> str:
        """渲染 Markdown 文本（简化版）"""
        lines = text.split('\n')
        output = []
        
        for line in lines:
            # 标题 ##
            if line.startswith('## '):
                title = line[3:]
                output.append(f"\n{C.BRIGHT_CYAN}{C.BOLD}{title}{C.RESET}")
                output.append(f"{C.DIM}{'─' * len(title)}{C.RESET}")
            # 标题 #
            elif line.startswith('# '):
                title = line[2:]
                output.append(f"\n{C.BRIGHT_CYAN}{C.BOLD}{title}{C.RESET}")
            # 列表
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                content = line.strip()[2:]
                output.append(f"  {C.CYAN}●{C.RESET} {content}")
            # 分隔线
            elif line.strip() == '---':
                output.append(f"{C.DIM}{'─' * 50}{C.RESET}")
            # 普通文本
            else:
                output.append(line)
        
        return '\n'.join(output)


# ============================================================
# 命令历史
# ============================================================
class CommandHistory:
    """命令历史管理器"""
    
    def __init__(self, max_size: int = 100):
        self.history: deque = deque(maxlen=max_size)
        self.current_idx: int = -1
    
    def add(self, cmd: str):
        """添加命令"""
        if cmd and (not self.history or self.history[-1] != cmd):
            self.history.append(cmd)
        self.current_idx = len(self.history)
    
    def get_prev(self) -> Optional[str]:
        """获取上一条命令"""
        if self.history:
            self.current_idx = max(0, self.current_idx - 1)
            return self.history[self.current_idx]
        return None
    
    def get_next(self) -> Optional[str]:
        """获取下一条命令"""
        if self.history:
            self.current_idx = min(len(self.history), self.current_idx + 1)
            if self.current_idx >= len(self.history):
                return ""
            return self.history[self.current_idx]
        return None


# ============================================================
# UI 组件
# ============================================================
class UI:
    """UI 组件库"""
    
    # ASCII 艺术横幅
    BANNER = f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════════════╗
║{C.RESET}                                                                      
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}  ██████╗ ██╗   ██╗ ██████╗ ███████╗ ██████╗ ███╗   ██╗  {C.RESET}   
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}  ██╔══██╗██║   ██║██╔═══██╗██╔════╝██╔═══██╗████╗  ██║  {C.RESET}   
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}  ██████╔╝██║   ██║██║   ██║█████╗  ██║   ██║██╔██╗ ██║  {C.RESET}   
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}  ██╔═══╝ ██║   ██║██║   ██║██╔══╝  ██║   ██║██║╚██╗██║  {C.RESET}   
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}  ██║     ╚██████╔╝╚██████╔╝██║     ╚██████╔╝██║ ╚████║  {C.RESET}   
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}  ╚═╝      ╚═════╝  ╚═════╝ ╚═╝      ╚═════╝ ╚═╝  ╚═══╝  {C.RESET}   
║{C.RESET}                                                                      
║{C.RESET}   {C.BRIGHT_CYAN}{C.BOLD}        {C.BRIGHT_YELLOW}AI 投 资 智 能 体{C.RESET}{C.BRIGHT_CYAN}                                       {C.RESET}   
║{C.RESET}                                                                      
║{C.RESET}   {C.DIM}  全知全能 · 天眼洞察 · 投资决策 · 风险评估  {C.RESET}                    {C.CYAN}║
╚══════════════════════════════════════════════════════════════════════╝{C.RESET}
"""
    
    @staticmethod
    def banner():
        """显示横幅"""
        print(UI.BANNER)
        print(f"{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}")
        print(f"  {C.WHITE}输入你的问题，二郎神将为你分析投资机会和风险{C.RESET}")
        print(f"{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}\n")
    
    @staticmethod
    def help_panel():
        """帮助面板"""
        print(f"""
{C.CYAN}╭─────────────────────────────────────────────────────────────────────╮{C.RESET}
{C.CYAN}│{C.RESET}                           {C.BOLD}快捷命令{C.RESET}                                {C.CYAN}│{C.RESET}
{C.CYAN}├─────────────────────────────────────────────────────────────────────┤{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/help{C.RESET}      显示帮助信息                                      {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/market{C.RESET}    查询股票行情  例: /market 000001                  {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/macro{C.RESET}     查询宏观数据  例: /macro CPI                     {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/search{C.RESET}    网络搜索      例: /search A股走势               {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/report{C.RESET}    生成报告      例: /report 周报                  {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/status{C.RESET}   查看状态                                       {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.GREEN}/clear{C.RESET}    清除屏幕                                        {C.CYAN}│{C.RESET}
{C.CYAN}│{C.RESET}  {C.RED}/quit{C.RESET}     退出程序                                        {C.CYAN}│{C.RESET}
{C.CYAN}╰─────────────────────────────────────────────────────────────────────╯{C.RESET}

{C.DIM}示例：{C.RESET}
  {C.WHITE}→{C.RESET}  分析美联储加息对A股的影响
  {C.WHITE}→{C.RESET}  茅台现在值得买入吗？
  {C.WHITE}→{C.RESET}  当前应该怎么配置资产？
  {C.WHITE}→{C.RESET}  分析半导体行业前景
""")
    
    @staticmethod
    def status_bar():
        """状态栏"""
        try:
            width = os.get_terminal_size().columns
        except:
            width = 80
        bar = "─" * max(10, width - 20)
        print(f"\n{C.DIM}┌{bar}┐{C.RESET}")
        print(f"{C.DIM}│{C.RESET}  {C.DIM}↑↓: 历史{C.RESET}  |  {C.DIM}Ctrl+L: 清屏{C.RESET}  |  {C.DIM}Ctrl+C: 中断{C.RESET}  |  {C.DIM}/quit: 退出{C.RESET}  {C.DIM}│{C.RESET}")
        print(f"{C.DIM}└{bar}┘{C.RESET}")

    @staticmethod
    def thinking():
        """思考中"""
        return f"{C.YELLOW}⏳ 思考中...{C.RESET}"

    @staticmethod
    def success(msg: str):
        print(c(C.BRIGHT_GREEN, f"✓ {msg}"))

    @staticmethod
    def error(msg: str):
        print(c(C.BRIGHT_RED, f"✗ {msg}"))

    @staticmethod
    def warning(msg: str):
        print(c(C.YELLOW, f"⚠ {msg}"))

    @staticmethod
    def info(msg: str):
        print(c(C.CYAN, f"ℹ {msg}"))

    @staticmethod
    def section(title: str):
        """分节标题"""
        print(f"\n{C.CYAN}╭{'─' * 58}╮{C.RESET}")
        print(f"{C.CYAN}│{C.RESET}{C.BOLD}{C.BRIGHT_CYAN}  {title}{C.RESET}{' ' * (52 - len(title))}{C.CYAN}│{C.RESET}")
        print(f"{C.CYAN}╰{'─' * 58}╯{C.RESET}\n")


# ============================================================
# 主 CLI 类
# ============================================================
class EnhancedCLI:
    """增强版二郎神CLI"""
    
    def __init__(self):
        self.erlangshen = self._init_erlangshen()
        self.running = True
        self.history = CommandHistory()
        self.spinner = Spinner()
        self.ui = UI()
        self.md = MarkdownRenderer()
        logger.info("Enhanced CLI initialized")

    def _init_erlangshen(self) -> 二郎神:
        """初始化二郎神"""
        logger.info("Initializing 二郎神...")
        
        try:
            from src.config import load_config
            config = load_config()
            deepseek_key = config.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
            if deepseek_key:
                os.environ["DEEPSEEK_API_KEY"] = deepseek_key
        except Exception as e:
            logger.warning(f"Config load failed: {e}")

        return 二郎神(
            brain=Brain(),
            memory=Memory(),
            knowledge=KnowledgeBase(),
            tools={
                "market_tools": MarketTools(),
                "macro_tools": MacroTools(),
                "search_tools": SearchTools(),
                "file_tools": FileTools(),
            },
        )

    def _read_input(self, prompt: str) -> str:
        """读取输入（支持历史）"""
        try:
            import readline
            # 配置 readline
            readline.parse_and_bind('tab: complete')
            readline.set_history_length(100)
            
            # 尝试使用历史
            for cmd in reversed(list(self.history.history)):
                readline.add_history(cmd)
        except:
            pass
        
        try:
            return input(prompt)
        except OSError as exc:
            if is_terminal_closed_error(exc):
                raise EOFError from exc
            raise
        except Exception as exc:
            if is_terminal_closed_error(exc):
                raise EOFError from exc
            raise

    async def _process_command(self, cmd: str) -> Optional[str]:
        """处理命令"""
        cmd = cmd.strip()
        if not cmd:
            return None

        # 命令路由
        if cmd == "/quit":
            self.running = False
            return c(C.CYAN, "\n👋 再见！二郎神退下了。\n")

        if cmd == "/help":
            self.ui.help_panel()
            return None

        if cmd == "/clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            self.ui.banner()
            self.ui.help_panel()
            return None

        if cmd == "/status":
            stats = self.erlangshen.knowledge.stats()
            return f"\n{self.ui.section('知识库状态')}\n{stats}"

        if cmd.startswith("/market "):
            symbol = cmd.split(maxsplit=1)[1]
            try:
                result = await self.erlangshen.tools["market_tools"].get_stock_price(symbol)
                return f"\n{self.ui.section(f'📈 {symbol} 行情')}\n{result}"
            except Exception as e:
                return c(C.BRIGHT_RED, f"查询失败: {e}")

        if cmd.startswith("/macro "):
            indicator = cmd.split(maxsplit=1)[1]
            try:
                result = await self.erlangshen.tools["macro_tools"].get_macro_indicator(indicator)
                return f"\n{self.ui.section(f'📊 {indicator} 数据')}\n{result}"
            except Exception as e:
                return c(C.BRIGHT_RED, f"查询失败: {e}")

        if cmd.startswith("/search "):
            query = cmd.split(maxsplit=1)[1]
            self.ui.status_bar()
            print(f"\n{self.ui.thinking()}")
            self.spinner.message = "搜索中"
            self.spinner.start()
            try:
                result = await self.erlangshen.tools["search_tools"].web_search(query)
                self.spinner.stop("搜索完成")
                return f"\n{self.ui.section(f'🔍 搜索: {query}')}\n{result}"
            except Exception as e:
                self.spinner.stop()
                return c(C.BRIGHT_RED, f"搜索失败: {e}")

        if cmd.startswith("/report "):
            title = cmd.split(maxsplit=1)[1]
            return c(C.YELLOW, f"报告功能开发中: /report {title}")

        # 默认：分析查询
        return await self._analyze(cmd)

    async def _analyze(self, query: str) -> str:
        """执行分析"""
        self.ui.status_bar()
        print(f"\n{self.ui.thinking()}")
        self.spinner.message = "二郎神正在分析"
        self.spinner.start()

        try:
            result = await self.erlangshen.process(query)
            self.spinner.stop("分析完成")
            
            # 格式化输出
            output = self._format_result(result)
            return output
        except Exception as e:
            self.spinner.stop()
            logger.error(f"Analysis error: {e}")
            return c(C.BRIGHT_RED, f"\n❌ 分析出错: {e}")

    def _format_result(self, result: dict) -> str:
        """格式化分析结果"""
        lines = []
        
        lines.append(f"\n{self.ui.section('二郎神分析结果')}")

        # 核心结论
        if "conclusion" in result:
            conclusion = result["conclusion"]
            lines.append(f"{C.BOLD}📊 核心结论{C.RESET}")
            lines.append(f"{C.DIM}{'─' * 50}{C.RESET}")
            lines.append(self.md.render(conclusion[:800]))
            lines.append("")

        # 洞察
        if "erlangshen_insight" in result:
            lines.append(f"{C.BOLD}💡 二郎神洞察{C.RESET}")
            lines.append(f"{C.DIM}{'─' * 50}{C.RESET}")
            insight = result["erlangshen_insight"]
            lines.append(c(C.CYAN, insight[:400]))
            lines.append("")

        # 置信度
        if "analysis" in result:
            analysis = result["analysis"]
            if "confidence" in analysis:
                conf = analysis["confidence"]
                conf_color = C.BRIGHT_GREEN if conf > 0.7 else C.BRIGHT_YELLOW if conf > 0.4 else C.BRIGHT_RED
                lines.append(f"{C.BOLD}🎯 置信度{C.RESET}  {c(conf_color, f'{conf:.0%}')}")

        lines.append(f"\n{C.DIM}{'─' * 60}{C.RESET}")
        return "\n".join(lines)

    async def run(self):
        """运行CLI"""
        os.system('cls' if os.name == 'nt' else 'clear')
        self.ui.banner()
        self.ui.help_panel()

        while self.running:
            try:
                self.ui.status_bar()
                user_input = self._read_input(f"{C.BRIGHT_CYAN}❓ 你:{C.RESET} ")
                
                if not user_input.strip():
                    continue
                
                # 添加到历史
                self.history.add(user_input)
                
                # 处理命令
                result = await self._process_command(user_input)
                if result:
                    print(result)

            except KeyboardInterrupt:
                print(c(C.CYAN, "\n\n👋 已收到 Ctrl+C，正在退出。"))
                self.running = False
                break
            except EOFError:
                break
            except Exception as e:
                if is_terminal_closed_error(e):
                    self.running = False
                    break
                logger.error(f"CLI error: {e}")
                print(c(C.BRIGHT_RED, f"\n❌ 错误: {e}"))

        print(c(C.CYAN, "\n👋 二郎神已退出。再见！\n"))


async def main():
    """入口"""
    print(f"{C.DIM}启动二郎神增强版CLI...{C.RESET}")
    cli = EnhancedCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
