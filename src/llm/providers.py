"""
Unified LLM provider routing.

Supports OpenAI-compatible Chat Completions providers and Anthropic
Messages-compatible providers without adding provider-specific SDKs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import httpx

from src.model_presets import default_model_for


OPENAI_COMPATIBLE = "openai_chat"
ANTHROPIC_MESSAGES = "anthropic_messages"
MIMO_OPENAI_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_ANTHROPIC_BASE_URL = "https://api.xiaomimimo.com/anthropic"


@dataclass(frozen=True)
class LLMProviderDefinition:
    name: str
    display_name: str
    protocol: str
    default_model: str
    default_base_url: Optional[str]
    api_key_envs: tuple[str, ...]
    model_envs: tuple[str, ...]
    base_url_envs: tuple[str, ...]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class LLMProviderSettings:
    provider: str
    display_name: str
    protocol: str
    model: str
    base_url: Optional[str]
    api_key: Optional[str]
    api_key_envs: tuple[str, ...]

    @property
    def has_api_key(self) -> bool:
        return bool((self.api_key or "").strip())


PROVIDERS: dict[str, LLMProviderDefinition] = {
    "openai": LLMProviderDefinition(
        name="openai",
        display_name="OpenAI",
        protocol=OPENAI_COMPATIBLE,
        default_model=default_model_for("openai"),
        default_base_url="https://api.openai.com/v1",
        api_key_envs=("OPENAI_API_KEY",),
        model_envs=("OPENAI_MODEL",),
        base_url_envs=("OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_API_BASE_URL"),
    ),
    "claude": LLMProviderDefinition(
        name="claude",
        display_name="Claude / Anthropic",
        protocol=ANTHROPIC_MESSAGES,
        default_model=default_model_for("claude"),
        default_base_url="https://api.anthropic.com",
        api_key_envs=("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
        model_envs=("ANTHROPIC_MODEL", "CLAUDE_MODEL"),
        base_url_envs=("ANTHROPIC_BASE_URL", "CLAUDE_BASE_URL"),
        aliases=("anthropic",),
    ),
    "deepseek": LLMProviderDefinition(
        name="deepseek",
        display_name="DeepSeek",
        protocol=OPENAI_COMPATIBLE,
        default_model=default_model_for("deepseek"),
        default_base_url="https://api.deepseek.com",
        api_key_envs=("DEEPSEEK_API_KEY",),
        model_envs=("DEEPSEEK_MODEL",),
        base_url_envs=("DEEPSEEK_BASE_URL", "DEEPSEEK_API_BASE", "DEEPSEEK_API_BASE_URL"),
    ),
    "mimo": LLMProviderDefinition(
        name="mimo",
        display_name="Xiaomi MiMo",
        protocol=OPENAI_COMPATIBLE,
        default_model=default_model_for("mimo"),
        default_base_url=MIMO_OPENAI_BASE_URL,
        api_key_envs=("MIMO_API_KEY", "XIAOMI_API_KEY"),
        model_envs=("MIMO_MODEL", "XIAOMI_MODEL"),
        base_url_envs=("MIMO_BASE_URL", "MIMO_API_BASE_URL", "XIAOMI_BASE_URL", "XIAOMI_API_BASE_URL"),
        aliases=("xiaomi",),
    ),
    "kimi": LLMProviderDefinition(
        name="kimi",
        display_name="Kimi / Moonshot",
        protocol=OPENAI_COMPATIBLE,
        default_model=default_model_for("kimi"),
        default_base_url="https://api.moonshot.ai/v1",
        api_key_envs=("KIMI_API_KEY", "MOONSHOT_API_KEY"),
        model_envs=("KIMI_MODEL", "MOONSHOT_MODEL"),
        base_url_envs=("KIMI_BASE_URL", "KIMI_API_BASE_URL", "MOONSHOT_BASE_URL", "MOONSHOT_API_BASE"),
        aliases=("moonshot",),
    ),
}


ALIASES = {
    alias: provider.name
    for provider in PROVIDERS.values()
    for alias in (provider.name, *provider.aliases)
}


def normalize_provider(provider: Optional[str]) -> str:
    name = (provider or "openai").strip().lower()
    return ALIASES.get(name, name)


def supported_providers() -> list[str]:
    return sorted(PROVIDERS)


def resolve_llm_settings(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config: Any = None,
) -> LLMProviderSettings:
    """Resolve provider settings from explicit args, environment and config."""

    provider_name = normalize_provider(provider or getattr(config, "llm_provider", None))
    if provider_name not in PROVIDERS:
        raise ValueError(f"不支持的 LLM 提供商: {provider_name}。可用: {', '.join(supported_providers())}")

    definition = PROVIDERS[provider_name]
    if api_key is not None:
        resolved_api_key = _clean(api_key)
    else:
        resolved_api_key = (
            _provider_config_value(config, provider_name, "api_key")
            or _first_env(definition.api_key_envs)
            or _clean(getattr(config, "llm_api_key", None))
            or _first_env(("LLM_API_KEY",))
        )
    resolved_model = (
        _clean(model)
        or _first_env(definition.model_envs)
        or _provider_config_value(config, provider_name, "model")
        or _generic_model_from_config(config, provider_name)
        or definition.default_model
    )
    configured_base_url = (
        _clean(base_url)
        or _first_env(definition.base_url_envs)
        or _provider_config_value(config, provider_name, "base_url")
        or _generic_base_url_from_config(config, provider_name)
    )
    resolved_protocol = _resolve_protocol(config, provider_name, definition.protocol)
    resolved_base_url = configured_base_url or _default_base_url(definition, resolved_protocol)

    return LLMProviderSettings(
        provider=definition.name,
        display_name=definition.display_name,
        protocol=resolved_protocol,
        model=resolved_model,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        api_key_envs=definition.api_key_envs,
    )


class LLMClient:
    """Small async client for supported LLM provider protocols."""

    def __init__(self, settings: LLMProviderSettings, timeout: float = 60.0):
        self.settings = settings
        self.timeout = timeout

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        if not self.settings.has_api_key:
            raise RuntimeError(
                f"{self.settings.display_name} API Key 未配置，请设置 "
                f"{' 或 '.join(self.settings.api_key_envs)}"
            )
        if not self.settings.base_url:
            raise RuntimeError(
                f"{self.settings.display_name} API Base URL 未配置，请设置对应 BASE_URL 环境变量"
            )

        if self.settings.protocol == ANTHROPIC_MESSAGES:
            return await self._complete_anthropic(messages, temperature=temperature, max_tokens=max_tokens)
        return await self._complete_openai_compatible(messages, temperature=temperature, max_tokens=max_tokens)

    async def _complete_openai_compatible(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.settings.provider == "mimo":
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = max_tokens
        headers = _api_key_headers(self.settings)
        url = _join_openai_url(self.settings.base_url or "", "chat/completions")
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=True) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])

    async def _complete_anthropic(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        system, conversation = _split_anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": conversation,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            payload["system"] = system

        headers = _api_key_headers(self.settings)
        headers["anthropic-version"] = "2023-06-01"
        url = _join_anthropic_url(self.settings.base_url or "")
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=True) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return _extract_anthropic_text(data)


def _first_env(names: Iterable[str]) -> Optional[str]:
    for name in names:
        value = _clean(os.getenv(name))
        if value:
            return value
    return None


def _default_base_url(definition: LLMProviderDefinition, protocol: str) -> Optional[str]:
    if definition.name == "mimo" and protocol == ANTHROPIC_MESSAGES:
        return MIMO_ANTHROPIC_BASE_URL
    return definition.default_base_url


def _api_key_headers(settings: LLMProviderSettings) -> dict[str, str]:
    if settings.provider == "mimo":
        if settings.protocol == OPENAI_COMPATIBLE:
            return {
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            }
        return {
            "api-key": settings.api_key or "",
            "Content-Type": "application/json",
        }
    if settings.protocol == ANTHROPIC_MESSAGES:
        return {
            "x-api-key": settings.api_key or "",
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _provider_config_value(config: Any, provider: str, field: str) -> Optional[str]:
    if not config:
        return None
    candidates = [f"{provider}_{field}"]
    if provider == "claude":
        candidates.append(f"anthropic_{field}")
    if provider == "mimo":
        candidates.append(f"xiaomi_{field}")
    if provider == "kimi":
        candidates.append(f"moonshot_{field}")
    for name in candidates:
        value = _clean(getattr(config, name, None))
        if value:
            return value
    return None


def _generic_model_from_config(config: Any, provider: str) -> Optional[str]:
    if not config:
        return None
    env_model = _first_env(("LLM_MODEL",))
    if env_model:
        return env_model
    value = _clean(getattr(config, "llm_model", None))
    if not value:
        return None
    config_provider = normalize_provider(getattr(config, "llm_provider", None))
    if config_provider == provider and value not in {"gpt-4", "gpt-4o-mini"}:
        return value
    if provider == "openai":
        return value
    return None


def _generic_base_url_from_config(config: Any, provider: str) -> Optional[str]:
    if not config:
        return None
    env_base_url = _first_env(("LLM_BASE_URL",))
    if env_base_url:
        return env_base_url
    value = _clean(getattr(config, "llm_base_url", None))
    if not value:
        return None
    config_provider = normalize_provider(getattr(config, "llm_provider", None))
    return value if config_provider == provider else None


def _resolve_protocol(config: Any, provider: str, default: str) -> str:
    value = (
        _first_env((f"{provider.upper()}_PROTOCOL", "LLM_PROTOCOL"))
        or _provider_config_value(config, provider, "protocol")
        or _clean(getattr(config, "llm_protocol", None))
        or default
    )
    aliases = {
        "openai": OPENAI_COMPATIBLE,
        "openai_chat": OPENAI_COMPATIBLE,
        "openai-compatible": OPENAI_COMPATIBLE,
        "chat_completions": OPENAI_COMPATIBLE,
        "anthropic": ANTHROPIC_MESSAGES,
        "anthropic_messages": ANTHROPIC_MESSAGES,
        "claude": ANTHROPIC_MESSAGES,
        "messages": ANTHROPIC_MESSAGES,
    }
    normalized = str(value).strip().lower()
    if normalized not in aliases:
        raise ValueError(f"不支持的 LLM 协议: {value}")
    return aliases[normalized]


def _join_openai_url(base_url: str, endpoint: str) -> str:
    base = base_url.rstrip("/")
    endpoint = endpoint.strip("/")
    return f"{base}/{endpoint}"


def _join_anthropic_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _split_anthropic_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    system_parts: list[str] = []
    conversation: list[dict[str, str]] = []
    for message in messages:
        role = (message.get("role") or "user").strip()
        content = str(message.get("content") or "")
        if role == "system":
            system_parts.append(content)
        elif role in {"user", "assistant"}:
            conversation.append({"role": role, "content": content})
        else:
            conversation.append({"role": "user", "content": content})
    if not conversation:
        conversation.append({"role": "user", "content": ""})
    return "\n\n".join(part for part in system_parts if part), conversation


def _extract_anthropic_text(data: dict[str, Any]) -> str:
    content = data.get("content") or []
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "".join(parts)
