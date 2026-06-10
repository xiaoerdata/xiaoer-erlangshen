"""
/server command - call the Erlangshen API from the native CLI.
"""

import json
import unicodedata

from src.auth.session import load_auth_session
from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient
from src.config import get_config


def _display_width(text: str) -> int:
    width = 0
    for char in str(text):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def _clip_display(text: str, limit: int) -> str:
    output = []
    width = 0
    for char in str(text):
        char_width = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1)
        if width + char_width > limit:
            break
        output.append(char)
        width += char_width
    return "".join(output)


def _pad_display(text: str, width: int) -> str:
    clipped = _clip_display(text, width)
    return clipped + " " * max(0, width - _display_width(clipped))


class ServerCommand:
    """Service-side Erlangshen API helpers."""

    def __init__(self, brain, mcp):
        self.brain = brain
        self.mcp = mcp

    async def execute(self, args: str = "") -> str:
        args = (args or "").strip()
        if not args:
            return self._help()

        action, content = self._split(args)
        client = self._client()

        try:
            if action in {"commands", "cmd", "?", "help", "帮助", "命令", "menu", "panel", "面板"}:
                return self._command_palette()
            if action in {"guide", "指南", "workflow", "workbench", "工作台", "推荐", "next"}:
                return self._guide_panel()
            if action in {"actions", "action", "next-actions", "下一步", "行动", "任务"}:
                return self._action_board_panel()
            if action in {"goals", "goal", "select", "选择", "目标", "路由"}:
                return self._goal_selector_panel()
            if action in {"flow", "流程", "route", "链路"}:
                return self._flow_panel()
            if action in {"capabilities", "capability", "tools", "能力", "工具"}:
                return self._capabilities_panel()
            if action in {"artifact", "artifacts", "chart", "图表", "产物"}:
                return self._artifact_panel()
            if action in {"resource", "resources", "links", "link", "网页", "图片", "资源", "链接"}:
                return self._resource_panel()
            if action in {"health", "健康"}:
                return self._format_health(await client.health())
            if action in {"status", "状态"}:
                return self._format_status(await client.status())
            if action in {"me", "auth"}:
                return self._format_me(await client.me())
            if action in {"map", "映射"}:
                if not content:
                    return "请提供要映射的投资问题或场景"
                return self._format_map(await client.cognition_map(content))
            if action in {"advice", "建议", "投顾"}:
                if not content:
                    return "请提供需要生成投资建议的问题"
                parsed = self._parse_advice_content(content)
                if isinstance(parsed, str):
                    return parsed
                query, payload = parsed
                return self._format_advice(await client.advice(
                    query,
                    mcp_data=payload.get("mcp_data"),
                    user_data=payload.get("user_data"),
                    current_cognition=payload.get("current_cognition"),
                ))
            if action in {"scenarios", "场景", "days", "认知日", "cases", "案例"}:
                return "服务端认知库不向用户端枚举开放，请使用 /server map <问题> 或 /server advice <问题>"
        except ErlangshenAPIError as exc:
            return f"服务端请求失败 ({exc.status_code}): {exc}"

        return self._help()

    def _split(self, args: str) -> tuple[str, str]:
        parts = args.split(maxsplit=1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""

    def _client(self) -> ErlangshenServerClient:
        session = load_auth_session()
        return ErlangshenServerClient(
            base_url=session.get("base_url") or get_config().erlangshen_api_base_url,
            token=session.get("token"),
        )

    def _format_health(self, data: dict) -> str:
        status = data.get("status") or "unknown"
        return "\n".join([
            "【服务端健康检查】",
            f"- status: {status}",
            "- 下一步: /server status 查看鉴权、账号、认知保护和服务端模型边界",
            "- 分析入口: 直接输入投资问题，客户端会先取 MCP 数据再请求服务端映射",
            "- 排障入口: /server actions 或 /doctor",
        ])

    def _format_status(self, data: dict) -> str:
        auth = data.get("auth") or {}
        cognition = data.get("cognition") or {}
        llm = data.get("llm") or {}
        policy = data.get("user_llm_key_policy") or {}
        user = auth.get("user") or {}
        access = auth.get("access") or {}
        lines = [
            "【二郎神服务端状态】",
            f"- 服务: {data.get('service')} {data.get('version')}",
            f"- 鉴权: {'开启' if auth.get('enabled') else '关闭'} ({auth.get('mode')})",
            f"- 当前用户: {user.get('username') or user.get('email') or user.get('id') or '未绑定'}",
            f"- 权限层级: {access.get('label')} ({access.get('tier')})",
            f"- 服务端大模型: {llm.get('display_name') or llm.get('provider') or '未返回'} / {llm.get('model') or '未返回'} ({'已配置Key' if llm.get('api_key_configured') else '未配置Key'})",
            f"- 用户大模型Key: {'服务端不接收' if policy.get('accepted_by_server') is False else '仅保存在客户端'}；/advice 默认由客户端直连模型供应商生成",
            f"- 认知保护: {'开启' if cognition.get('protected') else '关闭'}",
            f"- 问题匹配: {'开启' if cognition.get('matching_enabled') else '关闭'}",
            f"- 建议生成: {'开启' if cognition.get('advice_enabled') else '关闭'}",
            "",
            "下一步:",
        ]
        if not user:
            lines.append("- /login xwab <账号> 登录后再检查服务端账号和 super-66 MCP")
        if policy.get("accepted_by_server") is False:
            lines.append("- /model key 在本机配置大模型 Key；服务端不会接收用户 Key")
        if not cognition.get("protected"):
            lines.append("- /server capabilities 查看服务端能力边界，确认认知保护配置")
        lines.extend([
            "- 直接输入投资问题，客户端会先取 MCP 数据，再请求服务端场景映射",
            "- /server actions 按目标查看健康检查、映射、图表和排障路径",
        ])
        return "\n".join(lines)

    def _format_me(self, data: dict) -> str:
        user = data.get("user") or {}
        access = data.get("access") or {}
        lines = [
            "【服务端账号】",
            f"- 用户: {user.get('username') or user.get('email') or user.get('id') or '未绑定'}",
            f"- 角色: {user.get('role') or '未返回'}",
            f"- 账号体系: {user.get('loginEntry') or '未返回'}",
            f"- 权限层级: {access.get('label') or '未返回'}",
            "",
            "下一步:",
        ]
        if not user:
            lines.append("- /login xwab <账号> 登录后再查看账号和权限")
        if not access.get("label") or access.get("tier") in {"guest", "limited"}:
            lines.append("- /server status 查看服务端鉴权、权限层级和认知保护")
        lines.extend([
            "- 直接输入投资问题，客户端会复用该账号访问服务端和 super-66 MCP",
            "- /server actions 查看账号、映射、图表和排障路径",
        ])
        return "\n".join(lines)

    def _format_map(self, data: dict) -> str:
        matches = data.get("matches") or []
        lines = ["【服务端场景映射】"]
        if not matches:
            return "\n".join([
                "【服务端场景映射】",
                "- 未命中明确场景",
                "",
                "下一步:",
                "- 补充市场、标的、时间周期或你的持仓约束后重新 /server map <问题>",
                "- 也可以直接输入自然语言问题，让客户端先取 MCP 数据再做完整分析",
            ])
        for idx, match in enumerate(matches, 1):
            lines.extend([
                f"{idx}. {match.get('scene')}",
                f"   方向: {match.get('orientation')} | 置信度: {match.get('confidence')}",
                f"   保护: {match.get('protection')}",
            ])
            if match.get("case_hint"):
                lines.append(f"   案例提示: {match.get('case_hint')}")
        lines.extend([
            "",
            "怎么使用这个映射:",
            "- 如果只想看服务端理解是否合理，到这里即可；服务端不会暴露内部认知库全文。",
            "- 如果要完整投资分析，直接输入自然语言问题或使用 /advice <问题>，客户端会加入 MCP 数据和本机大模型。",
            "- 如果需要复盘工具选择和数据快照，完成一次分析后输入 /plan。",
        ])
        return "\n".join(lines)

    def _format_advice(self, data: dict) -> str:
        advice = data.get("advice") or {}
        matched = advice.get("matched") or {}
        synthesis = advice.get("synthesis") or {}
        data_inputs = advice.get("data_inputs") or {}
        llm = advice.get("llm") or {}
        lines = [
            "【服务端投资建议】",
            "- 提示: 推荐直接使用 /advice；CLI 会在本机调用用户大模型 Key，不会把 Key 发给服务端。",
            f"- 命中场景: {matched.get('scene')}",
            f"- 置信度: {matched.get('confidence')}",
            f"- 大模型: {llm.get('display_name') or llm.get('provider') or '未返回'} / {llm.get('model') or '未返回'}",
            f"- 综合判断: {synthesis.get('view')}",
            f"- MCP数据键: {', '.join(data_inputs.get('mcp_data') or []) or '未提供'}",
            f"- 用户数据键: {', '.join(data_inputs.get('user_data') or []) or '未提供'}",
            "",
            "建议:",
        ]
        for item in synthesis.get("suggestions") or []:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("风控:")
        for item in synthesis.get("risk_controls") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    def _parse_advice_content(self, content: str):
        if "::" not in content:
            return content.strip(), {}

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

    def _help(self) -> str:
        return self._command_palette()

    def _command_palette(self) -> str:
        workbench_rows = [
            ("1 健康与账号", "/server status 或 /server me"),
            ("2 完整分析", "直接输入自然语言问题；客户端先做 LLM 意图理解和 MCP 数据读取"),
            ("3 只看映射", "/server map <问题>"),
            ("4 图表产物", "/server artifact 或 /chart <标题> :: {json}"),
            ("5 排障复盘", "/server actions、/server flow、/plan、/doctor"),
        ]
        groups = [
            ("Quick Actions", [
                ("/server guide", "不知道该用哪个命令时，按任务选择下一步"),
                ("/server goals", "按用户目标选择最合适的服务端/客户端命令"),
                ("/server actions", "按目标查看下一步行动面板"),
                ("/server status", "服务端状态、鉴权、模型、认知保护"),
                ("/server me", "当前账号和权限层级"),
                ("/server health", "公开健康检查"),
            ]),
            ("Analysis Flow", [
                ("/server flow", "查看客户端、MCP、服务端场景映射、本机大模型的协作链路"),
                ("/server map <问题>", "只做受保护场景映射，不生成最终投资结论"),
                ("/advice <问题>", "推荐路径：客户端先取 MCP，再本机大模型生成自然分析"),
            ]),
            ("Artifacts", [
                ("/server artifact", "查看服务端 chart artifact 通信方式"),
                ("/server resources", "查看网页、图片、HTML/PDF、图表和报告如何变成 /links"),
                ("/chart <标题> :: {\"A股\":1.2}", "请求服务端生成结构化图表 artifact"),
                ('/server advice <问题> :: {"mcp_data": {...}}', "兼容旧服务端建议接口的数据包形式"),
            ]),
            ("Boundaries", [
                ("/server capabilities", "查看服务端暴露能力和安全边界"),
                ("/tools", "查看 super-66 MCP、web_search 和图表能力地图"),
            ]),
        ]
        lines = [
            "【服务端命令面板】",
            "Server Workbench: 输入 /server 后加空格，会在下拉菜单中收窄到服务端子命令；↑↓ 选择，Enter 确认。",
            "服务端只暴露状态、账号、受保护场景映射和 artifact/建议接口；不会暴露内部认知库全文。",
            "",
            "任务入口:",
        ]
        for label, action in workbench_rows:
            lines.append(f"- {_pad_display(label, 16)} {action}")
        lines.extend([
            "",
            "最常用路径:",
            "1. /server status 检查鉴权、账号和认知保护",
            "2. 直接输入投资问题，让客户端本机大模型选择 super-66 MCP/web_search 与服务端映射",
            "3. /plan 复盘工具选择、数据快照、服务端场景和图表/报告产物",
            "4. /links 1 或 /open 1 打开网页、图片、图表和报告资源",
            "",
            "服务端决策矩阵:",
            *self._workbench_decision_matrix_lines(),
            "",
        ])
        for title, rows in groups:
            lines.append(f"{title}:")
            for command, desc in rows:
                lines.append(f"- {_pad_display(command, 48)} {desc}")
            lines.append("")
        lines.extend([
            "推荐路径:",
            "1. /service 或 /server status 检查服务端状态",
            "2. 直接输入自然语言问题，客户端会先理解意图并取 super-66 MCP 数据",
            "3. /plan 查看本机大模型选择的工具、MCP 快照、服务端映射和图表产物",
            "",
            *self._communication_contract_lines(),
            "",
            "提示: 在交互模式输入 /server 后，可继续选择 guide、goals、actions、status、flow、capabilities、artifact、resources、map。",
            "资源呈现: 服务端返回网页/图片/HTML/PDF/图表时，客户端会显示名称链接；使用 /links 1 或 /open 1 打开。",
        ])
        return "\n".join(lines)

    def _workbench_decision_matrix_lines(self) -> list[str]:
        cards = [
            {
                "target": "健康检查",
                "need": "server base url",
                "command": "/server health -> /server status",
                "result": "确认反向代理、API 进程和鉴权策略",
            },
            {
                "target": "账号权限",
                "need": "XWAB/XCZT token",
                "command": "/login xwab <账号> -> /server me",
                "result": "确认服务端与 super-66 MCP 可共用登录态",
            },
            {
                "target": "完整分析",
                "need": "本机大模型 Key + MCP 数据 + 服务端映射",
                "command": "直接输入自然语言问题",
                "result": "本机 LLM 选择 MCP/web_search，再综合服务端场景信号",
            },
            {
                "target": "只看映射",
                "need": "登录态",
                "command": "/server map <问题>",
                "result": "只返回受保护场景、方向和置信度",
            },
            {
                "target": "图表报告",
                "need": "授权工作区 + 结构化数据",
                "command": "说“做成图表”或 /chart <标题> :: {json}",
                "result": "服务端 chart artifact -> 客户端保存 HTML/JSON -> /links 打开",
            },
            {
                "target": "资源打开",
                "need": "resource_links 或已保存产物",
                "command": "/links 1、/open 1、/open chart",
                "result": "网页、图片、HTML、PDF、图表和报告用系统链接打开",
            },
        ]
        lines: list[str] = []
        for index, card in enumerate(cards, 1):
            lines.append(f"{index}. {card['target']} · 需要: {card['need']}")
            lines.append(f"   命令: {card['command']}")
            lines.append(f"   结果: {card['result']}")
        return lines

    def _goal_selector_panel(self) -> str:
        cards = [
            {
                "goal": "确认服务是否在线",
                "why": "先排除反向代理、鉴权和服务端进程问题。",
                "primary": "/server health",
                "next": ["/server status", "/doctor"],
            },
            {
                "goal": "确认账号和权限",
                "why": "二郎神服务端、super-66 MCP 共用 XWAB/XCZT 登录态。",
                "primary": "/server me",
                "next": ["/status", "/login xwab <账号>"],
            },
            {
                "goal": "完整回答投资问题",
                "why": "生产推荐路径：本机 LLM 先理解上下文并选择 MCP，再请求服务端受保护映射。",
                "primary": "直接输入自然语言问题",
                "next": ["/plan", "/tools"],
            },
            {
                "goal": "只检查服务端怎么理解问题",
                "why": "只返回场景、方向、置信度和保护边界，不暴露内部认知库。",
                "primary": "/server map <问题>",
                "next": ["/advice <问题>", "/plan"],
            },
            {
                "goal": "生成图表或报告",
                "why": "服务端生成 chart artifact，客户端保存 JSON/HTML 到授权工作区。",
                "primary": "/chart <标题> :: {\"沪深300\":1.2,\"黄金\":0.8}",
                "next": ["/workspace browse", "/open", "/artifacts"],
            },
            {
                "goal": "排查数据和工具链路",
                "why": "检查 super-66 MCP、web_search、本机大模型、工作区和产物保存。",
                "primary": "/doctor",
                "next": ["/tools", "/plan", "/server flow"],
            },
        ]
        lines = [
            "【服务端目标选择器】",
            "不用记接口名。先看你现在想完成什么，再执行对应命令；在交互模式输入 /server 可用上下键选择这些入口。",
            "",
        ]
        for index, card in enumerate(cards, 1):
            lines.extend([
                f"{index}. {card['goal']}",
                f"   为什么: {card['why']}",
                f"   首选: {card['primary']}",
                f"   后续: {', '.join(card['next'])}",
                "",
            ])
        lines.extend([
            "推荐原则:",
            "- 能用自然语言直接问时，就直接问；客户端会让本机大模型决定 MCP/web_search/服务端映射如何组合。",
            "- 只想验证服务端理解时，再使用 /server map。",
            "- 需要可视化或沉淀报告时，先授权工作区，再让服务端生成 chart artifact。",
            "",
            "安全边界: 用户大模型 API Key 只在本机直连供应商；服务端只处理账号、受保护映射和 artifact 通道。",
        ])
        return "\n".join(lines)

    def _guide_panel(self) -> str:
        return "\n".join([
            "【服务端交互工作台】",
            "你不需要记接口名；按当前任务选择路径即可。",
            "",
            "如果你想确认远程服务是否可用:",
            "  /service 或 /server status",
            "",
            "如果你想让二郎神完整回答投资问题:",
            "  直接输入自然语言问题",
            "  客户端会先让本机大模型理解上下文，再读取 super-66 MCP / web_search，随后请求服务端场景映射。",
            "",
            "如果你只想看服务端如何理解一个问题:",
            "  /server map <问题>",
            "  返回受保护场景、方向和置信度，不暴露内部认知库全文。",
            "",
            "如果你想生成图表或报告:",
            "  /chart <标题> :: {\"沪深300\":1.2,\"黄金\":0.8}",
            "  或直接问“把这个做成图表”，本机大模型可请求 chart artifact。",
            "",
            "如果你想复盘本轮 agent 做了什么:",
            "  /plan",
            "  查看意图理解、工具理由、数据策略、MCP 快照、服务端命中场景和产物。",
            "",
            "如果你想直接看下一步行动:",
            "  /server actions",
            "  按“检查服务、登录、完整分析、只看映射、图表产物、复盘过程”给出可执行命令。",
            "",
            "安全边界:",
            "- 大模型 API Key 只在客户端本机使用。",
            "- 服务端只处理账号、受保护场景映射和 artifact 通道。",
            "- super-66 MCP 使用 XWAB/XCZT 登录态，优先提供行情、产品和市场数据。",
        ])

    def _action_board_panel(self) -> str:
        groups = [
            ("我想确认服务能不能用", [
                "/server health",
                "/service",
                "/server status",
            ]),
            ("我还没登录或不确定账号", [
                "/login xwab <账号>",
                "/status",
                "/server me",
            ]),
            ("我想完整问一个投资问题", [
                "直接输入自然语言问题",
                "/advice <问题>",
                "/plan",
            ]),
            ("我只想看服务端怎么理解问题", [
                "/server map <问题>",
                "/server capabilities",
            ]),
            ("我想把结果做成图表或报告", [
                "/workspace browse",
                "/workspace allow",
                "/chart <标题> :: {\"沪深300\":1.2,\"黄金\":0.8}",
                "/open",
            ]),
            ("我想排查数据链路", [
                "/doctor",
                "/tools",
                "/plan",
            ]),
        ]
        lines = [
            "【服务端行动面板】",
            "按你现在想完成的事选择命令；服务端负责状态、账号、受保护映射和 chart artifact 通道。",
            "",
        ]
        for title, commands in groups:
            lines.append(f"{title}:")
            for command in commands:
                lines.append(f"  - {command}")
            lines.append("")
        lines.extend([
            "推荐完整路径:",
            "  1. /setup run 选择项目文件夹、登录账号、配置本机大模型",
            "  2. 直接输入投资问题；客户端先取 super-66 MCP / web_search，再请求服务端场景映射",
            "  3. 需要可视化时继续说“把这个做成图表”，或使用 /chart",
            "",
            "边界:",
            "  - 大模型 API Key 只在本机直连供应商，不发送给服务端。",
            "  - 服务端不暴露内部认知库全文，只返回受保护的公开信号。",
        ])
        return "\n".join(lines)

    def _flow_panel(self) -> str:
        return "\n".join([
            "【服务端协作流程】",
            "1. 客户端接收自然语言问题，并由本机大模型理解上下文、改写问题、选择工具组合。",
            "2. 行情、产品、宏观和公开网页线索优先从 super-66 MCP / web_search 获取。",
            "3. 服务端只接收问题做受保护场景映射，返回场景、方向、置信度等公开信号。",
            "4. 本机大模型结合 MCP 快照、用户数据和服务端场景信号生成自然分析。",
            "5. 如果需要可视化，客户端通过服务端 chart artifact 通道生成图表，再保存到授权工作区。",
            "",
            *self._communication_contract_lines(),
            "",
            "安全边界:",
            "- 用户大模型 API Key 只在本机直连供应商，不发送给服务端。",
            "- 服务端不暴露内部认知库全文，只返回受保护的映射信号。",
            "- 工作区未授权时，客户端不会写入本地图表或报告。",
        ])

    def _capabilities_panel(self) -> str:
        return "\n".join([
            "【服务端能力边界】",
            "可用能力:",
            "- health/status/me: 健康、鉴权、账号和权限状态。",
            "- map: 把用户问题映射到受保护认知场景。",
            "- advice: 兼容旧服务端建议接口；生产推荐优先走客户端 /advice。",
            "- artifact/chart: 接收结构化图表请求，返回可保存和展示的 artifact。",
            "- resource links: 网页、图片、HTML/PDF 等非文本资源由客户端以命名链接呈现和打开。",
            "",
            "不提供能力:",
            "- 不枚举或泄露内部认知库全文。",
            "- 不接收、不存储、不转发用户的大模型 API Key。",
            "- 不替代客户端本机大模型做个性化最终判断。",
            "",
            *self._communication_contract_lines(),
            "",
            "客户端应优先使用 /tools 和 /plan 观察 MCP 工具选择、行情快照和图表产物。",
        ])

    def _artifact_panel(self) -> str:
        return "\n".join([
            "【服务端图表 Artifact 通信】",
            "用途: 把行情、收益、回撤、配置比例或对比结果生成结构化图表产物。",
            "",
            "客户端命令:",
            '  /chart 资产表现 :: {"沪深300":1.2,"黄金":0.8}',
            "",
            "大模型自动请求:",
            '  {"artifacts":[{"type":"chart","chart_type":"bar","title":"资产表现","data":{"沪深300":1.2}}]}',
            "",
            "兼容输入:",
            "- artifacts / charts / visualizations / chart_requests / artifact_requests 都可被客户端归一化。",
            "- 图表数据可使用 {\"沪深300\":1.2}、labels+values、series 列表或 dataset/points。",
            "- 缺少数值数据时客户端会跳过生成，不会请求服务端编造图表。",
            "",
            "客户端处理:",
            "- 调用服务端 chart artifact 通道。",
            "- 若已授权工作区，保存 JSON/HTML 到 .erlangshen/artifacts/charts。",
            "- 非文本资源用命名链接展示；输入 /links open 1 或 /open link 1 打开网页、图片、图表和报告。",
            "- 输入 /open 打开最近图表，/artifacts 查看全部产物。",
            "",
            *self._communication_contract_lines(),
            "",
            "边界: 用户大模型 API Key 不发送给服务端；服务端只处理结构化 chart artifact 请求。",
        ])

    def _resource_panel(self) -> str:
        return "\n".join([
            "【服务端资源通信】",
            "用途: 当服务端、MCP 或 web_search 返回网页、图片、HTML、PDF、图表和报告时，让 CLI 用名称链接承接。",
            "",
            "推荐返回结构:",
            '  {"resource_links":[{"source":"server artifact","title":"资产表现图","html_url":"https://.../chart.html","image_url":"https://.../chart.png"}]}',
            "",
            "客户端归一化:",
            "- label: 用户看到的名称，例如 资产表现图、政策原文、完整报告。",
            "- target: 可打开目标，例如 https://...、file:///... 或授权工作区内路径。",
            "- type: webpage / image / chart_image / html / pdf / report / json / local_file。",
            "- link: 兼容旧格式的“名称: URL/路径”。",
            "",
            "CLI 呈现:",
            "- 回答正文只放命名链接和打开提示，不内嵌富文本或二进制内容。",
            "- /links 查看最近资源和项目 resources.json 索引。",
            "- /links 1、/links open 1、/open 1、/open link 1 打开指定网页、图片、图表或报告。",
            "- 授权工作区后，资源索引保存到 .erlangshen/artifacts/resources.json。",
            "",
            "服务端可返回的常见字段:",
            "- url/link/href/web_url/source_url: 普通网页或公告原文。",
            "- html_url/file_url/download_url/pdf_url: HTML 图表、报告或 PDF。",
            "- image_url/thumbnail/preview_url/png_url/jpg_url/svg_url: 图片或图表预览。",
            "",
            *self._communication_contract_lines(),
            "",
            "边界: 用户大模型 API Key 不发送给服务端；resource_links 不应包含 token、secret、password 或授权头。",
        ])

    def _communication_contract_lines(self) -> list[str]:
        return [
            "服务端/客户端通信契约:",
            "- 服务端返回: health/status/me、protected map、chart artifact、resource links。",
            "- 客户端负责: 本机大模型、super-66 MCP/web_search、工作区保存、/links 和 /open 打开。",
            "- 图表传输: 服务端返回 JSON/HTML/图片/网页等 artifact 元数据，客户端只在授权项目内落盘。",
            "- 资源传输: 网页、图片、HTML、PDF、报告统一归一化为 label/target/type 和“名称: URL/路径”，不把富文本塞进终端正文。",
        ]
