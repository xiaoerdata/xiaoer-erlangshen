"""
Investment Universe - 全资产多策略能力图谱
定义和管理所有支持的资产类别和策略类型
"""
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass


# ============================================================
# 资产类别定义
# ============================================================

class AssetClass(str, Enum):
    """资产类别枚举"""
    # 权益类
    A_STOCK = "a_stock"           # A股
    H_STOCK = "h_stock"           # 港股
    US_STOCK = "us_stock"          # 美股
    EUROPE_STOCK = "europe_stock"  # 欧股
    JAPAN_STOCK = "japan_stock"    # 日股
    
    # 债券类
    GOV_BOND = "gov_bond"         # 国债
    CORPORATE_BOND = "corporate_bond"  # 信用债
    convertible_bond = "convertible_bond"  # 可转债
    
    # 商品类
    GOLD = "gold"                 # 黄金
    SILVER = "silver"             # 白银
    CRUDE_OIL = "crude_oil"      # 原油
    NATURAL_GAS = "natural_gas"   # 天然气
    COPPER = "copper"            # 铜
    AGRICULTURAL = "agricultural"  # 农产品
    
    # 外汇类
    USD = "usd"                   # 美元
    EUR = "eur"                   # 欧元
    JPY = "jpy"                   # 日元
    GBP = "gbp"                   # 英镑
    CNY = "cny"                   # 人民币
    
    # 数字资产
    BTC = "btc"                   # 比特币
    ETH = "eth"                   # 以太坊
    CRYPTO = "crypto"             # 加密货币
    
    # 基金类
    PUBLIC_FUND = "public_fund"   # 公募基金
    PRIVATE_FUND = "private_fund" # 私募基金
    ETF = "etf"                   # ETF
    INDEX_FUND = "index_fund"     # 指数基金
    
    # 期货类
    STOCK_FUTURES = "stock_futures"     # 股指期货
    COMMODITY_FUTURES = "commodity_futures"  # 商品期货
    BOND_FUTURES = "bond_futures"       # 国债期货


@dataclass
class AssetInfo:
    """资产信息"""
    code: AssetClass
    name_cn: str
    name_en: str
    category: str  # 权益/债券/商品/外汇/数字/基金/期货
    data_source: str  # 数据来源
    keywords: List[str]  # 识别关键词


# 资产类别映射
ASSET_REGISTRY: Dict[AssetClass, AssetInfo] = {
    AssetClass.A_STOCK: AssetInfo(
        code=AssetClass.A_STOCK,
        name_cn="A股（沪深）",
        name_en="China A-Shares",
        category="权益",
        data_source="remote_db",
        keywords=["a股", "沪深", "上证", "深证", "沪市", "深市", "主板", "创业板", "科创板"],
    ),
    AssetClass.H_STOCK: AssetInfo(
        code=AssetClass.H_STOCK,
        name_cn="港股",
        name_en="Hong Kong Stocks",
        category="权益",
        data_source="yahoo_finance",
        keywords=["港股", "恒生", "hk", "h股", "香港上市"],
    ),
    AssetClass.US_STOCK: AssetInfo(
        code=AssetClass.US_STOCK,
        name_cn="美股",
        name_en="US Stocks",
        category="权益",
        data_source="yahoo_finance",
        keywords=["美股", "纳斯达克", "纽交所", "标普", "道琼斯", "nyse", "nasdaq", "sp500"],
    ),
    AssetClass.GOLD: AssetInfo(
        code=AssetClass.GOLD,
        name_cn="黄金",
        name_en="Gold",
        category="商品",
        data_source="yahoo_finance",
        keywords=["黄金", "gold", "xau", "金价", "贵金属"],
    ),
    AssetClass.CRUDE_OIL: AssetInfo(
        code=AssetClass.CRUDE_OIL,
        name_cn="原油",
        name_en="Crude Oil",
        category="商品",
        data_source="yahoo_finance",
        keywords=["原油", "石油", "oil", "wti", "brent", "布伦特"],
    ),
    AssetClass.GOV_BOND: AssetInfo(
        code=AssetClass.GOV_BOND,
        name_cn="国债",
        name_en="Government Bond",
        category="债券",
        data_source="macro_tools",
        keywords=["国债", "债券", "国开行", "国债期货", "treasury", "bond"],
    ),
    AssetClass.PUBLIC_FUND: AssetInfo(
        code=AssetClass.PUBLIC_FUND,
        name_cn="公募基金",
        name_en="Public Fund",
        category="基金",
        data_source="remote_db",
        keywords=["公募", "基金", "净值", "基金经理", "认购", "申购"],
    ),
    AssetClass.PRIVATE_FUND: AssetInfo(
        code=AssetClass.PRIVATE_FUND,
        name_cn="私募基金",
        name_en="Private Fund",
        category="基金",
        data_source="remote_db",
        keywords=["私募", "备案", "管理人", "托管", "阳光私募"],
    ),
    AssetClass.ETF: AssetInfo(
        code=AssetClass.ETF,
        name_cn="ETF",
        name_en="ETF",
        category="基金",
        data_source="remote_db",
        keywords=["etf", "交易型开放式指数基金", "指数etf", "行业etf"],
    ),
    AssetClass.BTC: AssetInfo(
        code=AssetClass.BTC,
        name_cn="比特币",
        name_en="Bitcoin",
        category="数字",
        data_source="coingecko",
        keywords=["比特币", "btc", "bitcoin", "数字货币", "加密货币"],
    ),
    AssetClass.ETH: AssetInfo(
        code=AssetClass.ETH,
        name_cn="以太坊",
        name_en="Ethereum",
        category="数字",
        data_source="coingecko",
        keywords=["以太坊", "eth", "ethereum"],
    ),
    AssetClass.STOCK_FUTURES: AssetInfo(
        code=AssetClass.STOCK_FUTURES,
        name_cn="股指期货",
        name_en="Stock Index Futures",
        category="期货",
        data_source="yahoo_finance",
        keywords=["股指期货", "if", "ih", "ic", "沪深300期货", "中证500期货"],
    ),
}


