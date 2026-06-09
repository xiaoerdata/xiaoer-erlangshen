#!/usr/bin/env python3
"""
二郎神 CLI - 投资分析智能体命令行入口
"""

import sys
import asyncio
import difflib
import importlib
import os
import shutil

from src import __version__
from src.auth.session import load_auth_session
from src.config import get_config


LOGO_WIDE = [
    "███████╗██████╗ ██╗      █████╗ ███╗   ██╗ ██████╗ ███████╗██╗  ██╗███████╗███╗   ██╗",
    "██╔════╝██╔══██╗██║     ██╔══██╗████╗  ██║██╔════╝ ██╔════╝██║  ██║██╔════╝████╗  ██║",
    "█████╗  ██████╔╝██║     ███████║██╔██╗ ██║██║  ███╗███████╗███████║█████╗  ██╔██╗ ██║",
    "██╔══╝  ██╔══██╗██║     ██╔══██║██║╚██╗██║██║   ██║╚════██║██╔══██║██╔══╝  ██║╚██╗██║",
    "███████╗██║  ██║███████╗██║  ██║██║ ╚████║╚██████╔╝███████║██║  ██║███████╗██║ ╚████║",
    "╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝",
]
LOGO_COMPACT = [
    "╭────────────────────────────────────╮",
    "│ 二郎神 ERLANGSHEN                  │",
    "│ Service-first investing CLI        │",
    "╰────────────────────────────────────╯",
]

COMMAND_PALETTE = [
    ("login", "/login xwab <账号>", "登录 XWAB/XCZT 账号，获取核心服务端访问权限"),
    ("logout", "/logout", "清除本地登录状态"),
    ("status", "/status", "查看本地登录状态，并校验服务端账号"),
    ("whoami", "/whoami", "查看当前账号状态"),
    ("model", "/model", "检查当前大模型 provider/model/key 配置"),
    ("commands", "/commands", "查看所有斜杠命令"),
    ("service", "/service", "查看核心服务端状态、鉴权、模型和认知保护"),
    ("health", "/health", "检查服务端健康状态"),
    ("me", "/me", "查看服务端绑定账号"),
    ("map", "/map <问题>", "映射服务端受保护认知场景"),
    ("advice", "/advice <问题>", "生成服务端投资建议"),
    ("auth", "/auth <cmd>", "登录、账号状态和服务端地址管理"),
    ("server", "/server <cmd>", "直接调用核心服务端 API"),
    ("analyze", "/analyze <query>", "本地综合分析"),
    ("macro", "/macro <query>", "本地宏观分析"),
    ("stock", "/stock <query>", "本地股票分析"),
    ("report", "/report <query>", "本地报告生成"),
    ("search", "/search <query>", "本地搜索"),
    ("portfolio", "/portfolio <query>", "本地组合分析"),
    ("risk", "/risk <query>", "本地风险分析"),
    ("memo", "/memo <query>", "本地纪要管理"),
    ("invest", "/invest [option]", "本地投资分析工具"),
    ("omniscient", "/omniscient [cmd]", "全知投资 agent 框架"),
    ("god", "/god [cmd]", "全知投资 agent 快捷入口"),
    ("cognition", "/cognition <cmd>", "投资认知体系"),
    ("clear", "/clear", "清屏并重新展示启动面板"),
    ("help", "/help", "查看完整帮助"),
    ("exit", "/exit", "退出交互模式"),
]

PROVIDER_KEY_HINTS = {
    "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"),
    "claude": ("CLAUDE_API_KEY", "CLAUDE_MODEL"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "mimo": ("MIMO_API_KEY", "MIMO_MODEL"),
    "xiaomi": ("XIAOMI_API_KEY", "XIAOMI_MODEL"),
    "kimi": ("KIMI_API_KEY", "KIMI_MODEL"),
    "moonshot": ("MOONSHOT_API_KEY", "MOONSHOT_MODEL"),
}


