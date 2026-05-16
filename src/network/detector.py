"""
网络环境检测
检测当前是否使用VPN、直连等
"""

import asyncio
import socket
import os
from typing import Dict, Optional


class NetworkDetector:
    """网络环境检测器"""
    
    # 中国测试主机
    CHINA_TEST_HOSTS = [
        ("www.baidu.com", 80),
        ("www.aliyun.com", 80),
        ("api.binance.com", 443),  # Binance中国可直连
        ("api.okx.com", 443),      # OKX中国可直连
    ]
    
    # 国际测试主机
    GLOBAL_TEST_HOSTS = [
        ("www.google.com", 443),
        ("www.cloudflare.com", 443),
        ("api.coingecko.com", 443),
        ("api.openai.com", 443),
    ]
    
    async def detect_environment(self) -> Dict[str, bool]:
        """
        检测网络环境
        返回: {
            "china_reachable": True,  # 中国网络是否可达
            "global_reachable": True,  # 全球网络是否可达
            "vpn_active": False,      # VPN是否激活
            "proxy_active": False,    # 代理是否激活
        }
        """
        results = {
            "china_reachable": False,
            "global_reachable": False,
            "vpn_active": False,
            "proxy_active": False,
        }
        
        # 并发检测中国和国际网络
        china_task = self._test_hosts(self.CHINA_TEST_HOSTS)
        global_task = self._test_hosts(self.GLOBAL_TEST_HOSTS)
        
        china_results, global_results = await asyncio.gather(china_task, global_task)
        
        results["china_reachable"] = any(china_results)
        results["global_reachable"] = any(global_results)
        
        # 检测VPN
        results["vpn_active"] = await self._detect_vpn()
        
        # 检测代理环境变量
        results["proxy_active"] = self._detect_proxy_env()
        
        return results
    
    async def _test_hosts(self, hosts: list) -> list:
        """测试一组主机是否可达"""
        tasks = [self._test_host(host, port) for host, port in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if r is True]
    
    async def _test_host(self, host: str, port: int, timeout: float = 3.0) -> bool:
        """测试单个主机"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    
    async def _detect_vpn(self) -> bool:
        """检测VPN是否激活"""
        import subprocess
        try:
            # macOS检测VPN接口
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True, text=True, timeout=5
            )
            # 检查是否有VPN相关的网络服务
            return "VPN" in result.stdout or "utun" in result.stdout
        except Exception:
            return False
    
    def _detect_proxy_env(self) -> bool:
        """检测代理环境变量"""
        proxy_vars = [
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy",
            "SOCKS_PROXY", "socks_proxy"
        ]
        for var in proxy_vars:
            if os.environ.get(var):
                return True
        return False
    
    def get_recommended_mode(self) -> str:
        """获取推荐的代理模式"""
        env = asyncio.run(self.detect_environment())
        
        if env["vpn_active"] and env["global_reachable"]:
            return "vpn"
        elif env["china_reachable"] and not env["global_reachable"]:
            return "china_only"
        elif env["global_reachable"] and env["china_reachable"]:
            return "auto"
        else:
            return "direct"
    
    async def quick_test(self, host: str = "www.baidu.com", port: int = 80) -> bool:
        """快速网络测试"""
        return await self._test_host(host, port, timeout=2.0)
