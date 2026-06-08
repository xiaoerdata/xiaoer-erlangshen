"""
/server command - call the Erlangshen API from the native CLI.
"""

import json

from src.auth.session import load_auth_session
from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient
from src.config import get_config


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
        return f"【服务端健康检查】{data.get('status')}"

    def _format_status(self, data: dict) -> str:
        auth = data.get("auth") or {}
        cognition = data.get("cognition") or {}
        user = auth.get("user") or {}
        access = auth.get("access") or {}
        return "\n".join([
            "【二郎神服务端状态】",
            f"- 服务: {data.get('service')} {data.get('version')}",
            f"- 鉴权: {'开启' if auth.get('enabled') else '关闭'} ({auth.get('mode')})",
            f"- 当前用户: {user.get('username') or user.get('email') or user.get('id') or '未绑定'}",
            f"- 权限层级: {access.get('label')} ({access.get('tier')})",
            f"- 认知保护: {'开启' if cognition.get('protected') else '关闭'}",
            f"- 问题匹配: {'开启' if cognition.get('matching_enabled') else '关闭'}",
            f"- 建议生成: {'开启' if cognition.get('advice_enabled') else '关闭'}",
        ])

    def _format_me(self, data: dict) -> str:
        user = data.get("user") or {}
        return "\n".join([
            "【服务端账号】",
            f"- 用户: {user.get('username') or user.get('email') or user.get('id')}",
            f"- 角色: {user.get('role')}",
            f"- 账号体系: {user.get('loginEntry')}",
            f"- 权限层级: {(data.get('access') or {}).get('label')}",
        ])

    def _format_map(self, data: dict) -> str:
        matches = data.get("matches") or []
        lines = ["【服务端场景映射】"]
        for idx, match in enumerate(matches, 1):
            lines.extend([
                f"{idx}. {match.get('scene')}",
                f"   方向: {match.get('orientation')} | 置信度: {match.get('confidence')}",
                f"   保护: {match.get('protection')}",
            ])
            if match.get("case_hint"):
                lines.append(f"   案例提示: {match.get('case_hint')}")
        return "\n".join(lines)

    def _format_advice(self, data: dict) -> str:
        advice = data.get("advice") or {}
        matched = advice.get("matched") or {}
        synthesis = advice.get("synthesis") or {}
        data_inputs = advice.get("data_inputs") or {}
        lines = [
            "【服务端投资建议】",
            f"- 命中场景: {matched.get('scene')}",
            f"- 置信度: {matched.get('confidence')}",
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
        return """
/server - 调用二郎神服务端 API

用法:
    /server health                 # 公开健康检查
    /server status                 # 服务端状态，需要登录
    /server me                     # 当前账号，需要登录
    /server map <问题>             # 受保护的服务端场景命中
    /server advice <问题>          # 结合服务端认知生成受保护建议
    /server advice <问题> :: {"mcp_data": {...}, "user_data": {...}}
"""
