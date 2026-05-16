"""
MCP 工具 - 基金数据
私募/公募基金数据接口
"""

import sys
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# 导入投资系统数据库连接
sys.path.insert(0, '/Users/wanghui/.openclaw-agent-06/workspace/investment-strategy')
from backend.core.database import execute_remote_query


class FundMCP:
    """
    基金数据 MCP

    提供私募基金、公募基金数据接口
    数据来源：远程数据库 (193.112.183.130:3306)
    """

    def __init__(self):
        self.name = "fund"

    # ==================== 私募基金接口 ====================

    async def get_private_fund_managers(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取私募基金管理人列表

        Args:
            limit: 返回数量上限，默认50

        Returns:
            管理人信息列表
        """
        try:
            sql = """
            SELECT * FROM 私募基金管理人信息表
            LIMIT %s
            """
            rows = execute_remote_query('product', sql, (limit,))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取私募基金管理人失败: {e}")
            return []

    async def get_private_fund_nav(
        self, fund_name: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取私募产品净值

        Args:
            fund_name: 产品名称（模糊匹配），可选
            limit: 返回数量上限，默认100

        Returns:
            净值数据列表
        """
        try:
            if fund_name:
                sql = """
                SELECT * FROM 私募产品净值表
                WHERE 产品名称 LIKE %s
                ORDER BY 净值日期 DESC
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (f'%{fund_name}%', limit))
            else:
                sql = """
                SELECT * FROM 私募产品净值表
                ORDER BY 净值日期 DESC
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (limit,))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取私募产品净值失败: {e}")
            return []

    async def get_private_fund_info(self, fund_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取私募基金备案信息

        Args:
            fund_name: 产品名称（模糊匹配），可选
            limit: 返回数量上限，默认50

        Returns:
            备案信息列表
        """
        try:
            if fund_name:
                sql = """
                SELECT * FROM 所有私募基金备案信息表
                WHERE 产品名称 LIKE %s
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (f'%{fund_name}%', limit))
            else:
                sql = """
                SELECT * FROM 所有私募基金备案信息表
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (limit,))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取私募基金备案信息失败: {e}")
            return []

    # ==================== 公募基金接口 ====================

    async def get_public_fund_info(
        self, fund_code: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取公募基金基本信息

        Args:
            fund_code: 基金代码，精确匹配；为空时返回列表
            limit: 返回数量上限，默认50

        Returns:
            基金基本信息列表
        """
        try:
            if fund_code:
                sql = """
                SELECT * FROM 公募基金基本信息表
                WHERE 基金代码 = %s
                """
                rows = execute_remote_query('product', sql, (fund_code,))
            else:
                sql = """
                SELECT * FROM 公募基金基本信息表
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (limit,))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取公募基金信息失败: {e}")
            return []

    async def get_public_fund_nav(
        self, fund_code: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取公募基金净值

        Args:
            fund_code: 基金代码（必填）
            limit: 返回数量上限，默认100

        Returns:
            净值数据列表
        """
        try:
            if not fund_code:
                return []
            sql = """
            SELECT * FROM 公募基金净值表
            WHERE 基金代码 = %s
            ORDER BY 净值日期 DESC
            LIMIT %s
            """
            rows = execute_remote_query('product', sql, (fund_code, limit))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取公募基金净值失败: {e}")
            return []

    async def get_public_fund_holdings(
        self, fund_code: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取公募基金个股持仓汇总

        Args:
            fund_code: 基金代码
            limit: 返回数量上限，默认50

        Returns:
            持仓汇总列表
        """
        try:
            if not fund_code:
                return []
            sql = """
            SELECT * FROM 公募基金个股持仓汇总表
            WHERE 基金代码 = %s
            LIMIT %s
            """
            rows = execute_remote_query('product', sql, (fund_code, limit))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取公募基金持仓失败: {e}")
            return []

    async def get_etf_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取ETF列表

        Args:
            limit: 返回数量上限，默认100

        Returns:
            ETF基金列表
        """
        try:
            sql = """
            SELECT * FROM ETF基金净值表
            LIMIT %s
            """
            rows = execute_remote_query('product', sql, (limit,))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取ETF列表失败: {e}")
            return []

    async def get_fund_manager_info(
        self, manager_name: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取基金经理信息

        Args:
            manager_name: 基金经理姓名（模糊匹配），可选
            limit: 返回数量上限，默认50

        Returns:
            基金经理信息列表
        """
        try:
            if manager_name:
                sql = """
                SELECT * FROM 基金经理信息对照表
                WHERE 基金经理 LIKE %s
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (f'%{manager_name}%', limit))
            else:
                sql = """
                SELECT * FROM 基金经理信息对照表
                LIMIT %s
                """
                rows = execute_remote_query('product', sql, (limit,))
            return [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"获取基金经理信息失败: {e}")
            return []

    # ==================== 工具列表 ====================

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return [
            {
                "name": "get_private_fund_managers",
                "description": "获取私募基金管理人列表",
                "parameters": {
                    "limit": "返回数量上限，默认50"
                }
            },
            {
                "name": "get_private_fund_nav",
                "description": "获取私募产品净值",
                "parameters": {
                    "fund_name": "产品名称（模糊匹配），可选",
                    "limit": "返回数量上限，默认100"
                }
            },
            {
                "name": "get_private_fund_info",
                "description": "获取私募基金备案信息",
                "parameters": {
                    "fund_name": "产品名称（模糊匹配），可选",
                    "limit": "返回数量上限，默认50"
                }
            },
            {
                "name": "get_public_fund_info",
                "description": "获取公募基金基本信息",
                "parameters": {
                    "fund_code": "基金代码，精确匹配；为空时返回列表",
                    "limit": "返回数量上限，默认50"
                }
            },
            {
                "name": "get_public_fund_nav",
                "description": "获取公募基金净值",
                "parameters": {
                    "fund_code": "基金代码（必填）",
                    "limit": "返回数量上限，默认100"
                }
            },
            {
                "name": "get_public_fund_holdings",
                "description": "获取公募基金个股持仓汇总",
                "parameters": {
                    "fund_code": "基金代码",
                    "limit": "返回数量上限，默认50"
                }
            },
            {
                "name": "get_etf_list",
                "description": "获取ETF列表",
                "parameters": {
                    "limit": "返回数量上限，默认100"
                }
            },
            {
                "name": "get_fund_manager_info",
                "description": "获取基金经理信息",
                "parameters": {
                    "manager_name": "基金经理姓名（模糊匹配），可选",
                    "limit": "返回数量上限，默认50"
                }
            },
        ]
