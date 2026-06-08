import pytest

from src.cli import CLI
from src.config import get_config, reset_config


@pytest.mark.asyncio
async def test_slash_help_returns_help_text():
    result = await CLI().dispatch("/help")

    assert "二郎神 - 服务端优先 CLI" in result
    assert "/login [xwab|xczt] [账号]" in result


def test_default_client_server_url():
    reset_config()

    assert get_config().erlangshen_api_base_url == "https://xiaoerdata.site/api/erlangshen"
    reset_config()
