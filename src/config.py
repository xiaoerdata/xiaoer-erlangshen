"""
二郎神配置管理
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from src.model_presets import default_model_for
from src.paths import get_default_knowledge_dir, get_project_root


API_KEY_CONFIG_FIELDS = (
    "llm_api_key",
    "deepseek_api_key",
    "anthropic_api_key",
    "claude_api_key",
    "mimo_api_key",
    "xiaomi_api_key",
    "kimi_api_key",
    "moonshot_api_key",
)


class Config(BaseModel):
    """二郎神配置"""

    # ==================== LLM 配置 ====================
    llm_provider: str = "openai"
    llm_model: str = default_model_for("openai")
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_protocol: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # ==================== DeepSeek 专用配置 ====================
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = default_model_for("deepseek")
    deepseek_base_url: Optional[str] = None

    # ==================== Claude / Anthropic 配置 ====================
    claude_api_key: Optional[str] = None
    claude_model: str = default_model_for("claude")
    claude_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    anthropic_base_url: Optional[str] = None

    # ==================== 小米 MiMo 配置 ====================
    mimo_api_key: Optional[str] = None
    mimo_model: str = default_model_for("mimo")
    mimo_base_url: Optional[str] = None
    mimo_protocol: Optional[str] = None
    xiaomi_api_key: Optional[str] = None
    xiaomi_model: Optional[str] = None
    xiaomi_base_url: Optional[str] = None
    xiaomi_protocol: Optional[str] = None

    # ==================== Kimi / Moonshot 配置 ====================
    kimi_api_key: Optional[str] = None
    kimi_model: str = default_model_for("kimi")
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    moonshot_api_key: Optional[str] = None
    moonshot_model: Optional[str] = None
    moonshot_base_url: Optional[str] = None

    # ==================== MCP 配置 ====================
    mcp_enabled: bool = True
    mcp_timeout: int = 30

    # ==================== 二郎神服务端配置 ====================
    erlangshen_api_base_url: str = "https://xiaoerdata.site/api/erlangshen"
    erlangshen_auth_login_entry: str = "xwab"

    # ==================== 数据库配置 ====================
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "market"
    db_user: str = "postgres"
    db_password: Optional[str] = None

    # ==================== 飞书配置 ====================
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None

    # ==================== 知识库路径 ====================
    knowledge_dir: str = Field(default_factory=lambda: str(get_default_knowledge_dir()))

    # ==================== 日志配置 ====================
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # ==================== 搜索配置 ====================
    search_provider: str = "duckduckgo"  # duckduckgo, serpapi, minimax
    search_language: str = "auto"  # auto, zh, en
    serpapi_key: Optional[str] = None  # SerpAPI API Key

    # ==================== 市场数据 API 配置 ====================

    # Alpha Vantage (免费额度: 25次/天)
    alpha_vantage_key: Optional[str] = None

    # Twelve Data (免费额度: 800次/天)
    twelve_data_key: Optional[str] = None

    # Trading Economics (免费额度: 有限)
    trading_economics_key: Optional[str] = None

    # CoinMarketCap (免费额度: 有限)
    coinmarketcap_key: Optional[str] = None

    # FRED (美联储经济数据 - 免费，需要API Key)
    fred_api_key: Optional[str] = None

    # ==================== 缓存配置 ====================
    cache_enabled: bool = True
    cache_ttl: int = 300  # 默认缓存时间(秒)
    cache_max_size: int = 1000  # 最大缓存条目数

    # ==================== 代理配置 ====================
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    proxy_enabled: bool = False

    # ==================== 请求配置 ====================
    request_timeout: int = 30  # 请求超时(秒)
    max_retries: int = 3  # 最大重试次数
    user_agent: str = "二郎神/1.0"

    # ==================== 工具启用配置 ====================
    enabled_tools: List[str] = Field(
        default_factory=lambda: [
            "market",
            "search",
            "file",
        ]
    )

    # 市场工具子选项
    enable_stock: bool = True  # 股票数据
    enable_crypto: bool = True  # 加密货币
    enable_commodity: bool = True  # 大宗商品
    enable_forex: bool = True  # 外汇
    enable_macro: bool = True  # 宏观数据

    # 搜索工具子选项
    enable_web_search: bool = True
    enable_news_search: bool = True
    enable_academic_search: bool = True
    enable_company_search: bool = True

    class Config:
        extra = "allow"


def get_config_path() -> Path:
    """获取配置路径"""
    env_path = os.getenv("ERLANGSHEN_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    project_config = get_project_root() / ".claude" / "settings.json"
    if project_config.exists():
        return project_config

    return Path("~/.erlangshen/settings.json").expanduser()


def get_default_config() -> Config:
    """获取默认配置"""
    return Config()


def load_config() -> Config:
    """加载配置"""
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Config(**data)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Failed to load config: {e}")
            return Config()

    return Config()


def save_config(config: Config) -> None:
    """保存配置"""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


def merge_config(base: Config, updates: Dict[str, Any]) -> Config:
    """
    合并配置更新

    Args:
        base: 基础配置
        updates: 更新字典

    Returns:
        Config: 合并后的配置
    """
    base_dict = base.model_dump()

    # 递归合并
    def deep_merge(base_dict: dict, update_dict: dict) -> dict:
        result = base_dict.copy()
        for key, value in update_dict.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged = deep_merge(base_dict, updates)
    return Config(**merged)


# ==================== 环境变量支持 ====================

def load_config_from_env() -> Dict[str, Any]:
    """从环境变量加载配置"""
    updates = {}

    # LLM provider/model routing
    if os.getenv("LLM_PROVIDER"):
        updates["llm_provider"] = os.getenv("LLM_PROVIDER")
    if os.getenv("LLM_MODEL"):
        updates["llm_model"] = os.getenv("LLM_MODEL")
    if os.getenv("LLM_PROTOCOL"):
        updates["llm_protocol"] = os.getenv("LLM_PROTOCOL")
    if os.getenv("OPENAI_MODEL"):
        updates["llm_model"] = os.getenv("OPENAI_MODEL")
    if os.getenv("DEEPSEEK_MODEL"):
        updates["deepseek_model"] = os.getenv("DEEPSEEK_MODEL")
    if os.getenv("ANTHROPIC_MODEL"):
        updates["anthropic_model"] = os.getenv("ANTHROPIC_MODEL")
    if os.getenv("CLAUDE_MODEL"):
        updates["claude_model"] = os.getenv("CLAUDE_MODEL")
    if os.getenv("MIMO_MODEL"):
        updates["mimo_model"] = os.getenv("MIMO_MODEL")
    if os.getenv("MIMO_PROTOCOL"):
        updates["mimo_protocol"] = os.getenv("MIMO_PROTOCOL")
    if os.getenv("XIAOMI_MODEL"):
        updates["xiaomi_model"] = os.getenv("XIAOMI_MODEL")
    if os.getenv("XIAOMI_PROTOCOL"):
        updates["xiaomi_protocol"] = os.getenv("XIAOMI_PROTOCOL")
    if os.getenv("KIMI_MODEL"):
        updates["kimi_model"] = os.getenv("KIMI_MODEL")
    if os.getenv("MOONSHOT_MODEL"):
        updates["moonshot_model"] = os.getenv("MOONSHOT_MODEL")

    # API Keys
    if os.getenv("OPENAI_API_KEY"):
        updates["llm_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("LLM_API_KEY"):
        updates["llm_api_key"] = os.getenv("LLM_API_KEY")
    if os.getenv("DEEPSEEK_API_KEY"):
        updates["deepseek_api_key"] = os.getenv("DEEPSEEK_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):
        updates["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("CLAUDE_API_KEY"):
        updates["claude_api_key"] = os.getenv("CLAUDE_API_KEY")
    if os.getenv("MIMO_API_KEY"):
        updates["mimo_api_key"] = os.getenv("MIMO_API_KEY")
    if os.getenv("XIAOMI_API_KEY"):
        updates["xiaomi_api_key"] = os.getenv("XIAOMI_API_KEY")
    if os.getenv("KIMI_API_KEY"):
        updates["kimi_api_key"] = os.getenv("KIMI_API_KEY")
    if os.getenv("MOONSHOT_API_KEY"):
        updates["moonshot_api_key"] = os.getenv("MOONSHOT_API_KEY")

    # OpenAI-compatible local model endpoints (Ollama, LM Studio, vLLM, etc.)
    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or os.getenv("DEEPSEEK_BASE_URL")
    )
    if base_url:
        updates["llm_base_url"] = base_url
    if os.getenv("DEEPSEEK_BASE_URL"):
        updates["deepseek_base_url"] = os.getenv("DEEPSEEK_BASE_URL")
    if os.getenv("ANTHROPIC_BASE_URL"):
        updates["anthropic_base_url"] = os.getenv("ANTHROPIC_BASE_URL")
    if os.getenv("CLAUDE_BASE_URL"):
        updates["claude_base_url"] = os.getenv("CLAUDE_BASE_URL")
    if os.getenv("MIMO_BASE_URL"):
        updates["mimo_base_url"] = os.getenv("MIMO_BASE_URL")
    if os.getenv("MIMO_API_BASE_URL"):
        updates["mimo_base_url"] = os.getenv("MIMO_API_BASE_URL")
    if os.getenv("XIAOMI_BASE_URL"):
        updates["xiaomi_base_url"] = os.getenv("XIAOMI_BASE_URL")
    if os.getenv("XIAOMI_API_BASE_URL"):
        updates["xiaomi_base_url"] = os.getenv("XIAOMI_API_BASE_URL")
    if os.getenv("KIMI_BASE_URL"):
        updates["kimi_base_url"] = os.getenv("KIMI_BASE_URL")
    if os.getenv("KIMI_API_BASE_URL"):
        updates["kimi_base_url"] = os.getenv("KIMI_API_BASE_URL")
    if os.getenv("MOONSHOT_BASE_URL"):
        updates["moonshot_base_url"] = os.getenv("MOONSHOT_BASE_URL")
    if os.getenv("MOONSHOT_API_BASE"):
        updates["moonshot_base_url"] = os.getenv("MOONSHOT_API_BASE")

    if os.getenv("SERPAPI_KEY"):
        updates["serpapi_key"] = os.getenv("SERPAPI_KEY")
    if os.getenv("ALPHA_VANTAGE_KEY"):
        updates["alpha_vantage_key"] = os.getenv("ALPHA_VANTAGE_KEY")
    if os.getenv("FRED_API_KEY"):
        updates["fred_api_key"] = os.getenv("FRED_API_KEY")
    if os.getenv("COINMARKETCAP_KEY"):
        updates["coinmarketcap_key"] = os.getenv("COINMARKETCAP_KEY")

    if os.getenv("ERLANGSHEN_API_BASE_URL"):
        updates["erlangshen_api_base_url"] = os.getenv("ERLANGSHEN_API_BASE_URL")
    if os.getenv("ERLANGSHEN_SERVER_URL"):
        updates["erlangshen_api_base_url"] = os.getenv("ERLANGSHEN_SERVER_URL")
    if os.getenv("ERLANGSHEN_AUTH_LOGIN_ENTRY"):
        updates["erlangshen_auth_login_entry"] = os.getenv("ERLANGSHEN_AUTH_LOGIN_ENTRY")

    # 飞书配置
    if os.getenv("FEISHU_APP_ID"):
        updates["feishu_app_id"] = os.getenv("FEISHU_APP_ID")
    if os.getenv("FEISHU_APP_SECRET"):
        updates["feishu_app_secret"] = os.getenv("FEISHU_APP_SECRET")

    # 数据库配置
    if os.getenv("DB_HOST"):
        updates["db_host"] = os.getenv("DB_HOST")
    if os.getenv("DB_PASSWORD"):
        updates["db_password"] = os.getenv("DB_PASSWORD")

    # 代理配置
    if os.getenv("HTTP_PROXY"):
        updates["http_proxy"] = os.getenv("HTTP_PROXY")
        updates["proxy_enabled"] = True
    if os.getenv("HTTPS_PROXY"):
        updates["https_proxy"] = os.getenv("HTTPS_PROXY")

    return updates


# ==================== 全局配置实例 ====================

_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        # 先从环境变量加载
        env_updates = load_config_from_env()
        base_config = load_config()
        env_updates = _remove_api_key_env_overrides_when_local_key_exists(base_config, env_updates)

        if env_updates:
            _config = merge_config(base_config, env_updates)
        else:
            _config = base_config

    return _config


def _remove_api_key_env_overrides_when_local_key_exists(
    base_config: Config,
    env_updates: Dict[str, Any],
) -> Dict[str, Any]:
    """Keep API key usage consistent with keys saved by `/model key`.

    Provider/model/base-url environment variables may still override config.
    API keys saved in settings.json win over same-field environment variables so
    the key that passed local validation is also the key used for `/advice`.
    """
    if not env_updates:
        return env_updates
    updates = env_updates.copy()
    for field in API_KEY_CONFIG_FIELDS:
        if getattr(base_config, field, None):
            updates.pop(field, None)
    return updates


def update_config(**kwargs) -> Config:
    """更新配置"""
    global _config
    config = get_config()

    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    save_config(config)
    return config


def reset_config() -> None:
    """重置配置"""
    global _config
    _config = None


# ==================== 配置验证 ====================

def validate_config(config: Config) -> List[str]:
    """
    验证配置

    Args:
        config: 配置对象

    Returns:
        List[str]: 警告列表
    """
    warnings = []

    # 检查 API Keys
    if not config.llm_api_key and not config.deepseek_api_key:
        warnings.append("未配置 LLM API Key，请设置 openai_api_key 或 deepseek_api_key")

    if not config.serpapi_key:
        warnings.append("未配置 SerpAPI Key，部分搜索功能可能受限 (仍可使用 DuckDuckGo)")

    if not config.fred_api_key:
        warnings.append("未配置 FRED API Key，宏观数据功能可能受限")

    # 检查代理
    if config.proxy_enabled and not (config.http_proxy or config.https_proxy):
        warnings.append("启用了代理但未配置代理地址")

    # 检查缓存
    if config.cache_ttl < 60:
        warnings.append("缓存 TTL 太短 (<60秒)，可能导致频繁请求")

    return warnings


# ==================== 常用配置模板 ====================

CONFIG_TEMPLATES = {
    "development": {
        "log_level": "DEBUG",
        "cache_ttl": 60,
    },
    "production": {
        "log_level": "INFO",
        "cache_ttl": 300,
        "cache_max_size": 5000,
    },
    "testing": {
        "log_level": "WARNING",
        "cache_enabled": False,
    },
}


def apply_template(name: str) -> Config:
    """
    应用配置模板

    Args:
        name: 模板名称 (development, production, testing)

    Returns:
        Config: 应用模板后的配置
    """
    if name not in CONFIG_TEMPLATES:
        raise ValueError(f"Unknown template: {name}")

    config = get_config()
    merged = merge_config(config, CONFIG_TEMPLATES[name])
    save_config(merged)
    global _config
    _config = merged
    return merged
