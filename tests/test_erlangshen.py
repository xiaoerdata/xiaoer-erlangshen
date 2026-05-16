"""
测试套件 - 二郎神核心功能测试
"""
import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.brain import Brain
from src.core.memory import Memory
from src.core.knowledge import KnowledgeBase
from src.core.cerebellum import Cerebellum
from src.tools.market_tools import MarketTools
from src.tools.macro_tools import MacroTools
from src.tools.search_tools import SearchTools
from src.agents.erlang import 二郎神 as Erlangshen


@pytest.fixture
def brain():
    return Brain()


@pytest.fixture
def memory():
    return Memory()


@pytest.fixture
def knowledge(tmp_path):
    return KnowledgeBase(base_path=str(tmp_path))


@pytest.fixture
def erlangshen(brain, memory, knowledge):
    tools = {
        "market_tools": MarketTools(),
        "macro_tools": MacroTools(),
        "search_tools": SearchTools(),
    }
    return Erlangshen(brain=brain, memory=memory, knowledge=knowledge, tools=tools)


class TestBrain:
    def test_brain_init(self, brain):
        assert brain.model is not None
        assert brain.api_base is not None

    @pytest.mark.asyncio
    async def test_think(self, brain):
        result = await brain.think("你好，请用一句话介绍自己")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_analyze(self, brain):
        result = await brain.analyze("分析当前全球经济形势")
        assert result.conclusion is not None
        assert 0 <= result.confidence <= 1


class TestMemory:
    @pytest.mark.asyncio
    async def test_add_message(self, memory):
        await memory.add_message("user", "Hello")
        context = await memory.get_context()
        assert len(context) == 1
        assert context[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_add_interaction(self, memory):
        await memory.add_interaction("Query", "Response")
        events = await memory.get_recent_events(hours=1)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_register_skill(self, memory):
        async def dummy_skill():
            return "done"
        memory.register_skill("dummy", dummy_skill)
        skill = memory.get_skill("dummy")
        assert skill is not None


class TestKnowledgeBase:
    @pytest.mark.asyncio
    async def test_add_entry(self, knowledge):
        entry = knowledge.add("Test knowledge", category="test")
        assert entry.entry_id is not None
        assert entry.content == "Test knowledge"

    @pytest.mark.asyncio
    async def test_search(self, knowledge):
        knowledge.add("茅台是高端白酒", category="stock")
        results = await knowledge.search("茅台", top_k=5)
        assert len(results) >= 1


class TestMarketTools:
    @pytest.mark.asyncio
    async def test_get_stock_price(self):
        tools = MarketTools()
        result = await tools.get_stock_price("600519")
        assert "symbol" in result
        assert result["symbol"] == "600519"


class TestMacroTools:
    @pytest.mark.asyncio
    async def test_get_interest_rates(self):
        tools = MacroTools()
        result = await tools.get_interest_rates("CN")
        assert "rates" in result
        assert "CN" in result["country"]


class TestErlangshen:
    @pytest.mark.asyncio
    async def test_classify_query(self, erlangshen):
        assert erlangshen._classify_query("分析茅台股票") == "equity"
        assert erlangshen._classify_query("分析宏观经济") == "macro"
        assert erlangshen._classify_query("资产配置建议") == "multi_asset"

    @pytest.mark.asyncio
    async def test_process(self, erlangshen):
        result = await erlangshen.process("分析当前A股市场")
        assert "query" in result
        assert "erlangshen_insight" in result

    @pytest.mark.asyncio
    async def test_analyze_stock(self, erlangshen):
        result = await erlangshen.analyze_stock("600519")
        assert "query" in result
        assert result["symbol"] == "600519"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
