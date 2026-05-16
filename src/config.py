"""
二郎神配置管理
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class Config(BaseModel):
    """二郎神配置"""

    # ==================== LLM 配置 ====================
    llm_provider: str = "openai"
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # ==================== DeepSeek 专用配置 ====================
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"

    # ==================== MCP 配置 ====================
    mcp_enabled: bool = True
    mcp_timeout: int = 30

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
    knowledge_dir: str = "~/.openclaw-agent-06/workspace/erlangshen/knowledge"

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
    return Path("~/.openclaw-agent-06/workspace/erlangshen/.claude/settings.json").expanduser()


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

    # API Keys
    if os.getenv("OPENAI_API_KEY"):
        updates["llm_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("DEEPSEEK_API_KEY"):
        updates["deepseek_api_key"] = os.getenv("DEEPSEEK_API_KEY")
    if os.getenv("SERPAPI_KEY"):
        updates["serpapi_key"] = os.getenv("SERPAPI_KEY")
    if os.getenv("ALPHA_VANTAGE_KEY"):
        updates["alpha_vantage_key"] = os.getenv("ALPHA_VANTAGE_KEY")
    if os.getenv("FRED_API_KEY"):
        updates["fred_api_key"] = os.getenv("FRED_API_KEY")
    if os.getenv("COINMARKETCAP_KEY"):
        updates["coinmarketcap_key"] = os.getenv("COINMARKETCAP_KEY")

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

        if env_updates:
            _config = merge_config(base_config, env_updates)
        else:
            _config = base_config

    return _config


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