# ============================================================
# 策略类型定义
# ============================================================

class StrategyType(str, Enum):
    """策略类型枚举"""
    MACRO_STRATEGY = "macro_strategy"          # 宏观策略
    CTA_QUANT = "cta_quant"                   # CTA量化
    EQUITY_LONG_SHORT = "equity_long_short"    # 股票多空
    SUBJECTIVE_EQUITY = "subjective_equity"    # 主观股票
    PRIVATE_FOF = "private_fof"               # 私募FOF
    PUBLIC_FOF = "public_fof"                 # 公募FOF
    RISK_PARITY = "risk_parity"               # 风险平价
    MOMENTUM = "momentum"                     # 趋势动量
    REVERSAL = "reversal"                     # 均值回归
    arbitrage = "arbitrage"                   # 套利
    OPTIONS_HEDGE = "options_hedge"           # 期权对冲
    FIXED_INCOME = "fixed_income"             # 固收


@dataclass
class StrategyInfo:
    """策略信息"""
    code: StrategyType
    name_cn: str
    name_en: str
    category: str  # 权益/债券/宏观/量化/组合
    team_agent: str  # 负责的Agent
    keywords: List[str]


# 策略类型映射
STRATEGY_REGISTRY: Dict[StrategyType, StrategyInfo] = {
    StrategyType.MACRO_STRATEGY: StrategyInfo(
        code=StrategyType.MACRO_STRATEGY,
        name_cn="宏观策略",
        name_en="Macro Strategy",
        category="宏观",
        team_agent="agent-05",
        keywords=["宏观", "大类资产配置", "经济周期", "货币政策", "财政政策", "利率", "通胀"],
    ),
    StrategyType.CTA_QUANT: StrategyInfo(
        code=StrategyType.CTA_QUANT,
        name_cn="CTA量化",
        name_en="CTA Quant",
        category="量化",
        team_agent="agent-04",
        keywords=["cta", "量化", "趋势跟踪", "商品期货", "动量", "趋势策略", "期货策略"],
    ),
    StrategyType.SUBJECTIVE_EQUITY: StrategyInfo(
        code=StrategyType.SUBJECTIVE_EQUITY,
        name_cn="主观股票",
        name_en="Subjective Equity",
        category="权益",
        team_agent="agent-09",
        keywords=["主观", "股票", "基本面", "价值投资", "成长投资", "个股研究"],
    ),
    StrategyType.PRIVATE_FOF: StrategyInfo(
        code=StrategyType.PRIVATE_FOF,
        name_cn="私募FOF",
        name_en="Private Fund of Funds",
        category="组合",
        team_agent="agent-01",
        keywords=["私募", "fof", "基金筛选", "尽调", "私募基金配置", "组合配置"],
    ),
    StrategyType.PUBLIC_FOF: StrategyInfo(
        code=StrategyType.PUBLIC_FOF,
        name_cn="公募FOF",
        name_en="Public Fund of Funds",
        category="组合",
        team_agent="agent-02",
        keywords=["公募", "fof", "基金配置", "养老基金", "稳健配置"],
    ),
    StrategyType.RISK_PARITY: StrategyInfo(
        code=StrategyType.RISK_PARITY,
        name_cn="风险平价",
        name_en="Risk Parity",
        category="组合",
        team_agent="agent-05",
        keywords=["风险平价", "风险预算", "波动率", "夏普比率", "资产配置"],
    ),
    StrategyType.MOMENTUM: StrategyInfo(
        code=StrategyType.MOMENTUM,
        name_cn="趋势动量",
        name_en="Momentum",
        category="量化",
        team_agent="agent-04",
        keywords=["动量", "趋势", "趋势跟踪", " momentum", "技术分析"],
    ),
    StrategyType.FIXED_INCOME: StrategyInfo(
        code=StrategyType.FIXED_INCOME,
        name_cn="固定收益",
        name_en="Fixed Income",
        category="债券",
        team_agent="agent-05",
        keywords=["固收", "债券", "信用债", "利率债", "中高收益", "债券基金"],
    ),
}


