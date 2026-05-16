"""
FastAPI Server - 二郎神API服务
提供REST API接口
"""
import os
import sys
from pathlib import Path
from typing import Optional

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn

from src.core.brain import Brain
from src.core.memory import Memory
from src.core.knowledge import KnowledgeBase
from src.core.cerebellum import Cerebellum
from src.tools.market_tools import MarketTools
from src.tools.macro_tools import MacroTools
from src.tools.search_tools import SearchTools
from src.tools.file_tools import FileTools
from src.agents.erlangshen import 二郎神

# 初始化应用
app = FastAPI(
    title="二郎神 API",
    description="全知全能的AI投资智能体API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
_brain: Optional[Brain] = None
_memory: Optional[Memory] = None
_knowledge: Optional[KnowledgeBase] = None
_cerebellum: Optional[Cerebellum] = None
_erlangshen: Optional[二郎神] = None


def get_erlangshen() -> 二郎神:
    """获取或初始化二郎神实例"""
    global _brain, _memory, _knowledge, _cerebellum, _erlangshen
    if _erlangshen is None:
        logger.info("Initializing 二郎神...")
        _brain = Brain()
        _memory = Memory()
        _knowledge = KnowledgeBase()
        _cerebellum = Cerebellum(brain=_brain, memory=_memory, knowledge=_knowledge)

        # 初始化工具
        market_tools = MarketTools()
        macro_tools = MacroTools()
        search_tools = SearchTools()
        file_tools = FileTools()

        tools = {
            "market_tools": market_tools,
            "macro_tools": macro_tools,
            "search_tools": search_tools,
            "file_tools": file_tools,
        }

        _erlangshen = 二郎神(
            brain=_brain,
            memory=_memory,
            knowledge=_knowledge,
            tools=tools,
        )
        logger.info("二郎神 initialized")
    return _erlangshen


# === 请求/响应模型 ===

class AnalyzeRequest(BaseModel):
    query: str = Field(description="分析问题")
    context: Optional[dict] = Field(default=None, description="额外上下文")


class AnalyzeResponse(BaseModel):
    status: str
    result: dict


class MarketRequest(BaseModel):
    symbol: str = Field(description="股票代码")
    days: int = Field(default=30, description="历史天数")


class ReportRequest(BaseModel):
    title: str = Field(description="报告标题")
    content: str = Field(description="报告内容")


class ThinkRequest(BaseModel):
    prompt: str = Field(description="用户输入")
    context: Optional[dict] = Field(default=None, description="额外上下文")
    system: Optional[str] = Field(default=None, description="系统提示")


# === API端点 ===

@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "二郎神 API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


@app.post("/api/brain/think")
async def brain_think(request: ThinkRequest):
    """
    直接调用 Brain 进行深度思考
    前端全息界面调用此接口
    """
    try:
        erlangshen = get_erlangshen()
        result = await erlangshen.brain.think(
            prompt=request.prompt,
            context=request.context,
            system=request.system,
        )
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Brain think failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    分析接口 - 二郎神的核心分析能力

    支持:
    - 宏观经济分析
    - 股票分析
    - 多资产配置建议
    - 综合投资分析
    """
    try:
        erlangshen = get_erlangshen()
        result = await erlangshen.process(request.query, request.context)
        return AnalyzeResponse(status="success", result=result)
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def query(request: AnalyzeRequest):
    """
    查询接口 - 简化的查询接口
    """
    try:
        erlangshen = get_erlangshen()
        result = await erlangshen.process(request.query, request.context)
        return result
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/{symbol}")
async def get_market(symbol: str, days: int = 30):
    """获取股票行情"""
    try:
        erlangshen = get_erlangshen()
        market_tools = erlangshen.tools.get("market_tools")
        if market_tools:
            result = await market_tools.get_stock_history(symbol, days)
            return result
        raise HTTPException(status_code=503, detail="Market tools not available")
    except Exception as e:
        logger.error(f"Market query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/macro/{indicator}")
async def get_macro(indicator: str):
    """获取宏观指标"""
    try:
        erlangshen = get_erlangshen()
        macro_tools = erlangshen.tools.get("macro_tools")
        if macro_tools:
            result = await macro_tools.get_macro_indicator(indicator)
            return result
        raise HTTPException(status_code=503, detail="Macro tools not available")
    except Exception as e:
        logger.error(f"Macro query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report")
async def create_report(request: ReportRequest):
    """创建报告"""
    try:
        erlangshen = get_erlangshen()
        result = await erlangshen.generate_report(request.title, request.content)
        return result
    except Exception as e:
        logger.error(f"Report creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/knowledge/stats")
async def knowledge_stats():
    """知识库统计"""
    try:
        erlangshen = get_erlangshen()
        if erlangshen.knowledge:
            return erlangshen.knowledge.stats()
        raise HTTPException(status_code=503, detail="Knowledge not available")
    except Exception as e:
        logger.error(f"Knowledge stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats")
async def memory_stats():
    """记忆统计"""
    try:
        erlangshen = get_erlangshen()
        if erlangshen.memory:
            return erlangshen.memory.export_state()
        raise HTTPException(status_code=503, detail="Memory not available")
    except Exception as e:
        logger.error(f"Memory stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === 启动函数 ===

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动API服务器"""
    logger.info(f"Starting 二郎神 API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="二郎神API服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    args = parser.parse_args()
    run_server(args.host, args.port)
