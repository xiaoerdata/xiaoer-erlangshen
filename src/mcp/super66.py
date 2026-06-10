"""
Lightweight Super-66 MCP client for the npm CLI package.

The client reuses the Erlangshen/XWAB/XCZT auth token saved by `/login`.
No separate Super-66 password is required on the client side.
"""

from __future__ import annotations

import json
import os
import re
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
        normalized_tool = self._normalize_tool_name(tool_name)
        normalized_arguments = self._normalize_tool_arguments(tool_name, arguments)
        cache_key = self._cache_key(normalized_tool, normalized_arguments)
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
                json={"name": normalized_tool, "arguments": normalized_arguments},
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
            result = self._extract_result(payload, tool_name, normalized_arguments)
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

    def _normalize_tool_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = dict(arguments or {})
        normalized_name = tool_name.removeprefix("dc66_")
        common_aliases = {
            "start_date": "startDate",
            "end_date": "endDate",
        }
        aliases = {
            "get_index_data": {"index_name": "indexName", "index_code": "indexName"},
            "get_global_asset_data": {"asset_name": "assetName", "asset_code": "assetCode", "source_table": "sourceTable"},
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
        return args

    def _parse_payload(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

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
        rows = self._extract_rows(result)
        if rows:
            normalized_rows = [self._normalize_market_row(row, arguments) for row in rows if isinstance(row, dict)]
            latest = normalized_rows[-1] if normalized_rows else {}
            return {
                "tool": tool_name,
                "arguments": self._safe_arguments(arguments),
                "rows": normalized_rows[-120:],
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

    def _extract_rows(self, value: Any, depth: int = 0) -> list[dict[str, Any]]:
        if depth > 6:
            return []
        if isinstance(value, list):
            rows = []
            for item in value:
                if isinstance(item, dict):
                    rows.append(item)
                elif isinstance(item, list):
                    rows.extend(self._extract_rows(item, depth + 1))
            return rows
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
                normalized[target] = self._coerce_market_value(value, percent=target == "change_pct")
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
