"""MCP wire helpers shared by the built-in tool registry and remote clients.

Erlangshen targets the 2026-07-15 MCP revision.  This revision uses stateless,
per-request HTTP metadata.  The protocol-specific code stays in one place so
callers can use it without dropping the current Super66 compatibility gateway.
"""

from __future__ import annotations

import base64
import inspect
import json
import re
import types
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Union, get_args, get_origin, get_type_hints


MCP_STABLE_PROTOCOL_VERSION = "2025-11-25"
MCP_LATEST_PROTOCOL_VERSION = "2026-07-15"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def _annotation_schema(annotation: Any) -> Dict[str, Any]:
    """Convert the common Python annotations used by built-in tools to JSON Schema."""
    if annotation in {inspect.Signature.empty, Any, None}:
        return {}
    if annotation is type(None):
        return {"type": "null"}

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        values = list(args)
        schema: Dict[str, Any] = {"enum": values}
        value_types = {type(value) for value in values}
        if len(value_types) == 1:
            schema.update(_annotation_schema(next(iter(value_types))))
        return schema
    if origin in {Union, types.UnionType}:
        non_null = [arg for arg in args if arg is not type(None)]
        if len(non_null) == 1 and len(non_null) != len(args):
            schema = _annotation_schema(non_null[0])
            value_type = schema.get("type")
            if isinstance(value_type, str):
                schema["type"] = [value_type, "null"]
            else:
                schema = {"anyOf": [schema, {"type": "null"}]}
            return schema
        return {"anyOf": [_annotation_schema(arg) for arg in args]}
    if origin in {list, List, tuple, set, frozenset}:
        item_type = args[0] if args else Any
        return {"type": "array", "items": _annotation_schema(item_type)}
    if origin in {dict, Dict, Mapping}:
        value_type = args[1] if len(args) > 1 else Any
        schema = _annotation_schema(value_type)
        return {"type": "object", "additionalProperties": schema or True}
    if annotation is str:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation in {list, tuple, set, frozenset}:
        return {"type": "array"}
    if annotation is dict:
        return {"type": "object"}
    return {}


