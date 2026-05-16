"""
Brain - LLM大脑接口
任务感知型知识路由：选择性加载对应知识/能力
"""
import os
import json
import httpx
from pathlib import Path
from typing import Optional, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field
from loguru import logger


# ============================================================
# 任务类型定义
# ============================================================
class TaskType(str, Enum):
    """任务类型枚举"""
    # 轻量级任务 - 不需要深度分析框架
    QUERY_PRICE = "query_price"        # 行情查询
    QUERY_MACRO = "query_macro"        # 宏观数据查询
    QUICK_FACT = "quick_fact"          # 快速事实查询
    GENERAL_CHAT = "general_chat"      # 日常对话
    
    # 中等任务 - 需要基础分析能力
    STOCK_ANALYSIS = "stock_analysis"  # 个股分析
    FUND_ANALYSIS = "fund_analysis"    # 基金分析
    RISK_ASSESSMENT = "risk_assessment"  # 风险评估
    
    # 深度任务 - 需要完整分析框架
    DEEP_RESEARCH = "deep_research"    # 深度研究
    INDUSTRY_OUTLOOK = "industry_outlook"  # 产业格局分析（自上而下）
    MACRO_STRATEGY = "macro_strategy"  # 宏观策略分析
    PORTFOLIO_OPT = "portfolio_optimization"  # 组合优化
    
    # 综合任务 - 需要多维度分析
    COMPREHENSIVE = "comprehensive"    # 综合分析


# ============================================================
# 知识模块定义
# ============================================================
class KnowledgeModule:
    """知识模块定义"""
    def __init__(
        self,
        name: str,
        path: str,
        keywords: list[str],
        description: str = "",
    ):
        self.name = name
        self.path = path
        self.keywords = keywords
        self.description = description
        self._content: Optional[str] = None
    
    def load(self) -> str:
        """按需加载知识内容"""
        if self._content is None:
            try:
                p = Path(self.path)
                if p.exists():
                    self._content = p.read_text(encoding="utf-8")
                else:
                    self._content = ""
            except Exception as e:
                logger.warning(f"Failed to load knowledge {self.name}: {e}")
                self._content = ""
        return self._content
    
    def match_score(self, query: str) -> float:
        """计算query与本知识模块的匹配度"""
        query_lower = query.lower()
        score = 0.0
        for kw in self.keywords:
            if kw.lower() in query_lower:
                score += 1.0
        return score


