"""
MCP 工具 - 市场行情数据
使用真实数据库数据
"""

import sys
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# 导入投资系统数据库连接
sys.path.insert(0, '/Users/wanghui/.openclaw-agent-06/workspace/investment-strategy')
from backend.core.database import execute_remote_query


class MarketMCP:
    """
    行情数据 MCP

    提供股票、指数、期货等行情数据接口
    数据来源：远程数据库 (193.112.183.130)
    """

    def __init__(self):
        self.name = "market"

    async def get_stock_price(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票实时价格

        Args:
            symbol: 股票代码，如 "000001", "600519"

        Returns:
            价格数据字典
        """
        try:
            sql = """
            SELECT 日期, 代码, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 涨跌幅, 涨跌额, 换手率
            FROM A股历史行情表
            WHERE 代码 = %s
            ORDER BY 日期 DESC
            LIMIT 1
            """
            rows = execute_remote_query('stock', sql, (symbol,))
            if rows:
                r = rows[0]
                return {
                    "symbol": r['代码'],
                    "date": str(r['日期']),
                    "price": float(r['收盘']) if r['收盘'] else None,
                    "open": float(r['开盘']) if r['开盘'] else None,
                    "high": float(r['最高']) if r['最高'] else None,
                    "low": float(r['最低']) if r['最低'] else None,
                    "change": float(r['涨跌额']) if r['涨跌额'] else 0.0,
                    "change_pct": float(r['涨跌幅']) if r['涨跌幅'] else 0.0,
                    "volume": float(r['成交量']) if r['成交量'] else 0,
                    "amount": float(r['成交额']) if r['成交额'] else 0.0,
                    "turnover": float(r['换手率']) if r['换手率'] else None,
                    "source": "remote_db"
                }
            return {"error": f"未找到股票 {symbol} 的数据", "symbol": symbol}
        except Exception as e:
            logger.error(f"获取股票 {symbol} 价格失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "symbol": symbol}

    async def get_stock_history(
        self,
        symbol: str,
        days: int = 30,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取股票历史行情

        Args:
            symbol: 股票代码
            days: 历史天数
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            历史行情列表
        """
        try:
            sql = """
            SELECT 日期, 代码, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 涨跌幅, 涨跌额
            FROM A股历史行情表
            WHERE 代码 = %s
            ORDER BY 日期 DESC
            LIMIT %s
            """
            rows = execute_remote_query('stock', sql, (symbol, days))
            if rows:
                return [
                    {
                        "date": str(r['日期']),
                        "symbol": r['代码'],
                        "open": float(r['开盘']) if r['开盘'] else None,
                        "close": float(r['收盘']) if r['收盘'] else None,
                        "high": float(r['最高']) if r['最高'] else None,
                        "low": float(r['最低']) if r['最低'] else None,
                        "volume": float(r['成交量']) if r['成交量'] else 0,
                        "amount": float(r['成交额']) if r['成交额'] else 0.0,
                        "change_pct": float(r['涨跌幅']) if r['涨跌幅'] else 0.0,
                        "change": float(r['涨跌额']) if r['涨跌额'] else 0.0,
                        "source": "remote_db"
                    }
                    for r in rows
                ]
            return [{"error": f"未找到股票 {symbol} 的历史数据"}]
        except Exception as e:
            logger.error(f"获取股票 {symbol} 历史失败: {e}")
            return [{"error": f"数据库查询失败: {str(e)}"}]

    async def get_index_quote(self, index_name: str) -> Dict[str, Any]:
        """
        获取指数行情

        Args:
            index_name: 指数名称，如 "上证指数", "沪深300", "创业板指"

        Returns:
            指数行情数据
        """
        index_names = {
            "上证指数": "000001",
            "深证成指": "399001",
            "创业板指": "399006",
            "沪深300": "000300",
            "上证50": "000016",
            "中证500": "000905",
            "科创50": "科创50",
        }
        try:
            sql = """
            SELECT 指数名称, 日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交额, 涨跌幅, 涨跌额
            FROM 国内宽基指数行情表
            WHERE 指数名称 = %s
            ORDER BY 日期 DESC
            LIMIT 1
            """
            rows = execute_remote_query('index', sql, (index_name,))
            if rows:
                r = rows[0]
                return {
                    "index_name": r['指数名称'],
                    "date": str(r['日期']),
                    "price": float(r['收盘价']) if r['收盘价'] else None,
                    "open": float(r['开盘价']) if r['开盘价'] else None,
                    "high": float(r['最高价']) if r['最高价'] else None,
                    "low": float(r['最低价']) if r['最低价'] else None,
                    "change": float(r['涨跌额']) if r['涨跌额'] else 0.0,
                    "change_pct": float(r['涨跌幅']) if r['涨跌幅'] else 0.0,
                    "volume": float(r['成交量']) if r['成交量'] else 0,
                    "amount": float(r['成交额']) if r['成交额'] else 0.0,
                    "source": "remote_db"
                }
            return {"error": f"未找到指数 {index_name} 的数据", "index_name": index_name}
        except Exception as e:
            logger.error(f"获取指数 {index_name} 行情失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "index_name": index_name}

    async def get_index_history(
        self,
        index_name: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        获取指数历史行情

        Args:
            index_name: 指数名称
            days: 历史天数

        Returns:
            历史行情列表
        """
        try:
            sql = """
            SELECT 指数名称, 日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交额, 涨跌幅, 涨跌额
            FROM 国内宽基指数行情表
            WHERE 指数名称 = %s
            ORDER BY 日期 DESC
            LIMIT %s
            """
            rows = execute_remote_query('index', sql, (index_name, days))
            if rows:
                return [
                    {
                        "index_name": r['指数名称'],
                        "date": str(r['日期']),
                        "open": float(r['开盘价']) if r['开盘价'] else None,
                        "high": float(r['最高价']) if r['最高价'] else None,
                        "low": float(r['最低价']) if r['最低价'] else None,
                        "close": float(r['收盘价']) if r['收盘价'] else None,
                        "volume": float(r['成交量']) if r['成交量'] else 0,
                        "amount": float(r['成交额']) if r['成交额'] else 0.0,
                        "change_pct": float(r['涨跌幅']) if r['涨跌幅'] else 0.0,
                        "change": float(r['涨跌额']) if r['涨跌额'] else 0.0,
                        "source": "remote_db"
                    }
                    for r in rows
                ]
            return [{"error": f"未找到指数 {index_name} 的历史数据"}]
        except Exception as e:
            logger.error(f"获取指数 {index_name} 历史失败: {e}")
            return [{"error": f"数据库查询失败: {str(e)}"}]

    async def get_futures_price(self, contract: str) -> Dict[str, Any]:
        """
        获取期货价格

        Args:
            contract: 期货合约名称

        Returns:
            期货行情数据
        """
        try:
            sql = """
            SELECT contract_code, trade_date, open, high, low, close, volume, open_interest
            FROM 全部期货合约历史行情
            WHERE contract_code = %s
            ORDER BY trade_date DESC
            LIMIT 1
            """
            rows = execute_remote_query('futures', sql, (contract,))
            if rows:
                r = rows[0]
                return {
                    "contract": r['contract_code'],
                    "date": str(r['trade_date']),
                    "price": float(r['close']),
                    "open": float(r['open']) if r['open'] else None,
                    "high": float(r['high']) if r['high'] else None,
                    "low": float(r['low']) if r['low'] else None,
                    "volume": int(r['volume']) if r['volume'] else 0,
                    "open_interest": int(r['open_interest']) if r['open_interest'] else 0,
                    "source": "remote_db"
                }
            return {"error": f"未找到期货合约 {contract} 的数据", "contract": contract}
        except Exception as e:
            logger.error(f"获取期货 {contract} 价格失败: {e}")
            return {"error": f"数据库查询失败: {str(e)}", "contract": contract}

    async def get_etf_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取ETF行情 (暂无独立ETF表，暂用股票表)

        Args:
            symbol: ETF代码

        Returns:
            ETF行情数据
        """
        return await self.get_stock_price(symbol)

    async def get_realtime_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            行情列表
        """
        results = []
        for symbol in symbols:
            quote = await self.get_stock_price(symbol)
            results.append(quote)
        return results

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return [
            {
                "name": "get_stock_price",
                "description": "获取股票实时价格",
                "parameters": {
                    "symbol": "股票代码，如 000001, 600519"
                }
            },
            {
                "name": "get_stock_history",
                "description": "获取股票历史行情",
                "parameters": {
                    "symbol": "股票代码",
                    "days": "历史天数 (默认30)",
                    "end_date": "结束日期 (YYYY-MM-DD)"
                }
            },
            {
                "name": "get_index_quote",
                "description": "获取指数行情",
                "parameters": {
                    "index_name": "指数名称，如 上证指数, 沪深300, 创业板指"
                }
            },
            {
                "name": "get_index_history",
                "description": "获取指数历史行情",
                "parameters": {
                    "index_name": "指数名称",
                    "days": "历史天数"
                }
            },
            {
                "name": "get_futures_price",
                "description": "获取期货价格",
                "parameters": {
                    "contract": "期货合约代码"
                }
            },
            {
                "name": "get_etf_quote",
                "description": "获取ETF行情",
                "parameters": {
                    "symbol": "ETF代码"
                }
            },
            {
                "name": "get_realtime_quotes",
                "description": "批量获取实时行情",
                "parameters": {
                    "symbols": "股票代码列表"
                }
            },
        ]
