"""
Lightweight Super-66 MCP client for the npm CLI package.

The client reuses the Erlangshen/XWAB/XCZT auth token saved by `/login`.
No separate Super-66 password is required on the client side.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import httpx

from src.auth.session import format_bearer_token, load_auth_session


class Super66MCP:
    """Small async client for the preset Super-66 MCP gateway."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.base_url = os.environ.get("SUPER66_MCP_URL", "https://www.xiaoerdata.site/mcp").rstrip("/")
        self.timeout = float(os.environ.get("SUPER66_TIMEOUT_SECONDS", "12"))
        self.trust_env = os.environ.get("SUPER66_TRUST_ENV", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: dict[str, tuple[Any, float]] = {}
        self.cache_ttl = int(os.environ.get("SUPER66_CACHE_TTL_SECONDS", "60"))

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=self.trust_env)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        arguments = arguments or {}
        cache_key = self._cache_key(tool_name, arguments)
        if use_cache and cache_key in self._cache:
            value, expires_at = self._cache[cache_key]
            if time.time() < expires_at:
                return value
            self._cache.pop(cache_key, None)

        token = self._token()
        if not token:
            return {
                "error": "未登录，super-66 MCP 需要先执行 /login xwab <账号> 或设置 SUPER66_MCP_TOKEN",
                "auth": "missing_token",
            }

        try:
            response = await self.client.post(
                f"{self.base_url}/tools/call",
                json={"name": self._normalize_tool_name(tool_name), "arguments": arguments},
                headers={
                    "Authorization": format_bearer_token(token),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            payload = self._parse_payload(response)
            if response.status_code >= 400:
                return {
                    "error": f"HTTP {response.status_code}",
                    "detail": payload,
                }
            result = self._extract_result(payload)
            if use_cache:
                self._cache[cache_key] = (result, time.time() + self.cache_ttl)
            return result
        except httpx.RequestError as exc:
            return {"error": f"super-66 MCP 网络请求失败: {exc}"}

    def list_registry_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "search_astocks", "description": "搜索 A股标的"},
            {"name": "get_astock_realtime", "description": "获取 A股实时/最新行情"},
            {"name": "get_astock_history", "description": "获取 A股历史行情"},
            {"name": "get_index_data", "description": "获取国内指数历史数据"},
            {"name": "get_global_asset_data", "description": "获取全球资产历史数据"},
            {"name": "get_future_market_data", "description": "获取期货行情"},
            {"name": "search_products", "description": "搜索 ETF、公募、私募等产品"},
            {"name": "get_product_detail", "description": "获取产品详情"},
            {"name": "get_product_history", "description": "获取产品历史净值或行情"},
        ]

    def _token(self) -> str:
        token = os.environ.get("SUPER66_MCP_TOKEN") or os.environ.get("SUPER66_TOKEN")
        if token:
            return token.strip()
        saved = load_auth_session().get("token")
        return str(saved).strip() if saved else ""

    def _cache_key(self, tool_name: str, arguments: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True)}"

    def _normalize_tool_name(self, tool_name: str) -> str:
        if tool_name.startswith("dc66_"):
            return tool_name
        return f"dc66_{tool_name}"

    def _parse_payload(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _extract_result(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"result": payload}
        if payload.get("code") not in {None, 0, 200}:
            return {
                "error": payload.get("message") or payload.get("error") or "super-66 MCP 调用失败",
                "code": payload.get("code"),
            }
        data = payload.get("data")
        if isinstance(data, dict):
            result = data.get("result", data)
            return result if isinstance(result, dict) else {"result": result}
        return payload


super66_mcp = Super66MCP()


async def get_mcp() -> Super66MCP:
    return super66_mcp


async def close_mcp() -> None:
    await super66_mcp.close()
