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
    assert "API Key 未设置" in result
    assert "export KIMI_API_KEY=..." in result
    assert "/model select" in result
    assert "kimi-k2.6" in result
    assert "mimo-v2.5-pro" in result
    assert "GPT-5.5/GPT-5.3" in result
    reset_config()


@pytest.mark.asyncio
async def test_model_select_requires_interactive_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    reset_config()

    result = await CLI().dispatch("/model select")

    assert "不能打开光标选择器" in result
    assert "OPENAI_MODEL=gpt-5.2" in result
    reset_config()


@pytest.mark.asyncio
async def test_model_key_explains_local_only_storage_in_non_tty(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    reset_config()

    result = await CLI().dispatch("/model key")

    assert "不能安全读取 API Key" in result
    assert "只用于客户端直连大模型" in result
    assert "不会发送给二郎神服务端" in result
    reset_config()


def test_provider_model_update_uses_provider_specific_fields():
    cli = CLI()

    assert cli._provider_model_update("openai", "gpt-5.2") == {"llm_model": "gpt-5.2"}
    assert cli._provider_model_update("anthropic", "claude-sonnet-4-6") == {
        "claude_model": "claude-sonnet-4-6"
    }
    assert cli._provider_model_update("mimo", "mimo-v2.5-pro") == {"mimo_model": "mimo-v2.5-pro"}
    assert cli._provider_model_update("moonshot", "kimi-k2.6") == {"kimi_model": "kimi-k2.6"}


def test_provider_key_update_uses_provider_specific_fields():
    cli = CLI()

    assert cli._provider_key_update("openai", "key") == {"llm_api_key": "key"}
    assert cli._provider_key_update("anthropic", "key") == {"claude_api_key": "key"}
    assert cli._provider_key_update("mimo", "key") == {"mimo_api_key": "key"}
    assert cli._provider_key_update("moonshot", "key") == {"kimi_api_key": "key"}


def test_selection_styles_do_not_use_white_reverse():
    cli = CLI()

    assert "bg:#00a3a3 #000000 bold" in cli._select_style_current()
    assert cli._ansi_selected_style() == "30;46"


@pytest.mark.asyncio
async def test_client_side_advice_requires_local_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "kimi")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    reset_config()

    result = await CLI().dispatch("/advice A股怎么看")

    assert "需要本机大模型 API Key" in result
    assert "erlangshen /model key" in result
    assert "不接收、不存储、不转发" in result
    reset_config()


@pytest.mark.asyncio
async def test_client_side_advice_maps_server_then_calls_local_llm(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-secret")
    reset_config()

    class FakeServerClient:
        def __init__(self, **kwargs):
            assert "local-secret" not in str(kwargs)

        async def cognition_map(self, query):
            assert query == "A股怎么看"
            return {
                "matches": [
                    {
                        "scene": "市场监测与事件响应",
                        "confidence": 0.72,
                        "orientation": "risk_asset",
                        "protection": "public_match_only",
                    }
                ]
            }

    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            assert settings.api_key == "local-secret"
            assert settings.provider == "deepseek"

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            payload = messages[-1]["content"]
            assert "server_protected_matches" in payload
            return '{"view":"模型综合判断","suggestions":["降低单点暴露"],"risk_controls":["控制回撤"],"missing_data":["持仓"]}'

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)

    result = await CLI().dispatch("/advice A股怎么看")

    assert "客户端大模型投资建议" in result
    assert "服务端命中场景: 市场监测与事件响应" in result
    assert "本机大模型: DeepSeek / deepseek-v4-flash" in result
    assert "Key 仅在本机用于直连供应商" in result
    assert "降低单点暴露" in result
    reset_config()


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