def _supports_color() -> bool:
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def _color(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _terminal_width() -> int:
    return shutil.get_terminal_size((100, 20)).columns


def _logo() -> str:
    lines = LOGO_WIDE if _terminal_width() >= 96 else LOGO_COMPACT
    return "\n".join(_color(line, "36;1") for line in lines)


def _panel(title: str, rows: list[tuple[str, str]]) -> str:
    width = min(max(54, *(len(label) + len(value) + 8 for label, value in rows)), 92)
    top = f"╭─ {title} " + "─" * max(0, width - len(title) - 5) + "╮"
    bottom = "╰" + "─" * (len(top) - 2) + "╯"
    body = []
    for label, value in rows:
        text = f"{label:<10} {value}"
        body.append("│ " + text[: width - 3].ljust(width - 3) + "│")
    return "\n".join([_color(top, "36"), *body, _color(bottom, "36")])


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
    LOCAL_COMMANDS = {"commands", "cmd", "?", "model", "models", "config"}

    def __init__(self):
        self.brain = None
        self.mcp = None
        self.hooks = None
        self._slash_dropdown_lines = 0

    async def dispatch(self, user_input: str) -> str:
        """把交互输入或一次性参数分发到对应命令。"""
        user_input = (user_input or "").strip()
        if not user_input:
            return ""
        if user_input.startswith("/"):
            raw_command = user_input[1:].strip()
            if not raw_command:
                return self.command_palette_text()
            parts = raw_command.split(maxsplit=1)
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
        if command in {"help", "h"}:
            return self.help_text()
        if command in {"commands", "cmd", "?"}:
            return self.command_palette_text()
        if command in {"model", "models", "config"}:
            return self.model_help_text()
        if command in self.COMMANDS:
            try:
                command_class = self._load_command_class(command)
                brain, mcp = self._command_context(command)
            except Exception as exc:
                return self._missing_local_module_message(command, exc)
            cmd = command_class(brain, mcp)
            return await cmd.execute(args)
        suggestion = self._command_suggestion(command)
        aliases = ", ".join(f"/{item[0]}" for item in COMMAND_PALETTE[:7])
        lines = [f"未知命令: /{command}"]
        if suggestion:
            lines.append(f"你是不是想输入: /{suggestion}")
        lines.extend(["", f"常用命令: {aliases}", "输入 /commands 打开命令面板，输入 /help 查看完整帮助。"])
        return "\n".join(lines)

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

    def _missing_local_module_message(self, command: str, exc: Exception) -> str:
        reason = getattr(exc, "name", None) or str(exc)
        return (
            f"当前安装包不包含 /{command} 的本地分析模块: {reason}。\n"
            "用户端默认作为瘦客户端运行，请使用 /auth 登录后调用 /server map 或 /server advice。"
        )

    def _init_hooks(self) -> bool:
        if self.hooks is not None:
            return True
        try:
            self._command_context("analyze")
            from src.hooks.session_start import SessionStartHook
            from src.hooks.session_end import SessionEndHook
        except Exception:
            self.hooks = {}
            return False

        self.hooks = {
            "session_start": SessionStartHook(self.brain, self.mcp),
            "session_end": SessionEndHook(self.brain, self.mcp),
        }
        return True

    async def interactive_mode(self):
        """交互模式"""
        self._setup_completion()
        self.print_header()

        # Session start hook
        if self._init_hooks():
            await self.hooks["session_start"].run()

        while True:
            try:
                user_input = self._read_prompt().strip()

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

                print(f"\n{result}\n")

            except (KeyboardInterrupt, EOFError):
                print("\n再见!")
                break
            except OSError as exc:
                if self._is_terminal_closed_error(exc):
                    print("\n再见!")
                    break
                print(f"\n错误: {exc}\n")
            except Exception as e:
                print(f"\n错误: {e}\n")

        # Session end hook
        if self.hooks and "session_end" in self.hooks:
            await self.hooks["session_end"].run()

    def print_header(self) -> None:
        session = load_auth_session()
        config = get_config()
        base_url = session.get("base_url") or config.erlangshen_api_base_url
        user = session.get("user") or {}
        username = user.get("username") or user.get("email") or user.get("id")
        auth_text = username or ("已保存 token" if session.get("token") else "未登录")
        provider, model, llm_ready, _ = self._llm_status(config)
        print(_logo())
        print()
        print(_panel("Session", [
            ("version", f"v{__version__}"),
            ("server", base_url),
            ("account", auth_text),
            ("model", f"{provider} / {model} ({'key ready' if llm_ready else 'missing key'})"),
            ("mode", "service-first / protected by xwab/xczt"),
        ]))
        print()
        next_steps = self._next_steps(session, llm_ready)
        if next_steps:
            print(_panel("Next Steps", next_steps))
            print()
        print(_color("输入 / 会弹出命令选择器；输入自然语言会默认请求 /advice；输入 /exit 退出。", "2"))
        print()

    def prompt(self) -> str:
        session = load_auth_session()
        user = session.get("user") or {}
        name = user.get("username") or user.get("email") or user.get("id") or "guest"
        if len(name) > 24:
            name = name[:21] + "..."
        return f"erlangshen:{name}> "

    def print_help(self):
        """打印帮助信息"""
        print(self.help_text())

    def help_text(self) -> str:
        """Return CLI help text."""
        return f"""
{_logo()}

二郎神 - 服务端优先 CLI

常用命令:
  /login [xwab|xczt] [账号]    登录核心服务端
  /logout                     清除本地登录状态
  /status                     查看登录状态
  /model                      检查大模型 provider/model/API key 配置
  /commands                   打开命令面板
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
  erlangshen /model
  erlangshen /commands
  erlangshen /status
  erlangshen /map 全球流动性转向时风险资产怎么看
  erlangshen /advice 利率下行时A股红利资产怎么看
  erlangshen 利率下行时A股红利资产怎么看
"""

    def command_palette_text(self) -> str:
        """Return a compact slash-command palette."""
        rows = [("command", "what it does")]
        rows.extend((shortcut, description) for _, shortcut, description in COMMAND_PALETTE)
        return "\n".join([
            "【二郎神命令面板】",
            _panel("Slash Commands", rows),
            "",
            "提示: 在交互模式下输入 / 会弹出可选择命令列表；输入字母可过滤，↑↓ 选择，Enter 确认。",
        ])

    def model_help_text(self) -> str:
        config = get_config()
        provider, model, ready, key_hint = self._llm_status(config)
        status = "已配置" if ready else "未配置"
        lines = [
            "【大模型配置】",
            f"- 当前 provider: {provider}",
            f"- 当前 model: {model}",
            f"- API key: {status}",
        ]
        if not ready:
            lines.extend([
                "",
                "生产环境建议用环境变量配置，不要写进仓库:",
                f"  export LLM_PROVIDER={provider}",
                f"  export {key_hint}=...",
            ])
            _, model_hint = PROVIDER_KEY_HINTS.get(provider, PROVIDER_KEY_HINTS["openai"])
            if model_hint:
                lines.append(f"  export {model_hint}={model}")
            lines.extend([
                "",
                "常用 provider: openai, claude, deepseek, mimo, kimi",
                "配置后重启 PM2/API 服务，再执行 /service 查看服务端状态。",
            ])
        else:
            lines.append("- 下一步: 执行 /service 查看服务端是否已加载该模型配置")
        return "\n".join(lines)

    def _next_steps(self, session: dict, llm_ready: bool) -> list[tuple[str, str]]:
        steps = []
        if not session.get("token"):
            steps.append(("1 login", "/login xwab <账号>"))
        if not llm_ready:
            steps.append(("2 model", "/model 查看 API key 配置方式"))
        if not steps:
            steps.append(("ready", "直接输入投资问题，或执行 /service"))
        return steps

    def _llm_status(self, config) -> tuple[str, str, bool, str]:
        provider = (config.llm_provider or "openai").lower()
        key_hint, _ = PROVIDER_KEY_HINTS.get(provider, PROVIDER_KEY_HINTS["openai"])
        key = getattr(config, "llm_api_key", None)
        model = getattr(config, "llm_model", None)
        if provider == "deepseek":
            key = getattr(config, "deepseek_api_key", None)
            model = getattr(config, "deepseek_model", None)
        elif provider in {"claude", "anthropic"}:
            key = getattr(config, "claude_api_key", None) or getattr(config, "anthropic_api_key", None)
            model = (
                getattr(config, "claude_model", None)
                or getattr(config, "anthropic_model", None)
                or getattr(config, "llm_model", None)
            )
            key_hint = "CLAUDE_API_KEY"
        elif provider in {"mimo", "xiaomi"}:
            key = getattr(config, "mimo_api_key", None) or getattr(config, "xiaomi_api_key", None)
            model = (
                getattr(config, "mimo_model", None)
                or getattr(config, "xiaomi_model", None)
                or getattr(config, "llm_model", None)
            )
            key_hint = "MIMO_API_KEY"
        elif provider in {"kimi", "moonshot"}:
            key = getattr(config, "kimi_api_key", None) or getattr(config, "moonshot_api_key", None)
            model = (
                getattr(config, "kimi_model", None)
                or getattr(config, "moonshot_model", None)
                or getattr(config, "llm_model", None)
            )
            key_hint = "KIMI_API_KEY"
        return provider, model or "未设置", bool(key), key_hint

    def _command_suggestion(self, command: str) -> str | None:
        candidates = set(self.COMMANDS) | set(self.ALIASES) | self.LOCAL_COMMANDS | {"help", "clear", "exit"}
        matches = difflib.get_close_matches(command, sorted(candidates), n=1, cutoff=0.55)
        return matches[0] if matches else None

    def _read_prompt(self) -> str:
        """Read one prompt, opening a slash-command picker when / starts the line."""
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return input(self.prompt()).strip()

        try:
            import termios
            import tty
        except ImportError:
            return input(self.prompt()).strip()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        buffer = ""
        try:
            tty.setcbreak(fd)
            self._render_prompt(buffer)
            while True:
                ch = sys.stdin.read(1)
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch == "\x04":
                    raise EOFError
                if ch in {"\r", "\n"}:
                    print()
                    return buffer.strip()
                if ch in {"\x7f", "\b"}:
                    buffer = buffer[:-1]
                    self._render_prompt(buffer)
                    continue
                if ch == "/" and not buffer:
                    selected = self._slash_command_picker()
                    self._clear_slash_dropdown()
                    if selected:
                        buffer, needs_more = self._input_from_shortcut(selected[1])
                        if not needs_more:
                            self._render_prompt(buffer)
                            print()
                            return buffer.strip()
                    self._render_prompt(buffer)
                    continue
                if ch.isprintable():
                    buffer += ch
                    self._render_prompt(buffer)
                if not ch:
                    raise EOFError
        except OSError as exc:
            if self._is_terminal_closed_error(exc):
                raise EOFError from exc
            raise
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except OSError:
                pass

    def _render_prompt(self, buffer: str) -> None:
        sys.stdout.write("\r\033[2K" + self.prompt() + buffer)
        sys.stdout.flush()

    def _slash_command_picker(self) -> tuple[str, str, str] | None:
        """Interactive slash-command picker used inside cbreak mode."""
        query = ""
        selected = 0
        while True:
            matches = self._filter_palette(query)
            if selected >= len(matches):
                selected = max(0, len(matches) - 1)
            self._render_slash_picker(matches, selected, query)
            ch = sys.stdin.read(1)
            if ch == "\x03":
                raise KeyboardInterrupt
            if not ch:
                raise EOFError
            if ch == "\x1b":
                import select
                if not select.select([sys.stdin], [], [], 0.05)[0]:
                    return None
                next_char = sys.stdin.read(1)
                if next_char == "[":
                    if not select.select([sys.stdin], [], [], 0.05)[0]:
                        return None
                    direction = sys.stdin.read(1)
                    if direction == "A" and matches:
                        selected = (selected - 1) % len(matches)
                    elif direction == "B" and matches:
                        selected = (selected + 1) % len(matches)
                    continue
                return None
            if ch in {"q", "Q"}:
                return None
            if ch in {"\r", "\n"}:
                return matches[selected] if matches else None
            if ch in {"\x7f", "\b"}:
                query = query[:-1]
                selected = 0
                continue
            if ch.isprintable() and ch != "/":
                query += ch.lower()
                selected = 0
                continue

    def _filter_palette(self, query: str) -> list[tuple[str, str, str]]:
        if not query:
            return COMMAND_PALETTE
        lowered = query.lower()
        return [
            item for item in COMMAND_PALETTE
            if lowered in item[0].lower()
            or lowered in item[1].lower()
            or lowered in item[2].lower()
        ]

    def _render_slash_picker(self, matches: list[tuple[str, str, str]], selected: int, query: str) -> None:
        width = min(max(72, _terminal_width() - 4), 110)
        term_lines = shutil.get_terminal_size((100, 24)).lines
        max_visible = min(14, max(6, term_lines - 8))
        start = max(0, selected - max_visible + 1)
        visible = matches[start:start + max_visible]
        lines = [
            _color("╭─ Slash Commands " + "─" * max(0, width - 20) + "╮", "36"),
            "│ " + f"filter: /{query}".ljust(width - 3) + "│",
            "│ " + "↑↓ 选择  Enter 确认  输入字母过滤  Backspace 删除  Esc/q 取消".ljust(width - 3) + "│",
            "├" + "─" * (width - 2) + "┤",
        ]
        if not visible:
            lines.append("│ " + "没有匹配命令".ljust(width - 3) + "│")
        for idx, (_, shortcut, description) in enumerate(visible):
            marker = "›" if start + idx == selected else " "
            text = f"{marker} {shortcut:<24} {description}"
            lines.append("│ " + text[: width - 3].ljust(width - 3) + "│")
        hidden_before = start
        hidden_after = max(0, len(matches) - start - len(visible))
        if hidden_before or hidden_after:
            lines.append("│ " + f"... 上方 {hidden_before} 条，下方 {hidden_after} 条".ljust(width - 3) + "│")
        lines.append(_color("╰" + "─" * (width - 2) + "╯", "36"))
        self._render_dropdown_below("/" + query, lines)

    def _input_from_shortcut(self, shortcut: str) -> tuple[str, bool]:
        parts = shortcut.split()
        concrete = []
        needs_more = False
        for part in parts:
            if part.startswith("<"):
                needs_more = True
                break
            if part.startswith("["):
                break
            concrete.append(part)
        command = " ".join(concrete)
        if needs_more:
            command += " "
        return command, needs_more

    def _clear_screen(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def _clear_slash_dropdown(self) -> None:
        lines = self._slash_dropdown_lines
        if not lines:
            return
        sys.stdout.write("\n")
        for _ in range(lines):
            sys.stdout.write("\r\033[2K\n")
        sys.stdout.write(f"\033[{lines + 1}A\r\033[2K")
        sys.stdout.flush()
        self._slash_dropdown_lines = 0

    def _render_dropdown_below(self, prompt_buffer: str, lines: list[str]) -> None:
        previous_lines = self._slash_dropdown_lines
        draw_lines = max(previous_lines, len(lines))
        self._render_prompt(prompt_buffer)
        sys.stdout.write("\n")
        for idx in range(draw_lines):
            sys.stdout.write("\r\033[2K")
            if idx < len(lines):
                sys.stdout.write(lines[idx])
            sys.stdout.write("\n")
        sys.stdout.write(f"\033[{draw_lines + 1}A")
        self._render_prompt(prompt_buffer)
        sys.stdout.flush()
        self._slash_dropdown_lines = len(lines)

    def _is_terminal_closed_error(self, exc: OSError) -> bool:
        return getattr(exc, "errno", None) == 5 or "Input/output error" in str(exc)

    def _setup_completion(self) -> None:
        try:
            import readline
        except ImportError:
            return

        commands = sorted({f"/{item[0]}" for item in COMMAND_PALETTE} | {f"/{name}" for name in self.ALIASES})

        def complete(text: str, state: int):
            matches = [command for command in commands if command.startswith(text)]
            return matches[state] if state < len(matches) else None

        readline.set_completer(complete)
        readline.parse_and_bind("tab: complete")


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