# ============================================================
# 能力图谱查询
# ============================================================

class InvestmentUniverse:
    """
    投资宇宙 - 全资产多策略能力图谱
    
    提供：
    - 资产类别识别
    - 策略类型识别
    - 能力状态查询
    - 数据源路由
    """
    
    def __init__(self):
        self.assets = ASSET_REGISTRY
        self.strategies = STRATEGY_REGISTRY
    
    def identify_assets(self, query: str) -> List[AssetClass]:
        """
        从查询中识别涉及的资产类别
        
        Args:
            query: 用户查询
        
        Returns:
            List[AssetClass] 匹配的资产类别列表
        """
        query_lower = query.lower()
        matched = []
        
        for asset_class, info in self.assets.items():
            for keyword in info.keywords:
                if keyword.lower() in query_lower:
                    if asset_class not in matched:
                        matched.append(asset_class)
                    break
        
        return matched
    
    def identify_strategies(self, query: str) -> List[StrategyType]:
        """
        从查询中识别涉及的策略类型
        
        Args:
            query: 用户查询
        
        Returns:
            List[StrategyType] 匹配的策略类型列表
        """
        query_lower = query.lower()
        matched = []
        
        for strategy_type, info in self.strategies.items():
            for keyword in info.keywords:
                if keyword.lower() in query_lower:
                    if strategy_type not in matched:
                        matched.append(strategy_type)
                    break
        
        return matched
    
    def get_asset_info(self, asset: AssetClass) -> Optional[AssetInfo]:
        """获取资产信息"""
        return self.assets.get(asset)
    
    def get_strategy_info(self, strategy: StrategyType) -> Optional[StrategyInfo]:
        """获取策略信息"""
        return self.strategies.get(strategy)
    
    def get_data_source(self, asset: AssetClass) -> str:
        """获取资产对应的数据源"""
        info = self.assets.get(asset)
        return info.data_source if info else "unknown"
    
    def get_team_agent(self, strategy: StrategyType) -> str:
        """获取策略对应的团队Agent"""
        info = self.strategies.get(strategy)
        return info.team_agent if info else "unknown"
    
    def get_capability_state(self) -> dict:
        """
        获取当前能力状态
        
        Returns:
            dict 包含已实现的资产类别和策略类型
        """
        return {
            "assets": {
                "total": len(self.assets),
                "implemented": [
                    {
                        "code": a.value,
                        "name": info.name_cn,
                        "data_source": info.data_source,
                    }
                    for a, info in self.assets.items()
                ],
            },
            "strategies": {
                "total": len(self.strategies),
                "implemented": [
                    {
                        "code": s.value,
                        "name": info.name_cn,
                        "team_agent": info.team_agent,
                    }
                    for s, info in self.strategies.items()
                ],
            },
        }
    
    def list_all_assets(self) -> List[Dict[str, str]]:
        """列出所有资产类别"""
        return [
            {
                "code": a.value,
                "name_cn": info.name_cn,
                "name_en": info.name_en,
                "category": info.category,
            }
            for a, info in self.assets.items()
        ]
    
    def list_all_strategies(self) -> List[Dict[str, str]]:
        """列出所有策略类型"""
        return [
            {
                "code": s.value,
                "name_cn": info.name_cn,
                "name_en": info.name_en,
                "category": info.category,
                "team_agent": info.team_agent,
            }
            for s, info in self.strategies.items()
        ]


# ============================================================
# 全局实例
# ============================================================

_universe: Optional[InvestmentUniverse] = None


def get_universe() -> InvestmentUniverse:
    """获取投资宇宙实例"""
    global _universe
    if _universe is None:
        _universe = InvestmentUniverse()
    return _universe
