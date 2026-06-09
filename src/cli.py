#!/usr/bin/env python3
"""
二郎神 CLI - 投资分析智能体命令行入口
"""

import sys
import asyncio
import difflib
import getpass
import importlib
import json
import os
import shutil

from src import __version__
from src.auth.session import load_auth_session
from src.config import get_config, get_config_path, update_config
from src.model_presets import MODEL_PRESETS, get_provider_preset, normalize_provider


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
    ("model-select", "/model select", "用光标选择大模型供应商和型号"),
    ("model-key", "/model key", "在本机输入并保存当前供应商 API Key"),
    ("commands", "/commands", "查看所有斜杠命令"),
    ("service", "/service", "查看核心服务端状态、鉴权、模型和认知保护"),
    ("health", "/health", "检查服务端健康状态"),
    ("me", "/me", "查看服务端绑定账号"),
    ("map", "/map <问题>", "映射服务端受保护认知场景"),
    ("advice", "/advice <问题>", "服务端映射场景，本机大模型生成投资建议"),
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
    }
    LOCAL_COMMANDS = {"commands", "cmd", "?", "model", "models", "config"}

    def __init__(self):
        self.brain = None
        self.mcp = None
        self.hooks = None
        self._slash_dropdown_lines = 0
        self._input_history: list[str] = []
        self._prompt_session = None
        self._slash_selected = 0

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
        return await self.client_side_advice(user_input)

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
            if args.strip().lower() in {"select", "choose", "set", "配置", "选择"}:
                return await self.model_select_interactive()
            if args.strip().lower() in {"key", "apikey", "api-key", "密钥", "配置key"}:
                return self.model_key_interactive()
            return self.model_help_text()
        if command in {"advice", "建议", "投顾"}:
            if not args.strip():
                return "请提供需要分析的投资问题。示例：/advice 利率下行时A股红利资产怎么看"
            return await self.client_side_advice(args.strip())
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
                user_input = (await self._read_prompt()).strip()

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
                if self._should_exit_for_terminal(exc):
                    print("\n再见!")
                    break
                print(f"\n错误: {exc}\n")
            except Exception as exc:
                if self._should_exit_for_terminal(exc):
                    print("\n再见!")
                    break
                print(f"\n错误: {exc}\n")

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
        provider, model, llm_ready, key_hint = self._llm_status(config)
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
        if not llm_ready:
            print(_color(f"注意: 当前大模型 API Key 未配置，请输入 /model key 在本机保存，或设置 {key_hint}=...。", "33;1"))
            print()
        print(_color("输入 / 会弹出命令选择器；自然语言会先请求服务端场景映射，再由本机大模型生成建议；输入 /exit 退出。", "2"))
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
  /model select               光标选择大模型供应商和型号
  /model key                  在本机输入并保存当前供应商 API Key
  /commands                   打开命令面板
  /service                    查看服务端状态
  /health                     服务端健康检查
  /map <问题>                 映射服务端认知场景
  /advice <问题>              服务端映射场景，本机大模型生成建议
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
  erlangshen /model select
  erlangshen /model key
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
        preset = get_provider_preset(provider)
        status = "已配置" if ready else "未配置"
        lines = [
            "【大模型配置】",
            f"- 当前 provider: {provider}",
            f"- 当前 model: {model}",
            f"- API key: {status}",
            "- Key 位置: 只保存在本机配置/环境变量；不会发送给二郎神服务端",
            "- 调用方式: 服务端只返回受保护场景映射；最终投资建议由客户端直连大模型生成",
            "",
            "OpenAI 提示: GPT-5.5/GPT-5.3 当前主要是 ChatGPT/Codex 侧选择；API 预设仍使用官方 API 模型列表中的 gpt-5.2。",
            "",
            "可选供应商和型号:",
        ]
        for provider_preset in MODEL_PRESETS:
            default_marker = " (当前)" if provider_preset.id == normalize_provider(provider) else ""
            lines.append(f"- {provider_preset.id}: {provider_preset.display_name}{default_marker}")
            for model_preset in provider_preset.models:
                selected = " *" if provider_preset.id == normalize_provider(provider) and model_preset.id == model else ""
                lines.append(f"  - {model_preset.id}{selected}: {model_preset.description}")
        lines.extend([
            "",
            "交互配置: 输入 /model select 选择供应商和型号；输入 /model key 在本机保存 API Key。",
        ])
        if not ready:
            lines.extend([
                "",
                f"注意: 当前 {preset.display_name} API Key 未设置，客户端无法直连该供应商生成投资建议。",
                "",
                "可直接输入:",
                "  erlangshen /model key",
                "",
                "也可以用环境变量配置，不要写进仓库:",
                f"  export LLM_PROVIDER={preset.id}",
                f"  export {key_hint}=...",
            ])
            lines.append(f"  export {preset.model_env}={model}")
            lines.extend([
                "",
                "配置后直接重新运行 erlangshen；无需把 Key 配到二郎神服务端。",
            ])
        else:
            lines.append("- 下一步: 直接输入投资问题，客户端会用本机 Key 调用大模型")
        return "\n".join(lines)

    async def model_select_interactive(self) -> str:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return "\n".join([
                "【大模型选择】",
                "当前不是交互终端，不能打开光标选择器。",
                "",
                "请在 erlangshen 交互模式里输入 /model select；或者用环境变量配置:",
                "  export LLM_PROVIDER=openai",
                "  export OPENAI_MODEL=gpt-5.2",
            ])

        provider_items = [
            (preset.id, preset.display_name, f"{preset.key_env} / 默认 {preset.default_model}")
            for preset in MODEL_PRESETS
        ]
        provider_id = await self._select_list("选择大模型供应商", provider_items)
        if not provider_id:
            return "已取消模型选择。"

        provider = get_provider_preset(provider_id)
        model_items = [
            (model.id, model.label, model.description)
            for model in provider.models
        ]
        model_id = await self._select_list(f"选择 {provider.display_name} 模型", model_items)
        if not model_id:
            return "已取消模型选择。"

        update_kwargs = {"llm_provider": provider.id}
        update_kwargs.update(self._provider_model_update(provider.id, model_id))
        update_config(**update_kwargs)
        saved_key = self._maybe_prompt_api_key(provider.id)
        _, _, ready, key_hint = self._llm_status(get_config())

        lines = [
            "【大模型配置已更新】",
            f"- provider: {provider.id} ({provider.display_name})",
            f"- model: {model_id}",
            f"- 配置文件: {get_config_path()}",
            "- Key 处理: 只保存在本机配置/环境变量，不会发送给二郎神服务端",
        ]
        if saved_key:
            lines.append("- API Key: 已保存到本机配置")
        elif not ready:
            lines.extend([
                f"- API Key: 未配置，请设置 {key_hint}=...",
                "",
                f"注意: 未配置 {provider.display_name} API Key 前，客户端无法直连该供应商生成投资建议。",
            ])
        lines.extend([
            "",
            "也可以用环境变量配置:",
            f"  export LLM_PROVIDER={provider.id}",
            f"  export {provider.key_env}=...",
            f"  export {provider.model_env}={model_id}",
            "",
            "之后可直接输入投资问题；服务端只做场景映射，最终建议由本机大模型生成。",
        ])
        return "\n".join(lines)

    def model_key_interactive(self) -> str:
        config = get_config()
        provider, model, ready, key_hint = self._llm_status(config)
        preset = get_provider_preset(provider)
        if not sys.stdin.isatty():
            return "\n".join([
                "【本机 API Key 配置】",
                "当前不是交互终端，不能安全读取 API Key。",
                "",
                "请在交互终端执行:",
                "  erlangshen /model key",
                "",
                "或使用环境变量:",
                f"  export LLM_PROVIDER={preset.id}",
                f"  export {key_hint}=...",
                f"  export {preset.model_env}={model}",
                "",
                "说明: 该 Key 只用于客户端直连大模型，不会发送给二郎神服务端。",
            ])
        api_key = getpass.getpass(f"{preset.display_name} API Key（只保存本机，不发送服务端；留空取消）: ").strip()
        if not api_key:
            return "已取消 API Key 输入。"
        update_config(**self._provider_key_update(preset.id, api_key))
        return "\n".join([
            "【API Key 已保存到本机】",
            f"- provider: {preset.id} ({preset.display_name})",
            f"- model: {model}",
            f"- 配置文件: {get_config_path()}",
            "- 安全边界: Key 不会发送给二郎神服务端；/advice 只把问题发给服务端做场景映射",
            "- 下一步: 直接输入投资问题，客户端会直连大模型生成分析",
        ])

    def _maybe_prompt_api_key(self, provider: str) -> bool:
        _, _, ready, _ = self._llm_status(get_config())
        if ready or not sys.stdin.isatty():
            return False
        preset = get_provider_preset(provider)
        answer = input(f"是否现在输入 {preset.display_name} API Key？只保存本机，不发送服务端 [y/N]: ").strip().lower()
        if answer not in {"y", "yes", "是", "好"}:
            return False
        api_key = getpass.getpass(f"{preset.display_name} API Key: ").strip()
        if not api_key:
            return False
        update_config(**self._provider_key_update(provider, api_key))
        return True

    def _provider_model_update(self, provider: str, model: str) -> dict[str, str]:
        provider = normalize_provider(provider)
        if provider == "openai":
            return {"llm_model": model}
        if provider == "deepseek":
            return {"deepseek_model": model}
        if provider == "claude":
            return {"claude_model": model}
        if provider == "mimo":
            return {"mimo_model": model}
        if provider == "kimi":
            return {"kimi_model": model}
        return {"llm_model": model}

    def _provider_key_update(self, provider: str, api_key: str) -> dict[str, str]:
        provider = normalize_provider(provider)
        if provider == "openai":
            return {"llm_api_key": api_key}
        if provider == "deepseek":
            return {"deepseek_api_key": api_key}
        if provider == "claude":
            return {"claude_api_key": api_key}
        if provider == "mimo":
            return {"mimo_api_key": api_key}
        if provider == "kimi":
            return {"kimi_api_key": api_key}
        return {"llm_api_key": api_key}

    def _select_style_current(self) -> str:
        return "bg:#00a3a3 #000000 bold"

    def _ansi_selected_style(self) -> str:
        return "30;46"

    async def client_side_advice(self, raw_query: str) -> str:
        parsed = self._parse_client_advice_input(raw_query)
        if isinstance(parsed, str):
            return parsed
        query, payload = parsed
        config = get_config()
        provider, model, ready, key_hint = self._llm_status(config)
        if not ready:
            return "\n".join([
                "【需要本机大模型 API Key】",
                f"- 当前 provider: {provider}",
                f"- 当前 model: {model}",
                f"- 缺少: {key_hint}",
                "",
                "二郎神不会要求你把大模型 API Key 发给服务端。",
                "请先在本机配置 Key，之后客户端会直连模型供应商生成投资建议:",
                "  erlangshen /model key",
                "",
                "服务端只接收你的问题用于受保护场景映射，不接收、不存储、不转发你的大模型 API Key。",
            ])

        try:
            from src.auth.session import load_auth_session
            from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient
            from src.llm import LLMClient, resolve_llm_settings

            session = load_auth_session()
            client = ErlangshenServerClient(
                base_url=session.get("base_url") or config.erlangshen_api_base_url,
                token=session.get("token"),
            )
            mapping = await client.cognition_map(query)
        except ErlangshenAPIError as exc:
            return "\n".join([
                f"服务端场景映射失败 ({exc.status_code}): {exc}",
                "",
                "注意: 大模型 API Key 没有发送给服务端；这里只是账号/认知映射请求失败。",
                "可先执行 /login xwab <账号> 或 /service 检查服务端状态。",
            ])
        except Exception as exc:
            return f"本机建议生成准备失败: {exc}"

        matches = mapping.get("matches") or []
        if not matches:
            return "服务端未返回可用场景映射，暂不生成投资建议。"

        try:
            settings = resolve_llm_settings(config=get_config())
            raw_text = await LLMClient(settings, timeout=float(config.request_timeout or 30)).complete(
                self._client_advice_messages(
                    query=query,
                    matches=matches,
                    mcp_data=payload.get("mcp_data"),
                    user_data=payload.get("user_data"),
                    current_cognition=payload.get("current_cognition"),
                ),
                temperature=0.35,
                max_tokens=min(int(config.llm_max_tokens or 4096), 1600),
            )
        except Exception as exc:
            return "\n".join([
                f"本机大模型调用失败: {exc}",
                "",
                "请检查 /model、/model key、网络代理或模型供应商额度。",
                "二郎神服务端没有收到你的大模型 API Key。",
            ])

        synthesis = self._parse_client_llm_advice(raw_text)
        return self._format_client_advice(
            query=query,
            matches=matches,
            synthesis=synthesis,
            raw_text=raw_text,
            provider=settings.display_name or settings.provider,
            model=settings.model,
            data_inputs={
                "mcp_data": sorted((payload.get("mcp_data") or {}).keys()) if isinstance(payload.get("mcp_data"), dict) else [],
                "user_data": sorted((payload.get("user_data") or {}).keys()) if isinstance(payload.get("user_data"), dict) else [],
            },
        )

    def _parse_client_advice_input(self, content: str):
        content = (content or "").strip()
        if not content:
            return "请提供需要分析的投资问题。"
        if "::" not in content:
            return content, {}
        query, raw_payload = [part.strip() for part in content.split("::", 1)]
        if not query:
            return "请在 JSON 数据包前提供投资问题"
        if not raw_payload:
            return query, {}
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            return f"建议数据包不是合法 JSON: {exc}"
        if not isinstance(payload, dict):
            return "建议数据包必须是 JSON 对象"
        return query, payload

    def _client_advice_messages(
        self,
        *,
        query: str,
        matches: list[dict],
        mcp_data=None,
        user_data=None,
        current_cognition=None,
    ) -> list[dict[str, str]]:
        system = (
            "你是二郎神客户端的大模型分析层。二郎神服务端只提供受保护的场景映射，"
            "不会接收用户的大模型 API Key。你必须基于服务端返回的公开映射、用户数据和 MCP 数据生成投资分析，"
            "不能声称看到了完整服务端认知库或内部案例全文。输出 JSON 对象，字段为 view, suggestions, risk_controls, missing_data。"
        )
        user_payload = {
            "query": query,
            "server_protected_matches": matches[:3],
            "mcp_data": mcp_data or {},
            "user_data": user_data or {},
            "current_cognition": current_cognition or {},
            "requirements": [
                "先给综合判断，再给可执行建议和风控",
                "如数据不足必须降低确定性并列出需要补充的数据",
                "不要暴露或编造服务端内部认知库内容",
            ],
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ]

    def _parse_client_llm_advice(self, raw_text: str) -> dict:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"view": text}
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end + 1])
                    return data if isinstance(data, dict) else {"view": text}
                except json.JSONDecodeError:
                    pass
        return {"view": text, "suggestions": [], "risk_controls": [], "missing_data": []}

    def _format_client_advice(
        self,
        *,
        query: str,
        matches: list[dict],
        synthesis: dict,
        raw_text: str,
        provider: str,
        model: str,
        data_inputs: dict,
    ) -> str:
        top = matches[0] if matches else {}
        suggestions = synthesis.get("suggestions") or []
        risks = synthesis.get("risk_controls") or []
        missing = synthesis.get("missing_data") or []
        lines = [
            "【客户端大模型投资建议】",
            f"- 问题: {query}",
            f"- 服务端命中场景: {top.get('scene')}",
            f"- 置信度: {top.get('confidence')}",
            f"- 本机大模型: {provider} / {model}",
            "- Key 边界: 大模型 API Key 仅在本机用于直连供应商，未发送给二郎神服务端",
            f"- MCP数据键: {', '.join(data_inputs.get('mcp_data') or []) or '未提供'}",
            f"- 用户数据键: {', '.join(data_inputs.get('user_data') or []) or '未提供'}",
            "",
            f"综合判断: {synthesis.get('view') or raw_text}",
            "",
            "建议:",
        ]
        for item in suggestions:
            lines.append(f"- {item}")
        if not suggestions:
            lines.append("- 大模型未返回结构化建议，请参考综合判断。")
        lines.extend(["", "风控:"])
        for item in risks:
            lines.append(f"- {item}")
        if not risks:
            lines.append("- 注意仓位、期限、流动性与最大回撤约束。")
        if missing:
            lines.extend(["", "需补充数据:"])
            for item in missing:
                lines.append(f"- {item}")
        return "\n".join(lines)

    async def _select_list(self, title: str, items: list[tuple[str, str, str]]) -> str | None:
        try:
            return await self._select_list_prompt_toolkit(title, items)
        except ImportError:
            return self._select_list_manual(title, items)

    async def _select_list_prompt_toolkit(self, title: str, items: list[tuple[str, str, str]]) -> str | None:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style

        selected = 0
        width = min(max(76, _terminal_width()), 140)

        def fragments():
            result = [
                ("class:title", f"{title}\n"),
                ("class:border", "─" * width + "\n"),
                ("class:hint", "↑↓ 选择  Enter 确认  Esc/Ctrl+C 取消\n"),
            ]
            for index, (_, label, description) in enumerate(items):
                style = "class:current" if index == selected else "class:item"
                marker = "❯" if index == selected else " "
                line = f"{marker} {label:<24} {description}"
                result.append((style, line[:width] + "\n"))
            result.append(("class:border", "─" * width))
            return result

        bindings = KeyBindings()

        @bindings.add("down")
        def _(event):
            nonlocal selected
            selected = (selected + 1) % len(items)
            event.app.invalidate()

        @bindings.add("up")
        def _(event):
            nonlocal selected
            selected = (selected - 1) % len(items)
            event.app.invalidate()

        @bindings.add("enter")
        def _(event):
            event.app.exit(result=items[selected][0])

        @bindings.add("escape")
        @bindings.add("c-c")
        def _(event):
            event.app.exit(result=None)

        root = HSplit([
            Window(height=1),
            Window(FormattedTextControl(fragments), dont_extend_height=True),
        ])
        app = Application(
            layout=Layout(root),
            key_bindings=bindings,
            full_screen=False,
            erase_when_done=True,
            style=Style.from_dict({
                "title": "ansicyan bold",
                "border": "#888888",
                "hint": "#888888",
                "item": "#d0d0d0",
                "current": self._select_style_current(),
            }),
        )
        return await app.run_async()

    def _select_list_manual(self, title: str, items: list[tuple[str, str, str]]) -> str | None:
        try:
            import termios
            import tty
        except ImportError:
            return None

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        selected = 0
        try:
            tty.setcbreak(fd)
            while True:
                self._render_model_picker(title, items, selected)
                ch = sys.stdin.read(1)
                if ch in {"\x03", "q", "Q"}:
                    return None
                if ch in {"\r", "\n"}:
                    return items[selected][0]
                if ch == "\x04":
                    raise EOFError
                if ch == "\x1b":
                    action = self._read_escape_sequence()
                    if action == "escape":
                        return None
                    if action == "up":
                        selected = (selected - 1) % len(items)
                    elif action == "down":
                        selected = (selected + 1) % len(items)
                    continue
                if ch in {"k", "K"}:
                    selected = (selected - 1) % len(items)
                elif ch in {"j", "J"}:
                    selected = (selected + 1) % len(items)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except OSError:
                pass

    def _render_model_picker(self, title: str, items: list[tuple[str, str, str]], selected: int) -> None:
        width = min(max(76, _terminal_width() - 4), 120)
        lines = [
            _color("╭─ " + title + " " + "─" * max(0, width - len(title) - 5) + "╮", "36"),
            "│ " + "↑↓/jk 选择  Enter 确认  q/Esc 取消".ljust(width - 3) + "│",
            "├" + "─" * (width - 2) + "┤",
        ]
        for index, (_, label, description) in enumerate(items):
            marker = "›" if index == selected else " "
            line = "│ " + f"{marker} {label:<24} {description}"[: width - 3].ljust(width - 3) + "│"
            if index == selected:
                line = _color(line, self._ansi_selected_style())
            lines.append(line)
        lines.append(_color("╰" + "─" * (width - 2) + "╯", "36"))
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.write(f"\033[{len(lines)}A")
        sys.stdout.flush()

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

    async def _read_prompt(self) -> str:
        """Read one prompt, opening a slash-command picker when / starts the line."""
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return input(self.prompt()).strip()

        try:
            return await self._read_prompt_toolkit()
        except ImportError:
            return self._read_prompt_manual()

    async def _read_prompt_toolkit(self) -> str:
        from prompt_toolkit.application import Application
        from prompt_toolkit.application.current import get_app_or_none
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import ConditionalContainer, Dimension, HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import TextArea

        cli = self
        history_index: int | None = None
        draft = ""
        text_area = TextArea(
            height=1,
            multiline=False,
            prompt=HTML("<prompt>❯ </prompt>"),
        )

        def slash_active() -> bool:
            return text_area.text.startswith("/")

        def slash_matches():
            text = text_area.text
            return cli._filter_palette(text[1:].lower()) if text.startswith("/") else []

        def clamp_selected(matches):
            if not matches:
                cli._slash_selected = 0
                return 0
            cli._slash_selected = max(0, min(cli._slash_selected, len(matches) - 1))
            return cli._slash_selected

        def slash_menu_fragments():
            text = text_area.text
            if not text.startswith("/"):
                return []
            matches = slash_matches()
            selected = clamp_selected(matches)
            width = min(max(72, _terminal_width()), 150)
            max_visible = 8
            start = max(0, selected - max_visible + 1)
            visible = matches[start:start + max_visible]
            fragments = [("class:menu.border", "─" * width + "\n")]
            if not visible:
                fragments.append(("class:menu.muted", "没有匹配命令\n"))
            for idx, (_, shortcut, description) in enumerate(visible):
                actual = start + idx
                style = "class:menu.current" if actual == selected else "class:menu"
                line = f"{shortcut:<30} {description}"
                fragments.append((style, line[:width] + "\n"))
            fragments.append(("class:menu.border", "─" * width))
            return fragments

        def invalidate(_=None):
            app = get_app_or_none()
            if app:
                app.invalidate()

        text_area.buffer.on_text_changed += invalidate
        bindings = KeyBindings()

        @bindings.add("down", filter=Condition(slash_active))
        def _(event):
            matches = slash_matches()
            if matches:
                cli._slash_selected = (clamp_selected(matches) + 1) % len(matches)
                event.app.invalidate()

        @bindings.add("up", filter=Condition(slash_active))
        def _(event):
            matches = slash_matches()
            if matches:
                cli._slash_selected = (clamp_selected(matches) - 1) % len(matches)
                event.app.invalidate()

        @bindings.add("up", filter=Condition(lambda: not slash_active()))
        def _(event):
            nonlocal history_index, draft
            if not cli._input_history:
                return
            if history_index is None:
                draft = text_area.text
                history_index = len(cli._input_history) - 1
            else:
                history_index = max(0, history_index - 1)
            text_area.text = cli._input_history[history_index]
            text_area.buffer.cursor_position = len(text_area.text)

        @bindings.add("down", filter=Condition(lambda: not slash_active()))
        def _(event):
            nonlocal history_index
            if history_index is None:
                return
            if history_index < len(cli._input_history) - 1:
                history_index += 1
                text_area.text = cli._input_history[history_index]
            else:
                history_index = None
                text_area.text = draft
            text_area.buffer.cursor_position = len(text_area.text)

        @bindings.add("enter")
        def _(event):
            if slash_active():
                matches = slash_matches()
                if matches:
                    _, shortcut, _ = matches[clamp_selected(matches)]
                    command, needs_more = cli._input_from_shortcut(shortcut)
                    text_area.text = command
                    text_area.buffer.cursor_position = len(command)
                    if needs_more:
                        event.app.invalidate()
                        return
                    event.app.exit(result=command)
                    return
            event.app.exit(result=text_area.text)

        @bindings.add("c-c")
        def _(event):
            event.app.exit(exception=KeyboardInterrupt)

        @bindings.add("c-d")
        def _(event):
            event.app.exit(exception=EOFError)

        menu = ConditionalContainer(
            Window(
                FormattedTextControl(slash_menu_fragments),
                height=Dimension(max=10),
                dont_extend_height=True,
            ),
            filter=Condition(slash_active),
        )
        root = HSplit([text_area, menu])
        app = Application(
            layout=Layout(root, focused_element=text_area),
            key_bindings=bindings,
            full_screen=False,
            erase_when_done=True,
            style=Style.from_dict({
                "prompt": "ansicyan bold",
                "menu": "#d0d0d0",
                "menu.current": cli._select_style_current(),
                "menu.border": "#888888",
                "menu.muted": "#888888",
            }),
        )

        command = await app.run_async()
        command = command.strip()
        if command and (not self._input_history or self._input_history[-1] != command):
            self._input_history.append(command)
        return command

    def _read_prompt_manual(self) -> str:
        """Fallback prompt for environments without prompt_toolkit."""
        try:
            import termios
            import tty
        except ImportError:
            return input(self.prompt()).strip()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        buffer = ""
        cursor = 0
        history_index: int | None = None
        draft = ""
        try:
            tty.setcbreak(fd)
            self._render_prompt(buffer, cursor)
            while True:
                ch = sys.stdin.read(1)
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch == "\x04":
                    raise EOFError
                if ch in {"\r", "\n"}:
                    print()
                    command = buffer.strip()
                    if command and (not self._input_history or self._input_history[-1] != command):
                        self._input_history.append(command)
                    return command
                if ch == "\x1b":
                    action = self._read_escape_sequence()
                    if action == "up":
                        if self._input_history:
                            if history_index is None:
                                draft = buffer
                                history_index = len(self._input_history) - 1
                            else:
                                history_index = max(0, history_index - 1)
                            buffer = self._input_history[history_index]
                            cursor = len(buffer)
                            self._render_prompt(buffer, cursor)
                        continue
                    if action == "down":
                        if history_index is not None:
                            if history_index < len(self._input_history) - 1:
                                history_index += 1
                                buffer = self._input_history[history_index]
                            else:
                                history_index = None
                                buffer = draft
                            cursor = len(buffer)
                            self._render_prompt(buffer, cursor)
                        continue
                    if action == "left":
                        cursor = max(0, cursor - 1)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "right":
                        cursor = min(len(buffer), cursor + 1)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "home":
                        cursor = 0
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "end":
                        cursor = len(buffer)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "delete":
                        if cursor < len(buffer):
                            buffer = buffer[:cursor] + buffer[cursor + 1:]
                            history_index = None
                            self._render_prompt(buffer, cursor)
                        continue
                    continue
                if ch in {"\x7f", "\b"}:
                    if cursor > 0:
                        buffer = buffer[:cursor - 1] + buffer[cursor:]
                        cursor -= 1
                        history_index = None
                        self._render_prompt(buffer, cursor)
                    continue
                if ch == "/" and not buffer:
                    selected = self._slash_command_picker()
                    self._clear_slash_dropdown()
                    if selected:
                        buffer, needs_more = self._input_from_shortcut(selected[1])
                        cursor = len(buffer)
                        history_index = None
                        if not needs_more:
                            self._render_prompt(buffer, cursor)
                            print()
                            if buffer and (not self._input_history or self._input_history[-1] != buffer):
                                self._input_history.append(buffer)
                            return buffer.strip()
                    self._render_prompt(buffer, cursor)
                    continue
                if ch.isprintable():
                    buffer = buffer[:cursor] + ch + buffer[cursor:]
                    cursor += 1
                    history_index = None
                    self._render_prompt(buffer, cursor)
                if not ch:
                    raise EOFError
        except OSError as exc:
            if self._should_exit_for_terminal(exc):
                raise EOFError from exc
            raise
        except Exception as exc:
            if self._should_exit_for_terminal(exc):
                raise EOFError from exc
            raise
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except OSError:
                pass

    def _render_prompt(self, buffer: str, cursor: int | None = None) -> None:
        if cursor is None:
            cursor = len(buffer)
        cursor = max(0, min(cursor, len(buffer)))
        sys.stdout.write("\r\033[2K" + self.prompt() + buffer)
        tail = len(buffer) - cursor
        if tail > 0:
            sys.stdout.write(f"\033[{tail}D")
        sys.stdout.flush()

    def _read_escape_sequence(self, timeout: float = 0.05) -> str:
        import select

        if not select.select([sys.stdin], [], [], timeout)[0]:
            return "escape"
        second = sys.stdin.read(1)
        if second == "O":
            if not select.select([sys.stdin], [], [], timeout)[0]:
                return "escape"
            return {
                "A": "up",
                "B": "down",
                "C": "right",
                "D": "left",
                "H": "home",
                "F": "end",
            }.get(sys.stdin.read(1), "escape")
        if second != "[":
            return "escape"
        if not select.select([sys.stdin], [], [], timeout)[0]:
            return "escape"
        third = sys.stdin.read(1)
        simple = {
            "A": "up",
            "B": "down",
            "C": "right",
            "D": "left",
            "H": "home",
            "F": "end",
        }
        if third in simple:
            return simple[third]
        if third.isdigit():
            sequence = third
            while select.select([sys.stdin], [], [], timeout)[0]:
                part = sys.stdin.read(1)
                sequence += part
                if part == "~":
                    break
            return {
                "1~": "home",
                "3~": "delete",
                "4~": "end",
                "7~": "home",
                "8~": "end",
            }.get(sequence, "escape")
        return "escape"

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
                action = self._read_escape_sequence()
                if action == "escape":
                    return None
                if action == "up" and matches:
                    selected = (selected - 1) % len(matches)
                    continue
                if action == "down" and matches:
                    selected = (selected + 1) % len(matches)
                    continue
                if action == "home" and matches:
                    selected = 0
                    continue
                if action == "end" and matches:
                    selected = len(matches) - 1
                    continue
                continue
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
            line = "│ " + text[: width - 3].ljust(width - 3) + "│"
            if start + idx == selected:
                line = _color(line, self._ansi_selected_style())
            lines.append(line)
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

    def _should_exit_for_terminal(self, exc: BaseException) -> bool:
        if isinstance(exc, (EOFError, BrokenPipeError)):
            return True
        if isinstance(exc, OSError):
            return self._is_terminal_closed_error(exc)
        message = str(exc)
        return "Input/output error" in message or "(5," in message

    def _is_terminal_closed_error(self, exc: OSError) -> bool:
        args = getattr(exc, "args", ())
        return (
            getattr(exc, "errno", None) == 5
            or 5 in args
            or "Input/output error" in str(exc)
        )

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

        try:
            result = asyncio.run(cli.dispatch(raw))
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n再见!")
            return

        print(result)
    else:
        # 交互模式
        try:
            asyncio.run(cli.interactive_mode())
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n再见!")


if __name__ == "__main__":
    main()
