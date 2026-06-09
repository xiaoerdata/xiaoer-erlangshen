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
    assert "/model" in result
    assert "/commands" in result


@pytest.mark.asyncio
async def test_command_palette_and_command_suggestion():
    cli = CLI()

    palette = await cli.dispatch("/")
    assert "二郎神命令面板" in palette
    assert "/login xwab <账号>" in palette
    assert "/model" in palette
    assert "/analyze <query>" in palette
    assert "/cognition <cmd>" in palette

    typo = await cli.dispatch("/statsu")
    assert "未知命令: /statsu" in typo
    assert "你是不是想输入: /status" in typo


def test_slash_picker_helpers_cover_all_commands():
    cli = CLI()
    shortcuts = {item[1].split()[0] for item in cli._filter_palette("")}

    assert {f"/{name}" for name in cli.COMMANDS}.issubset(shortcuts)
    assert {f"/{name}" for name in cli.ALIASES}.issubset(shortcuts)
    assert cli._filter_palette("cognition")[0][1] == "/cognition <cmd>"
    assert cli._input_from_shortcut("/login xwab <账号>") == ("/login xwab ", True)
    assert cli._input_from_shortcut("/status") == ("/status", False)


@pytest.mark.asyncio
async def test_model_help_guides_api_key_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "kimi")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    reset_config()

    result = await CLI().dispatch("/model")

    assert "【大模型配置】" in result
    assert "当前 provider: kimi" in result
    assert "API key: 未配置" in result
    assert "export KIMI_API_KEY=..." in result
    assert "/model select" in result
    assert "kimi-k2.6" in result
    assert "mimo-v2.5-pro" in result
    reset_config()


@pytest.mark.asyncio
async def test_model_select_requires_interactive_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    reset_config()

    result = await CLI().dispatch("/model select")

    assert "不能打开光标选择器" in result
    assert "OPENAI_MODEL=gpt-5.2" in result
    reset_config()


def test_provider_model_update_uses_provider_specific_fields():
    cli = CLI()

    assert cli._provider_model_update("openai", "gpt-5.2") == {"llm_model": "gpt-5.2"}
    assert cli._provider_model_update("anthropic", "claude-sonnet-4-6") == {
        "claude_model": "claude-sonnet-4-6"
    }
    assert cli._provider_model_update("mimo", "mimo-v2.5-pro") == {"mimo_model": "mimo-v2.5-pro"}
    assert cli._provider_model_update("moonshot", "kimi-k2.6") == {"kimi_model": "kimi-k2.6"}


@pytest.mark.asyncio
async def test_local_analysis_command_degrades_to_service_hint():
    result = await CLI().dispatch("/analyze A股怎么看")

    assert "用户端默认作为瘦客户端运行" in result
    assert "/server map" in result


@pytest.mark.asyncio
async def test_interactive_mode_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    cli = CLI()
    monkeypatch.setattr(cli, "_init_hooks", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    await cli.interactive_mode()

    output = capsys.readouterr().out
    assert "再见!" in output
    assert "错误:" not in output


@pytest.mark.asyncio
async def test_interactive_mode_exits_cleanly_on_terminal_eio(monkeypatch, capsys):
    cli = CLI()
    error = OSError(5, "Input/output error")
    monkeypatch.setattr(cli, "_init_hooks", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(error))

    await cli.interactive_mode()

    output = capsys.readouterr().out
    assert "再见!" in output
    assert "Input/output error" not in output
    assert "错误:" not in output


@pytest.mark.asyncio
async def test_interactive_mode_exits_cleanly_on_stringified_terminal_eio(monkeypatch, capsys):
    class TerminalClosed(Exception):
        def __str__(self):
            return "(5, 'Input/output error')"

    cli = CLI()
    monkeypatch.setattr(cli, "_init_hooks", lambda: False)
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(TerminalClosed()))

    await cli.interactive_mode()

    output = capsys.readouterr().out
    assert "再见!" in output
    assert "Input/output error" not in output
    assert "错误:" not in output


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