# ============================================================
# 知识库注册表
# ============================================================
class KnowledgeRegistry:
    """知识库注册表 - 管理所有可用的知识模块"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.modules: dict[str, KnowledgeModule] = {}
        self._register_builtin_modules()
    
    def _register_builtin_modules(self):
        """注册内置知识模块"""
        
        # 第一性原理 - 精简核心版（轻量）
        fp_light_path = self.base_path / "knowledge" / "first_principles.md"
        self.register(KnowledgeModule(
            name="first_principles",
            path=str(fp_light_path),
            keywords=["第一性", "底层逻辑", "产业格局", "技术革命", "能源革命", 
                      "信息革命", "变革", "格局", "趋势判断", "未来预判",
                      "deep_research", "first_principle"],
            description="第一性原理认知框架（精简版）",
        ))
        
        # 第一性原理 - 深度版（按需加载）
        fp_deep_path = self.base_path / "knowledge" / "first_principles_deep.md"
        self.register(KnowledgeModule(
            name="first_principles_deep",
            path=str(fp_deep_path),
            keywords=["deep_research", "深度研究", "详细分析", "完整框架"],
            description="第一性原理详细框架（深度研究用）",
        ))
        
        # 宏观知识库
        macro_path = self.base_path / "knowledge" / "economic_indicators.md"
        self.register(KnowledgeModule(
            name="economic_indicators",
            path=str(macro_path),
            keywords=["gdp", "通胀", "cpi", "ppi", "利率", "货币政策", 
                     "财政政策", "宏观", "经济指标", "经济数据"],
            description="宏观经济指标知识库",
        ))
        
        # 市场基础知识
        market_path = self.base_path / "knowledge" / "market_basics.md"
        self.register(KnowledgeModule(
            name="market_basics",
            path=str(market_path),
            keywords=["市场", "股票", "债券", "基金", "etf", "期货",
                     "交易", "市值", "估值", "市盈率"],
            description="市场基础知识",
        ))
        
        # 风险知识
        risk_path = self.base_path / "knowledge" / "risk_management.md"
        self.register(KnowledgeModule(
            name="risk_management",
            path=str(risk_path),
            keywords=["风险", "回撤", "止损", "仓位", "杠杆", "风控",
                     "波动率", "夏普", "最大回撤"],
            description="风险管理知识",
        ))
        
        # 交易策略
        strategy_path = self.base_path / "knowledge" / "trading_strategies.md"
        self.register(KnowledgeModule(
            name="trading_strategies",
            path=str(strategy_path),
            keywords=["策略", "轮动", "趋势", "动量", "反转", "套利",
                     "cta", "量化", "因子", "阿尔法"],
            description="交易策略知识库",
        ))
        
        # 团队洞察
        insights_path = self.base_path / "knowledge" / "insights.md"
        self.register(KnowledgeModule(
            name="team_insights",
            path=str(insights_path),
            keywords=["团队", "agent", "协作", "配合", "二郎神",
                     "v19", "宏观策略", "etf轮动"],
            description="团队洞察和经验总结",
        ))
        
        # 团队上下文
        context_path = self.base_path / "knowledge" / "team_context.md"
        self.register(KnowledgeModule(
            name="team_context",
            path=str(context_path),
            keywords=["团队成员", "agent-01", "agent-02", "分工",
                     "私募", "公募", "cta", "数据", "营销"],
            description="团队上下文和Agent分工",
        ))
        
        # 全球市场
        global_path = self.base_path / "knowledge" / "global_markets.md"
        self.register(KnowledgeModule(
            name="global_markets",
            path=str(global_path),
            keywords=["美股", "港股", "欧股", "日经", "纳斯达克",
                     "标普", "道琼斯", "恒生", "外汇", "美元", "欧元"],
            description="全球市场知识",
        ))
        
        logger.info(f"KnowledgeRegistry initialized with {len(self.modules)} modules")
    
    def register(self, module: KnowledgeModule):
        """注册知识模块"""
        self.modules[module.name] = module
    
    def select_for_task(self, task_type: TaskType, query: str) -> list[KnowledgeModule]:
        """根据任务类型选择需要加载的知识模块"""
        selected = []
        query_lower = query.lower()
        
        # 根据任务类型决定必须加载的模块
        required_modules = {
            TaskType.DEEP_RESEARCH: ["first_principles", "team_insights"],
            TaskType.INDUSTRY_OUTLOOK: ["first_principles", "economic_indicators", "market_basics"],
            TaskType.MACRO_STRATEGY: ["first_principles", "economic_indicators", "risk_management", "trading_strategies"],
            TaskType.PORTFOLIO_OPT: ["risk_management", "trading_strategies", "market_basics"],
            TaskType.COMPREHENSIVE: ["first_principles", "economic_indicators", "market_basics", "team_insights"],
            TaskType.STOCK_ANALYSIS: ["market_basics", "risk_management", "global_markets"],
            TaskType.FUND_ANALYSIS: ["market_basics", "team_insights"],
            TaskType.RISK_ASSESSMENT: ["risk_management"],
            TaskType.QUERY_PRICE: [],
            TaskType.QUERY_MACRO: ["economic_indicators"],
            TaskType.QUICK_FACT: [],
            TaskType.GENERAL_CHAT: [],
        }
        
        # 添加任务类型要求的模块
        for module_name in required_modules.get(task_type, []):
            if module_name in self.modules:
                selected.append(self.modules[module_name])
        
        # 基于query关键词追加匹配度高的模块
        for name, module in self.modules.items():
            if module not in selected:
                if module.match_score(query_lower) > 0:
                    selected.append(module)
        
        return selected


# ============================================================
# 任务分类器
# ============================================================
class TaskClassifier:
    """任务分类器 - 判断用户查询属于哪种任务类型"""
    
    # 关键词到任务类型的映射
    KEYWORD_MAP = {
        TaskType.QUERY_PRICE: ["价格", "行情", "现在多少", "涨了多少", "报价", 
                               "看了一眼", "现在价格", "收盘价", "开盘价"],
        TaskType.QUERY_MACRO: ["数据", "指标", "是多少", "公布了", "统计局"],
        TaskType.QUICK_FACT: ["什么是", "什么叫", "定义", "解释一下"],
        TaskType.STOCK_ANALYSIS: ["股票", "个股", "茅台", "苹果", "估值", "基本面",
                                  "业绩", "利润", "营收", "值得买吗"],
        TaskType.FUND_ANALYSIS: ["基金", "私募", "公募", "etf", "净值", "基金经理"],
        TaskType.RISK_ASSESSMENT: ["风险", "回撤", "能承受", "亏损", "止损"],
        TaskType.DEEP_RESEARCH: ["深度", "研究", "分析报告", "怎么看", "底层逻辑",
                                 "第一性", "本质", "核心逻辑", "deepseek", "chatgpt", "突破",
                                 "意味着", "颠覆", "革命", "变革", "跃升"],
        TaskType.INDUSTRY_OUTLOOK: ["产业格局", "行业", "赛道", "竞争格局", "格局分析",
                                   "产业链", "上中下游", "技术路线", "市场规模"],
        TaskType.MACRO_STRATEGY: ["宏观", "经济周期", "货币政策", "财政政策", "大类资产",
                                  "配置", "利率走势", "通胀预期", "经济形势"],
        TaskType.PORTFOLIO_OPT: ["组合", "配置", "仓位", "分散", "优化", "权重"],
        TaskType.COMPREHENSIVE: ["综合", "全面", "整体", "分析一下当前"],
    }
    
    @classmethod
    def classify(cls, query: str) -> TaskType:
        """
        分类用户查询
        
        Args:
            query: 用户查询文本
            
        Returns:
            TaskType 任务类型
        """
        query_lower = query.lower()
        
        # 遍历所有任务类型，找关键词匹配
        best_match = TaskType.GENERAL_CHAT
        best_score = 0
        
        for task_type, keywords in cls.KEYWORD_MAP.items():
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            if score > best_score:
                best_score = score
                best_match = task_type
        
        # 如果没有任何关键词匹配，但query较长，认为是深度任务
        if best_score == 0 and len(query) > 50:
            best_match = TaskType.COMPREHENSIVE
        
        logger.info(f"TaskClassifier: '{query[:30]}...' -> {best_match.value}")
        return best_match


# ============================================================
# 基础系统提示
# ============================================================
BASE_SYSTEM_PROMPT = """你是二郎神 - 一位专业的AI投资智能体。

