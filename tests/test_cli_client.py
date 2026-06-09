import pytest

from src.cli import CLI
from src.client.server_client import _normalize_login_payload
from src.config import get_config, reset_config, update_config
from src.llm.providers import resolve_llm_settings


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


def test_header_server_display_does_not_expose_url():
    cli = CLI()

    assert cli._server_display_text("https://xiaoerdata.site/api/erlangshen") == "已配置"
    assert "xiaoerdata" not in cli._server_display_text("https://xiaoerdata.site/api/erlangshen")
    assert cli._server_display_text("") == "未配置"


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


@pytest.mark.asyncio
async def test_model_key_validates_before_saving(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "mimo")
    monkeypatch.setenv("MIMO_MODEL", "mimo-v2.5")
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.delenv("XIAOMI_API_KEY", raising=False)
    reset_config()

    calls = []

    async def fake_validate(self, provider, model, api_key):
        calls.append((provider, model, api_key))
        return True, "连接测试成功"

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt: "candidate-key")
    monkeypatch.setattr(CLI, "_validate_local_api_key", fake_validate)

    result = await CLI().dispatch("/model key")

    assert "API Key 已保存到本机" in result
    assert "连接测试: 连接测试成功" in result
    assert calls == [("mimo", "mimo-v2.5", "candidate-key")]
    assert get_config().mimo_api_key == "candidate-key"
    reset_config()


@pytest.mark.asyncio
async def test_model_key_does_not_save_when_validation_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "mimo")
    monkeypatch.setenv("MIMO_MODEL", "mimo-v2.5")
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.delenv("XIAOMI_API_KEY", raising=False)
    reset_config()

    async def fake_validate(self, provider, model, api_key):
        assert api_key == "bad-key"
        return False, "401 Unauthorized"

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt: "bad-key")
    monkeypatch.setattr(CLI, "_validate_local_api_key", fake_validate)

    result = await CLI().dispatch("/model key")

    assert "API Key 未保存" in result
    assert "401 Unauthorized" in result
    assert get_config().mimo_api_key is None
    assert not (tmp_path / "settings.json").exists()
    reset_config()


def test_saved_local_api_key_overrides_stale_environment_key(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    reset_config()
    update_config(llm_provider="mimo", mimo_model="mimo-v2.5", mimo_api_key="validated-local-key")

    reset_config()
    monkeypatch.setenv("MIMO_API_KEY", "stale-env-key")

    config = get_config()
    settings = resolve_llm_settings(config=config)

    assert config.mimo_api_key == "validated-local-key"
    assert settings.api_key == "validated-local-key"
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
            if "allowed_mcp_tools" in payload:
                return '{"intent":"market_overview","needs_server_mapping":true,"needs_mcp":false,"mcp_tools":[],"rewritten_query":"A股怎么看"}'
            assert "server_protected_matches" in payload
            assert "client_intent_plan" in payload
            return '{"view":"模型综合判断","suggestions":["降低单点暴露"],"risk_controls":["控制回撤"],"missing_data":["持仓"]}'

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)

    result = await CLI().dispatch("/advice A股怎么看")

    assert "我先按“A股怎么看”来理解" in result
    assert "服务端场景：市场监测与事件响应" in result
    assert "本机模型：DeepSeek / deepseek-v4-flash" in result
    assert "大模型 API Key 只在本机直连供应商" in result
    assert "降低单点暴露" in result
    reset_config()


@pytest.mark.asyncio
async def test_client_side_advice_uses_local_intent_to_fetch_super66_mcp(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-secret")
    reset_config()

    class FakeServerClient:
        def __init__(self, **kwargs):
            pass

        async def cognition_map(self, query):
            return {"matches": [{"scene": "市场监测与事件响应", "confidence": 0.9}]}

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            assert tool_name == "get_index_data"
            assert arguments["index_name"] == "沪深300"
            return {"index_name": "沪深300", "change_pct": 1.23}

    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            payload = messages[-1]["content"]
            if "allowed_mcp_tools" in payload:
                return (
                    '{"intent":"market_overview","needs_server_mapping":true,"needs_mcp":true,'
                    '"mcp_tools":[{"name":"get_index_data","arguments":{"index_name":"沪深300","limit":60}}],'
                    '"rewritten_query":"今天A股市场情况怎么样"}'
                )
            assert "沪深300" in payload
            assert "change_pct" in payload
            return '{"view":"结合实时数据看，A股今天偏强。","suggestions":["先看主线"],"risk_controls":["别追高"],"missing_data":[]}'

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)
    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)

    result = await CLI().dispatch("今天市场情况怎么样")

    assert "结合实时数据看" in result
    assert "先看主线" in result
    assert "服务端场景：市场监测与事件响应" in result
    reset_config()


def test_interactive_turn_visually_separates_question_and_answer():
    output = CLI()._format_interactive_turn("今天市场情况怎么样", "先看主线。")

    assert "╭─ 你 " in output
    assert "今天市场情况怎么样" in output
    assert "╭─ 二郎神 " in output
    assert "先看主线。" in output


@pytest.mark.asyncio
async def test_client_side_advice_formats_string_sections_as_items():
    cli = CLI()
    result = cli._format_client_advice(
        query="A股怎么看",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.72}],
        synthesis={
            "view": "短期还需要观察。",
            "suggestions": "可执行建议：1. 先看成交量。 2. 再看主线持续性。",
            "risk_controls": "风险控制：1. 不追高。 2. 控制仓位。",
            "missing_data": "需补充数据：1. 持仓。 2. 周期。",
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={},
    )

    assert "- 先看成交量。" in result
    assert "- 再看主线持续性。" in result
    assert "- 不追高。" in result
    assert "- 控制仓位。" in result
    assert "- 持仓。" in result
    assert "- 周期。" in result
    assert "- 可" not in result


@pytest.mark.asyncio
async def test_small_talk_returns_natural_response_without_analysis(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    reset_config()

    result = await CLI().dispatch("在吗")

    assert result.startswith("在，我在。")
    assert "投资问题" in result
    assert "服务端场景" not in result
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
