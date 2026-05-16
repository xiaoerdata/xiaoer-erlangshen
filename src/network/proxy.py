"""
网络代理配置管理
"""

import os
from typing import Optional, Dict, Literal
from pydantic import BaseModel
from dataclasses import dataclass


class ProxyConfig(BaseModel):
    """代理配置"""
    # 代理模式: auto=自动, vpn=强制VPN, direct=直连, china_only=仅中国
    mode: Literal["auto", "vpn", "direct", "china_only"] = "auto"
    
    # 代理服务器
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    socks_proxy: Optional[str] = None
    
    # 白名单/黑名单
    china_domains: list[str] = []  # 中国域名列表，走直连
    global_domains: list[str] = []  # 全球域名列表，走代理
    
    # VPN配置
    vpn_interface: str = "utun"  # macOS VPN接口
    vpn_bypass: list[str] = []   # VPN绕过列表


class ProxyManager:
    """代理管理器 - 根据URL自动选择代理配置"""
    
    # 中国域名列表（精确匹配或后缀匹配）
    CHINA_DOMAINS = {
        # 顶级后缀 - 中国区划
        ".cn",
        ".com.cn",
        ".net.cn",
        ".gov.cn",
        ".org.cn",
        ".edu.cn",
        # 中国金融数据
        "baidu.com",        # 百度
        "akshare.com",
        "eastmoney.com",
        "sina.com",
        "tencent.com",
        "wind.com",
        "tushare.pro",
        "tushare.io",
        "jqdata.com",
        "joinquant.com",
        "aliyun.com",        # 阿里云
        "alipay.com",        # 支付宝
        "taobao.com",        # 淘宝
        # 中国交易所API
        "api.binance.com",  # Binance
        "api.okx.com",     # OKX
        # Mixin生态
        "api.mixin-messenger.io",
    }
    
    # 国际域名后缀（这些后缀默认走代理）
    GLOBAL_TLDS = {".io", ".ai", ".tech", ".xyz", ".cc", ".tv"}
    
    # 已知国际域名（精确或后缀匹配）
    GLOBAL_DOMAINS = {
        # 国际金融数据
        "yahoo.com",
        "finance.yahoo.com",
        "fred.stlouisfed.org",
        "alphavantage.co",
        "twelvedata.com",
        "coinmarketcap.com",
        "coingecko.com",
        # 搜索引擎
        "duckduckgo.com",
        "duck.com",
        "google.com",
        # AI服务
        "openai.com",
        "anthropic.com",
        "minimax.io",
    }
    
    def __init__(self, config: Optional[ProxyConfig] = None):
        self.config = config or ProxyConfig()
        self._detect_environment()
    
    def _detect_environment(self):
        """检测环境变量中的代理设置"""
        # 读取环境变量代理
        if not self.config.http_proxy:
            self.config.http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if not self.config.https_proxy:
            self.config.https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if not self.config.socks_proxy:
            self.config.socks_proxy = os.environ.get("SOCKS_PROXY") or os.environ.get("socks_proxy")
    
    def get_proxy_for_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        根据URL自动选择代理配置
        
        Args:
            url: 目标URL
            
        Returns:
            代理字典 {"http": "...", "https": "..."} 或 None(直连)
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        
        # 提取根域名
        parts = domain.split(".")
        root_domain = ".".join(parts[-2:]) if len(parts) >= 2 else domain
        
        # 判断应该走什么路由
        routing = self._should_use_proxy(domain, root_domain)
        
        if routing == "direct":
            return None  # 直连，不走代理
        elif routing == "proxy":
            return self._get_proxy_dict()
        else:  # auto
            # 自动判断：中国域名直连，其他走代理
            if self._is_china_domain(domain, root_domain):
                return None
            else:
                return self._get_proxy_dict()
    
    def _should_use_proxy(self, domain: str, root: str) -> str:
        """判断是否使用代理"""
        mode = self.config.mode
        
        if mode == "direct":
            return "direct"
        elif mode == "vpn":
            return "proxy"
        elif mode == "china_only":
            return "direct"
        else:  # auto
            if self._is_china_domain(domain, root):
                return "direct"
            return "proxy"
    
    def _is_china_domain(self, domain: str, root: str) -> bool:
        """判断是否为中国域名"""
        # 检查内置中国域名列表
        for china in self.CHINA_DOMAINS:
            if china in domain or domain.endswith(china):
                return True
        
        # 检查已知国际域名 - 如果匹配则不走中国路由
        for global_d in self.GLOBAL_DOMAINS:
            if global_d in domain or domain.endswith(global_d):
                return False
        
        # 检查国际域名后缀
        for tld in self.GLOBAL_TLDS:
            if domain.endswith(tld):
                return False
        
        return False
    
    def _get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """获取代理字典"""
        proxies = {}
        if self.config.http_proxy:
            proxies["http"] = self.config.http_proxy
        if self.config.https_proxy:
            proxies["https"] = self.config.https_proxy
        if self.config.socks_proxy:
            proxies["socks5"] = self.config.socks_proxy
        return proxies if proxies else None
    
    def set_mode(self, mode: str):
        """设置代理模式"""
        if mode in ("auto", "vpn", "direct", "china_only"):
            self.config.mode = mode
            print(f"[ProxyManager] 代理模式切换为: {mode}")
        else:
            print(f"[ProxyManager] 未知模式: {mode}, 保持当前: {self.config.mode}")
    
    def get_session_config(self) -> Dict:
        """获取aiohttp session配置"""
        return {
            "trust_env": True,  # 信任环境变量
            "skip_auto_headers": ["User-Agent"],
        }
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            "mode": self.config.mode,
            "has_proxy": bool(self.config.http_proxy or self.config.https_proxy or self.config.socks_proxy),
            "http_proxy": self.config.http_proxy,
            "https_proxy": self.config.https_proxy,
            "socks_proxy": self.config.socks_proxy,
        }
