"""
Lightweight Super-66 MCP client for the npm CLI package.

The client refreshes its MCP token by logging in with SUPER66_USERNAME /
SUPER66_PASSWORD or the encrypted password saved by `/login`. Saved auth tokens
are treated as stale across CLI starts and are not reused for MCP calls.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Optional

import httpx

from src.auth.session import decrypt_auth_password, format_bearer_token, load_auth_session


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
        self.api_base = os.environ.get("SUPER66_API_URL", "https://www.xiaoerdata.site/api/v1").rstrip("/")
        self.login_entry = os.environ.get("SUPER66_LOGIN_ENTRY", "xwab").strip().lower() or "xwab"
        self.username = os.environ.get("SUPER66_USERNAME", "小二MCP助手")
        self.password = os.environ.get("SUPER66_PASSWORD", "")
        self.timeout = float(os.environ.get("SUPER66_TIMEOUT_SECONDS", "12"))
        self.trust_env = os.environ.get("SUPER66_TRUST_ENV", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.allow_static_token = os.environ.get("SUPER66_ALLOW_STATIC_TOKEN", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._client: Optional[httpx.AsyncClient] = None
        env_token = os.environ.get("SUPER66_MCP_TOKEN") or os.environ.get("SUPER66_TOKEN")
        self._token_value: str = env_token.strip() if env_token and (self.password or self.allow_static_token) else ""
        self._token_expires_at: float = (
            0 if (env_token and self.password) else (float("inf") if (env_token and self.allow_static_token) else 0)
        )
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

    async def refresh_auth_from_cli_login(
        self,
        *,
        login_entry: str = "",
        account: str = "",
        password: str = "",
        token: str = "",
    ) -> bool:
        """Synchronize the MCP session immediately after CLI auth refreshes."""
        if login_entry:
            self.login_entry = str(login_entry).strip().lower() or self.login_entry
        if account:
            self.username = str(account).strip() or self.username
        if password:
            self.password = str(password)
        if token:
            self._token_value = str(token).strip()
            self._token_expires_at = 0 if self.password else time.time() + 3600
        self._cache.clear()
        if not self.password:
            return bool((self._token_value or token) and self.allow_static_token)
        return bool(await self._ensure_token(force_refresh=True))

    async def refresh_auth_from_saved_session(self) -> bool:
        session = load_auth_session()
        password = decrypt_auth_password(session)
        account = str(session.get("account") or session.get("username") or "").strip()
        token = str(session.get("token") or "").strip()
        if not password:
            return False
        return await self.refresh_auth_from_cli_login(
            login_entry=str(session.get("loginEntry") or session.get("login_entry") or self.login_entry),
            account=account,
            password=password,
            token=token,
        )

    async def ensure_fresh_login(self) -> bool:
        """Force a new MCP login before data calls when credentials are available."""
        self._cache.clear()
        return bool(await self._ensure_token(force_refresh=True))

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        arguments = arguments or {}
        normalized_tool, normalized_arguments = self._normalize_tool_call(tool_name, arguments)
        cache_key = self._cache_key(normalized_tool, normalized_arguments)
        if use_cache and cache_key in self._cache:
            value, expires_at = self._cache[cache_key]
            if time.time() < expires_at:
                return value
            self._cache.pop(cache_key, None)

        if normalized_tool in {"dc66_batch_get_index_data", "dc66_get_index_batch_series"}:
            result = await self._client_batch_get_index_data(normalized_arguments, use_cache=use_cache)
            if use_cache:
                self._cache[cache_key] = (result, time.time() + self.cache_ttl)
            return result

        if normalized_tool == "dc66_batch_get_global_asset_data":
            result = await self._client_batch_get_global_asset_data(normalized_arguments, use_cache=use_cache)
            if use_cache:
                self._cache[cache_key] = (result, time.time() + self.cache_ttl)
            return result

        token = await self._ensure_token()
        if not token:
            return {
                "error": "super-66 MCP 需要重新登录获取新 token；请执行 /login xwab <账号> 保存加密密码，或设置 SUPER66_USERNAME/SUPER66_PASSWORD",
                "auth": "missing_relogin_credentials",
            }

        try:
            response = await self.client.post(
                f"{self.base_url}/tools/call",
                json={"name": normalized_tool, "arguments": normalized_arguments},
                headers={
                    "Authorization": format_bearer_token(token),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            payload = self._parse_payload(response)
            if response.status_code in {401, 403}:
                self._token_value = ""
                self._token_expires_at = 0
                refreshed = await self._ensure_token(force_refresh=True)
                if refreshed and refreshed != token:
                    response = await self.client.post(
                        f"{self.base_url}/tools/call",
                        json={"name": normalized_tool, "arguments": normalized_arguments},
                        headers={
                            "Authorization": format_bearer_token(refreshed),
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        },
                    )
                    payload = self._parse_payload(response)
            if response.status_code >= 400:
                if normalized_tool == "dc66_get_index_batch_series" and self._is_tool_not_found(payload):
                    result = await self._client_batch_get_index_data(normalized_arguments, use_cache=use_cache)
                    if use_cache:
                        self._cache[cache_key] = (result, time.time() + self.cache_ttl)
                    return result
                return {
                    "error": f"HTTP {response.status_code}",
                    "detail": payload,
                }
            result = self._extract_result(payload, normalized_tool, normalized_arguments)
            if use_cache:
                self._cache[cache_key] = (result, time.time() + self.cache_ttl)
            return result
        except httpx.RequestError as exc:
            return {"error": f"super-66 MCP 网络请求失败: {exc}"}

    def list_registry_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "search_astocks", "description": "搜索 A股标的"},
            {"name": "get_hot_stocks", "description": "获取 A股热门股票、成交额或涨跌幅榜"},
            {"name": "batch_get_astock_realtime", "description": "批量获取 A股实时/最新行情"},
            {"name": "get_astock_realtime", "description": "获取 A股实时/最新行情"},
            {"name": "get_astock_history", "description": "获取 A股历史行情"},
            {"name": "batch_get_index_data", "description": "批量获取 A股、港股、美股等指数历史和最新行情"},
            {"name": "get_index_data", "description": "获取 A股和港股宽基指数历史数据，如沪深300、恒生科技指数、恒生指数"},
            {"name": "batch_get_global_asset_data", "description": "批量获取黄金、美元、原油等全球资产历史数据"},
            {"name": "get_global_asset_data", "description": "获取黄金、美元、原油等全球资产历史数据；港股指数走 get_index_data"},
            {"name": "get_macro_data", "description": "获取宏观指标目录、最新值或时序数据"},
            {"name": "get_macro_indicator", "description": "按名称获取宏观指标最新值"},
            {"name": "list_macro_indicators", "description": "列出宏观指标目录"},
            {"name": "get_future_market_data", "description": "获取期货行情"},
            {"name": "search_products", "description": "搜索 ETF、公募、私募等产品"},
            {"name": "get_product_detail", "description": "获取产品详情"},
            {"name": "get_product_history", "description": "获取产品历史净值或行情"},
        ]

    async def _ensure_token(self, *, force_refresh: bool = False) -> str:
        token = os.environ.get("SUPER66_MCP_TOKEN") or os.environ.get("SUPER66_TOKEN")
        if token and not self.password and self.allow_static_token:
            return token.strip()
        now = time.time()
        if self.password:
            if not force_refresh and self._token_value and now < self._token_expires_at - 300:
                return self._token_value
            try:
                response = await self.client.post(
                    f"{self.api_base}/auth/{self.login_entry}/login",
                    json={"identifier": self.username, "password": self.password},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                payload = self._parse_payload(response)
                if response.status_code >= 400:
                    return ""
                data = payload.get("data") if isinstance(payload, dict) else {}
                if isinstance(data, dict):
                    refreshed = data.get("token") or data.get("accessToken") or data.get("access_token")
                    if refreshed:
                        self._token_value = str(refreshed).strip()
                        try:
                            self._token_expires_at = now + int(data.get("expiresInSeconds") or 86400)
                        except (TypeError, ValueError):
                            self._token_expires_at = now + 86400
                        return self._token_value
            except httpx.RequestError:
                return ""
        session = load_auth_session()
        saved_password = decrypt_auth_password(session)
        saved_account = str(session.get("account") or session.get("username") or "").strip()
        if saved_password and saved_account:
            self.login_entry = str(session.get("loginEntry") or session.get("login_entry") or self.login_entry).strip().lower() or self.login_entry
            self.username = saved_account
            self.password = saved_password
            return await self._ensure_token(force_refresh=True)
        return ""

    def _cache_key(self, tool_name: str, arguments: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True)}"

    async def _client_batch_get_index_data(self, arguments: dict[str, Any], *, use_cache: bool = True) -> dict[str, Any]:
        labels = self._coerce_label_list(
            arguments.get("indexNames")
            or arguments.get("indexName")
            or arguments.get("indices")
            or arguments.get("names")
        )
        if not labels:
            return {
                "error": "batch_get_index_data 缺少 indexNames",
                "tool": "dc66_batch_get_index_data",
                "arguments": self._safe_arguments(arguments),
            }
        window = {
            key: value
            for key, value in arguments.items()
            if key not in {"indexNames", "indexName", "indices", "names"}
        }
        rows: list[dict[str, Any]] = []
        latest_rows: list[dict[str, Any]] = []
        results: dict[str, Any] = {}
        errors: dict[str, Any] = {}
        for label in labels[:12]:
            child_args = {"indexName": label, **window}
            result = await self.call_tool("get_index_data", child_args, use_cache=use_cache)
            if isinstance(result, dict) and result.get("error"):
                errors[label] = result
                continue
            results[label] = result
            if isinstance(result, dict):
                child_rows = result.get("rows") if isinstance(result.get("rows"), list) else []
                for row in child_rows:
                    if isinstance(row, dict):
                        item = dict(row)
                        item.setdefault("index_name", label)
                        rows.append(item)
                latest = result.get("latest")
                if isinstance(latest, dict):
                    item = dict(latest)
                    item.setdefault("index_name", label)
                    latest_rows.append(item)
        if not results and errors:
            return {
                "error": "batch_get_index_data 拆分调用全部失败",
                "tool": "dc66_batch_get_index_data",
                "arguments": self._safe_arguments(arguments),
                "errors": errors,
            }
        return {
            "tool": "dc66_batch_get_index_data",
            "arguments": self._safe_arguments(arguments),
            "rows": self._sort_market_rows(rows),
            "latest_rows": self._sort_market_rows(latest_rows),
            "results": results,
            "errors": errors,
            "count": len(rows),
            "source_format": "client_batch_fanout",
        }

    async def _client_batch_get_global_asset_data(self, arguments: dict[str, Any], *, use_cache: bool = True) -> dict[str, Any]:
        labels = self._coerce_label_list(
            arguments.get("assetNames")
            or arguments.get("assetName")
            or arguments.get("assets")
            or arguments.get("names")
        )
        if not labels:
            return {
                "error": "batch_get_global_asset_data 缺少 assetNames",
                "tool": "dc66_batch_get_global_asset_data",
                "arguments": self._safe_arguments(arguments),
            }
        window = {
            key: value
            for key, value in arguments.items()
            if key not in {"assetNames", "assetName", "assets", "names"}
        }
        rows: list[dict[str, Any]] = []
        latest_rows: list[dict[str, Any]] = []
        results: dict[str, Any] = {}
        errors: dict[str, Any] = {}
        for label in labels[:12]:
            child_args = {"assetName": label, **window}
            result = await self.call_tool("get_global_asset_data", child_args, use_cache=use_cache)
            if isinstance(result, dict) and result.get("error"):
                errors[label] = result
                continue
            results[label] = result
            if isinstance(result, dict):
                child_rows = result.get("rows") if isinstance(result.get("rows"), list) else []
                for row in child_rows:
                    if isinstance(row, dict):
                        item = dict(row)
                        item.setdefault("asset_name", label)
                        item.setdefault("index_name", label)
                        rows.append(item)
                latest = result.get("latest")
                if isinstance(latest, dict):
                    item = dict(latest)
                    item.setdefault("asset_name", label)
                    item.setdefault("index_name", label)
                    latest_rows.append(item)
        if not results and errors:
            return {
                "error": "batch_get_global_asset_data 拆分调用全部失败",
                "tool": "dc66_batch_get_global_asset_data",
                "arguments": self._safe_arguments(arguments),
                "errors": errors,
            }
        return {
            "tool": "dc66_batch_get_global_asset_data",
            "arguments": self._safe_arguments(arguments),
            "rows": self._sort_market_rows(rows),
            "latest_rows": self._sort_market_rows(latest_rows),
            "results": results,
            "errors": errors,
            "count": len(rows),
            "source_format": "client_batch_fanout",
        }

    def _coerce_label_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            items = re.split(r"[,，、/|;\s]+", value)
        else:
            items = []
        result: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    def _normalize_tool_name(self, tool_name: str) -> str:
        if "." in tool_name:
            return tool_name
        normalized = tool_name if tool_name.startswith("dc66_") else f"dc66_{tool_name}"
        if normalized == "dc66_batch_get_index_data":
            return "dc66_get_index_batch_series"
        return normalized

    def _canonical_index_market_label(self, label: Any) -> str:
        text = re.sub(r"\s+", "", str(label or "").lower())
        if not text:
            return ""
        if (
            "hstech" in text
            or "hangsengtech" in text
            or "hangsengtechnology" in text
            or "恒生科技" in text
        ):
            return "恒生科技指数"
        if "hscei" in text or "国企指数" in text or "恒生中国企业" in text or "hangsengchinaenterprises" in text:
            return "恒生中国企业指数"
        if "hsi" in text or "恒生指数" in text or "香港恒生指数" in text or "hangsengindex" in text:
            return "恒生指数"
        return ""

    def _normalize_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        normalized_tool = self._normalize_tool_name(tool_name)
        normalized_name = normalized_tool.removeprefix("dc66_")
        args = dict(arguments or {})
        if normalized_name in {"get_global_asset_data", "get_index_data"}:
            label_keys = (
                "asset_name",
                "assetName",
                "index_name",
                "indexName",
                "source_table",
                "sourceTable",
                "table_name",
                "tableName",
                "code",
                "symbol",
                "ticker",
                "index_code",
                "indexCode",
                "asset_code",
                "assetCode",
                "label",
            )
            canonical_label = next(
                (canonical for canonical in (self._canonical_index_market_label(args.get(key)) for key in label_keys) if canonical),
                "",
            )
            if canonical_label:
                for key in label_keys:
                    args.pop(key, None)
                args["index_name"] = canonical_label
                normalized_tool = "dc66_get_index_data"
        if normalized_name == "get_macro_indicator":
            indicator = args.get("indicator") or args.get("indicatorName") or args.get("indicator_name") or args.get("keyword")
            if indicator:
                normalized_tool = "dc66_get_macro_data"
                args = {"keyword": indicator, "latestOnly": True, "limit": args.get("limit", 20)}
        normalized_arguments = self._normalize_tool_arguments(normalized_tool, args)
        return normalized_tool, normalized_arguments

    def _normalize_tool_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = dict(arguments or {})
        normalized_name = tool_name.removeprefix("dc66_")
        common_aliases = {
            "start_date": "startDate",
            "end_date": "endDate",
        }
        aliases = {
            "get_index_data": {"index_name": "indexName", "index_code": "indexName", "indexCode": "indexName"},
            "batch_get_index_data": {"index_names": "indexNames", "index_name": "indexNames", "indices": "indexNames", "names": "indexNames"},
            "get_index_batch_series": {"index_names": "indexNames", "index_name": "indexNames", "indices": "indexNames", "names": "indexNames"},
            "get_global_asset_data": {"asset_name": "assetName", "asset_code": "assetCode", "assetCode": "assetCode", "source_table": "sourceTable"},
            "batch_get_global_asset_data": {"asset_names": "assetNames", "asset_name": "assetNames", "assets": "assetNames", "names": "assetNames"},
            "batch_get_astock_realtime": {"stock_codes": "codes", "stockCodes": "codes", "code": "codes"},
            "get_astock_realtime_batch": {"stock_codes": "codes", "stockCodes": "codes", "code": "codes"},
            "get_astock_realtime": {"code": "codes", "stockCode": "codes", "stock_code": "codes", "symbol": "codes"},
            "get_astock_history": {"code": "codes", "stockCode": "codes", "stock_code": "codes", "symbol": "codes"},
            "get_macro_data": {
                "indicator_codes": "indicatorCodes",
                "indicatorCodes": "indicatorCodes",
                "indicator_names": "keyword",
                "indicatorNames": "keyword",
                "latest_only": "latestOnly",
                "latestOnly": "latestOnly",
            },
            "get_macro_snapshot": {
                "indicator_codes": "indicatorCodes",
                "indicatorCodes": "indicatorCodes",
                "indicator_keywords": "indicatorKeywords",
                "indicatorNames": "indicatorKeywords",
                "latest_only": "latestOnly",
                "latestOnly": "latestOnly",
            },
            "batch_get_macro_data": {
                "indicator_codes": "indicatorCodes",
                "indicatorCodes": "indicatorCodes",
                "indicator_keywords": "indicatorKeywords",
                "indicatorNames": "indicatorKeywords",
                "latest_only": "latestOnly",
                "latestOnly": "latestOnly",
            },
            "get_future_market_data": {"contract_code": "contractCode", "contract_type": "contractType"},
            "search_products": {"product_type": "productType"},
            "get_product_detail": {"product_id": "productId", "product_type": "productType"},
            "get_product_history": {"product_id": "productId", "product_type": "productType"},
        }
        for old, new in common_aliases.items():
            if old in args and new not in args:
                args[new] = args.pop(old)
        for old, new in aliases.get(normalized_name, {}).items():
            if old in args and new not in args:
                args[new] = args.pop(old)
        if normalized_name == "get_astock_realtime" and args.get("codes"):
            args.setdefault("limit", 1)
        if normalized_name == "get_astock_history":
            args.pop("adjust", None)
        for key in ("indexNames", "assetNames", "codes", "indicatorCodes", "indicatorKeywords"):
            if key == "codes" and normalized_name in {"get_astock_realtime", "get_astock_history"}:
                continue
            if isinstance(args.get(key), str):
                args[key] = [
                    item.strip()
                    for item in re.split(r"[,，、/|;\s]+", args[key])
                    if item.strip()
                ]
        return args

    def _parse_payload(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _is_tool_not_found(self, payload: Any) -> bool:
        if isinstance(payload, str):
            return "TOOL_NOT_FOUND" in payload or "not registered" in payload
        if not isinstance(payload, dict):
            return False
        values = [
            payload.get("code"),
            payload.get("message"),
            payload.get("error"),
        ]
        detail = payload.get("detail")
        if isinstance(detail, dict):
            values.extend([detail.get("code"), detail.get("message"), detail.get("error")])
        error = payload.get("error")
        if isinstance(error, dict):
            values.extend([error.get("code"), error.get("message")])
        text = " ".join(str(value) for value in values if value is not None)
        return "TOOL_NOT_FOUND" in text or "not registered" in text

    def _extract_result(
        self,
        payload: Any,
        tool_name: str = "",
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        arguments = arguments or {}
        if not isinstance(payload, dict):
            return self._normalize_supabase_result(payload, tool_name, arguments)
        if payload.get("success") is False:
            return {
                "error": payload.get("message") or payload.get("error") or "super-66 MCP 调用失败",
                "code": payload.get("code"),
            }
        if payload.get("code") not in {None, 0, 200}:
            return {
                "error": payload.get("message") or payload.get("error") or "super-66 MCP 调用失败",
                "code": payload.get("code"),
            }
        result = self._unwrap_payload(payload)
        return self._normalize_supabase_result(result, tool_name, arguments)

    def _unwrap_payload(self, payload: Any) -> Any:
        current = payload
        for _ in range(6):
            if not isinstance(current, dict):
                return current
            if isinstance(current.get("result"), (dict, list)):
                current = current["result"]
                continue
            if isinstance(current.get("data"), (dict, list)):
                current = current["data"]
                continue
            if isinstance(current.get("payload"), (dict, list)):
                current = current["payload"]
                continue
            break
        return current

    def _normalize_supabase_result(
        self,
        result: Any,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if tool_name == "dc66_get_index_batch_series":
            batch = self._normalize_batch_index_series_result(result, arguments)
            if batch:
                return batch
        rows = self._extract_rows(result)
        if rows:
            normalized_rows = [self._normalize_market_row(row, arguments) for row in rows if isinstance(row, dict)]
            normalized_rows = self._sort_market_rows(normalized_rows)
            latest = normalized_rows[-1] if normalized_rows else {}
            row_limit = self._result_row_limit(arguments)
            return {
                "tool": tool_name,
                "arguments": self._safe_arguments(arguments),
                "rows": normalized_rows[-row_limit:],
                "latest": latest,
                "count": self._result_count(result, len(normalized_rows)),
                "source_format": "supabase_rows",
            }
        if isinstance(result, dict):
            normalized = self._normalize_market_row(result, arguments)
            if self._looks_like_market_row(normalized):
                output = dict(result)
                output["latest"] = normalized
                output["source_format"] = "supabase_object"
                output.setdefault("tool", tool_name)
                output.setdefault("arguments", self._safe_arguments(arguments))
                return output
            return result
        return {"result": result}

    def _normalize_batch_index_series_result(self, result: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {}
        items = result.get("items")
        if not isinstance(items, list):
            return {}
        rows: list[dict[str, Any]] = []
        latest_rows: list[dict[str, Any]] = []
        grouped: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            label = (
                item.get("indexName")
                or item.get("index_name")
                or item.get("assetName")
                or item.get("name")
                or ""
            )
            label_text = str(label).strip()
            item_rows = self._columnar_rows(item.get("data")) if isinstance(item.get("data"), dict) else []
            if not item_rows:
                item_rows = self._extract_rows(item.get("data"))
            normalized_item_rows: list[dict[str, Any]] = []
            for row in item_rows:
                if not isinstance(row, dict):
                    continue
                next_row = dict(row)
                if label_text:
                    next_row.setdefault("index_name", label_text)
                normalized = self._normalize_market_row(next_row, arguments)
                normalized_item_rows.append(normalized)
                rows.append(normalized)
            normalized_item_rows = self._sort_market_rows(normalized_item_rows)
            latest = normalized_item_rows[-1] if normalized_item_rows else {}
            if latest:
                latest_rows.append(latest)
            if label_text:
                item_row_limit = self._result_row_limit(arguments)
                grouped[label_text] = {
                    "tool": "dc66_get_index_data",
                    "arguments": {
                        **self._safe_arguments(arguments),
                        "indexName": label_text,
                    },
                    "rows": normalized_item_rows[-item_row_limit:],
                    "latest": latest,
                    "count": len(normalized_item_rows),
                    "actualStartDate": item.get("actualStartDate"),
                    "actualEndDate": item.get("actualEndDate"),
                    "latestAvailableDate": item.get("latestAvailableDate"),
                }
        if not rows:
            return {}
        rows = self._sort_market_rows(rows)
        latest_rows = self._sort_market_rows(latest_rows)
        row_limit = self._result_row_limit(arguments)
        return {
            "tool": "dc66_get_index_batch_series",
            "arguments": self._safe_arguments(arguments),
            "rows": rows[-row_limit:],
            "latest_rows": latest_rows,
            "latest": rows[-1],
            "results": grouped,
            "count": len(rows),
            "missingIndexNames": result.get("missingIndexNames", []),
            "source_format": "index_batch_series",
        }

    def _result_row_limit(self, arguments: dict[str, Any], default: int = 120) -> int:
        raw_limit = arguments.get("limit") or arguments.get("historyLimit") or arguments.get("pageSize") or default
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = default
        return max(1, min(limit, 10000))

    def _extract_rows(self, value: Any, depth: int = 0) -> list[dict[str, Any]]:
        if depth > 6:
            return []
        if isinstance(value, str):
            parsed = self._parse_json_text(value)
            return self._extract_rows(parsed, depth + 1) if parsed is not None else []
        if isinstance(value, list):
            rows = []
            for item in value:
                if isinstance(item, dict):
                    text_payload = item.get("text") if item.get("type") in {None, "text"} else None
                    parsed = self._parse_json_text(text_payload) if isinstance(text_payload, str) else None
                    if parsed is not None:
                        rows.extend(self._extract_rows(parsed, depth + 1))
                    else:
                        rows.append(item)
                elif isinstance(item, list):
                    rows.extend(self._extract_rows(item, depth + 1))
                elif isinstance(item, str):
                    rows.extend(self._extract_rows(item, depth + 1))
            return rows if any(self._looks_like_market_row(item) for item in rows) else []
        if not isinstance(value, dict):
            return []
        columnar_rows = self._columnar_rows(value)
        if columnar_rows:
            return columnar_rows
        row_keys = (
            "rows",
            "records",
            "items",
            "data",
            "result",
            "list",
            "values",
            "history",
            "prices",
            "payload",
            "content",
        )
        for key in row_keys:
            nested = value.get(key)
            rows = self._extract_rows(nested, depth + 1)
            if rows:
                return rows
        nested_rows = []
        for nested in value.values():
            rows = self._extract_rows(nested, depth + 1)
            if rows:
                nested_rows.extend(rows)
        if nested_rows:
            return nested_rows
        if self._looks_like_market_row(value):
            return [value]
        return []

    def _parse_json_text(self, value: Any) -> Any:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text or text[0] not in "{[":
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def _columnar_rows(self, value: dict[str, Any]) -> list[dict[str, Any]]:
        dates = value.get("dates") or value.get("date") or value.get("trade_dates")
        if not isinstance(dates, list) or not dates:
            return []
        series_aliases = {
            "open": ("opens", "open"),
            "high": ("highs", "high"),
            "low": ("lows", "low"),
            "close": ("closes", "close", "prices"),
            "volume": ("volumes", "volume"),
            "amount": ("amounts", "amount", "turnovers"),
            "change_pct": ("change_pcts", "pct_chgs", "change_pct", "pct_chg"),
        }
        rows = []
        for index, date in enumerate(dates):
            row = {"date": date}
            for field, aliases in series_aliases.items():
                for alias in aliases:
                    series = value.get(alias)
                    if isinstance(series, list) and index < len(series):
                        row[field] = series[index]
                        break
            indicators = value.get("indicators")
            if isinstance(indicators, dict):
                for name, series in indicators.items():
                    if isinstance(series, list) and index < len(series):
                        row[str(name)] = series[index]
            if len(row) > 1:
                rows.append(row)
        return rows

    def _normalize_market_row(self, row: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        aliases = {
            "index_name": (
                "index_name",
                "asset_name",
                "name",
                "product_name",
                "security_name",
                "fund_name",
                "symbol_name",
                "指数名称",
                "资产名称",
                "名称",
                "简称",
                "股票简称",
            ),
            "code": ("code", "symbol", "ts_code", "ticker", "代码", "证券代码"),
            "date": ("date", "trade_date", "tradedate", "trading_date", "datetime", "timestamp", "time", "日期", "交易日期", "时间"),
            "close": ("close", "close_price", "latest", "latest_price", "current_price", "last", "last_price", "price", "收盘", "收盘价", "最新价", "现价"),
            "change_pct": ("change_pct", "pct_chg", "change_percent", "changeRate", "percent", "涨跌幅", "涨幅", "涨跌幅(%)", "日涨跌幅"),
            "change": ("change", "change_amount", "price_change", "涨跌", "涨跌额"),
            "amount": ("amount", "turnover", "turnover_amount", "成交额", "成交额(元)"),
            "volume": ("volume", "vol", "成交量", "成交量(手)"),
            "nav": ("nav", "unit_nav", "acc_nav", "净值", "单位净值", "累计净值"),
        }
        for target, keys in aliases.items():
            value = self._first_present(row, keys)
            if value is None:
                continue
            current = normalized.get(target)
            if target not in normalized or current is None or current == "":
                normalized[target] = (
                    self._normalize_date_value(value)
                    if target == "date"
                    else self._coerce_market_value(value, percent=target == "change_pct")
                )
        if normalized.get("date"):
            normalized["date"] = self._normalize_date_value(normalized.get("date"))
        label = (
            arguments.get("index_name")
            or arguments.get("indexName")
            or arguments.get("asset_name")
            or arguments.get("assetName")
            or arguments.get("keyword")
            or arguments.get("code")
            or arguments.get("contract_code")
            or arguments.get("contractCode")
            or arguments.get("product_id")
            or arguments.get("productId")
        )
        if label and not any(normalized.get(key) for key in ("name", "index_name", "asset_name", "product_name")):
            normalized["index_name"] = str(label)
        return normalized

    def _first_present(self, row: dict[str, Any], keys: tuple[str, ...]) -> Any:
        lowered = {str(key).lower(): key for key in row.keys()}
        for key in keys:
            if key in row:
                value = row.get(key)
                if value is not None and value != "":
                    return value
            actual = lowered.get(key.lower())
            if actual is not None:
                value = row.get(actual)
                if value is not None and value != "":
                    return value
        return None

    def _coerce_market_value(self, value: Any, *, percent: bool = False) -> Any:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if value is None:
            return value
        text = str(value).strip()
        if not text:
            return value
        numeric = text.replace(",", "").replace("，", "")
        if percent:
            numeric = numeric.rstrip("%％")
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", numeric):
            try:
                return float(numeric) if "." in numeric else int(numeric)
            except ValueError:
                return value
        return value

    def _normalize_date_value(self, value: Any) -> Any:
        text = str(value or "").strip()
        if not text:
            return value
        digits = re.sub(r"\D", "", text)
        if len(digits) >= 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
        return text

    def _looks_like_market_row(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        keys = {str(key).lower() for key in value.keys()}
        marker_keys = {
            "date",
            "trade_date",
            "tradedate",
            "trading_date",
            "close",
            "close_price",
            "latest",
            "latest_price",
            "price",
            "pct_chg",
            "change_pct",
            "change_percent",
            "amount",
            "turnover",
            "volume",
            "vol",
            "nav",
            "unit_nav",
        }
        chinese_markers = {"日期", "交易日期", "收盘", "收盘价", "最新价", "涨跌幅", "成交额", "成交量", "净值"}
        return bool(keys & marker_keys or set(value.keys()) & chinese_markers)

    def _sort_market_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not any(self._market_date_key(row) for row in rows):
            return rows
        return [
            row
            for _, row in sorted(
                enumerate(rows),
                key=lambda item: (
                    0 if not self._market_date_key(item[1]) else 1,
                    self._market_date_key(item[1]),
                    item[0],
                ),
            )
        ]

    def _market_date_key(self, row: dict[str, Any]) -> str:
        value = (
            row.get("date")
            or row.get("trade_date")
            or row.get("tradedate")
            or row.get("trading_date")
            or row.get("datetime")
            or row.get("timestamp")
            or row.get("time")
            or row.get("日期")
            or row.get("交易日期")
            or row.get("时间")
        )
        if value is None:
            return ""
        return re.sub(r"\D", "", str(value))[:14]

    def _result_count(self, result: Any, fallback: int) -> int:
        if isinstance(result, dict):
            for key in ("count", "total", "row_count", "total_count"):
                value = result.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return fallback

    def _safe_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        safe = {}
        for key, value in arguments.items():
            if any(word in str(key).lower() for word in ("token", "key", "secret", "password", "authorization")):
                continue
            safe[str(key)] = value
        return safe


super66_mcp = Super66MCP()


async def get_mcp() -> Super66MCP:
    return super66_mcp


async def close_mcp() -> None:
    await super66_mcp.close()
