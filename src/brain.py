"""
二郎神大脑 - LLM调用层
"""

import os
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

from src.config import get_config


class Brain:
    """
    二郎神大脑 - 统一的LLM调用接口
    支持 DeepSeek、OpenAI 等多种模型
    """
    
    def __init__(self):
        self.config = get_config()
        self.max_context = self.config.llm_max_context  # 1M tokens for deepseek-v4-pro
        self._client = None
        self.conversation_history: List[Dict[str, str]] = []
    
    @property
    def client(self):
        """懒加载 LLM 客户端"""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self):
        """创建 LLM 客户端"""
        provider = self.config.llm_provider.lower()
        
        if provider == "deepseek":
            try:
                from openai import OpenAI
                # 优先使用环境变量
                api_key = os.environ.get("DEEPSEEK_API_KEY") or self.config.deepseek_api_key
                return OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com"
                )
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        
        elif provider == "openai":
            try:
                from openai import OpenAI
                return OpenAI(
                    api_key=self.config.llm_api_key or os.environ.get("OPENAI_API_KEY"),
                    base_url=self.config.llm_base_url
                )
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")
    
    def _get_model(self) -> str:
        """获取模型名称"""
        if self.config.llm_provider.lower() == "deepseek":
            # 优先使用环境变量
            return os.environ.get("DEEPSEEK_MODEL") or self.config.deepseek_model
        return self.config.llm_model
    
    async def think(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        核心思考方法
        
        Args:
            prompt: 用户提示
            system: 系统提示 (可选)
            temperature: 温度参数 (可选)
            max_tokens: 最大 token 数 (可选)
            context: 对话上下文 (可选)
        
        Returns:
            LLM 生成的响应
        """
        messages = []
        
        # 系统提示
        if system:
            messages.append({"role": "system", "content": system})
        
        # 上下文
        if context:
            messages.extend(context)
        
        # 用户提示
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self._get_model(),
                messages=messages,
                temperature=temperature or self.config.llm_temperature,
                max_tokens=max_tokens or self.config.llm_max_tokens,
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            return f"思考过程出错: {str(e)}"
    
    async def analyze(
        self,
        query: str,
        framework: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        分析查询
        
        Args:
            query: 分析查询
            framework: 分析框架 (可选)
            data: 相关数据 (可选)
        
        Returns:
            分析结果
        """
        system_prompt = self._build_analysis_prompt(framework)
        
        user_prompt = query
        if data:
            user_prompt += f"\n\n相关数据:\n{json.dumps(data, ensure_ascii=False, indent=2)}"
        
        return await self.think(user_prompt, system=system_prompt)
    
    def _build_analysis_prompt(self, framework: Optional[str] = None) -> str:
        """构建分析提示"""
        base = """你是二郎神，一个全知全能的AI投资智能体。

## 你的背景
- 你是小二配置团队的AI投资智能体
- 你具备团队全貌认知，了解9个专业Agent的能力和成果
- 你可以调用真实数据库获取行情和宏观数据

## 团队能力
- Agent-01/02: 基金筛选配置（ETF轮动V7年化16.1%）
- Agent-03: 交易执行验证
- Agent-04: CTA量化策略
- Agent-05: 宏观策略（V19年化25.6%，净值5.23）
- Agent-07: 数据采集治理
- Agent-08: 客户服务
- Agent-09: 个股基本面研究

## 核心数据资源
- 宏观数据库: 48个指标，SHIBOR_3M/CPI/GDP/PMI等
- 远程行情: 股票/指数/期货实时数据
- MCP工具: 东方财富dc-66，飞书文档

## 分析原则
1. 基于真实数据进行分析
2. 客观中立，不带偏见
3. 风险与收益并重
4. 考虑多种情景和可能性
5. 可以调用团队各Agent的专业能力

输出格式:
- 核心观点 (1-3句话)
- 详细分析
- 风险提示
- 行动建议 (如适用)
"""
        
        if framework:
            base += f"\n\n分析框架: {framework}"
        
        return base
    
    def reset_history(self):
        """重置对话历史"""
        self.conversation_history = []
    
    def add_to_history(self, role: str, content: str):
        """添加到对话历史"""
        self.conversation_history.append({"role": role, "content": content})
    
    async def think_with_history(
        self,
        prompt: str,
        system: Optional[str] = None,
    ) -> str:
        """带历史的思考"""
        return await self.think(
            prompt,
            system=system,
            context=self.conversation_history
        )