def schema_from_callable(
    handler: Callable[..., Any],
    parameter_descriptions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a bounded JSON Schema 2020-12 input schema from a tool handler."""
    descriptions = parameter_descriptions or {}
    try:
        hints = get_type_hints(handler)
    except Exception:
        hints = {}
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, parameter in inspect.signature(handler).parameters.items():
        if name in {"self", "cls"} or parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        schema = _annotation_schema(hints.get(name, parameter.annotation))
        description = descriptions.get(name)
        if isinstance(description, str) and description:
            schema["description"] = description
        if parameter.default is inspect.Signature.empty:
            required.append(name)
        elif parameter.default is not None and isinstance(parameter.default, (str, int, float, bool, list, dict)):
            schema["default"] = parameter.default
        properties[name] = schema

    result: Dict[str, Any] = {
        "$schema": JSON_SCHEMA_DIALECT,
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        result["required"] = required
    return result


def normalize_tool_definition(
    definition: Mapping[str, Any],
    handler: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Return a 2026-ready MCP Tool while retaining legacy ``parameters``."""
    tool = dict(definition)
    legacy_parameters = tool.get("parameters")
    if not isinstance(legacy_parameters, Mapping):
        legacy_parameters = {}
    input_schema = tool.get("inputSchema")
    if not isinstance(input_schema, Mapping):
        input_schema = schema_from_callable(handler, legacy_parameters) if handler else {
            "$schema": JSON_SCHEMA_DIALECT,
            "type": "object",
            "additionalProperties": False,
        }
    else:
        input_schema = dict(input_schema)
        input_schema.setdefault("$schema", JSON_SCHEMA_DIALECT)
        input_schema.setdefault("type", "object")
    tool["inputSchema"] = input_schema
    tool["parameters"] = dict(legacy_parameters)
    return tool


def request_metadata(
    *,
    client_name: str,
    client_version: str,
    protocol_version: str = MCP_LATEST_PROTOCOL_VERSION,
    capabilities: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "io.modelcontextprotocol/protocolVersion": protocol_version,
        "io.modelcontextprotocol/clientInfo": {
            "name": client_name,
            "version": client_version,
        },
        "io.modelcontextprotocol/clientCapabilities": dict(capabilities or {}),
    }


def build_request(
    method: str,
    params: Optional[Mapping[str, Any]],
    *,
    request_id: Union[str, int],
    client_name: str,
    client_version: str,
    protocol_version: str = MCP_LATEST_PROTOCOL_VERSION,
    capabilities: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    request_params = dict(params or {})
    existing_meta = request_params.get("_meta")
    meta = dict(existing_meta) if isinstance(existing_meta, Mapping) else {}
    meta.update(request_metadata(
        client_name=client_name,
        client_version=client_version,
        protocol_version=protocol_version,
        capabilities=capabilities,
    ))
    request_params["_meta"] = meta
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


def encode_header_value(value: Any) -> str:
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    safe = (
        text == text.strip()
        and all(character == "\t" or 0x20 <= ord(character) <= 0x7E for character in text)
        and not (text.startswith("=?base64?") and text.endswith("?="))
    )
    if safe:
        return text
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"=?base64?{encoded}?="


def request_headers(
    method: str,
    *,
    protocol_version: str = MCP_LATEST_PROTOCOL_VERSION,
    name: Optional[str] = None,
    authorization: Optional[str] = None,
    input_schema: Optional[Mapping[str, Any]] = None,
    arguments: Optional[Mapping[str, Any]] = None,
) -> Dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": protocol_version,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = encode_header_value(name)
    if authorization:
        headers["Authorization"] = authorization
    headers.update(tool_parameter_headers(input_schema or {}, arguments or {}))
    return headers


def tool_parameter_headers(
    input_schema: Mapping[str, Any],
    arguments: Mapping[str, Any],
) -> Dict[str, str]:
    """Mirror valid ``x-mcp-header`` parameters for 2026 Streamable HTTP."""
    found: List[tuple[str, Any]] = []

    def visit(schema: Any, value: Any) -> None:
        if not isinstance(schema, Mapping):
            return
        header_name = schema.get("x-mcp-header")
        if header_name is not None and value is not None:
            if not isinstance(header_name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", header_name):
                raise ValueError(f"invalid x-mcp-header name: {header_name!r}")
            schema_type = schema.get("type")
            if schema_type not in {"string", "integer", "boolean"}:
                raise ValueError(f"x-mcp-header {header_name!r} must annotate a string, integer, or boolean")
            if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
                raise ValueError(f"x-mcp-header {header_name!r} integer is outside the safe range")
            found.append((header_name, value))
        properties = schema.get("properties")
        if isinstance(properties, Mapping) and isinstance(value, Mapping):
            for property_name, property_schema in properties.items():
                if property_name in value:
                    visit(property_schema, value[property_name])

    visit(input_schema, arguments)
    lowered = [name.lower() for name, _ in found]
    if len(lowered) != len(set(lowered)):
        raise ValueError("x-mcp-header names must be case-insensitively unique")
    return {f"Mcp-Param-{name}": encode_header_value(value) for name, value in found}


def parse_sse_payload(text: str) -> Any:
    """Return the final JSON-RPC message from a request-scoped SSE response."""
    messages: List[Any] = []
    data_lines: List[str] = []
    for line in (text or "").splitlines() + [""]:
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
            continue
        if not line and data_lines:
            try:
                messages.append(json.loads("\n".join(data_lines)))
            except ValueError:
                pass
            data_lines = []
    responses = [item for item in messages if isinstance(item, dict) and ("result" in item or "error" in item)]
    return responses[-1] if responses else (messages[-1] if messages else {})


def response_payload(response: Any) -> Any:
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).lower()
    if "text/event-stream" in content_type:
        return parse_sse_payload(str(getattr(response, "text", "")))
    try:
        return response.json()
    except Exception:
        text = str(getattr(response, "text", ""))
        try:
            return json.loads(text)
        except ValueError:
            return {"error": text or "MCP returned an empty response"}


def unwrap_tool_result(payload: Any) -> Any:
    """Normalize 2025/2026 CallToolResult without discarding MCP error context."""
    if not isinstance(payload, Mapping):
        return payload
    protocol_error = payload.get("error")
    if isinstance(protocol_error, Mapping):
        return {
            "error": str(protocol_error.get("message") or "MCP protocol error"),
            "code": protocol_error.get("code"),
            "details": protocol_error.get("data"),
            "protocol_error": True,
        }
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return result if result is not None else dict(payload)
    result_type = result.get("resultType", "complete")
    if result_type == "input_required":
        return {
            "input_required": True,
            "inputRequests": result.get("inputRequests", {}),
            "requestState": result.get("requestState"),
        }
    if result_type != "complete":
        return {"error": f"不支持的 MCP resultType: {result_type}", "result": dict(result)}

    structured_present = "structuredContent" in result
    structured = result.get("structuredContent")
    content = result.get("content") if isinstance(result.get("content"), list) else []
    text_parts = [
        str(item.get("text"))
        for item in content
        if isinstance(item, Mapping) and item.get("type") == "text" and item.get("text") is not None
    ]
    if result.get("isError"):
        return {
            "error": "\n".join(text_parts) or structured or "MCP tool execution failed",
            "isError": True,
            "content": content,
        }
    if structured_present:
        return structured
    if len(text_parts) == 1:
        try:
            return json.loads(text_parts[0])
        except ValueError:
            return {"text": text_parts[0], "content": content}
    return {"content": content}
