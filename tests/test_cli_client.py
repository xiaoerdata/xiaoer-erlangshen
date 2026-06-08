import pytest

from src.cli import CLI
from src.client.server_client import _normalize_login_payload
from src.config import get_config, reset_config


@pytest.mark.asyncio
async def test_slash_help_returns_help_text():
    result = await CLI().dispatch("/help")

    assert "███████" in result or "二郎神 ERLANGSHEN" in result
    assert "二郎神 - 服务端优先 CLI" in result
    assert "/login [xwab|xczt] [账号]" in result


def test_default_client_server_url():
    reset_config()

    assert get_config().erlangshen_api_base_url == "https://xiaoerdata.site/api/erlangshen"
    reset_config()


def test_normalize_account_system_login_payload():
    payload = {
        "code": 200,
        "message": "success",
        "data": {
            "authenticated": True,
            "entry": "xwab",
            "token": "token-value",
            "expiresInSeconds": 3600,
            "user": {
                "id": "00423",
                "username": "小二MCP助手",
                "role": "corer",
                "email": "xwab-user",
            },
        },
    }

    result = _normalize_login_payload(payload, "xwab")

    assert result["status"] == "success"
    assert result["loginEntry"] == "xwab"
    assert result["token"] == "token-value"
    assert result["user"]["username"] == "小二MCP助手"
    assert result["user"]["loginEntry"] == "xwab"


def test_normalize_erlangshen_login_payload():
    payload = {
        "status": "success",
        "loginEntry": "xwab",
        "token": "token-value",
        "user": {"id": "u1", "username": "tester"},
    }

    result = _normalize_login_payload(payload, "xwab")

    assert result["token"] == "token-value"
    assert result["status"] == "success"
