"""
网络自适应模块
根据目标自动选择最优网络路径（直连/代理）
"""

from .proxy import ProxyManager, ProxyConfig
from .detector import NetworkDetector
from .router import NetworkRouter

__all__ = [
    "ProxyManager",
    "ProxyConfig", 
    "NetworkDetector",
    "NetworkRouter",
]
