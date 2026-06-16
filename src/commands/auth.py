"""
/auth command - CLI login and token management.
"""

import getpass
import shlex
import sys
from typing import Any

from src.auth.session import clear_auth_session, load_auth_session, save_auth_session
from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient
from src.config import get_config


class AuthCommand:
    """Manage Erlangshen CLI authentication."""

    def __init__(self, brain, mcp):
        self.brain = brain
        self.mcp = mcp

    async def execute(self, args: str = "") -> str:
        args = (args or "").strip()
        if not args:
            return self._help()

        action, content = self._split(args)
        if action in {"login", "登录"}:
            return await self._login(content)
        if action in {"status", "状态", "me"}:
            return await self._status()
        if action in {"logout", "退出", "清除"}:
            return await self._logout()
        if action in {"server", "服务端"}:
            return self._set_server(content)
        return self._help()

    def _split(self, args: str) -> tuple[str, str]:
        parts = args.split(maxsplit=1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""

    async def _login(self, content: str) -> str:
        try:
            parts = shlex.split(content)
        except ValueError as exc:
            return f"参数解析失败: {exc}"

        login_entry = get_config().erlangshen_auth_login_entry
        if parts and parts[0].lower() in {"xwab", "xczt"}:
            login_entry = parts.pop(0).lower()
        if not parts:
            if not sys.stdin.isatty():
                return "请提供账号。示例：/login xwab user@example.com"
            login_entry = self._prompt_login_entry(login_entry)
            self._prompt_server_if_needed()
            email_or_phone = input("账号: ").strip()
            if not email_or_phone:
                return "已取消登录：账号为空"
        else:
            email_or_phone = parts.pop(0)

        if parts:
            password = parts.pop(0)
        elif sys.stdin.isatty():
            password = getpass.getpass("密码: ")
        else:
            return "当前不是交互终端，请在命令中提供密码用于开发测试，或进入交互模式后登录"

        session = load_auth_session()
        base_url = session.get("base_url") or get_config().erlangshen_api_base_url
        client = ErlangshenServerClient(base_url=base_url)
        try:
            result = await client.login(login_entry, email_or_phone, password)
        except ErlangshenAPIError as exc:
            return _format_login_error(exc)

        token = result.get("token") if isinstance(result, dict) else None
        if not token:
            return "登录失败: 服务端未返回 token，请检查登录代理是否返回标准二郎神响应"

        save_auth_session({
            "base_url": base_url,
            "token": token,
            "account": email_or_phone,
            "loginEntry": result.get("loginEntry") or login_entry,
            "expires": result.get("expires"),
            "user": self._safe_user(result.get("user") or {}),
        })
        user = result.get("user") or {}
        return "\n".join([
            "登录成功",
            f"- 服务端: {base_url}",
            f"- 账号体系: {result.get('loginEntry') or login_entry}",
            f"- 用户: {user.get('username') or user.get('email') or email_or_phone}",
            "- 下一步: 输入 /service 查看服务端状态，或直接输入投资问题",
        ])

    async def _status(self) -> str:
        session = load_auth_session()
        base_url = session.get("base_url") or get_config().erlangshen_api_base_url
        token = session.get("token")
        lines = [
            "【二郎神 CLI 登录状态】",
            f"- 服务端: {base_url}",
            f"- 本地 token: {'已保存' if token else '未登录'}",
        ]

        if not token:
            lines.append("- 提示: 使用 /login xwab <账号> 登录")
            return "\n".join(lines)

        client = ErlangshenServerClient(base_url=base_url, token=token)
        try:
            result = await client.me()
            user = result.get("user") if isinstance(result, dict) else {}
            lines.extend([
                "- 服务端校验: 通过",
                f"- 用户: {user.get('username') or user.get('email') or user.get('id')}",
                f"- 角色: {user.get('role')}",
                f"- 账号体系: {user.get('loginEntry') or session.get('loginEntry')}",
            ])
        except ErlangshenAPIError as exc:
            lines.extend([
                f"- 服务端校验: 失败 ({exc.status_code})",
                f"- 原因: {exc}",
            ])
        return "\n".join(lines)

    async def _logout(self) -> str:
        session = load_auth_session()
        token = session.get("token")
        if token:
            client = ErlangshenServerClient(
                base_url=session.get("base_url") or get_config().erlangshen_api_base_url,
                token=token,
            )
            try:
                await client.logout()
            except ErlangshenAPIError:
                pass
        clear_auth_session()
        return "已清除本地 CLI 登录状态"

    def _set_server(self, content: str) -> str:
        base_url = content.strip()
        if not base_url:
            return f"当前服务端: {load_auth_session().get('base_url') or get_config().erlangshen_api_base_url}"
        session = load_auth_session()
        session["base_url"] = base_url.rstrip("/")
        save_auth_session(session)
        return f"已设置 CLI 服务端: {session['base_url']}"

    def _prompt_login_entry(self, default_entry: str) -> str:
        raw = input(f"账号体系 [xwab/xczt，默认 {default_entry}]: ").strip().lower()
        if raw in {"xwab", "xczt"}:
            return raw
        return default_entry

    def _prompt_server_if_needed(self) -> None:
        session = load_auth_session()
        current = session.get("base_url") or get_config().erlangshen_api_base_url
        raw = input(f"服务端 [{current}]: ").strip()
        if raw:
            session["base_url"] = raw.rstrip("/")
            save_auth_session(session)

    def _safe_user(self, user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "role": user.get("role"),
            "loginEntry": user.get("loginEntry"),
        }

    def _help(self) -> str:
        return """
/auth - CLI 登录与账号状态

用法:
    /auth server <url>              # 设置二郎神服务端地址
    /auth login [xwab|xczt] <账号>  # 登录，交互模式会提示输入密码
    /auth status                    # 查看本地 token 和服务端校验状态
    /auth logout                    # 清除本地登录状态

快捷方式:
    /login [xwab|xczt] [账号]
    /status
    /logout
"""


def _format_login_error(exc: ErlangshenAPIError) -> str:
    message = str(exc).strip()
    if message.lower() == "success":
        message = "登录接口返回了 success 但 HTTP 状态不是成功，请检查服务端登录代理"
    if exc.status_code == 0:
        return f"登录失败: {message}"
    return f"登录失败 ({exc.status_code}): {message}"