【核心定位】
- 全知全能，擅长投资分析、风险评估、资产配置
- 数据驱动，逻辑严谨
- 团队协作，整合私募FOF、公募FOF、CTA量化、宏观策略等多领域知识

【沟通风格】
- 专业但不生硬
- 直接但有深度
- 简洁但有洞见

【工作原则】
- 数据真实性优先，不用模拟数据
- 明确给出结论和置信度
- 指出风险和限制
"""


# ============================================================
# 任务专用提示词
# ============================================================
TASK_SYSTEM_PROMPTS = {
    TaskType.QUERY_PRICE: """你正在处理行情查询任务。
要求：简洁、直接给出数据，不需要多余分析。""",
    
    TaskType.QUERY_MACRO: """你正在处理宏观数据查询任务。
要求：准确提供数据指标，注明数据来源和更新时间。""",
    
    TaskType.QUICK_FACT: """你正在回答一个概念性问题。
要求：清晰解释概念，必要时举例说明。""",
    
    TaskType.GENERAL_CHAT: """你正在与用户进行日常对话。
要求：友好、专业、有帮助，不需要过度分析。""",
    
    TaskType.STOCK_ANALYSIS: """你正在分析个股。
分析维度：基本面（估值、业绩、成长性）、市场情绪、技术面、风险因素。
输出结构：结论 → 支撑逻辑 → 风险提示。""",
    
    TaskType.FUND_ANALYSIS: """你正在分析基金产品。
分析维度：历史业绩、风险调整收益、基金经理能力、策略有效性。
输出结构：评级 → 业绩归因 → 风险评估 → 适用场景。""",
    
    TaskType.RISK_ASSESSMENT: """你正在评估风险。
分析维度：市场风险、信用风险、流动性风险、尾部风险。
输出结构：风险点识别 → 程度评估 → 缓解措施。""",
    
    TaskType.DEEP_RESEARCH: """你正在进行深度研究。
这是最重要的分析任务，需要：
1. 第一性原理分析：判断这是信息革命还是能量革命的突破？
2. 多维度验证：技术面、基本面、资金面、情绪面
3. 历史比较：类似变革的发展规律
4. 明确结论和置信度

