"""
MCP 工具 - 宏观数据
使用真实数据库数据
"""

import sys
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 导入投资系统数据库连接
sys.path.insert(0, '/Users/wanghui/.openclaw-agent-06/workspace/investment-strategy')
from backend.core.database import execute_local_query


class MacroMCP:
    """
    宏观数据 MCP

    提供宏观经济指标、利率、汇率等数据接口
    数据来源：本地数据库 (macro_monitor)
    """

    def __init__(self):
        self.name = "macro"

    async def get_macro_indicator(
        self,
        indicator_code: str,
        country: str = "CN"
    ) -> Dict[str, Any]:
        """
        获取宏观指标最新值

        Args:
            indicator_code: 指标代码，如 "GDP_YOY", "CPI", "PMI_MFG", "SHIBOR_3M"
            country: 国家代码 (CN, US, EU)

        Returns:
            宏观指标数据
        """
        try:
            sql = """
            SELECT indicator_code, indicator_name, data_value, period, period_type, publish_date
            FROM cn_macro_data
            WHERE indicator_code = %s
            ORDER BY period DESC
            LIMIT 1
            """
            rows = execute_local_query('macro', sql, (indicator_code,))
            if rows:
                r = rows[0]
                return {
                    "indicator_code": r['indicator_code'],
                    "name": r['indicator_name'],
                    "value": float(r['data_value']) if r['data_value'] else None,
                    "period": str(r['period']),
                    "period_type": r.get('period_type', ''),
                    "publish_date": str(r['publish_date']) if r.get('publish_date') else None,
                    "country": country,
                    "source": "macro_monitor_db"
                }
            return {"error": f"未找到指标 {indicator_code}", "indicator_code": indicator_code}
        except Exception as e:
            logger.error(f"获取宏观指标 {indicator_code} 失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "indicator_code": indicator_code}

    async def get_macro_history(
        self,
        indicator_code: str,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        获取宏观指标历史数据

        Args:
            indicator_code: 指标代码
            months: 历史月数

        Returns:
            历史数据列表
        """
        try:
            sql = """
            SELECT indicator_code, indicator_name, data_value, period, period_type
            FROM cn_macro_data
            WHERE indicator_code = %s
            ORDER BY period DESC
            LIMIT %s
            """
            rows = execute_local_query('macro', sql, (indicator_code, months))
            if rows:
                return [
                    {
                        "period": str(r['period']),
                        "value": float(r['data_value']) if r['data_value'] else None,
                        "name": r['indicator_name'],
                        "period_type": r.get('period_type', ''),
                    }
                    for r in rows
                ]
            return [{"error": f"未找到指标 {indicator_code} 的历史数据"}]
        except Exception as e:
            logger.error(f"获取宏观指标 {indicator_code} 历史失败: {e}")
            return [{"error": f"数据库查询失败: {str(e)}"}]

    async def list_indicators(self, category: str = None) -> List[Dict[str, Any]]:
        """
        列出可用指标

        Args:
            category: 指标类别 (可选)，如 "景气指标", "经济增长", "外贸", "金融"

        Returns:
            指标列表
        """
        try:
            if category:
                sql = "SELECT indicator_code, indicator_name, category, unit, frequency, source, description FROM indicator_metadata WHERE category = %s"
                rows = execute_local_query('macro', sql, (category,))
            else:
                sql = "SELECT indicator_code, indicator_name, category, unit, frequency, source, description FROM indicator_metadata"
                rows = execute_local_query('macro', sql, ())
            return rows if rows else []
        except Exception as e:
            logger.error(f"列出指标失败: {e}")
            return []

    async def get_interest_rates(
        self,
        rate_type: str = "LPR",
        country: str = "CN"
    ) -> Dict[str, Any]:
        """
        获取利率数据

        Args:
            rate_type: 利率类型 (LPR, MLF, SLF, SHIBOR_3M, SHIBOR_1Y)
            country: 国家代码

        Returns:
            利率数据
        """
        # 利率指标映射
        rate_map = {
            "LPR": "LPR",
            "MLF": "MLF",
            "SLF": "SLF",
            "SHIBOR_3M": "SHIBOR_3M",
            "SHIBOR_1Y": "SHIBOR_1Y",
        }
        indicator_code = rate_map.get(rate_type, rate_type)

        try:
            sql = """
            SELECT indicator_code, indicator_name, data_value, period, publish_date
            FROM cn_macro_data
            WHERE indicator_code = %s
            ORDER BY period DESC
            LIMIT 1
            """
            rows = execute_local_query('macro', sql, (indicator_code,))
            if rows:
                r = rows[0]
                return {
                    "rate_type": rate_type,
                    "name": r['indicator_name'],
                    "country": country,
                    "value": float(r['data_value']) if r['data_value'] else None,
                    "period": str(r['period']),
                    "publish_date": str(r['publish_date']) if r.get('publish_date') else None,
                    "source": "macro_monitor_db"
                }
            return {"error": f"未找到利率数据 {rate_type}", "rate_type": rate_type}
        except Exception as e:
            logger.error(f"获取利率 {rate_type} 失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "rate_type": rate_type}

    async def get_currency_rates(
        self,
        base: str = "USD",
        target: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取汇率数据

        Args:
            base: 基准货币代码
            target: 目标货币代码 (可选，None则返回所有)

        Returns:
            汇率数据
        """
        currency_names = {
            "USD": "美元",
            "CNY": "人民币",
            "EUR": "欧元",
            "JPY": "日元",
            "GBP": "英镑",
            "HKD": "港币",
            "AUD": "澳元",
            "CHF": "瑞士法郎",
        }

        if target:
            try:
                pair = f"{base}/{target}"
                sql = """
                SELECT currency_pair, rate, period
                FROM cn_currency_rates
                WHERE currency_pair = %s
                ORDER BY period DESC
                LIMIT 1
                """
                rows = execute_local_query('macro', sql, (pair,))
                if rows:
                    r = rows[0]
                    return {
                        "base": base,
                        "target": target,
                        "base_name": currency_names.get(base, base),
                        "target_name": currency_names.get(target, target),
                        "rate": float(r['rate']) if r['rate'] else None,
                        "period": str(r['period']),
                        "source": "macro_monitor_db"
                    }
                return {"error": f"未找到汇率 {pair}", "base": base, "target": target}
            except Exception as e:
                logger.error(f"获取汇率 {base}/{target} 失败: {e}")
                return {"error": f"数据库查询失败: {str(e)}"}
        else:
            # 返回主要货币对人民币汇率
            targets = ["CNY", "EUR", "JPY", "GBP", "HKD", "AUD"]
            rates = {}
            for t in targets:
                rates[t] = {"name": currency_names.get(t, t), "rate": None}
            return {
                "base": base,
                "base_name": currency_names.get(base, base),
                "rates": rates,
                "date": datetime.now().isoformat(),
                "source": "macro_monitor_db"
            }

    async def get_economic_calendar(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        country: str = "CN"
    ) -> List[Dict[str, Any]]:
        """
        获取经济日历

        Args:
            start_date: 开始日期
            end_date: 结束日期
            country: 国家代码

        Returns:
            经济事件列表
        """
        try:
            # 尝试从 global_macro_data 获取经济日历数据
            if start_date and end_date:
                sql = """
                SELECT indicator_code, indicator_name, data_value, period, publish_date
                FROM global_macro_data
                WHERE period BETWEEN %s AND %s
                ORDER BY period DESC
                LIMIT 50
                """
                rows = execute_local_query('macro', sql, (start_date, end_date))
            else:
                sql = """
                SELECT indicator_code, indicator_name, data_value, period, publish_date
                FROM global_macro_data
                ORDER BY period DESC
                LIMIT 20
                """
                rows = execute_local_query('macro', sql, ())
            if rows:
                return [
                    {
                        "period": str(r['period']),
                        "event": r['indicator_name'],
                        "value": float(r['data_value']) if r['data_value'] else None,
                        "publish_date": str(r['publish_date']) if r.get('publish_date') else None,
                        "country": country,
                    }
                    for r in rows
                ]
            return []
        except Exception as e:
            logger.error(f"获取经济日历失败: {e}")
            return []

    async def get_bond_yield(self, bond_type: str = "10Y") -> Dict[str, Any]:
        """
        获取债券收益率

        Args:
            bond_type: 债券期限 (2Y, 5Y, 10Y, 30Y)

        Returns:
            债券收益率数据
        """
        bond_info = {
            "2Y": {"name": "2年期国债收益率", "indicator": "国债收益率2Y"},
            "5Y": {"name": "5年期国债收益率", "indicator": "国债收益率5Y"},
            "10Y": {"name": "10年期国债收益率", "indicator": "国债收益率10Y"},
            "30Y": {"name": "30年期国债收益率", "indicator": "国债收益率30Y"},
        }

        info = bond_info.get(bond_type, {"name": bond_type, "indicator": bond_type})

        try:
            sql = """
            SELECT indicator_code, indicator_name, data_value, period, publish_date
            FROM cn_macro_data
            WHERE indicator_code = %s
            ORDER BY period DESC
            LIMIT 1
            """
            rows = execute_local_query('macro', sql, (info['indicator'],))
            if rows:
                r = rows[0]
                return {
                    "bond_type": bond_type,
                    "name": info['name'],
                    "yield": float(r['data_value']) if r['data_value'] else None,
                    "period": str(r['period']),
                    "publish_date": str(r['publish_date']) if r.get('publish_date') else None,
                    "source": "macro_monitor_db"
                }
            return {"error": f"未找到债券收益率 {bond_type}", "bond_type": bond_type}
        except Exception as e:
            logger.error(f"获取债券收益率 {bond_type} 失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "bond_type": bond_type}

    async def get_cn_credit_data(
        self,
        data_type: str = "社融"
    ) -> Dict[str, Any]:
        """
        获取中国信用数据

        Args:
            data_type: 数据类型 (社融, M2, 人民币贷款)

        Returns:
            信用数据
        """
        indicator_map = {
            "社融": "社会融资规模",
            "M2": "M2",
            "人民币贷款": "人民币贷款",
        }

        indicator_name = indicator_map.get(data_type, data_type)

        try:
            sql = """
            SELECT indicator_code, indicator_name, data_value, period, publish_date
            FROM cn_macro_data
            WHERE indicator_name = %s
            ORDER BY period DESC
            LIMIT 1
            """
            rows = execute_local_query('macro', sql, (indicator_name,))
            if rows:
                r = rows[0]
                return {
                    "type": data_type,
                    "name": r['indicator_name'],
                    "value": float(r['data_value']) if r['data_value'] else None,
                    "period": str(r['period']),
                    "publish_date": str(r['publish_date']) if r.get('publish_date') else None,
                    "source": "macro_monitor_db"
                }
            return {"error": f"未找到信用数据 {data_type}", "data_type": data_type}
        except Exception as e:
            logger.error(f"获取信用数据 {data_type} 失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "data_type": data_type}

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return [
            {
                "name": "get_macro_indicator",
                "description": "获取宏观指标数据",
                "parameters": {
                    "indicator_code": "指标代码 (GDP_YOY, CPI, PMI_MFG, SHIBOR_3M等)",
                    "country": "国家代码 (CN, US, EU)"
                }
            },
            {
                "name": "get_macro_history",
                "description": "获取宏观指标历史数据",
                "parameters": {
                    "indicator_code": "指标代码",
                    "months": "历史月数 (默认12)"
                }
            },
            {
                "name": "list_indicators",
                "description": "列出可用指标",
                "parameters": {
                    "category": "指标类别 (可选)"
                }
            },
            {
                "name": "get_interest_rates",
                "description": "获取利率数据",
                "parameters": {
                    "rate_type": "利率类型 (LPR, MLF, SHIBOR_3M等)",
                    "country": "国家代码"
                }
            },
            {
                "name": "get_currency_rates",
                "description": "获取汇率数据",
                "parameters": {
                    "base": "基准货币",
                    "target": "目标货币"
                }
            },
            {
                "name": "get_economic_calendar",
                "description": "获取经济日历",
                "parameters": {
                    "start_date": "开始日期",
                    "end_date": "结束日期",
                    "country": "国家代码"
                }
            },
            {
                "name": "get_bond_yield",
                "description": "获取债券收益率",
                "parameters": {
                    "bond_type": "债券期限 (2Y, 5Y, 10Y, 30Y)"
                }
            },
            {
                "name": "get_cn_credit_data",
                "description": "获取中国信用数据",
                "parameters": {
                    "data_type": "数据类型 (社融, M2, 人民币贷款)"
                }
            },
        ]
