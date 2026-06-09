"""Curated LLM provider/model presets for the CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPreset:
    id: str
    label: str
    description: str


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    display_name: str
    key_env: str
    model_env: str
    default_model: str
    models: tuple[ModelPreset, ...]


MODEL_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        id="openai",
        display_name="OpenAI",
        key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        default_model="gpt-5.2",
        models=(
            ModelPreset("gpt-5.2", "GPT-5.2", "当前旗舰模型，适合复杂分析和 agent 任务"),
            ModelPreset("gpt-5-mini", "GPT-5 mini", "速度和成本更均衡"),
            ModelPreset("gpt-5-nano", "GPT-5 nano", "轻量、低成本场景"),
            ModelPreset("gpt-4.1", "GPT-4.1", "长上下文、非推理任务"),
            ModelPreset("gpt-4.1-mini", "GPT-4.1 mini", "轻量长上下文"),
            ModelPreset("gpt-4o", "GPT-4o", "通用多模态兼容选择"),
        ),
    ),
    ProviderPreset(
        id="claude",
        display_name="Claude / Anthropic",
        key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_MODEL",
        default_model="claude-sonnet-4-6",
        models=(
            ModelPreset("claude-opus-4-8", "Claude Opus 4.8", "复杂推理和长程 agent 任务"),
            ModelPreset("claude-sonnet-4-6", "Claude Sonnet 4.6", "速度和智能综合最均衡"),
            ModelPreset("claude-haiku-4-5", "Claude Haiku 4.5", "最快、成本更友好"),
        ),
    ),
    ProviderPreset(
        id="deepseek",
        display_name="DeepSeek",
        key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_MODEL",
        default_model="deepseek-v4-flash",
        models=(
            ModelPreset("deepseek-v4-pro", "DeepSeek V4 Pro", "更强推理与复杂分析"),
            ModelPreset("deepseek-v4-flash", "DeepSeek V4 Flash", "默认推荐，速度和成本均衡"),
            ModelPreset("deepseek-chat", "DeepSeek Chat", "兼容旧名，计划于 2026-07-24 停用"),
            ModelPreset("deepseek-reasoner", "DeepSeek Reasoner", "兼容旧名，计划于 2026-07-24 停用"),
        ),
    ),
    ProviderPreset(
        id="mimo",
        display_name="Xiaomi MiMo",
        key_env="MIMO_API_KEY",
        model_env="MIMO_MODEL",
        default_model="mimo-v2.5-pro",
        models=(
            ModelPreset("mimo-v2.5-pro", "MiMo V2.5 Pro", "复杂推理、长文档、Agent 和 Coding"),
            ModelPreset("mimo-v2.5", "MiMo V2.5", "全模态理解与通用任务"),
            ModelPreset("mimo-v2-flash", "MiMo V2 Flash", "高并发、低成本、快速响应"),
        ),
    ),
    ProviderPreset(
        id="kimi",
        display_name="Kimi / Moonshot",
        key_env="KIMI_API_KEY",
        model_env="KIMI_MODEL",
        default_model="kimi-k2.6",
        models=(
            ModelPreset("kimi-k2.6", "Kimi K2.6", "最新智能模型，偏代码、Agent、视觉和复杂任务"),
            ModelPreset("kimi-k2.5", "Kimi K2.5", "视觉和文本输入，支持思考/非思考模式"),
            ModelPreset("kimi-k2", "Kimi K2", "K2 系列兼容选择"),
            ModelPreset("moonshot-v1-128k", "Moonshot V1 128K", "经典长上下文兼容模型"),
        ),
    ),
)

PROVIDER_PRESETS = {provider.id: provider for provider in MODEL_PRESETS}
PROVIDER_ALIASES = {
    "anthropic": "claude",
    "xiaomi": "mimo",
    "moonshot": "kimi",
}


def normalize_provider(provider: str | None) -> str:
    value = (provider or "openai").strip().lower()
    return PROVIDER_ALIASES.get(value, value)


def get_provider_preset(provider: str | None) -> ProviderPreset:
    key = normalize_provider(provider)
    return PROVIDER_PRESETS.get(key, PROVIDER_PRESETS["openai"])


def default_model_for(provider: str | None) -> str:
    return get_provider_preset(provider).default_model


def model_ids_for(provider: str | None) -> list[str]:
    return [model.id for model in get_provider_preset(provider).models]