【第一性原理框架】
- 信息能力 = 计算力 × 传输效率 × 智能水平
- 能量能力 = 能量密度 × 转化效率 × 获取便利性
- 判断：这是单维度突破还是双维度突破？
- 判断：处于技术成熟度的哪个阶段？""",
    
    TaskType.INDUSTRY_OUTLOOK: """你正在进行产业格局分析（自上而下）。
分析框架：
1. 产业链全景：上中下游、竞争格局
2. 变革驱动：第一性原理分析（信息/能量维度）
3. 周期定位：导入期、成长期、成熟期、衰退期
4. 投资逻辑：谁能受益？如何排序？
5. 风险因素：技术路线风险、政策风险、竞争风险""",
    
    TaskType.MACRO_STRATEGY: """你正在进行宏观策略分析。
分析维度：
1. 经济周期：增长、通胀、货币政策
2. 资产配置：大宗商品、股票、债券、现金
3. 风险预判：尾部风险、切换风险
4. 策略建议：方向、幅度、时间窗口""",
    
    TaskType.PORTFOLIO_OPT: """你正在优化投资组合。
分析维度：
1. 风险收益比最优化
2. 相关性分散化
3. 流动性管理
4. 再平衡策略""",
    
    TaskType.COMPREHENSIVE: """你正在进行综合分析。
需要整合宏观、行业、公司多维度视角，给出全面、平衡的判断。""",
}


# ============================================================
# Brain 主类
# ============================================================
class AnalysisResult(BaseModel):
    """分析结果"""
    conclusion: str = Field(description="分析结论")
    confidence: float = Field(description="置信度 0-1")
    reasoning: str = Field(description="推理过程")
    evidence: list[str] = Field(default_factory=list, description="支撑证据")
    caveats: list[str] = Field(default_factory=list, description="风险提示")


class Reflection(BaseModel):
    """反思结果"""
    action: str = Field(description="执行的动作")
    result: Any = Field(description="执行结果")
    lessons: list[str] = Field(default_factory=list, description="经验教训")
    improvement: str = Field(description="改进建议")


class Brain:
    """LLM大脑接口 - 支持任务感知型知识路由"""

    # 模型配置
    MODELS = {
        "deepseek": {
            "model": "deepseek-v4-pro",
            "api_base": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
    }

    def __init__(
        self,
        provider: str = "deepseek",
        api_key: Optional[str] = None,
        base_path: Optional[str] = None,
    ):
        if provider not in self.MODELS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(self.MODELS.keys())}")

        cfg = self.MODELS[provider]
        self.model = cfg["model"]
        self.api_base = cfg["api_base"]
        self.api_key = api_key or os.getenv(cfg["api_key_env"])
        self.provider = provider
        
        # 初始化知识库注册表
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent
        self.knowledge_registry = KnowledgeRegistry(Path(base_path))
        
        # 任务分类器
        self.task_classifier = TaskClassifier()

        if not self.api_key:
            logger.warning(f"{cfg['api_key_env']} not set, Brain will use mock mode")

    def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        return httpx.AsyncClient(
            base_url=self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    
    def _build_system_prompt(
        self, 
        task_type: TaskType,
        query: str,
        load_first_principles: bool = False,
    ) -> str:
        """构建系统提示 - 根据任务类型选择性组合"""
        
        # 1. 基础提示
        parts = [BASE_SYSTEM_PROMPT]
        
        # 2. 任务专用提示
        if task_type in TASK_SYSTEM_PROMPTS:
            parts.append(TASK_SYSTEM_PROMPTS[task_type])
        
        # 3. 按需加载知识模块
        selected_modules = self.knowledge_registry.select_for_task(task_type, query)
        
        if selected_modules:
            parts.append("\n【相关知识】")
            for module in selected_modules:
                content = module.load()
                if content:
                    parts.append(f"\n--- {module.name} ---\n{content[:3000]}")  # 限制单模块长度
        
        return "\n\n".join(parts)

    async def think(
        self,
        prompt: str,
        context: Optional[dict] = None,
        system: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        auto_classify: bool = True,
    ) -> str:
        """
        深度思考推理 - 任务感知型
        
        Args:
            prompt: 用户提示
            context: 额外上下文
            system: 额外系统提示（会覆盖自动判断）
            task_type: 指定任务类型（可选，默认自动分类）
            auto_classify: 是否自动分类任务（默认True）
        
        Returns:
            LLM生成的响应文本
        """
        if not self.api_key:
            logger.info("Brain mock mode: returning simulated response")
            return f"[Mock] 基于提示「{prompt[:50]}...」的思考结果"
        
        # 自动分类任务类型
        if task_type is None and auto_classify:
            task_type = self.task_classifier.classify(prompt)
        
        # 构建系统提示
        if system:
            sys_prompt = system
        else:
            sys_prompt = self._build_system_prompt(
                task_type or TaskType.GENERAL_CHAT,
                prompt,
            )
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }
        if context:
            payload["max_tokens"] = context.get("max_tokens", 2000)

        try:
            client = self._get_client()
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Brain think failed: {e}")
            return f"[Error] 思考失败: {e}"

    async def think_with_framework(
        self,
        prompt: str,
        framework: Literal["first_principles", "macro", "quant", "risk"],
        context: Optional[dict] = None,
    ) -> str:
        """
        指定框架的思考 - 用于需要强制使用特定框架的场景
        
        Args:
            prompt: 用户提示
            framework: 框架类型
            context: 额外上下文
        """
        if framework == "first_principles":
            fp_content = self.knowledge_registry.modules.get("first_principles")
            fp_text = fp_content.load() if fp_content else ""
            system = f"""你正在使用【第一性原理】进行分析。

