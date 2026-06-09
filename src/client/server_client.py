"""
Async client for the Erlangshen API service.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from src.auth.session import format_bearer_token
from src.config import get_config


class ErlangshenAPIError(Exception):
    def __init__(self, status_code: int, message: str, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ErlangshenServerClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        config = get_config()
        self.base_url = (base_url or config.erlangshen_api_base_url).strip().rstrip("/")
        self.token = token
        self.timeout = timeout or float(config.request_timeout or 30)

    def url(self, endpoint: str) -> str:
        endpoint = endpoint.strip("/")
        parsed = urlparse(self.base_url)
        base_path = parsed.path.rstrip("/")
        if base_path.endswith("/api") or base_path.endswith("/api/erlangshen"):
            return f"{self.base_url}/{endpoint}"
        if endpoint == "health":
            return f"{self.base_url}/health"
        return f"{self.base_url}/api/{endpoint}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = format_bearer_token(self.token)
        return headers

    async def request(self, method: str, endpoint: str, **kwargs) -> Any:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.request(
                    method,
                    self.url(endpoint),
                    headers=headers,
                    **kwargs,
                )
        except httpx.RequestError as exc:
            raise ErlangshenAPIError(0, f"网络请求失败: {exc}", None) from exc

        payload = self._parse_payload(response)
        if response.status_code >= 400:
            raise ErlangshenAPIError(
                response.status_code,
                self._error_message(payload, response.status_code),
                payload,
            )
        return payload

    async def health(self) -> Any:
        return await self.request("GET", "health")

    async def login(self, login_entry: str, email_or_phone: str, password: str) -> Any:
        try:
            payload = await self.request(
                "POST",
                "auth/login",
                json={
                    "loginEntry": login_entry,
                    "emailOrPhone": email_or_phone,
                    "password": password,
                },
            )
        except ErlangshenAPIError as exc:
            normalized = _normalize_login_payload(exc.payload, login_entry)
            if normalized:
                return normalized
            raise
        return _normalize_login_payload(payload, login_entry) or payload

    async def logout(self) -> Any:
        return await self.request("POST", "auth/logout")

    async def me(self) -> Any:
        return await self.request("GET", "auth/me")

    async def status(self) -> Any:
        return await self.request("GET", "status")

    async def cognition_scenarios(self) -> Any:
        return await self.request("GET", "cognition/scenarios")

    async def cognition_map(self, query: str, top_k: int = 3) -> Any:
        return await self.request(
            "POST",
            "cognition/map",
            json={"query": query, "top_k": top_k},
        )

    async def advice(
        self,
        query: str,
        mcp_data: Any = None,
        user_data: Any = None,
        current_cognition: Any = None,
    ) -> Any:
        return await self.request(
            "POST",
            "advice",
            json={
                "query": query,
                "mcp_data": mcp_data,
                "user_data": user_data,
                "current_cognition": current_cognition,
            },
        )

    async def chart_artifact(
        self,
        chart_type: str,
        title: str,
        data: dict[str, Any],
        width: int = 960,
        height: int = 540,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Any:
        return await self.request(
            "POST",
            "artifacts/chart",
            json={
                "chart_type": chart_type,
                "title": title,
                "data": data,
                "width": width,
                "height": height,
                "metadata": metadata or {},
            },
        )

    async def cognition_days(self, limit: int = 20) -> Any:
        return await self.request("GET", "cognition/days", params={"limit": limit})

    async def cognition_cases(self, limit: int = 20) -> Any:
        return await self.request("GET", "cognition/cases", params={"limit": limit})

    def _parse_payload(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _error_message(self, payload: Any, status_code: int) -> str:
        if isinstance(payload, dict):
            return str(payload.get("detail") or payload.get("message") or payload.get("error") or status_code)
        if isinstance(payload, str) and payload:
            return payload
        return f"HTTP {status_code}"


def _normalize_login_payload(payload: Any, login_entry: str) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    token = _token_from(payload)
    if token:
        normalized = dict(payload)
        normalized.setdefault("status", "success")
        normalized.setdefault("loginEntry", login_entry)
        normalized.setdefault("user", {})
        return normalized

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    token = _token_from(data)
    if not token:
        return None

    entry = str(data.get("entry") or login_entry)
    user = _normalize_user(data.get("user") or {}, entry)
    return {
        "status": "success",
        "loginEntry": entry,
        "token": token,
        "expires": data.get("expiresAt") or _expires_from_seconds(data.get("expiresInSeconds")),
        "user": user,
    }


def _token_from(payload: dict[str, Any]) -> Optional[str]:
    token = (
        payload.get("token")
        or payload.get("accessToken")
        or payload.get("access_token")
    )
    return str(token).strip() if token else None


def _normalize_user(user: dict[str, Any], login_entry: str) -> dict[str, Any]:
    return {
        "id": user.get("id") or user.get("user_id"),
        "username": user.get("username") or user.get("user_name"),
        "email": user.get("email"),
        "role": user.get("role") or user.get("user_type"),
        "loginEntry": user.get("loginEntry") or user.get("login_entry") or login_entry,
        "raw": user,
    }


def _expires_from_seconds(value: Any) -> Optional[str]:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
