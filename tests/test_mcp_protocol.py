from typing import Optional

import pytest

from src.mcp.protocol import (
    MCP_LATEST_PROTOCOL_VERSION,
    build_request,
    encode_header_value,
    parse_sse_payload,
    request_headers,
    schema_from_callable,
    unwrap_tool_result,
)
from src.mcp.registry import MCPRegistry
from src.mcp.super66 import Super66MCP


async def sample_tool(query: str, limit: int = 10, market: Optional[str] = None):
    return {"query": query, "limit": limit, "market": market}


def test_callable_schema_uses_json_schema_2020_12_and_required_fields():
    schema = schema_from_callable(sample_tool, {"query": "搜索词", "limit": "条数"})

    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"] == {"type": "string", "description": "搜索词"}
    assert schema["properties"]["limit"]["default"] == 10
    assert schema["properties"]["market"]["type"] == ["string", "null"]
    assert schema["additionalProperties"] is False


def test_latest_request_has_per_request_metadata_and_mirrored_headers():
    body = build_request(
        "tools/call",
        {"name": "搜索", "arguments": {"region": "华东"}},
        request_id=7,
        client_name="erlangshen",
        client_version="test",
    )
    headers = request_headers(
        "tools/call",
        name="搜索",
        input_schema={
            "type": "object",
            "properties": {
                "region": {"type": "string", "x-mcp-header": "Region"},
            },
        },
        arguments={"region": "华东"},
    )

    meta = body["params"]["_meta"]
    assert meta["io.modelcontextprotocol/protocolVersion"] == MCP_LATEST_PROTOCOL_VERSION
    assert headers["MCP-Protocol-Version"] == MCP_LATEST_PROTOCOL_VERSION
    assert headers["Mcp-Method"] == "tools/call"
    assert headers["Mcp-Name"] == encode_header_value("搜索")
    assert headers["Mcp-Param-Region"] == encode_header_value("华东")


def test_tool_result_supports_structured_scalars_errors_and_input_required():
    assert unwrap_tool_result({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"resultType": "complete", "structuredContent": [1, 2]},
    }) == [1, 2]
    assert unwrap_tool_result({
        "jsonrpc": "2.0",
        "id": 2,
        "error": {"code": -32602, "message": "bad arguments"},
    })["code"] == -32602
    pending = unwrap_tool_result({
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "resultType": "input_required",
            "inputRequests": {"confirm": {"method": "elicitation/create"}},
            "requestState": "opaque",
        },
    })
    assert pending["input_required"] is True
    assert pending["requestState"] == "opaque"


def test_request_scoped_sse_uses_final_jsonrpc_response():
    payload = parse_sse_payload(
        'event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
        'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"resultType":"complete"}}\n\n'
    )
    assert payload["id"] == 1


def test_registry_exposes_standard_input_schema_without_dropping_parameters():
    class DemoMCP:
        def list_tools(self):
            return [{
                "name": "sample_tool",
                "description": "demo",
                "parameters": {"query": "搜索词"},
            }]

        async def sample_tool(self, query: str, limit: int = 10):
            return {"query": query, "limit": limit}

    registry = MCPRegistry.__new__(MCPRegistry)
    registry._mcps = {}
    registry._tools = {}
    registry.register_mcp("demo", DemoMCP())
    tool = registry.list_tools()[0]

    assert tool["parameters"] == {"query": "搜索词"}
    assert tool["inputSchema"]["required"] == ["query"]
    assert tool["inputSchema"]["properties"]["limit"]["type"] == "integer"


@pytest.mark.asyncio
async def test_super66_can_use_stateless_latest_streamable_http(monkeypatch):
    monkeypatch.setenv("SUPER66_MCP_ENDPOINT", "https://mcp.example.test/mcp")
    monkeypatch.setenv("SUPER66_MCP_PROTOCOL", "2026-07-15")
    monkeypatch.setenv("SUPER66_MCP_TOKEN", "token")
    monkeypatch.setenv("SUPER66_ALLOW_STATIC_TOKEN", "true")
    Super66MCP._instance = None
    calls = []

    class Response:
        status_code = 200
        headers = {"content-type": "application/json"}

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

        def raise_for_status(self):
            return None

    class Client:
        is_closed = False

        async def post(self, url, json=None, headers=None):
            calls.append((url, json, headers))
            if json["method"] == "tools/list":
                return Response({
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "result": {
                        "resultType": "complete",
                        "tools": [{
                            "name": "dc66_echo",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "x-mcp-header": "Query"},
                                },
                            },
                        }],
                    },
                })
            return Response({
                "jsonrpc": "2.0",
                "id": json["id"],
                "result": {
                    "resultType": "complete",
                    "structuredContent": {"echo": json["params"]["arguments"]["query"]},
                    "content": [{"type": "text", "text": "compat"}],
                },
            })

    mcp = Super66MCP()
    mcp._client = Client()
    result = await mcp.call_tool("echo", {"query": "你好"}, use_cache=False)

    assert result == {"echo": "你好"}
    assert [call[1]["method"] for call in calls] == ["tools/list", "tools/call"]
    assert calls[-1][2]["Mcp-Name"] == "dc66_echo"
    assert calls[-1][2]["Mcp-Param-Query"] == encode_header_value("你好")
    assert calls[-1][1]["params"]["_meta"]["io.modelcontextprotocol/clientInfo"]["name"] == "erlangshen"
    Super66MCP._instance = None
