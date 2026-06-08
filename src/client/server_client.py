"""
Async client for the Erlangshen API service.
"""

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
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.request(
                method,
                self.url(endpoint),
                headers=headers,
                **kwargs,
            )

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
        return await self.request(
            "POST",
            "auth/login",
            json={
                "loginEntry": login_entry,
                "emailOrPhone": email_or_phone,
                "password": password,
            },
        )

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