【第一性原理框架】
{fp_text}

分析要求：
1. 判断变革的信息维度：计算/传输/智能哪个突破？
2. 判断变革的能量维度：密度/效率/清洁哪个突破？
3. 是单维度还是双维度突破？
4. 处于技术成熟度的哪个阶段？
"""
        elif framework == "macro":
            system = """你正在使用【宏观策略框架】进行分析。
关注：经济周期、货币政策、财政政策、大类资产配置。"""
        elif framework == "quant":
            system = """你正在使用【量化分析框架】进行分析。
关注：因子有效性、统计显著性、回测结果、样本外验证。"""
        elif framework == "risk":
            system = """你正在使用【风险管理框架】进行分析。
关注：尾部风险、相关性风险、流动性风险、情景测试。"""
        else:
            system = None
        
        return await self.think(prompt, context=context, system=system, task_type=TaskType.DEEP_RESEARCH)

    async def analyze(
        self,
        query: str,
        data: Optional[dict] = None,
        framework: Optional[str] = None,
    ) -> AnalysisResult:
        """
        分析能力 - 对输入进行结构化分析
        
        Args:
            query: 分析问题
            data: 补充数据
            framework: 分析框架名称
            
        Returns:
            AnalysisResult 结构化分析结果
        """
        # 确定任务类型
        task_type = self.task_classifier.classify(query)
        
        system_prompt = """你是一位专业的投资分析师。你的分析必须：
1. 逻辑严谨，数据驱动
2. 给出明确的结论和置信度
3. 说明推理过程和支撑证据
4. 指出潜在风险和限制

请以JSON格式返回，包含字段：conclusion, confidence, reasoning, evidence, caveats"""

        user_prompt = f"分析问题：{query}\n"
        if data:
            user_prompt += f"相关数据：{json.dumps(data, ensure_ascii=False, indent=2)}\n"

        try:
            result_text = await self.think(
                user_prompt, 
                system=system_prompt, 
                task_type=task_type,
            )
            # 尝试解析JSON
            result_text = result_text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_data = json.loads(result_text.strip())
            return AnalysisResult(**result_data)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse analysis as JSON, using fallback: {result_text[:100]}")
            return AnalysisResult(
                conclusion=result_text[:500],
                confidence=0.5,
                reasoning="JSON解析失败，返回原始文本",
                evidence=[],
                caveats=["可能存在解析误差"],
            )

    async def reflect(self, action: str, result: Any) -> Reflection:
        """
        反思能力 - 对执行结果进行反思学习
        """
        prompt = f"反思以下投资决策：\n行动：{action}\n结果：{str(result)[:1000]}"
        system_prompt = "你是一位经验丰富的投资顾问，请从成功和失败中学习，给出经验教训和改进建议。"

        try:
            response = await self.think(prompt, system=system_prompt, task_type=TaskType.QUICK_FACT)
            return Reflection(action=action, result=result, lessons=[], improvement=response)
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return Reflection(action=action, result=result, lessons=[], improvement=str(e))
