"""
流量路由 - 根据规则路由请求
"""

import aiohttp
from typing import Optional, Dict, Any
import asyncio


class NetworkRouter:
    """网络路由器 - 自动选择最优路径发送请求"""
    
    def __init__(self, proxy_manager):
        """
        初始化路由器
        
        Args:
            proxy_manager: ProxyManager实例
        """
        self.proxy_manager = proxy_manager
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """获取配置好的aiohttp session"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                trust_env=True,  # 信任环境变量
            )
        return self._session
    
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        发送请求，自动选择路由
        
        Args:
            method: HTTP方法 (GET, POST, etc.)
            url: 目标URL
            **kwargs: 传递给aiohttp的其他参数
            
        Returns:
            aiohttp.ClientResponse
        """
        session = await self.get_session()
        
        # 获取该URL应该使用的代理
        proxy = self.proxy_manager.get_proxy_for_url(url)
        
        if proxy:
            # 设置代理
            http_proxy = proxy.get("http") or proxy.get("https")
            if http_proxy:
                kwargs["proxy"] = http_proxy
        
        async with session.request(method, url, **kwargs) as response:
            return response
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """GET请求"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """POST请求"""
        return await self.request("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """PUT请求"""
        return await self.request("PUT", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """DELETE请求"""
        return await self.request("DELETE", url, **kwargs)
    
    async def get_json(self, url: str, **kwargs) -> Any:
        """GET请求并返回JSON"""
        async with await self.get(url, **kwargs) as resp:
            return await resp.json()
    
    async def post_json(self, url: str, **kwargs) -> Any:
        """POST请求并返回JSON"""
        async with await self.post(url, **kwargs) as resp:
            return await resp.json()
    
    async def close(self):
        """关闭session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
