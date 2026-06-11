import json

import pytest
from pathlib import Path

from src.cli import CLI, _display_width, _extract_startup_workspace_args, _logo, _panel, _text_panel, main
from src.commands.server import ServerCommand
from src.client.server_client import _normalize_login_payload
from src.client.chrome_search import build_search_url, _is_noise_search_result
from src.config import get_config, reset_config, update_config
from src.llm.providers import resolve_llm_settings
from src.mcp.super66 import Super66MCP
from src.workspace import approve_workspace, recent_workspaces, workspace_status


@pytest.fixture(autouse=True)
def isolate_local_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_MEMORY_FILE", str(tmp_path / "memory.json"))


@pytest.mark.asyncio
async def test_slash_help_returns_help_text():
    result = await CLI().dispatch("/help")

    assert "二郎神 ERLANGSHEN" in result
    assert "二郎神 - 服务端优先 CLI" in result
    assert "/login [xwab|xczt] [账号]" in result
    assert "/model" in result
    assert "/setup" in result
    assert "/setup workspace" in result
    assert "/doctor" in result
    assert "/workspace browse" in result
    assert "/workspace path <路径>" in result
    assert "/workspace allow [路径]" in result
    assert "erlangshen /workspace path /path/to/project" in result
    assert "/commands" in result


def test_compact_logo_keeps_agent_identity(monkeypatch):
    monkeypatch.setattr("src.cli._terminal_width", lambda: 72)

    logo = _logo()

    assert "███████╗██████╗" in logo
    assert "二郎神 ERLANGSHEN" in logo


def test_wide_logo_keeps_technical_mark(monkeypatch):
    monkeypatch.setattr("src.cli._terminal_width", lambda: 120)

    logo = _logo()

    assert "███████╗██████╗" in logo
    assert "二郎神 ERLANGSHEN" in logo


def test_panels_use_terminal_display_width_for_chinese_text(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")

    panel = _text_panel("欢迎界面", ["二郎神 投资智能体", "路径选择 /workspace browse"], min_width=40, max_width=80)
    widths = [_display_width(line) for line in panel.splitlines()]
    assert len(set(widths)) == 1

    rows = _panel("初始化", [("workspace", "未授权 项目文件夹"), ("model", "小米 MiMo / mimo-v2.5")])
    row_widths = [_display_width(line) for line in rows.splitlines()]
    assert len(set(row_widths)) == 1


@pytest.mark.asyncio
async def test_command_palette_and_command_suggestion():
    cli = CLI()

    palette = await cli.dispatch("/")
    assert "二郎神命令面板" in palette
    assert "Command Workbench" in palette
    assert "start      /setup run · 初始化项目沙箱、账号和本机大模型" in palette
    assert "ask        直接输入自然语言问题 · 本机 LLM 选择 MCP/web_search 和服务端" in palette
    assert "server     /server  · status / goals / flow / artifact / capabilities" in palette
    assert "workspace  /workspace browse · 选择项目文件夹并授权图表/报告保存" in palette
    assert "model      /model select · /model key 本机测试并保存 API Key" in palette
    assert "resources  /links 1 · /open 1 打开网页、图片、图表和报告" in palette
    assert "audit      /plan · /memory · /brief · /doctor 复盘工具链路、记忆和诊断" in palette
    assert "Getting Started" in palette
    assert "/setup" in palette
    assert "/setup run" in palette
    assert "/setup workspace" in palette
    assert "/brief" in palette
    assert "/doctor" in palette
    assert "/login xwab <账号>" in palette
    assert "/model" in palette
    assert "Server & Mapping" in palette
    assert "/server status" in palette
    assert "/server goals" in palette
    assert "/server flow" in palette
    assert "/server artifact" in palette
    assert "/server capabilities" in palette
    assert "/server map <问题>" in palette
    assert "/server advice <问题>" in palette
    assert "Workspace & Artifacts" in palette
    assert "/workspace browse" in palette
    assert "/workspace path <路径>" in palette
    assert "/chart <标题>" in palette
    assert "/artifacts" in palette
    assert "/open [chart|report|link N]" in palette
    assert "/open link <序号>" in palette
    assert "/links" in palette
    assert "/links open <序号>" in palette
    assert "/examples" in palette
    assert "/tools" in palette
    assert "/mcp" in palette
    assert "/plan" in palette
    assert "/context" in palette
    assert "/context clear" in palette
    assert "/clear" in palette
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
    login_detail = cli._slash_selection_detail(cli._filter_palette("login xwab"), 0)
    assert "登录 XWAB/XCZT 账号体系" in login_detail
    assert "访问服务端场景映射和 super-66 MCP 数据" in login_detail
    assert "下一步: /model key" in login_detail
    model_detail = cli._slash_selection_detail(cli._filter_palette("model key"), 0)
    assert "本机测试并保存当前供应商 API Key" in model_detail
    assert "Key 不接收、不存储、不转发到二郎神服务端" in model_detail
    model_select_detail = cli._slash_selection_detail(cli._filter_palette("model select"), 0)
    assert "用光标选择大模型供应商和型号" in model_select_detail
    assert "选择模型不会保存 API Key" in model_select_detail
    setup_detail = cli._slash_selection_detail(cli._filter_palette("setup run"), 0)
    assert "执行式初始化" in setup_detail
    assert "项目文件夹、登录和本机模型 Key" in setup_detail
    detail = cli._slash_selection_detail(cli._filter_palette("server guide"), 0)
    assert detail.startswith("选中: /server guide")
    assert "用途: 按任务选择服务端路径" in detail
    assert "下一步: 直接输入问题或 /server actions" in detail
    assert "边界: 只解释开放能力" in detail
    detail_lines = cli._slash_selection_detail_lines(cli._filter_palette("server guide"), 0)
    assert detail_lines[0] == "选中: /server guide"
    assert detail_lines[1] == "阶段: Server & Mapping"
    assert "用途: 按任务选择服务端路径" in detail_lines
    assert "适合: 想知道现在该先查状态、映射还是生成图表" in detail_lines
    assert "输出: 面向任务的命令路线" in detail_lines
    assert "下一步: 直接输入问题或 /server actions" in detail_lines
    assert "边界: 只解释开放能力" in detail_lines
    actions_detail = cli._slash_selection_detail(cli._filter_palette("server actions"), 0)
    assert "健康、账号、映射、图表、排障动作" in actions_detail
    assert "可复制执行的行动清单" in actions_detail
    map_detail = cli._slash_selection_detail(cli._filter_palette("server map"), 0)
    assert "不泄露认知库全文" in map_detail
    assert "输入: 一个投资问题" in map_detail
    artifact_detail = cli._slash_selection_detail(cli._filter_palette("server artifact"), 0)
    assert "artifacts/charts/visualizations/chart_requests" in artifact_detail
    assert "JSON/HTML/图片/网页名称链接" in artifact_detail
    resource_detail = cli._slash_selection_detail(cli._filter_palette("server resources"), 0)
    assert cli._filter_palette("server resources")[0][1] == "/server resources"
    assert "label/target/type 结构" in resource_detail
    assert "CLI 不内嵌富文本和二进制内容" in resource_detail
    links_detail = cli._slash_selection_detail(cli._filter_palette("links open"), 0)
    assert cli._filter_palette("links open")[0][1] == "/links open <序号>"
    assert "直接打开 /links 列表中的指定资源" in links_detail
    assert "/links open 1" in links_detail
    open_link_detail = cli._slash_selection_detail(cli._filter_palette("open link"), 0)
    assert cli._filter_palette("open link")[0][1] == "/open link <序号>"
    assert "打开最近资源链接" in open_link_detail
    server_detail = cli._slash_selection_detail(cli._filter_palette("server"), 0)
    assert "服务端交互工作台入口" in server_detail
    assert "展开 status/guide/goals/actions/flow/artifact" in server_detail
    workspace_detail = cli._slash_selection_detail(cli._filter_palette("workspace path"), 0)
    assert "阶段: Workspace & Artifacts" in workspace_detail
    assert "手动粘贴或输入项目路径" in workspace_detail
    assert "下一步: /workspace allow" in workspace_detail
    workspace_browse_detail = cli._slash_selection_detail(cli._filter_palette("workspace browse"), 0)
    assert "Project Sandbox Setup 选择器" in workspace_browse_detail
    assert "授权后仅写入所选项目的 .erlangshen/artifacts" in workspace_browse_detail
    chart_matches = [item for item in cli._filter_palette("chart ") if item[1].startswith("/chart")]
    chart_detail = cli._slash_selection_detail(chart_matches, 0)
    assert "请求服务端生成结构化图表 artifact" in chart_detail
    assert "JSON/HTML artifact" in chart_detail
    tools_detail = cli._slash_selection_detail(cli._filter_palette("tools"), 0)
    assert "阶段: Market Intelligence" in tools_detail
    assert "super-66 注册表、工具结果契约、组合模式和典型数据配方" in tools_detail
    assert "下一步: 直接输入问题或 /plan" in tools_detail
    plan_detail = cli._slash_selection_detail(cli._filter_palette("plan"), 0)
    assert "复盘最近一次分析的意图和工具链路" in plan_detail
    assert "路由来源、工具理由、MCP 快照、服务端映射、资源链接和产物计划" in plan_detail


def test_slash_picker_groups_commands_for_dropdown_rendering():
    cli = CLI()
    rows = cli._grouped_palette_rows(cli._filter_palette(""))
    group_titles = [payload for row_type, payload, _ in rows if row_type == "group"]
    command_rows = [payload for row_type, payload, _ in rows if row_type == "item"]

    assert group_titles[:3] == ["Getting Started", "Account & Model", "Server & Mapping"]
    assert any(item[1] == "/setup" for item in command_rows)
    assert any(item[1] == "/setup run" for item in command_rows)
    assert any(item[1] == "/setup workspace" for item in command_rows)
    assert any(item[1] == "/brief" for item in command_rows)
    assert any(item[1] == "/doctor" for item in command_rows)
    assert any(item[1] == "/workspace browse" for item in command_rows)
    assert any(item[1] == "/workspace path <路径>" for item in command_rows)
    assert any(item[1] == "/chart <标题> :: {\"A股\":1.2}" for item in command_rows)
    assert any(item[1] == "/open [chart|report|link N]" for item in command_rows)
    assert any(item[1] == "/open link <序号>" for item in command_rows)
    assert any(item[1] == "/links open <序号>" for item in command_rows)
    assert any(item[1] == "/links" for item in command_rows)
    assert any(item[1] == "/examples" for item in command_rows)
    assert any(item[1] == "/plan" for item in command_rows)
    assert any(item[1] == "/context" for item in command_rows)
    assert any(item[1] == "/context clear" for item in command_rows)
    assert any(item[1] == "/clear" for item in command_rows)

    filtered_rows = cli._grouped_palette_rows(cli._filter_palette("chart"))
    assert any(payload == "Workspace & Artifacts" for row_type, payload, _ in filtered_rows if row_type == "group")
    assert any(payload[1].startswith("/chart") for row_type, payload, _ in filtered_rows if row_type == "item")

    server_rows = cli._grouped_palette_rows(cli._filter_palette("server"))
    assert any(payload[1] == "/server status" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server flow" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server guide" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server goals" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server actions" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server artifact" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server capabilities" for row_type, payload, _ in server_rows if row_type == "item")
    assert any(payload[1] == "/server map <问题>" for row_type, payload, _ in server_rows if row_type == "item")


def test_slash_picker_filters_contextual_subcommands():
    cli = CLI()

    server = [item[1] for item in cli._filter_palette("server ")]
    workspace = [item[1] for item in cli._filter_palette("workspace ")]
    context = [item[1] for item in cli._filter_palette("context ")]
    setup = [item[1] for item in cli._filter_palette("setup ")]
    model = [item[1] for item in cli._filter_palette("model ")]
    auth = [item[1] for item in cli._filter_palette("auth ")]
    chart = [item[1] for item in cli._filter_palette("chart ")]
    open_items = [item[1] for item in cli._filter_palette("open ")]
    links_items = [item[1] for item in cli._filter_palette("links ")]
    server_map = [item[1] for item in cli._filter_palette("server map")]

    assert server[:8] == [
        "/server status",
        "/server me",
        "/server map <问题>",
        "/server advice <问题>",
        "/server flow",
        "/server artifact",
        "/server resources",
        "/server capabilities",
    ]
    assert "/server status" in server
    assert "/server guide" in server
    assert "/server goals" in server
    assert "/server flow" in server
    assert "/server artifact" in server
    assert "/server resources" in server
    assert all(item.startswith("/server") for item in server)
    assert workspace[:2] == ["/workspace browse", "/workspace path <路径>"]
    assert "/workspace browse" in workspace
    assert "/workspace path <路径>" in workspace
    assert "/context clear" in context
    assert "/setup run" in setup
    assert "/setup workspace" in setup
    assert "/model select" in model
    assert "/model key" in model
    assert "/login xwab <账号>" in auth
    assert "/logout" in auth
    assert "/chart <标题> :: {\"A股\":1.2}" in chart
    assert "/artifacts" in chart
    assert "/open [chart|report|link N]" in chart
    assert "/links" in chart
    assert "/open link <序号>" in open_items
    assert "/links" in open_items
    assert "/links open <序号>" in links_items
    assert "/open link <序号>" in links_items
    assert server_map == ["/server map <问题>"]
    assert cli._slash_context_hint("server ", len(server)).startswith("Server Workbench:")
    assert "status / me / map / advice / flow / artifact" in cli._slash_context_hint("server ", len(server))
    assert "status / me / map / advice / flow / artifact" in cli._slash_context_hint("server map", len(server_map))
    assert "个匹配" in cli._slash_context_hint("server ", len(server))
    assert cli._slash_picker_context_lines("server ") == [
        "目标导航: status 查健康/鉴权 · me 查账号 · map 只看映射 · flow 看协作链路",
        "智能体路径: 直接输入问题由本机 LLM 选 MCP/web_search，再请求服务端受保护映射",
        "产物导航: artifact/chart 生成图表 · capabilities 看边界 · actions 获取下一步",
        "资源出口: 服务端返回网页/图片/HTML/PDF/图表时，用 /links 1 或 /open 1 打开",
    ]
    assert cli._slash_picker_context_lines("workspace ") == [
        "沙箱导航: browse 方向键选路径 · path 粘贴路径 · allow 授权写入 · artifacts 看产物",
        "写入边界: 只在授权项目 .erlangshen/artifacts 保存图表、报告、resources.json",
        "隐私边界: 大模型 API Key、账号 token 和服务端内部认知库不会写入项目目录",
    ]
    assert cli._slash_picker_context_lines("setup ") == [
        "初始化顺序: workspace 选择项目文件夹 · login 登录账号 · model key 保存本机大模型 Key",
        "推荐入口: /setup run 一次检查；/setup workspace 只重选项目沙箱",
    ]
    assert cli._slash_picker_context_lines("model ") == [
        "模型边界: /model select 选供应商和型号；/model key 本机测试成功后才保存",
        "安全边界: Key 只在本机直连供应商，不发送给二郎神服务端",
    ]
    assert cli._slash_picker_context_lines("links ") == [
        "资源入口: 网页、图片、HTML、PDF、图表和报告都显示为名称链接",
        "打开方式: /links 1、/open 1、/links open 1 或 /open link 1",
    ]
    assert cli._slash_picker_context_lines("open ") == [
        "资源入口: 网页、图片、HTML、PDF、图表和报告都显示为名称链接",
        "打开方式: /links 1、/open 1、/links open 1 或 /open link 1",
    ]
    assert cli._slash_picker_context_lines("tools") == []
    assert cli._slash_context_hint("workspace ", len(workspace)).startswith("Project Sandbox:")
    assert cli._slash_context_hint("setup workspace", len(setup)).startswith("Setup Wizard:")
    assert cli._slash_context_hint("model key", len(model)).startswith("Local Model:")
    assert cli._slash_context_hint("serv", 3) == "filter: /serv · 3 个匹配"


def test_slash_picker_render_shows_selected_command_detail(capsys):
    cli = CLI()
    matches = cli._filter_palette("server guide")

    cli._render_slash_picker(matches, 0, "server guide")
    output = capsys.readouterr().out

    assert "Server Commands" in output
    assert "Server Workbench" in output
    assert "目标导航: status 查健康/鉴权" in output
    assert "智能体路径: 直接输入问题由本机 LLM 选 MCP/web_search" in output
    assert "产物导航: artifact/chart 生成图表" in output
    assert "资源出口: 服务端返回网页/图片/HTML/PDF/图表时" in output
    assert "选中: /server guide" in output
    assert "阶段: Server & Mapping" in output
    assert "❯ /server guide" in output
    assert "用途: 按任务选择服务端路径" in output
    assert "适合: 想知道现在该先查状态、映射还是生成图表" in output
    assert "输出: 面向任务的命令路线" in output
    assert "下一步: 直接输入问题或 /server actions" in output
    assert "边界: 只解释开放能力" in output

    matches = cli._filter_palette("tools")
    cli._render_slash_picker(matches, 0, "tools")
    output = capsys.readouterr().out

    assert "选中: /tools" in output
    assert "阶段: Market Intelligence" in output
    assert "下一步: 直接输入问题或 /plan" in output


def test_slash_picker_render_uses_display_width_for_chinese_rows(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("src.cli._terminal_width", lambda: 92)
    cli = CLI()
    rendered = []
    cli._render_dropdown_below = lambda prompt, lines: rendered.extend(lines)

    matches = cli._filter_palette("workspace ")
    cli._render_slash_picker(matches, 0, "workspace ")

    widths = [_display_width(line) for line in rendered if line.startswith(("╭", "│", "├", "╰"))]
    assert len(set(widths)) == 1
    assert any("Workspace Sandbox" in line for line in rendered)
    assert any("沙箱导航: browse 方向键选路径" in line for line in rendered)
    assert any("隐私边界: 大模型 API Key" in line for line in rendered)
    assert any("/workspace browse" in line for line in rendered)


def test_header_server_display_does_not_expose_url():
    cli = CLI()

    assert cli._server_display_text("https://xiaoerdata.site/api/erlangshen") == "已配置"
    assert "xiaoerdata" not in cli._server_display_text("https://xiaoerdata.site/api/erlangshen")
    assert cli._server_display_text("") == "未配置"


def test_message_block_wraps_markdown_and_list_continuations():
    cli = CLI()
    wrapped = cli._wrap_text("- 这是一个很长很长的建议，需要在终端消息块里保持列表层次并自然换行", 24)
    block = cli._message_block("二郎神", "## 综合判断\n" + "\n".join(wrapped), "32")

    assert "▸ 综合判断" in block
    assert "- 这是一个很长很长的建议" in block
    assert "  需要在终端消息块里保持列表层次" in block
    assert "并自然换行" in block
    for line in block.splitlines():
        if line.startswith("│ "):
            assert len(line) <= 111


def test_prompt_status_bar_shows_readiness_without_server_url(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    reset_config()

    cli = CLI()
    text = cli._prompt_status_text()

    assert "account[need]" in text
    assert "model[need]" in text
    assert "workspace[need]" in text
    assert "mcp[need]" in text
    assert "chart[need]" in text
    assert "links[none]" in text
    assert "model:deepseek/" in text
    assert "next:/setup run" in text
    assert "/server goals" in text
    assert "/tools" in text
    assert "xiaoerdata" not in text

    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-secret")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)
    monkeypatch.setattr("src.cli.load_auth_session", lambda: {"token": "token", "user": {"username": "小二MCP助手"}})
    reset_config()
    cli._last_agent_plan = {"query": "A股怎么看"}
    cli._remember_resource_links("A股怎么看", [{"source": "MCP/web_search", "link": "市场新闻: https://example.com"}])
    ready_text = cli._prompt_status_text()

    assert "account[ok]" in ready_text
    assert "model[ok]" in ready_text
    assert "workspace[ok]" in ready_text
    assert "mcp[ok]" in ready_text
    assert "chart[ok]" in ready_text
    assert "links[1]" in ready_text
    assert "next:/plan" in ready_text
    assert "links:/links open 1" in ready_text
    reset_config()


def test_header_shows_agent_workspace_and_tool_channels(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("ERLANGSHEN_MEMORY_FILE", str(tmp_path / "memory.json"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    reset_config()

    CLI().print_header()
    output = capsys.readouterr().out

    assert "Erlangshen" in output
    assert "███████╗██████╗" in output
    assert "二郎神 ERLANGSHEN" in output
    assert "Erlangshen agent workspace" in output
    assert "v0.1.39" in output
    assert "core      ready" in output
    assert "account   login · 未登录" in output
    assert "model     need key" in output
    assert "workspace sandbox" in output
    assert "memory    0 local notes" in output
    assert "下一步" in output
    assert "/model key" in output
    assert "/memory 查看本机记忆" in output
    assert "xiaoerdata" not in output
    assert "Erlangshen Agent Console" not in output
    assert "Mission Control" not in output
    assert "Agent HUD" not in output
    assert "Agent Launchpad" not in output
    assert "Workspace & Tools" not in output
    assert "Project Sandbox" not in output
    reset_config()


def test_mission_control_panel_shows_ready_agent_lanes(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    approve_workspace(project_dir)
    cli = CLI()
    cli._remember_resource_links("今天行情", [{"source": "MCP/web_search", "link": "市场新闻: https://example.com"}])

    output = cli._mission_control_panel(
        session={"token": "token"},
        base_url="https://xiaoerdata.site/api/erlangshen",
        llm_ready=True,
        workspace={"allowed": True, "path": str(project_dir)},
    )

    assert "Mission Control" in output
    assert "INPUT[ready]  ->  DATA[ready]  ->  CORE[ready]  ->  OUTPUT[ready]" in output
    assert "links[1]" in output
    assert "/links 1 或 /open 1" in output
    reset_config()


def test_welcome_panel_surfaces_primary_action_when_ready(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    output = CLI()._welcome_panel(
        base_url="https://xiaoerdata.site/api/erlangshen",
        auth_text="小二MCP助手",
        provider="mimo",
        model="mimo-v2.5",
        llm_ready=True,
        workspace={"allowed": True, "path": str(project_dir)},
    )

    assert "Primary Action  直接输入投资问题开始分析" in output
    assert "Command Deck    / 打开可选择命令面板；/setup run 进入执行式初始化" in output
    assert "First Run Path" in output
    assert "/workspace browse  用方向键选择项目文件夹" in output
    assert "/links 1 或 /open 1   打开网页、图片、图表、PDF 或报告" in output
    assert "Readiness  [OK] account ready · [OK] model ready · [OK] workspace ready · server 已配置" in output
    assert "Start      按 Primary Action 补齐缺口；准备好后直接输入投资问题" in output
    assert "xiaoerdata" not in output


def test_command_ribbon_surfaces_ready_shortcuts(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    approve_workspace(project_dir)
    cli = CLI()
    cli._last_agent_plan = {"query": "今天行情怎么样"}
    cli._remember_resource_links("今天行情怎么样", [{"source": "MCP/web_search", "link": "盘面新闻: https://example.com/news"}])

    output = cli._command_ribbon_panel(
        session={"token": "token"},
        llm_ready=True,
        workspace={"allowed": True, "path": str(project_dir)},
    )

    assert "Agent Command Ribbon" in output
    assert "Now       直接输入投资问题开始分析" in output
    assert "Ask       直接输入投资问题 · 本机 LLM 先理解意图，再选择 MCP/web_search" in output
    assert "Verify    /plan · 看服务端状态、工具链路和本轮 Agent 计划" in output
    assert "Create    /chart <标题> :: {json} · 服务端 chart artifact -> 授权工作区" in output
    assert "Recover   /links open 1 · 网页/图片/图表/报告链接收件箱 links[1]" in output
    assert "/tools 查看 MCP playbook" in output


def test_agent_hud_surfaces_recent_resource_shortcut(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    reset_config()

    cli = CLI()
    cli._remember_resource_links("今天行情怎么样", [{"source": "MCP/web_search", "link": "政策新闻: https://example.com/news"}])
    panel = cli._agent_hud_panel(
        session={"token": "token"},
        base_url="https://xiaoerdata.site/api/erlangshen",
        llm_ready=True,
        workspace={"allowed": True, "path": str(tmp_path)},
    )

    assert "links[1]" in panel
    assert "/links open 1 打开最近资源" in panel
    reset_config()


@pytest.mark.asyncio
async def test_setup_command_summarizes_readiness_and_next_actions(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "mimo")
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    reset_config()

    result = await CLI().dispatch("/setup")

    assert "【二郎神初始化向导】" in result
    assert "初始化完成度: 0/3" in result
    assert "首要下一步: /workspace browse 打开路径选择器，或 /workspace path <路径> 手动指定" in result
    assert "workspace" in result
    assert "未授权" in result
    assert "未登录" in result
    assert "mimo" in result
    assert "missing key" in result
    assert "Model Setup" in result
    assert "Project Folder Picker" in result
    assert "choose     /workspace browse 方向键浏览目录，Enter 选择，p 粘贴路径，q 跳过" in result
    assert "manual     /workspace path <路径> 粘贴任意项目文件夹，然后 /workspace allow 授权" in result
    assert "recent     暂无；首次使用建议选择当前项目根目录" in result
    assert "writes     .erlangshen/artifacts 下保存图表、报告、工作记忆和 resources.json" in result
    assert "links      当前项目资源索引 0 条；网页/图片/HTML/PDF 统一进入 /links" in result
    assert "privacy    不会把大模型 API Key、账号 token 或服务端内部认知库写进项目目录" in result
    assert "skip       输入 n/skip 可跳过；未授权时只进行对话和远程接口调用" in result
    assert "Agent Setup Checklist" in result
    assert "agent route" in result
    assert "NL -> local intent -> MCP/search -> server map -> local answer" in result
    assert "未授权前不写入本地项目" in result
    assert "super-66 MCP 优先，web_search 补当天公开事件线索" in result
    assert "intent -> MCP/search -> map -> answer" in result
    assert "provider   mimo (Xiaomi MiMo)" in result
    assert "key        missing MIMO_API_KEY" in result
    assert "/model key 会先本机直连供应商测试，成功后才保存" in result
    assert "Key 只在本机；服务端只接收问题做受保护场景映射" in result
    assert "LLM_PROVIDER=mimo" in result
    assert "/workspace browse 打开路径选择器，或 /workspace path <路径> 手动指定" in result
    assert ".erlangshen/artifacts" in result
    assert "/login xwab <账号>" in result
    assert "/model select" in result
    assert "super-66 MCP" in result
    assert "大模型 API Key 只保存在本机" in result
    assert "/tools" in result
    reset_config()


@pytest.mark.asyncio
async def test_tools_command_exposes_mcp_and_artifact_capabilities():
    result = await CLI().dispatch("/tools")

    assert "【二郎神工具能力地图】" in result
    assert "super-66 MCP" in result
    assert "注册表来源: Super66MCP.list_registry_tools" in result
    assert "super-66 注册表工具:" in result
    assert "search_astocks: 搜索 A股标的" in result
    assert "get_product_history:" in result
    assert "get_index_data" in result
    assert "get_astock_realtime" in result
    assert "search_products" in result
    assert "web_search" in result
    assert "chart_artifact" in result
    assert "/chart <标题>" in result
    assert "资源链接通信" in result
    assert "resource_links" in result
    assert "/links open 1" in result
    assert "/open link 1" in result
    assert "网页、图片、HTML、PDF" in result
    assert "本地 Chrome web_search:" in result
    assert "local_chrome_web_search" in result
    assert "web_search:<query> -> {results:[{title,url,source}], total, provider}" in result
    assert "只在客户端本机调用 Chrome/Chromium" in result
    assert "工具结果契约" in result
    assert "每个 key 形如 tool:label" in result
    assert "web_search 返回 results 数组" in result
    assert "大模型 API Key 只在客户端本机使用" in result
    assert "服务端/客户端通信契约" in result
    assert "server_role: 核心服务端只负责账号鉴权、受保护场景映射、能力边界说明和 chart artifact 生成" in result
    assert "client_role: CLI 客户端负责本机大模型意图理解、super-66 MCP/web_search 数据读取" in result
    assert "llm_key_boundary: 用户的大模型 API Key 只保存在本机并由客户端直连供应商" in result
    assert "mapping_contract:" in result
    assert "artifact_contract:" in result
    assert "workspace_contract: 只有用户授权项目文件夹后，客户端才写入 .erlangshen/artifacts" in result
    assert "resource_contract: 网页、图片、HTML、PDF、图表预览和报告统一转为命名 resource_links" in result
    assert "智能体编排协议:" in result
    assert "decision_owner: 本机大模型是主要编排者" in result
    assert "client_role: 客户端只做工具白名单、参数归一化、授权沙箱、安全脱敏" in result
    assert "不要先写死规则再让模型填空" in result
    assert "不要只按关键词触发固定工具链" in result
    assert "llm_must_return:" in result
    assert "route_summary: 解释你如何理解真实任务" in result
    assert "tool_rationale: 说明为什么选择或不选择 MCP/web_search" in result
    assert "data_strategy: 说明 MCP、web_search、用户数据、服务端映射如何组合" in result
    assert "artifact_plan: 需要图表/报告时说明数据来源、标题和保存边界" in result
    assert "client_may_override_only_when:" in result
    assert "模型返回的工具不在白名单或参数无法归一化" in result
    assert "宽泛行情任务没有任何工具计划" in result
    assert "audit_surface: 所有工具来源、补齐原因、降级和图表计划必须进入 /plan" in result
    assert "工具结果形态" in result
    assert "get_index_data: A股和港股宽基指数历史或最近行情序列" in result
    assert "恒生科技指数" in result
    assert "港股指数优先用 get_index_data" in result
    assert "字段: index_name, date, close, change_pct" in result
    assert "line 用于走势，bar 用于当日/近期涨跌幅对比" in result
    assert "web_search: 公开网页、新闻、公告、标题、摘要和 URL" in result
    assert "工具组合模式" in result
    assert "name_to_realtime_snapshot" in result
    assert "market_snapshot_to_narrative" in result
    assert "product_history_to_risk" in result
    assert "analysis_result_to_resource_links" in result
    assert "mcp_table_to_chart_artifact" in result
    assert "工具: get_index_data -> get_global_asset_data -> web_search -> server map" in result
    assert "读取: index_name/asset_name, date, close/latest, change_pct/pct_chg, title/source/url" in result
    assert "降级: 指数数据失败时保留 web_search 事件线索" in result
    assert "产物: 客户端调用服务端 chart artifact，保存 JSON/HTML，并把链接加入 /links" in result
    assert "Agent Playbook" in result
    assert "market_overview" in result
    assert "single_asset_or_product" in result
    assert "macro_event_cross_asset" in result
    assert "visualization_or_report_followup" in result
    assert "工具链: get_index_data: 沪深300/上证指数/创业板指/恒生科技指数 -> get_global_asset_data: 黄金/美元/原油等跨资产风险偏好参照" in result
    assert "生成的 HTML/JSON/图片/报告路径都加入 /links" in result
    assert "典型数据配方" in result
    assert "market_overview" in result
    assert "single_asset" in result
    assert "macro_event" in result
    assert "visualization_followup" in result
    assert "复用 recent_conversation" in result
    assert "可以这样问:" in result
    assert "今天行情怎么样？先帮我看盘面主线和风险。" in result
    assert "把刚才的资产表现做成图表。" in result
    assert "Agent 编排路线" in result
    assert "market_overview_to_analysis" in result
    assert "server map: 使用 rewritten_query 做受保护场景映射" in result
    assert "analysis_to_chart_artifact" in result
    assert "授权工作区后保存 JSON/HTML 到 .erlangshen/artifacts" in result


def test_mcp_catalog_includes_super66_registry_tools():
    catalog = CLI()._mcp_capability_catalog("今天行情怎么样")
    registry_names = {item["name"] for item in catalog["registry_tools"]}

    assert catalog["registry_source"] == "Super66MCP.list_registry_tools"
    assert "search_astocks" in registry_names
    assert "get_astock_realtime" in registry_names
    assert "get_product_history" in registry_names
    assert set(catalog["tool_names"]) == registry_names
    assert registry_names.issubset(CLI()._allowed_super66_tools())
    assert "composition_patterns" in catalog
    assert "agent_playbook" in catalog
    playbook_tasks = {item["task"] for item in catalog["agent_playbook"]}
    assert "market_overview" in playbook_tasks
    assert "single_asset_or_product" in playbook_tasks
    assert "macro_event_cross_asset" in playbook_tasks
    assert "visualization_or_report_followup" in playbook_tasks
    pattern_names = {item["name"] for item in catalog["composition_patterns"]}
    assert "market_snapshot_to_narrative" in pattern_names
    assert "mcp_table_to_chart_artifact" in pattern_names


@pytest.mark.asyncio
async def test_doctor_command_reports_local_readiness(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "mimo")
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    reset_config()

    cli = CLI()
    monkeypatch.setattr(cli, "_system_open_command", lambda: None)
    monkeypatch.setattr(cli, "_local_chrome_search_ready", lambda: (False, "optional Playwright not installed"))
    result = await cli.dispatch("/doctor")

    assert "【二郎神本地诊断】" in result
    assert "不会把大模型 API Key 发给服务端" in result
    assert "核心就绪度:" in result
    assert "首要修复: workspace -> /workspace browse 或 /workspace path <路径> && /workspace allow" in result
    assert "NEED workspace" in result
    assert "NEED account" in result
    assert "NEED model" in result
    assert "super-66 MCP" in result
    assert "NEED web_search" in result
    assert "optional Playwright not installed" in result
    assert "python3 -m pip install playwright" in result
    assert "生产链路矩阵:" in result
    assert "fix   account: XWAB/XCZT 登录态，保护服务端映射和 super-66 MCP 鉴权" in result
    assert "fix   model: 本机大模型负责意图理解、工具编排和最终自然语言分析" in result
    assert "fix   workspace: 项目沙箱用于保存报告、图表、JSON 和资源索引" in result
    assert "setup web_search: 补充当天新闻、公告、网页和图片入口，作为 MCP 未覆盖的信息线索" in result
    assert "fix   chart artifact: 服务端生成或客户端保存图表 HTML/JSON，并返回可打开名称链接" in result
    assert "ready resource links: 网页、图片、HTML、PDF、图表和报告统一进入可点击资源入口" in result
    assert "command: /links 查看；/links 1 或 /open 1 直接打开" in result
    assert "boundary: 终端不内嵌富文本或二进制内容，只展示名称和 URL/路径" in result
    assert "服务端不接收用户的大模型 API Key" in result
    assert "本地 Chrome web_search:" in result
    assert "补充 super-66 MCP 不覆盖的新闻、公告、网页、图片入口和最新事件线索" in result
    assert "results/title/url 会进入 MCP 快照" in result
    assert "网页、图片、HTML、PDF 会进入 /links 和 /open 资源入口" in result
    assert "资源和图表:" in result
    assert "服务器、MCP、web_search 或本机大模型返回网页/图片/HTML/PDF 时" in result
    assert "近期资源: /links；直接打开: /links 1 或 /open 1；图表产物: /artifacts 或 /open chart" in result
    assert "资源索引会保存为 resources.json" in result
    assert "Agent UX:" in result
    assert "slash picker" in result
    assert "workspace browser" in result
    assert "context memory" in result
    assert "agent trace" in result
    assert "chart preview" in result
    assert "server panels" in result
    assert "交互能力: 6/6 项可用" in result
    assert "/setup run" in result
    reset_config()


@pytest.mark.asyncio
async def test_brief_command_summarizes_session_capabilities(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-secret")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)
    monkeypatch.setattr("src.cli.load_auth_session", lambda: {"token": "token", "user": {"username": "小二MCP助手"}})
    reset_config()

    cli = CLI()
    cli._last_agent_plan = {"query": "今天行情怎么样"}
    cli._last_mcp_data = {"get_index_data:沪深300": {"index_name": "沪深300", "change_pct": 1.2}}
    cli._last_artifact_results = [{"title": "指数快照对比", "status": "success", "type": "chart"}]
    cli._remember_resource_links("今天行情怎么样", [{"source": "MCP/web_search", "link": "政策新闻: https://example.com/news"}])

    result = await cli.dispatch("/brief")

    assert "【二郎神会话能力摘要】" in result
    assert "模型: deepseek" in result
    assert "工作区:" in result
    assert "已授权" in result
    assert "最近计划: 今天行情怎么样" in result
    assert "上轮 MCP: get_index_data:沪深300" in result
    assert "最近产物: 指数快照对比" in result
    assert "最近资源: 1 个可打开链接" in result
    assert "account: OK" in result
    assert "model: OK" in result
    assert "workspace: OK" in result
    assert "mcp: OK" in result
    assert "chart: OK" in result
    assert "Agent 回合就绪度:" in result
    assert "- Ask: ready · 直接输入自然语言问题" in result
    assert "- Think: ready · 本机大模型负责意图、工具组合和最终分析" in result
    assert "- Data: ready · super-66 MCP 优先；上一轮 get_index_data:沪深300" in result
    assert "- Map: ready · 服务端只做受保护场景映射和 chart artifact" in result
    assert "- Build: ready · 图表/报告保存到授权工作区；最近 指数快照对比" in result
    assert "- Open: ready · 1 links · /links 1 或 /open 1 打开网页、图片、图表和报告" in result
    assert "- Sandbox: ready · API Key/token 不写入项目目录" in result
    assert "今天行情怎么样？先帮我看盘面主线和风险。" in result
    assert "/server goals" in result
    assert "/links" in result
    assert "/artifacts" in result
    assert "API Key 只在本机直连供应商" in result
    reset_config()


@pytest.mark.asyncio
async def test_examples_command_teaches_natural_language_prompts():
    result = await CLI().dispatch("/examples")

    assert "【二郎神提问范例】" in result
    assert "直接输入自然语言即可" in result
    assert "super-66 MCP/web_search" in result
    assert "复制一个开场:" in result
    assert "1. 今天行情怎么样？先帮我看盘面主线和风险。" in result
    assert "路线: 市场概览: super-66 MCP 指数/全球资产 + web_search + 服务端场景映射" in result
    assert "4. 把刚才的资产表现做成图表。" in result
    assert "路线: 产物生成: 复用 recent_conversation/MCP，服务端 chart artifact 保存到工作区" in result
    assert "市场概览:" in result
    assert "今天行情怎么样？先帮我看盘面主线和风险。" in result
    assert "路线: super-66 MCP 指数/全球资产 + web_search + 服务端场景映射" in result
    assert "单资产/产品:" in result
    assert "帮我看一下贵州茅台今天怎么走。" in result
    assert "search_astocks/get_astock_realtime" in result
    assert "组合和风控:" in result
    assert "给我一个更偏执行的版本" in result
    assert "图表/报告:" in result
    assert "把刚才的资产表现做成图表。" in result
    assert "服务端生成 chart artifact" in result
    assert "追问方式:" in result
    assert "那如果换成港股呢" in result
    assert "API Key 只在本机使用" in result
    assert "不暴露内部认知库全文" in result


@pytest.mark.asyncio
async def test_plan_command_shows_empty_state_before_analysis():
    result = await CLI().dispatch("/plan")

    assert "【最近一次分析计划】" in result
    assert "暂无记录" in result
    assert "/advice <问题>" in result


@pytest.mark.asyncio
async def test_plan_command_shows_recent_resource_links():
    cli = CLI()
    cli._last_agent_plan = {
        "query": "今天行情怎么样",
        "intent": "market_overview",
        "tone": "natural_analyst",
        "rewritten_query": "今天行情怎么样",
        "mapping_query": "今天行情怎么样",
        "route_summary": "读取行情后回答",
        "tool_rationale": "需要事实数据",
        "data_strategy": "MCP + web_search",
        "data_confidence": "medium",
        "provider": "Xiaomi MiMo",
        "model": "mimo-v2.5",
        "key_boundary": "API Key 仅本机直连供应商，未发送给二郎神服务端",
        "route_source": "local_llm",
        "tool_selection_source": "local_llm",
        "tool_selection_note": "本机大模型选择市场快照工具",
        "composition_patterns_used": ["market_snapshot_to_narrative"],
        "artifact_plan": {"type": "chart", "title": "市场快照对比"},
        "resource_links": [
            {"source": "MCP/web_search", "link": "政策新闻: https://example.com/news"},
            {"source": "local report", "link": "打开报告: file:///tmp/report.md"},
        ],
    }

    result = await cli.dispatch("/plan")

    assert "资源呈现: 命名链接 + /links 1 或 /open 1" in result
    assert "打开命令: /links 1, /open 1" in result
    assert "编排审计:" in result
    assert "- 决策者: 本机大模型" in result
    assert "- 客户端兜底: 否 · 本机大模型选择市场快照工具" in result
    assert "可复盘字段: route_summary / tool_rationale / data_strategy / composition_patterns_used / artifact_plan" in result
    assert "安全边界: API Key 仅本机直连供应商，未发送给二郎神服务端" in result
    assert "产物与资源: artifact_plan=chart · resource_links=2 · /links 1 或 /open 1 打开" in result
    assert "本轮可打开资源:" in result
    assert "1. MCP/web_search: 政策新闻: https://example.com/news" in result
    assert "2. local report: 打开报告: file:///tmp/report.md" in result
    assert "本轮 Playbook:" in result
    assert "- market_overview: 回答“今天行情/盘面/市场主线/风险偏好”这类宽泛问题" in result
    assert "工具链: get_index_data: 沪深300/上证指数/创业板指/恒生科技指数 -> get_global_asset_data" in result
    assert "新闻、政策原文、图片、图表页面必须转成 resource_links" in result
    assert "/links 查看最近网页、图片、图表和报告名称链接；/links open 1 直接打开第一个资源" in result


@pytest.mark.asyncio
async def test_server_commands_panel_exposes_service_subcommands():
    result = await CLI().dispatch("/server commands")
    default_result = await CLI().dispatch("/server")

    assert "【服务端命令面板】" in result
    assert result == default_result
    assert "Server Workbench" in result
    assert "输入 /server 后加空格" in result
    assert "任务入口:" in result
    assert "1 健康与账号" in result
    assert "2 完整分析" in result
    assert "3 只看映射" in result
    assert "4 图表产物" in result
    assert "5 排障复盘" in result
    assert "/plan 复盘工具选择" in result
    assert "/links 1 或 /open 1" in result
    assert "服务端决策矩阵:" in result
    assert "健康检查 · 需要: server base url" in result
    assert "命令: /server health -> /server status" in result
    assert "账号权限 · 需要: XWAB/XCZT token" in result
    assert "命令: /login xwab <账号> -> /server me" in result
    assert "完整分析 · 需要: 本机大模型 Key + MCP 数据 + 服务端映射" in result
    assert "命令: 直接输入自然语言问题" in result
    assert "图表报告 · 需要: 授权工作区 + 结构化数据" in result
    assert "服务端 chart artifact -> 客户端保存 HTML/JSON -> /links 打开" in result
    assert "资源打开 · 需要: resource_links 或已保存产物" in result
    assert "命令: /links 1、/open 1、/open chart" in result
    assert "/server status" in result
    assert "/server me" in result
    assert "/server map <问题>" in result
    assert "/server advice <问题>" in result
    assert "/server guide" in result
    assert "/server goals" in result
    assert "/server actions" in result
    assert "/server flow" in result
    assert "/server artifact" in result
    assert "/server resources" in result
    assert "/server capabilities" in result
    assert "不会暴露内部认知库全文" in result
    assert "直接输入自然语言问题" in result
    assert "资源呈现" in result
    assert "服务端/客户端通信契约:" in result
    assert "服务端返回: health/status/me、protected map、chart artifact、resource links" in result
    assert "客户端负责: 本机大模型、super-66 MCP/web_search、工作区保存、/links 和 /open 打开" in result


@pytest.mark.asyncio
async def test_server_commands_panel_aligns_chinese_columns():
    result = await CLI().dispatch("/server commands")
    lines = result.splitlines()
    task_rows = [
        line for line in lines
        if line.startswith("- ") and any(label in line for label in ["健康与账号", "完整分析", "只看映射", "图表产物", "排障复盘"])
    ]
    assert len(task_rows) == 5
    task_actions = [
        "/server status",
        "直接输入自然语言问题",
        "/server map",
        "/server artifact",
        "/server actions",
    ]
    task_widths = [_display_width(row.split(action, 1)[0]) for row, action in zip(task_rows, task_actions)]
    assert len(set(task_widths)) == 1

    command_checks = [
        ("/server guide", "不知道该用哪个命令时"),
        ("/server status", "服务端状态"),
        ("/server flow", "查看客户端"),
        ('/chart <标题> :: {"A股":1.2}', "请求服务端生成结构化图表"),
    ]
    command_widths = []
    for command, desc in command_checks:
        row = next(line for line in lines if line.startswith(f"- {command}"))
        command_widths.append(_display_width(row.split(desc, 1)[0]))
    assert len(set(command_widths)) == 1


def test_server_status_formats_next_actions_and_key_boundary():
    result = ServerCommand(None, None)._format_status({
        "service": "erlangshen",
        "version": "0.1.7",
        "auth": {
            "enabled": True,
            "mode": "xwab",
            "user": {},
            "access": {"label": "游客", "tier": "guest"},
        },
        "llm": {"display_name": "DeepSeek", "model": "deepseek-chat", "api_key_configured": False},
        "user_llm_key_policy": {"accepted_by_server": False},
        "cognition": {"protected": False, "matching_enabled": True, "advice_enabled": True},
    })

    assert "【二郎神服务端状态】" in result
    assert "下一步:" in result
    assert "/login xwab <账号>" in result
    assert "/model key 在本机配置大模型 Key" in result
    assert "服务端不会接收用户 Key" in result
    assert "/server capabilities" in result
    assert "客户端会先取 MCP 数据" in result
    assert "/server actions" in result


def test_server_me_formats_next_actions():
    result = ServerCommand(None, None)._format_me({
        "user": {"username": "小二MCP助手", "role": "user", "loginEntry": "xwab"},
        "access": {"label": "标准", "tier": "standard"},
    })

    assert "【服务端账号】" in result
    assert "小二MCP助手" in result
    assert "下一步:" in result
    assert "super-66 MCP" in result
    assert "/server actions" in result

    guest = ServerCommand(None, None)._format_me({"user": {}, "access": {}})

    assert "未绑定" in guest
    assert "/login xwab <账号>" in guest
    assert "/server status" in guest


def test_server_health_formats_next_actions():
    result = ServerCommand(None, None)._format_health({"status": "ok"})

    assert "【服务端健康检查】" in result
    assert "- status: ok" in result
    assert "/server status 查看鉴权" in result
    assert "客户端会先取 MCP 数据" in result
    assert "/server actions 或 /doctor" in result


def test_server_map_formats_usage_guidance():
    result = ServerCommand(None, None)._format_map({
        "matches": [
            {
                "scene": "市场监测与事件响应",
                "orientation": "risk_asset",
                "confidence": 0.82,
                "protection": "public_match_only",
                "case_hint": "只返回公开提示",
            }
        ]
    })

    assert "【服务端场景映射】" in result
    assert "市场监测与事件响应" in result
    assert "怎么使用这个映射:" in result
    assert "服务端不会暴露内部认知库全文" in result
    assert "/advice <问题>" in result
    assert "/plan" in result


def test_server_map_guides_when_no_match():
    result = ServerCommand(None, None)._format_map({"matches": []})

    assert "未命中明确场景" in result
    assert "补充市场、标的、时间周期" in result
    assert "客户端先取 MCP 数据" in result


@pytest.mark.asyncio
async def test_server_flow_capabilities_and_artifact_panels_are_discoverable():
    guide = await CLI().dispatch("/server guide")
    goals = await CLI().dispatch("/server goals")
    actions = await CLI().dispatch("/server actions")
    flow = await CLI().dispatch("/server flow")
    capabilities = await CLI().dispatch("/server capabilities")
    artifact = await CLI().dispatch("/server artifact")
    resources = await CLI().dispatch("/server resources")

    assert "【服务端交互工作台】" in guide
    assert "按当前任务选择路径" in guide
    assert "/service 或 /server status" in guide
    assert "/server map <问题>" in guide
    assert "super-66 MCP / web_search" in guide
    assert "/plan" in guide
    assert "大模型 API Key 只在客户端本机使用" in guide
    assert "/server actions" in guide

    assert "【服务端目标选择器】" in goals
    assert "确认服务是否在线" in goals
    assert "确认账号和权限" in goals
    assert "完整回答投资问题" in goals
    assert "只检查服务端怎么理解问题" in goals
    assert "生成图表或报告" in goals
    assert "排查数据和工具链路" in goals
    assert "本机大模型决定 MCP/web_search/服务端映射如何组合" in goals
    assert "chart artifact" in goals
    assert "API Key 只在本机" in goals

    assert "【服务端行动面板】" in actions
    assert "我想确认服务能不能用" in actions
    assert "/server health" in actions
    assert "我想把结果做成图表或报告" in actions
    assert "/workspace browse" in actions
    assert "/chart <标题>" in actions
    assert "不发送给服务端" in actions

    assert "【服务端协作流程】" in flow
    assert "本机大模型理解上下文" in flow
    assert "super-66 MCP / web_search" in flow
    assert "chart artifact" in flow
    assert "API Key 只在本机" in flow
    assert "服务端/客户端通信契约:" in flow
    assert "图表传输: 服务端返回 JSON/HTML/图片/网页等 artifact 元数据" in flow

    assert "【服务端能力边界】" in capabilities
    assert "不接收、不存储、不转发" in capabilities
    assert "resource links" in capabilities
    assert "命名链接呈现和打开" in capabilities
    assert "客户端负责: 本机大模型、super-66 MCP/web_search、工作区保存、/links 和 /open 打开" in capabilities
    assert "/tools" in capabilities
    assert "/plan" in capabilities

    assert "【服务端图表 Artifact 通信】" in artifact
    assert "/chart 资产表现" in artifact
    assert "兼容输入:" in artifact
    assert "artifacts / charts / visualizations / chart_requests / artifact_requests" in artifact
    assert "labels+values" in artifact
    assert "series 列表" in artifact
    assert "缺少数值数据时客户端会跳过生成" in artifact
    assert "/links open 1" in artifact
    assert "/open link 1" in artifact
    assert ".erlangshen/artifacts/charts" in artifact
    assert "资源传输: 网页、图片、HTML、PDF、报告统一归一化为 label/target/type" in artifact
    assert "/open" in artifact

    assert "【服务端资源通信】" in resources
    assert "resource_links" in resources
    assert "label: 用户看到的名称" in resources
    assert "target: 可打开目标" in resources
    assert "type: webpage / image / chart_image / html / pdf / report / json / local_file" in resources
    assert "link: 兼容旧格式" in resources
    assert "/links 1" in resources
    assert "/open link 1" in resources
    assert ".erlangshen/artifacts/resources.json" in resources
    assert "url/link/href/web_url/source_url" in resources
    assert "image_url/thumbnail/preview_url" in resources
    assert "不应包含 token、secret、password" in resources


@pytest.mark.asyncio
async def test_setup_run_guides_non_interactive_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    reset_config()

    result = await CLI().dispatch("/setup run")

    assert "【执行式初始化】" in result
    assert "当前不是交互终端" in result
    assert "erlangshen /setup workspace" in result
    assert "erlangshen /workspace path <项目路径>" in result
    assert "erlangshen /workspace use <项目路径>" in result
    assert "erlangshen /model key" in result
    reset_config()


@pytest.mark.asyncio
async def test_setup_workspace_guides_non_interactive_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))

    result = await CLI().dispatch("/setup workspace")

    assert "【项目文件夹初始化】" in result
    assert "当前不是交互终端" in result
    assert "erlangshen /setup workspace" in result
    assert "erlangshen /workspace path <项目路径>" in result
    assert "erlangshen /workspace allow" in result


@pytest.mark.asyncio
async def test_setup_run_selects_and_authorizes_workspace(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    default_dir = tmp_path / "default"
    selected_dir = tmp_path / "selected"
    default_dir.mkdir()
    selected_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(default_dir))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    reset_config()

    cli = CLI()
    monkeypatch.setattr(cli, "_read_workspace_path_selection", lambda workspace: str(selected_dir))
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    result = await cli.dispatch("/setup run")

    assert "【二郎神初始化执行】" in result
    assert f"工作区: 已授权 {selected_dir}" in result
    assert "- 初始化完成度:" in result
    assert "- 首要下一步: /login xwab <账号> 登录服务端和 super-66 MCP" in result
    assert "Agent Setup Checklist" in result
    assert "写入仅限授权项目" in result
    assert ".erlangshen/artifacts" in result
    assert "intent -> MCP/search -> map -> answer" in result
    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)
    assert workspace_status()["path"] == str(selected_dir)
    assert workspace_status()["allowed"] is True
    reset_config()


@pytest.mark.asyncio
async def test_setup_workspace_can_replace_existing_authorized_workspace(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    old_dir = tmp_path / "old"
    selected_dir = tmp_path / "selected"
    old_dir.mkdir()
    selected_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(old_dir))
    approve_workspace(old_dir)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    cli = CLI()
    monkeypatch.setattr(cli, "_read_workspace_path_selection", lambda workspace: str(selected_dir))
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    result = await cli.dispatch("/setup workspace")

    assert "【项目文件夹初始化】" in result
    assert f"工作区: 已授权 {selected_dir}" in result
    assert "下一步: /setup run" in result
    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)
    assert workspace_status()["path"] == str(selected_dir)
    assert workspace_status()["allowed"] is True


@pytest.mark.asyncio
async def test_setup_run_workspace_forces_workspace_selection(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    old_dir = tmp_path / "old"
    selected_dir = tmp_path / "selected"
    old_dir.mkdir()
    selected_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(old_dir))
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    approve_workspace(old_dir)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    reset_config()

    cli = CLI()
    monkeypatch.setattr(cli, "_read_workspace_path_selection", lambda workspace: str(selected_dir))
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    result = await cli.dispatch("/setup run workspace")

    assert f"工作区: 已授权 {selected_dir}" in result
    assert "Agent Setup Checklist" in result
    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)
    assert workspace_status()["path"] == str(selected_dir)
    assert workspace_status()["allowed"] is True
    reset_config()


def test_workspace_path_selection_falls_back_to_input(monkeypatch, tmp_path):
    cli = CLI()
    selected_dir = tmp_path / "selected"
    monkeypatch.setattr(cli, "_prompt_toolkit_available", lambda: False)
    monkeypatch.setattr("builtins.input", lambda prompt: str(selected_dir))

    selected = cli._read_workspace_path_selection(tmp_path / "current")

    assert selected == str(selected_dir)


def test_main_prints_version(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["erlangshen", "--version"])

    main()

    assert capsys.readouterr().out.strip() == "0.1.39"


def test_startup_workspace_arg_sets_project_directory(monkeypatch, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)
    monkeypatch.delenv("ERLANGSHEN_LAUNCH_CWD", raising=False)
    monkeypatch.setattr("sys.argv", ["erlangshen", "--cd", str(project), "--version"])

    main()

    assert capsys.readouterr().out.strip() == "0.1.39"
    assert Path.cwd() == project.resolve()
    assert workspace_status()["path"] == str(project.resolve())


def test_extract_startup_workspace_args_supports_codex_style_cd():
    workspace, remaining = _extract_startup_workspace_args(["--cd=/tmp/demo", "/status"])

    assert workspace == "/tmp/demo"
    assert remaining == ["/status"]


@pytest.mark.asyncio
async def test_model_help_guides_api_key_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "kimi")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    reset_config()

    result = await CLI().dispatch("/model")

    assert "【大模型配置】" in result
    assert "配置状态: missing key" in result
    assert "首要下一步: /model select 选择供应商和型号，然后 /model key 测试并保存 KIMI_API_KEY" in result
    assert "当前 provider: kimi" in result
    assert "API key: 未配置" in result
    assert "Model Agent Flow" in result
    assert "role       本机大模型负责意图理解、MCP 工具组合、自然投资分析" in result
    assert "facts      super-66 MCP/web_search 提供行情、产品、新闻和网页线索" in result
    assert "core       服务端只做受保护场景映射和 chart artifact，不接收模型 Key" in result
    assert "flow       /model select -> /model key -> 直接输入投资问题" in result
    assert "Model Setup" in result
    assert "provider   kimi (Kimi / Moonshot)" in result
    assert "test       /model key 会先本机直连供应商测试，成功后才保存" in result
    assert "boundary   Key 只在本机；服务端只接收问题做受保护场景映射" in result
    assert "commands   /model select -> /model key" in result
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


def test_model_picker_render_shows_provider_and_model_details(capsys):
    cli = CLI()
    provider_items = [
        ("openai", "OpenAI", "OPENAI_API_KEY / 默认 gpt-5.2"),
        ("mimo", "Xiaomi MiMo", "MIMO_API_KEY / 默认 mimo-v2.5-pro"),
    ]

    cli._render_model_picker("选择大模型供应商", provider_items, 1)
    provider_output = capsys.readouterr().out

    assert "选择大模型供应商" in provider_output
    assert "选中: Xiaomi MiMo (mimo)" in provider_output
    assert "Key: MIMO_API_KEY" in provider_output
    assert "Model: MIMO_MODEL" in provider_output
    assert "API Key 只保存在本机" in provider_output
    assert "下一步: Enter 选择供应商，再选择模型，随后 /model key 本机测试保存" in provider_output

    model_items = [
        ("mimo-v2.5-pro", "MiMo V2.5 Pro", "复杂推理、长文档、Agent 和 Coding"),
        ("mimo-v2-flash", "MiMo V2 Flash", "高并发、低成本、快速响应"),
    ]
    cli._render_model_picker("选择 Xiaomi MiMo 模型", model_items, 0)
    model_output = capsys.readouterr().out

    assert "选中: MiMo V2.5 Pro (mimo-v2.5-pro)" in model_output
    assert "Provider: Xiaomi MiMo" in model_output
    assert "默认模型" in model_output
    assert "用途: 复杂推理、长文档、Agent 和 Coding" in model_output
    assert "Key: MIMO_API_KEY 只在本机；下一步 /model key 测试连接后保存" in model_output


def test_model_picker_uses_display_width_for_chinese_rows(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("src.cli._terminal_width", lambda: 96)
    cli = CLI()
    items = [
        ("kimi", "Kimi / Moonshot", "KIMI_API_KEY / 默认 kimi-k2.6"),
        ("mimo", "Xiaomi MiMo 小米", "MIMO_API_KEY / 默认 mimo-v2.5-pro"),
        ("claude", "Claude Anthropic", "ANTHROPIC_API_KEY / 默认 claude-sonnet-4-6"),
    ]

    cli._render_model_picker("选择大模型供应商", items, 1)
    output = capsys.readouterr().out

    framed_lines = [line for line in output.splitlines() if line.startswith(("╭", "│", "├", "╰"))]
    widths = [_display_width(line) for line in framed_lines]
    assert len(set(widths)) == 1
    assert "Xiaomi MiMo 小米" in output
    assert "API Key 只保存在本机" in output


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
                assert "recent_conversation" in payload
                assert "昨天的红利问题" in payload
                assert "is_followup" in payload
                assert "followup_target" in payload
                return (
                    '{"intent":"market_overview","needs_server_mapping":true,"needs_mcp":false,'
                    '"mcp_tools":[],"rewritten_query":"A股怎么看",'
                    '"is_followup":true,"followup_target":"昨天的红利问题"}'
                )
            assert "server_protected_matches" in payload
            assert "client_intent_plan" in payload
            assert "recent_conversation" in payload
            assert "昨天的红利问题" in payload
            return '{"view":"模型综合判断","suggestions":["降低单点暴露"],"risk_controls":["控制回撤"],"missing_data":["持仓"]}'

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            return {"tool": tool_name, **(arguments or {})}

    async def fake_search(self, query, arguments):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "市场新闻"}]}

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)
    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    cli._remember_conversation_turn("昨天的红利问题", "先看利率和拥挤度。")
    result = await cli.dispatch("/advice A股怎么看")

    assert "我先按“A股怎么看”来理解" in result
    assert "服务端场景：市场监测与事件响应" not in result
    assert "本机模型：DeepSeek / deepseek-v4-flash" not in result
    assert "大模型 API Key 只在本机直连供应商" not in result
    assert "降低单点暴露" in result
    plan = await cli.dispatch("/plan")
    assert "路由来源: 本机大模型意图理解" in plan
    assert "上下文追问: 是 / 昨天的红利问题" in plan
    assert "工具理由: 该问题需要先读取行情/事件数据" in plan
    assert "数据策略: 优先读取 super-66 MCP 行情" in plan
    reset_config()


@pytest.mark.asyncio
async def test_client_side_advice_server_failure_keeps_agent_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-secret")
    reset_config()

    from src.client.server_client import ErlangshenAPIError

    class FakeServerClient:
        def __init__(self, **kwargs):
            pass

        async def cognition_map(self, query):
            raise ErlangshenAPIError(401, "Unauthorized")

    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            return (
                '{"intent":"market_overview","needs_server_mapping":true,"needs_mcp":true,'
                '"mcp_tools":[{"name":"get_index_data","arguments":{"index_name":"沪深300","limit":60}}],'
                '"rewritten_query":"今天A股市场情况怎么样"}'
            )

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            return {"index_name": "沪深300", "change_pct": 1.23}

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)
    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)

    result = await CLI().dispatch("今天市场情况怎么样")

    assert "服务端场景映射失败 (401): Unauthorized" in result
    assert "本轮执行：" in result
    assert "- 本机理解问题意图" in result
    assert "- 读取 super-66 MCP / 本地网页线索" in result
    assert "- 读取数据工具: get_index_data / 沪深300" in result
    assert "- 向服务端确认改写后的问题场景" in result
    assert "大模型 API Key 没有发送给服务端" in result
    assert "/login xwab <账号>" in result
    assert "/service" in result

    plan = await CLI().dispatch("/plan")
    assert "暂无记录" in plan

    cli = CLI()
    result = await cli.dispatch("今天市场情况怎么样")
    plan = await cli.dispatch("/plan")
    assert "服务端场景映射失败 (401): Unauthorized" in result
    assert "状态: 失败 / server_mapping" in plan
    assert "失败原因: 服务端场景映射失败 (401): Unauthorized" in plan
    assert "重写问题: 今天A股市场情况怎么样" in plan
    assert "服务端映射问题: 今天A股市场情况怎么样" in plan
    assert "实际 MCP 数据键: get_index_data:沪深300" in plan
    assert "执行过程: 本机理解问题意图；读取 super-66 MCP / 本地网页线索；读取数据工具: get_index_data / 沪深300；向服务端确认改写后的问题场景" in plan
    assert "服务端命中场景: 未返回" in plan
    assert "/login xwab <账号> 重新登录" in plan
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
            assert query == "今天A股市场情况怎么样"
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
                assert "tool_rationale" in payload
                assert "data_strategy" in payload
                assert "selection_policy" in payload
                assert "routing_contract" in payload
                assert "local_llm_context_router" in payload
                assert "不要只因为出现某个关键词就固定路由" in payload
                assert "client_fallback_boundary" in payload
                assert "flexible_tool_spec" in payload
                assert "OpenAI tool_calls 风格" in payload
                assert "local_web_search" in payload
                assert "data_recipes" in payload
                assert "route_plans" in payload
                assert "composition_patterns" in payload
                assert "market_snapshot_to_narrative" in payload
                assert "mcp_table_to_chart_artifact" in payload
                assert "market_overview_to_analysis" in payload
                assert "server map: 使用 rewritten_query 做受保护场景映射" in payload
                assert "analysis_to_chart_artifact" in payload
                return (
                    '{"intent":"market_overview","needs_server_mapping":true,"needs_mcp":true,'
                    '"mcp_tools":[{"name":"get_index_data","arguments":{"index_name":"沪深300","limit":60}}],'
                    '"rewritten_query":"今天A股市场情况怎么样",'
                    '"route_summary":"用户在问宽泛盘面，需要先拿指数快照再给方向判断",'
                    '"tool_rationale":"宽泛行情问题优先读取指数快照",'
                    '"data_strategy":"先取 super-66 MCP 行情，再做服务端场景映射和本机分析",'
                    '"data_confidence":"medium",'
                    '"chart_opportunity":true,'
                    '"chart_rationale":"指数快照适合做涨跌幅对比",'
                    '"artifact_plan":{"type":"chart","title":"指数快照对比","data_hint":"沪深300涨跌幅","save_to_workspace":true},'
                    '"missing_inputs":["用户持仓","关注周期"]}'
                )
            assert "沪深300" in payload
            assert "change_pct" in payload
            assert "用户在问宽泛盘面" in payload
            assert "宽泛行情问题优先读取指数快照" in payload
            assert "先取 super-66 MCP 行情" in payload
            assert "chart_opportunity" in payload
            assert "artifact_plan" in payload
            assert "指数快照对比" in payload
            return '{"view":"结合实时数据看，A股今天偏强。","suggestions":["先看主线"],"risk_controls":["别追高"],"missing_data":[]}'

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)
    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)

    cli = CLI()
    result = await cli.dispatch("今天市场情况怎么样")

    assert "结合实时数据看" in result
    assert "先看主线" in result
    assert "服务端场景：市场监测与事件响应" not in result
    assert "本轮执行：" not in result
    assert "Agent Trail：" not in result
    plan = await cli.dispatch("/plan")
    assert "【最近一次分析计划】" in plan
    assert "market_overview" in plan
    assert "路由来源: 本机大模型意图理解" in plan
    assert "重写问题: 今天A股市场情况怎么样" in plan
    assert "服务端映射问题: 今天A股市场情况怎么样" in plan
    assert "路由摘要: 用户在问宽泛盘面，需要先拿指数快照再给方向判断" in plan
    assert "工具理由: 宽泛行情问题优先读取指数快照" in plan
    assert "数据策略: 先取 super-66 MCP 行情，再做服务端场景映射和本机分析" in plan
    assert "数据充分度: medium" in plan
    assert "图表机会: 建议 / 指数快照适合做涨跌幅对比" in plan
    assert "产物计划: chart / 指数快照对比 / 沪深300涨跌幅 / 保存到授权项目文件夹" in plan
    assert "路由层认为还缺:" in plan
    assert "- 用户持仓" in plan
    assert "建议下一步:" in plan
    assert "继续说“把指数快照对比做成图表”" in plan
    assert "补充路由层认为还缺的信息后继续追问" in plan
    assert "get_index_data" in plan
    assert "沪深300" in plan
    assert "工具链路解释:" in plan
    assert "get_index_data / 沪深300: 已返回" in plan
    assert "用途: A股指数、港股宽基指数、市场整体、沪深300、上证指数、创业板指、恒生科技指数、恒生指数等行情问题" in plan
    assert '参数: {"index_name": "沪深300", "limit": 60}' in plan
    assert "数据键: get_index_data:沪深300" in plan
    assert "MCP 快照" in plan
    assert "涨跌幅 1.23" in plan
    assert "执行过程" in plan
    assert "本机理解问题意图" in plan
    assert "读取数据工具: get_index_data / 沪深300" in plan
    assert "向服务端确认改写后的问题场景" in plan
    assert "市场监测与事件响应" in plan
    assert "DeepSeek / deepseek-v4-flash" in plan
    assert "API Key 仅本机直连供应商" in plan
    reset_config()


@pytest.mark.asyncio
async def test_client_side_advice_materializes_llm_chart_artifact(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-secret")
    approve_workspace(project_dir)
    reset_config()

    class FakeServerClient:
        def __init__(self, **kwargs):
            pass

        async def cognition_map(self, query):
            return {"matches": [{"scene": "市场监测与事件响应", "confidence": 0.9}]}

        async def chart_artifact(self, chart_type, title, data, width=960, height=540, metadata=None):
            return {
                "artifact": {
                    "type": chart_type,
                    "title": title,
                    "data": data,
                    "html_url": "https://cdn.example.com/asset-chart.html",
                    "image_url": "https://cdn.example.com/asset-chart.png",
                    "metadata": {"source": "erlangshen-server"},
                }
            }

    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            payload = messages[-1]["content"]
            if "allowed_mcp_tools" in payload:
                return '{"intent":"market_overview","needs_server_mapping":true,"needs_mcp":false,"mcp_tools":[],"rewritten_query":"资产表现"}'
            return (
                '{"view":"我会把资产表现做成一张图。","suggestions":["看相对强弱"],'
                '"risk_controls":["别只看单日涨跌"],"missing_data":[],'
                '"artifacts":[{"type":"chart","chart_type":"bar","title":"资产表现","data":{"A股":1.2,"黄金":0.8}}]}'
            )

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            return {"tool": tool_name, **(arguments or {})}

    async def fake_search(self, query, arguments):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "市场新闻"}]}

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.llm.LLMClient", FakeLLMClient)
    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    result = await cli.dispatch("资产表现怎么样")
    links = await cli.dispatch("/links")

    assert "图表：" in result
    assert "资产表现: 已生成" in result
    assert "终端预览:" in result
    assert "A股" in result
    assert "黄金" in result
    assert "|" in result
    assert "打开: 资产表现 HTML" in result
    assert "JSON" not in result
    assert "资源: 资产表现: https://cdn.example.com/asset-chart.html" in result
    assert "资源: 资产表现 图片: https://cdn.example.com/asset-chart.png" in result
    assert "产物收件箱：" not in result
    assert "server artifact · 资产表现怎么样" in links
    assert "资产表现: https://cdn.example.com/asset-chart.html" in links
    assert "资产表现 图片: https://cdn.example.com/asset-chart.png" in links
    assert "local artifact · 资产表现怎么样" in links
    assert "资产表现 HTML: file://" in links
    assert "资产表现 JSON: file://" in links
    assert "报告已保存:" not in result
    assert list((project_dir / ".erlangshen" / "artifacts" / "charts").glob("*.json"))
    assert list((project_dir / ".erlangshen" / "artifacts" / "charts").glob("*.html"))
    reports = list((project_dir / ".erlangshen" / "artifacts" / "reports").glob("*.md"))
    assert not reports
    reset_config()


@pytest.mark.asyncio
async def test_materialize_synthesis_artifacts_accepts_flexible_chart_shapes():
    calls = []

    class FakeServerClient:
        async def chart_artifact(self, chart_type, title, data, width=960, height=540, metadata=None):
            calls.append((chart_type, title, data))
            return {
                "artifact": {
                    "type": chart_type,
                    "title": title,
                    "data": data,
                    "html_url": f"https://cdn.example.com/{len(calls)}.html",
                }
            }

    cli = CLI()
    results = await cli._materialize_synthesis_artifacts(
        {
            "charts": {
                "kind": "bar",
                "name": "资产涨跌",
                "series": [
                    {"asset": "A股", "change_pct": 1.2},
                    {"asset": "黄金", "change_pct": 0.8},
                ],
            },
            "visualizations": [
                {
                    "artifact_type": "visualization",
                    "visualization_type": "line",
                    "title": "指数走势",
                    "dataset": {"labels": ["周一", "周二"], "values": [1, 2]},
                }
            ],
            "artifact_requests": [
                {"type": "table", "title": "不支持的表格", "data": {"A": 1}},
                {"type": "chart", "title": "缺少数据"},
            ],
            "artifacts": [
                {
                    "type": "chart",
                    "title": "嵌套涨跌",
                    "data": {
                        "沪深300": {"change_pct": "1.23%"},
                        "黄金": {"return_pct": 0.8},
                    },
                },
                {
                    "type": "chart",
                    "title": "Rows 百分比",
                    "data": {
                        "rows": [
                            {"name": "红利", "pct": "1.5%"},
                            {"name": "成长", "percent": "-0.6%"},
                        ]
                    },
                },
            ],
        },
        FakeServerClient(),
        "今天行情怎么样",
    )

    assert calls == [
        ("bar", "嵌套涨跌", {"沪深300": "1.23%", "黄金": 0.8}),
        ("bar", "Rows 百分比", {"红利": "1.5%", "成长": "-0.6%"}),
        ("bar", "资产涨跌", {"A股": 1.2, "黄金": 0.8}),
        ("line", "指数走势", {"周一": 1, "周二": 2}),
    ]
    assert results[0]["status"] == "success"
    assert results[0]["data_keys"] == ["沪深300", "黄金"]
    assert results[2]["data_keys"] == ["A股", "黄金"]
    assert results[3]["type"] == "line"
    skipped = [item for item in results if item.get("status") == "skipped"]
    assert skipped == [{"title": "缺少数据", "status": "skipped", "reason": "缺少图表数据"}]


def test_client_advice_displays_llm_resource_links():
    result = CLI()._format_client_advice(
        query="把网页给我",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.5}],
        synthesis={
            "view": "我整理了两个可打开资源。",
            "suggestions": [],
            "risk_controls": [],
            "missing_data": [],
            "resources": [
                {"title": "市场网页", "url": "https://example.com/page"},
                {"title": "走势图", "image_url": "https://example.com/chart.png"},
            ],
            "resource_links": [
                {"source": "LLM resource", "title": "完整报告", "html_url": "https://example.com/report.html"},
                "新闻图片: https://example.com/news.png",
            ],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={},
    )

    assert "可打开资源：" in result
    assert "市场网页: https://example.com/page" in result
    assert "走势图 图片: https://example.com/chart.png" in result
    assert "完整报告: https://example.com/report.html" in result
    assert "新闻图片: https://example.com/news.png" in result


@pytest.mark.asyncio
async def test_links_command_lists_recent_named_resources(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    cli = CLI()

    empty = await cli.dispatch("/links")
    assert "【最近可打开资源】" in empty
    assert "未授权项目文件夹时不写入磁盘" in empty
    assert "暂无资源链接" in empty

    cli._remember_resource_links(
        "今天行情怎么样",
        [
            {"source": "MCP/web_search", "link": "政策新闻: https://example.com/news"},
            {"source": "server artifact", "link": "资产表现图片: https://cdn.example.com/chart.png"},
        ],
    )

    result = await cli.dispatch("/links")

    assert "MCP/web_search · 今天行情怎么样" in result
    assert "政策新闻: https://example.com/news" in result
    assert "server artifact · 今天行情怎么样" in result
    assert "资产表现图片: https://cdn.example.com/chart.png" in result
    assert "/links 1" in result
    assert "/links open 1" in result
    assert "/open 1" in result
    assert "/open link 1" in result
    assert "/open chart" in result
    assert "/artifacts" in result

    cli_no_opener = CLI()
    cli_no_opener._remember_resource_links("今天行情怎么样", [{"source": "MCP/web_search", "link": "政策新闻: https://example.com/news"}])
    cli_no_opener._system_open_command = lambda: None
    no_opener = await cli_no_opener.dispatch("/open link 1")
    assert "【打开最近资源】" in no_opener
    assert "当前环境没有可用桌面打开命令" in no_opener
    assert "政策新闻: https://example.com/news" in no_opener

    opened = []

    class FakePopen:
        def __init__(self, cmd, stdout=None, stderr=None):
            opened.append(cmd)

    cli_open = CLI()
    cli_open._remember_resource_links("今天行情怎么样", [{"source": "server artifact", "link": "资产表现图片: https://cdn.example.com/chart.png"}])
    cli_open._system_open_command = lambda: ["echo-open"]
    monkeypatch.setattr("subprocess.Popen", FakePopen)
    opened_result = await cli_open.dispatch("/open link 1")
    assert "已尝试打开: 资产表现图片" in opened_result
    assert opened == [["echo-open", "https://cdn.example.com/chart.png"]]

    alias_result = await cli_open.dispatch("/links open 1")
    assert "已尝试打开: 资产表现图片" in alias_result
    assert opened[-1] == ["echo-open", "https://cdn.example.com/chart.png"]

    short_open_result = await cli_open.dispatch("/open 1")
    assert "已尝试打开: 资产表现图片" in short_open_result
    assert opened[-1] == ["echo-open", "https://cdn.example.com/chart.png"]

    short_links_result = await cli_open.dispatch("/links 1")
    assert "已尝试打开: 资产表现图片" in short_links_result
    assert opened[-1] == ["echo-open", "https://cdn.example.com/chart.png"]

    label, target = cli_open._split_named_link("\x1b]8;;file:///tmp/chart.html\x1b\\打开图表\x1b]8;;\x1b\\ (file:///tmp/chart.html)")
    assert label
    assert target == "file:///tmp/chart.html"

    local_file = tmp_path / "report.html"
    local_file.write_text("<html></html>", encoding="utf-8")
    cli_open._remember_resource_links("本地报告", [{"source": "local report", "link": f"打开报告: {local_file}"}])
    local_result = await cli_open.dispatch("/open link 2")
    assert "已尝试打开: 打开报告" in local_result
    assert opened[-1] == ["echo-open", local_file.resolve().as_uri()]
    assert f"打开报告: {local_file.resolve().as_uri()}" in local_result

    out_of_range = await cli_open.dispatch("/open link 99")
    assert "序号超出范围" in out_of_range


@pytest.mark.asyncio
async def test_links_are_persisted_in_authorized_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    workspace = tmp_path / "project"
    workspace.mkdir()
    approve_workspace(workspace)

    cli = CLI()
    cli._remember_resource_links(
        "今天行情怎么样",
        [
            {"source": "MCP/web_search", "link": "盘面新闻: https://example.com/market"},
            {"source": "server artifact", "link": "盘面图片: https://cdn.example.com/market.png"},
        ],
    )

    index_path = workspace / ".erlangshen" / "artifacts" / "resources.json"
    assert index_path.exists()
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert index_data["resources"][0]["label"] == "盘面新闻"
    assert index_data["resources"][0]["target"] == "https://example.com/market"
    assert index_data["resources"][0]["type"] == "webpage"
    assert index_data["resources"][1]["label"] == "盘面图片"
    assert index_data["resources"][1]["target"] == "https://cdn.example.com/market.png"
    assert index_data["resources"][1]["type"] == "chart_image"

    fresh_cli = CLI()
    result = await fresh_cli.dispatch("/links")

    assert "本次 CLI 最近回答 + 已授权项目资源索引" in result
    assert str(index_path) in result
    assert "MCP/web_search · 今天行情怎么样" in result
    assert "盘面新闻: https://example.com/market" in result
    assert "类型: webpage · 目标: https://example.com/market" in result
    assert "server artifact · 今天行情怎么样" in result
    assert "盘面图片: https://cdn.example.com/market.png" in result
    assert "类型: chart_image · 目标: https://cdn.example.com/market.png" in result


def test_intent_resource_links_are_collected_as_named_links():
    cli = CLI()

    links = cli._collect_turn_resource_links(
        {
            "intent_resource_links": [
                {"source": "intent plan", "link": "研报图片: https://cdn.example.com/report.png"},
                {"source": "intent plan", "url": "https://example.com/page"},
            ],
            "mcp_links": [],
        },
        {"resources": []},
    )

    assert links == [
        {"source": "intent plan", "link": "研报图片: https://cdn.example.com/report.png"},
        {"source": "intent plan", "link": "https://example.com/page"},
    ]


def test_resource_links_extract_markdown_html_and_plain_targets(tmp_path):
    local_chart = tmp_path / "chart.html"
    local_chart.write_text("<html></html>", encoding="utf-8")
    cli = CLI()

    links = cli._resource_links_from_value(
        {
            "summary": (
                "[政策原文](https://example.com/policy) "
                "![走势图](https://cdn.example.com/chart.png) "
                "<a href=\"https://example.com/report.html\">完整报告</a> "
                "<img src=\"https://cdn.example.com/thumb.jpg\" alt=\"缩略图\"> "
                f"本地页面 {local_chart}"
            )
        },
        "行情资源",
    )

    assert "政策原文: https://example.com/policy" in links
    assert "走势图 图片: https://cdn.example.com/chart.png" in links
    assert "完整报告: https://example.com/report.html" in links
    assert "缩略图: https://cdn.example.com/thumb.jpg" in links
    assert f"行情资源: {local_chart.resolve().as_uri()}" in links

    direct_links = cli._coerce_resource_links(
        "[网页](https://example.com/page) ![新闻图](https://cdn.example.com/news.png)"
    )
    assert {"source": "resource", "link": "网页: https://example.com/page"} in direct_links
    assert {"source": "resource", "link": "新闻图 图片: https://cdn.example.com/news.png"} in direct_links


def test_interactive_turn_visually_separates_question_and_answer():
    output = CLI()._format_interactive_turn("今天市场情况怎么样", "先看主线。")

    assert "╭─ 你 " in output
    assert "今天市场情况怎么样" in output
    assert "╭─ 二郎神 " in output
    assert "先看主线。" in output


def test_chart_terminal_preview_formats_numeric_chart_data():
    preview = CLI()._chart_terminal_preview({
        "沪深300": "1.20%",
        "黄金": -0.8,
        "说明": "not-number",
    })

    assert len(preview) == 2
    assert preview[0].startswith("沪深300")
    assert "+1.2" in preview[0]
    assert "黄金" in preview[1]
    assert "-0.8" in preview[1]
    assert all("|" in row for row in preview)


@pytest.mark.asyncio
async def test_workspace_command_manages_project_sandbox(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    project_dir = tmp_path / "project"
    selected_dir = tmp_path / "selected"
    project_dir.mkdir()
    selected_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))

    status = await CLI().dispatch("/workspace")
    assert "未授权，当前不会写入本地文件" in status
    assert str(project_dir) in status
    assert "选择项目文件夹:" in status
    assert "/workspace browse" in status
    assert "/workspace path <路径>" in status
    assert "/workspace use <路径>" in status
    assert "最近项目:" in status
    assert "沙箱边界:" in status
    assert "大模型 API Key 仍只保存在本机配置" in status
    assert "产物和链接:" in status
    assert "网页、图片、PDF、HTML 和本地图表不会塞进终端正文" in status
    assert "授权后最近资源会写入项目资源索引" in status
    assert "未授权时仅保存在当前 CLI 进程内" in status

    allowed = await CLI().dispatch("/workspace allow")
    assert "已授权，可保存图表、报告和工作记忆" in allowed
    assert "/artifacts 查看已保存产物" in allowed
    assert "/open 打开最近图表或报告" in allowed
    assert "/links 查看最近网页、图片、PDF、图表和报告名称链接" in allowed
    assert "/open 1 或 /links 1 直接打开最近资源" in allowed
    assert "当前 · 已授权" in allowed

    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)
    selected = await CLI().dispatch(f"/workspace path {selected_dir}")
    assert str(selected_dir) in selected
    assert "未授权，当前不会写入本地文件" in selected
    assert f"可选 · 已授权 · {project_dir}" in selected

    allowed_selected = await CLI().dispatch(f"/workspace allow {selected_dir}")
    assert str(selected_dir) in allowed_selected
    assert "已授权，可保存图表、报告和工作记忆" in allowed_selected

    revoked = await CLI().dispatch("/workspace revoke")
    assert "未授权，当前不会写入本地文件" in revoked


@pytest.mark.asyncio
async def test_workspace_browse_guides_non_interactive_environment():
    result = await CLI().dispatch("/workspace browse")

    assert "【项目文件夹选择器】" in result
    assert "当前不是交互终端" in result
    assert "erlangshen /workspace browse" in result
    assert "erlangshen /workspace path <项目路径>" in result
    assert "erlangshen /workspace use <项目路径>" in result


@pytest.mark.asyncio
async def test_workspace_path_without_argument_guides_non_interactive_environment():
    result = await CLI().dispatch("/workspace path")

    assert "【手动选择项目文件夹】" in result
    assert "当前不是交互终端" in result
    assert "erlangshen /workspace path <项目路径>" in result
    assert "erlangshen /workspace allow" in result


def test_workspace_directory_items_offer_browse_actions(tmp_path):
    project = tmp_path / "project"
    child = project / "alpha"
    hidden = project / ".hidden"
    project.mkdir()
    child.mkdir()
    hidden.mkdir()

    items = CLI()._workspace_directory_items(project)

    assert items[0][0] == "use"
    assert items[0][2] == "使用当前目录作为项目沙箱"
    assert items[1][0] == "manual"
    assert items[1][2] == "手动输入或粘贴其他路径"
    assert any(item[1] == project.parent and item[2] == ".. 上一级目录" for item in items)
    assert any(item[1] == child and item[2] == "alpha/" for item in items)
    assert all(item[1] != hidden for item in items)


def test_workspace_directory_items_include_recent_workspaces(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    current = tmp_path / "current"
    recent = tmp_path / "recent"
    current.mkdir()
    recent.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    approve_workspace(recent)

    items = CLI()._workspace_directory_items(current)

    assert recent_workspaces()[0]["path"] == str(recent)
    assert ("choose", recent.resolve(), "最近项目 · 已授权 · 直接切换") in items


def test_startup_workspace_prompt_uses_launch_cwd_when_saved_workspace_is_package(monkeypatch, tmp_path, capsys):
    workspace_file = tmp_path / "workspaces.json"
    package_dir = tmp_path / "node_modules" / "erlangshen"
    launch_dir = tmp_path / "project"
    package_dir.mkdir(parents=True)
    launch_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_LAUNCH_CWD", str(launch_dir))
    approve_workspace(package_dir)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    cli = CLI()
    seen = []
    monkeypatch.setattr(cli, "_is_package_install_workspace", lambda path: str(package_dir) in str(path))
    monkeypatch.setattr(cli, "_read_workspace_path_selection", lambda workspace: seen.append(Path(workspace)) or str(launch_dir))
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    cli._confirm_workspace_sandbox()

    output = capsys.readouterr().out
    assert seen == [launch_dir.resolve()]
    assert "客户端安装目录" in output
    assert workspace_status()["path"] == str(launch_dir.resolve())
    assert workspace_status()["allowed"] is True


def test_workspace_directory_items_show_recent_resource_count(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    current = tmp_path / "current"
    recent = tmp_path / "recent"
    current.mkdir()
    recent.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    approve_workspace(recent)
    cli = CLI()
    cli._remember_resource_links(
        "今天行情怎么样",
        [
            {"source": "MCP/web_search", "link": "盘面新闻: https://example.com/news"},
            {"source": "server artifact", "link": "盘面图片: https://cdn.example.com/chart.png"},
        ],
    )
    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)

    items = CLI()._workspace_directory_items(current)

    assert ("choose", recent.resolve(), "最近项目 · 已授权 · 2 资源 · 直接切换") in items


def test_workspace_browser_render_explains_sandbox_boundary(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    items = CLI()._workspace_directory_items(project)

    height = CLI()._render_workspace_browser(project, items, 0)
    output = capsys.readouterr().out

    assert height > 0
    assert "Project Sandbox Setup" in output
    assert "选择二郎神本次可访问的项目文件夹" in output
    assert "当前项目资源索引: 暂无；授权后会保存 resources.json" in output
    assert "授权后: 仅在该目录内保存图表、报告、工作记忆和可打开资源索引" in output
    assert "不会写入: 大模型 API Key、账号 token、服务端内部认知库" in output
    assert "p 粘贴路径" in output
    assert "产物/资源索引 .erlangshen/artifacts" in output
    assert "后续 /setup run" in output
    assert "选定后还会再次确认写入权限" in output


def test_workspace_browser_uses_display_width_for_chinese_rows(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("src.cli._terminal_width", lambda: 92)
    project = tmp_path / "中文项目"
    project.mkdir()
    (project / "行业图表").mkdir()

    items = CLI()._workspace_directory_items(project)
    CLI()._render_workspace_browser(project, items, 0)
    output = capsys.readouterr().out

    framed_lines = [line for line in output.splitlines() if line.startswith(("╭", "│", "├", "╰"))]
    widths = [_display_width(line) for line in framed_lines]
    assert len(set(widths)) == 1
    assert "当前浏览:" in output
    assert "中文项目" in output
    assert "行业图表/" in output


def test_workspace_browser_render_shows_current_resource_count(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    project = tmp_path / "project"
    project.mkdir()
    approve_workspace(project)
    cli = CLI()
    cli._remember_resource_links(
        "今天行情怎么样",
        [
            {"source": "MCP/web_search", "link": "新闻: https://example.com/news"},
            {"source": "server artifact", "link": "图表: https://cdn.example.com/chart.png"},
        ],
    )

    items = cli._workspace_directory_items(project)
    cli._render_workspace_browser(project, items, 0)
    output = capsys.readouterr().out

    assert "当前项目资源索引: 已发现 2 条网页/图片/图表/报告链接" in output


def test_startup_workspace_prompt_can_select_and_authorize_path(monkeypatch, tmp_path, capsys):
    workspace_file = tmp_path / "workspaces.json"
    default_dir = tmp_path / "default"
    selected_dir = tmp_path / "selected"
    default_dir.mkdir()
    selected_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(default_dir))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    cli = CLI()
    monkeypatch.setattr(cli, "_read_workspace_path_selection", lambda workspace: str(selected_dir))
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    cli._confirm_workspace_sandbox()

    output = capsys.readouterr().out
    assert str(selected_dir) in output
    monkeypatch.delenv("ERLANGSHEN_WORKSPACE", raising=False)
    assert workspace_status()["path"] == str(selected_dir)


@pytest.mark.asyncio
async def test_chart_command_requests_server_artifact(monkeypatch):
    calls = []
    init_kwargs = []

    class FakeServerClient:
        def __init__(self, **kwargs):
            init_kwargs.append(kwargs)

        async def chart_artifact(self, chart_type, title, data, width=960, height=540, metadata=None):
            calls.append((chart_type, title, data, metadata))
            return {
                "artifact": {
                    "type": chart_type,
                    "title": title,
                    "data": data,
                    "metadata": {"source": "erlangshen-server"},
                }
            }

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    monkeypatch.setattr("src.cli.load_auth_session", lambda: {"token": "chart-token", "base_url": "https://example.test/api"})

    result = await CLI().dispatch('/chart 资产表现 :: {"A股":1.2,"黄金":0.8}')

    assert init_kwargs == [{"base_url": "https://example.test/api", "token": "chart-token"}]
    assert calls[0][0] == "bar"
    assert calls[0][1] == "资产表现"
    assert calls[0][2]["A股"] == 1.2
    assert "【图表 Artifact】" in result
    assert "A股, 黄金" in result
    assert "工作区未授权" in result


@pytest.mark.asyncio
async def test_chart_command_saves_artifact_inside_authorized_workspace(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)

    class FakeServerClient:
        def __init__(self, **kwargs):
            pass

        async def chart_artifact(self, chart_type, title, data, width=960, height=540, metadata=None):
            return {
                "artifact": {
                    "type": chart_type,
                    "title": title,
                    "data": data,
                    "metadata": {"source": "erlangshen-server"},
                }
            }

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)

    cli = CLI()
    result = await cli.dispatch('/chart 资产表现 :: {"A股":1.2,"黄金":0.8}')

    assert "已保存:" in result
    assert "可视化:" in result
    assert "资源入口: 已加入 /links" in result
    assert "file://" in result
    assert "资产表现 HTML:" in result
    saved_files = list((project_dir / ".erlangshen" / "artifacts" / "charts").glob("*.json"))
    html_files = list((project_dir / ".erlangshen" / "artifacts" / "charts").glob("*.html"))
    assert len(saved_files) == 1
    assert len(html_files) == 1
    assert "资产表现" in saved_files[0].name
    assert saved_files[0].read_text(encoding="utf-8").find('"A股": 1.2') >= 0

    links = await cli.dispatch("/links")
    assert "local artifact · /chart 资产表现" in links
    assert "资产表现 HTML:" in links
    assert ".erlangshen/artifacts/charts" in links
    assert "<h1>资产表现</h1>" in html_files[0].read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_chart_command_collects_server_resource_links(monkeypatch):
    class FakeServerClient:
        def __init__(self, **kwargs):
            pass

        async def chart_artifact(self, chart_type, title, data, width=960, height=540, metadata=None):
            return {
                "chart": {
                    "type": chart_type,
                    "title": title,
                    "data": data,
                    "image_url": "https://cdn.example.com/chart.png",
                    "html_url": "https://example.com/chart.html",
                    "resource_links": ["原始数据: https://example.com/data.json"],
                }
            }

    monkeypatch.setattr("src.client.server_client.ErlangshenServerClient", FakeServerClient)
    cli = CLI()

    result = await cli.dispatch('/chart 资产表现 :: {"A股":1.2}')
    links = await cli.dispatch("/links")

    assert "工作区未授权" in result
    assert "资源入口: 已加入 /links" in result
    assert "资产表现 图片: https://cdn.example.com/chart.png" in links
    assert "资产表现: https://example.com/chart.html" in links
    assert "原始数据: https://example.com/data.json" in links


@pytest.mark.asyncio
async def test_artifacts_command_lists_saved_chart_files(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)

    charts_dir = project_dir / ".erlangshen" / "artifacts" / "charts"
    reports_dir = project_dir / ".erlangshen" / "artifacts" / "reports"
    charts_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    (charts_dir / "20260101-120000-资产表现.json").write_text(
        '{"title":"资产表现","type":"bar","data":{"A股":1.2,"黄金":0.8}}',
        encoding="utf-8",
    )
    (charts_dir / "20260101-120000-资产表现.html").write_text("<html></html>", encoding="utf-8")
    (reports_dir / "20260101-120000-资产表现.md").write_text("# report", encoding="utf-8")

    result = await CLI().dispatch("/artifacts")

    assert "【分析产物】" in result
    assert "- 摘要: reports 1 / charts 2" in result
    assert "- 图表视图: 1" in result
    assert "- 最近报告: .erlangshen/artifacts/reports/20260101-120000-资产表现.md" in result
    assert "- 最近图表: .erlangshen/artifacts/charts/20260101-120000-资产表现" in result
    assert "- 最近可打开:" in result
    assert ".erlangshen/artifacts/charts/20260101-120000-资产表现.html" in result
    assert "- 名称链接: 打开最近产物: file://" in result
    assert "- 打开: /open report 或 /open chart" in result
    assert "产物收件箱:" in result
    assert "- 图表: /open chart 打开最近 HTML 图表；/artifacts 查看全部" in result
    assert "- 报告: /open report 打开最近 Markdown 报告" in result
    assert "- 资源: /links 1 或 /open 1 打开网页、图片、图表和报告名称链接" in result
    assert "把这个做成图表/报告" in result
    assert "用途: 图表由服务端 chart artifact 通道生成" in result
    assert "- 最近图表摘要:" in result
    assert "资产表现 (bar): A股, 黄金 -> .erlangshen/artifacts/charts/20260101-120000-资产表现.html" in result
    assert "打开 资产表现: file://" in result
    assert ".erlangshen/artifacts/reports/20260101-120000-资产表现.md" in result
    assert "打开报告: file://" in result
    assert ".erlangshen/artifacts/charts/20260101-120000-资产表现.json" in result
    assert ".erlangshen/artifacts/charts/20260101-120000-资产表现.html" in result
    assert "打开图表: file://" in result


def test_open_artifact_reports_path_when_no_desktop_opener(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)
    charts_dir = project_dir / ".erlangshen" / "artifacts" / "charts"
    charts_dir.mkdir(parents=True)
    chart_file = charts_dir / "20260101-120000-资产表现.html"
    chart_file.write_text("<html></html>", encoding="utf-8")
    cli = CLI()
    monkeypatch.setattr(cli, "_system_open_command", lambda: None)

    result = cli.open_artifact_text("chart")

    assert "当前环境没有可用桌面打开命令" in result
    assert str(chart_file) in result
    assert "链接: 打开产物: file://" in result


def test_open_artifact_uses_latest_report_when_requested(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)
    reports_dir = project_dir / ".erlangshen" / "artifacts" / "reports"
    reports_dir.mkdir(parents=True)
    report_file = reports_dir / "20260101-120000-分析.md"
    report_file.write_text("# report", encoding="utf-8")
    opened = []

    class FakePopen:
        def __init__(self, cmd, stdout=None, stderr=None):
            opened.append(cmd)

    cli = CLI()
    monkeypatch.setattr(cli, "_system_open_command", lambda: ["echo-open"])
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    result = cli.open_artifact_text("report")

    assert "已尝试打开" in result
    assert "链接: 打开产物: file://" in result
    assert opened == [["echo-open", str(report_file)]]


def test_llm_prompts_include_mcp_catalog_and_chart_channel():
    cli = CLI()
    cli._remember_conversation_turn("刚才说的红利策略呢", "先看利率方向和拥挤度。")
    cli._last_mcp_data = {
        "get_index_data:沪深300": {"index_name": "沪深300", "change_pct": 1.2},
    }
    cli._last_artifact_results = [
        {
            "title": "指数快照对比",
            "status": "success",
            "type": "chart",
            "data_keys": ["沪深300"],
            "saved": {"html": "/tmp/chart.html", "json": "/tmp/chart.json"},
        }
    ]
    cli._remember_resource_links("刚才说的红利策略呢", [{"source": "MCP/web_search", "link": "利率新闻: https://example.com/rate"}])
    messages = cli._client_advice_messages(
        query="今天行情怎么样",
        matches=[],
        mcp_data={},
        user_data={},
        current_cognition={},
        intent_plan={},
    )
    payload = messages[-1]["content"]

    assert "get_index_data" in payload
    assert "registry_tools" in payload
    assert "registry_source" in payload
    assert "tool_names" in payload
    assert "tool_result_hints" in payload
    assert "result_shape" in payload
    assert "chart_fit" in payload
    assert "line 用于走势" in payload
    assert "Super66MCP.list_registry_tools" in payload
    assert "搜索 A股标的" in payload
    assert "get_product_history" in payload
    assert "chart_artifact" in payload
    assert "resource_link_channel" in payload
    assert "resource_links" in payload
    assert "local_web_search" in payload
    assert "local_chrome_web_search" in payload
    assert "python3 -m pip install playwright" in payload
    assert "web_search:<query> -> {results:[{title,url,source}], total, provider}" in payload
    assert "/links open 1" in payload
    assert "/open link 1" in payload
    assert "网页、图片、HTML、PDF" in payload
    assert "artifacts" in payload
    assert "followups" in payload
    assert "next_actions" in payload
    assert "recent_conversation" in payload
    assert "previous_mcp_context" in payload
    assert "recent_artifacts" in payload
    assert "recent_resources" in payload
    assert "get_index_data:沪深300" in payload
    assert "指数快照对比" in payload
    assert "利率新闻: https://example.com/rate" in payload
    assert "刚才说的红利策略呢" in payload
    assert "先看利率方向和拥挤度" in payload
    assert "做成图表/继续/那它呢/详细说说" in payload
    assert "必须参考 previous_mcp_context 和 recent_artifacts" in payload
    assert "刚才那个网页/图片/图/链接/报告" in payload
    assert "/links 或 /open" in payload
    assert "tool_rationale" in payload
    assert "tool_selection_source" in payload
    assert "tool_selection_note" in payload
    assert "data_strategy" in payload
    assert "route_summary" in payload
    assert "data_confidence" in payload
    assert "chart_opportunity" in payload
    assert "artifact_plan" in payload
    assert "数据足够时可直接在 artifacts 请求图表" in payload
    assert "missing_inputs" in payload
    assert "tool_result_contract" in payload
    assert "server_client_contract" in payload
    assert "agent_orchestration_protocol" in payload
    assert "本机大模型是主要编排者" in payload
    assert "客户端只做工具白名单、参数归一化、授权沙箱、安全脱敏" in payload
    assert "不要先写死规则再让模型填空" in payload
    assert "不要只按关键词触发固定工具链" in payload
    assert "llm_must_return" in payload
    assert "route_summary: 解释你如何理解真实任务" in payload
    assert "tool_rationale: 说明为什么选择或不选择 MCP/web_search" in payload
    assert "data_strategy: 说明 MCP、web_search、用户数据、服务端映射如何组合" in payload
    assert "artifact_plan: 需要图表/报告时说明数据来源、标题和保存边界" in payload
    assert "client_may_override_only_when" in payload
    assert "所有工具来源、补齐原因、降级和图表计划必须进入 /plan" in payload
    assert "server_role" in payload
    assert "client_role" in payload
    assert "llm_key_boundary" in payload
    assert "mapping_contract" in payload
    assert "artifact_contract" in payload
    assert "workspace_contract" in payload
    assert "resource_contract" in payload
    assert "data_recipes" in payload
    assert "agent_playbook" in payload
    assert "single_asset_or_product" in payload
    assert "macro_event_cross_asset" in payload
    assert "visualization_or_report_followup" in payload
    assert "恒生科技指数、恒生指数、HSTECH、HSI、Hang Seng Tech 只能使用 get_index_data" in payload
    assert "不要使用 get_global_asset_data" in payload
    assert "国内宽基指数数据源" in payload
    assert "sourceTable=global_index_daily/global_indices/global_assets" not in payload
    assert "恒生科技指数/HSTECH/Hang Seng Tech/恒生指数/HSI/HSCEI 属于这里" in payload
    assert "preferred_chain" in payload
    assert "artifact_rule" in payload
    assert "resource_rule" in payload
    assert "get_index_data: 沪深300/上证指数/创业板指" in payload
    assert "A股和港股宽基指数历史或最近行情序列" in payload
    assert "港股宽基指数必须用 get_index_data" in payload
    assert "生成的 HTML/JSON/图片/报告路径都加入 /links" in payload
    assert "route_plans" in payload
    assert "composition_patterns" in payload
    assert "market_snapshot_to_narrative" in payload
    assert "mcp_table_to_chart_artifact" in payload
    assert "缺少数值字段时跳过图表生成" in payload
    assert "market_overview_to_analysis" in payload
    assert "named_asset_to_fact_check" in payload
    assert "analysis_to_chart_artifact" in payload
    assert "server map" in payload
    assert "market_overview" in payload
    assert "今天行情怎么样？先帮我看盘面主线和风险。" in payload
    assert "把刚才的资产表现做成图表。" in payload
    assert "single_asset" in payload
    assert "macro_event" in payload
    assert "visualization_followup" in payload
    assert "沪深300 / 上证指数 / 创业板指" in payload
    assert "复用 recent_conversation" in payload
    assert "每个 key 形如 tool:label" in payload
    assert "web_search 返回 results 数组" in payload
    assert "授权工作区保存 JSON/HTML" in payload
    assert "不要输出 token/key/secret/password/authorization" in payload
    assert "market_data_brief" in payload
    assert '"as_of_date":' in payload
    assert '"timezone": "Asia/Shanghai"' in payload
    assert "必须优先结合这些数据回答" in payload
    assert "missing_data 不要再列具体指数、实时点位、新闻事件等基础行情项" in payload
    assert "/chart <标题>" in payload


@pytest.mark.asyncio
async def test_intent_prompt_includes_recent_resource_context():
    captured = {}

    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            captured["system"] = messages[0]["content"]
            captured["payload"] = messages[-1]["content"]
            return (
                '{"intent":"general_investment","needs_server_mapping":true,"needs_mcp":false,"mcp_tools":[],'
                '"resource_links":[{"source":"server artifact","label":"资产图","url":"https://cdn.example.com/chart.png"}],'
                '"resource_presentation":"用命名链接展示图片，并提示 /links 1 或 /open 1 打开",'
                '"open_commands":["/links 1","/open 1"]}'
            )

    cli = CLI()
    cli._remember_resource_links("刚才那个图", [{"source": "server artifact", "link": "资产图: https://cdn.example.com/chart.png"}])

    plan = await cli._infer_client_intent("基于刚才那个图继续", {}, object(), FakeLLMClient)

    assert plan["intent"] == "general_investment"
    assert plan["resource_links"] == [{"source": "server artifact", "link": "资产图: https://cdn.example.com/chart.png"}]
    assert plan["resource_presentation"] == "用命名链接展示图片，并提示 /links 1 或 /open 1 打开"
    assert plan["open_commands"] == ["/links 1", "/open 1"]
    assert "不要把单个关键词命中当成主要判断方式" in captured["system"]
    assert "你是编排决策者，不要先写死规则再让模型填空" in captured["system"]
    assert "agent_orchestration_protocol" in captured["system"]
    assert "routing_contract.flexible_tool_spec" in captured["system"]
    assert "recent_resources" in captured["payload"]
    assert "agent_orchestration_protocol" in captured["payload"]
    assert "本机大模型是主要编排者" in captured["payload"]
    assert "client_may_override_only_when" in captured["payload"]
    assert "宽泛行情任务没有任何工具计划" in captured["payload"]
    assert "resource_link_channel" in captured["payload"]
    assert "server_client_contract" in captured["payload"]
    assert "核心服务端只负责账号鉴权、受保护场景映射" in captured["payload"]
    assert "用户的大模型 API Key 只保存在本机" in captured["payload"]
    assert "chart_type, title, data, metadata" in captured["payload"]
    assert "routing_contract" in captured["payload"]
    assert "agent_playbook" in captured["payload"]
    assert "market_overview" in captured["payload"]
    assert "preferred_chain" in captured["payload"]
    assert "server chart_artifact" in captured["payload"]
    assert "local_llm_context_router" in captured["payload"]
    assert "不要只因为出现某个关键词就固定路由" in captured["payload"]
    assert "flexible_tool_spec" in captured["payload"]
    assert "resource_links" in captured["payload"]
    assert "resource_presentation" in captured["payload"]
    assert "open_commands" in captured["payload"]
    assert "资产图: https://cdn.example.com/chart.png" in captured["payload"]


@pytest.mark.asyncio
async def test_intent_parser_accepts_markdown_fenced_json_with_examples():
    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            return """
示例格式: {"intent":"smalltalk","needs_mcp":false}

```json
{
  "intent": "market_overview",
  "needs_server_mapping": true,
  "needs_mcp": true,
  "mcp_tools": [
    {"name": "get_index_data", "arguments": {"index_name": "沪深300", "limit": 30}}
  ],
  "rewritten_query": "今天 A 股行情怎么样",
  "route_summary": "用户想看今日市场概览",
  "tool_rationale": "需要指数数据和服务端场景映射",
  "data_strategy": "先取 super-66 指数，再映射场景，最后本机大模型综合"
}
```
"""

    plan = await CLI()._infer_client_intent("今天行情怎么样", {}, object(), FakeLLMClient)

    assert plan["route_source"] == "local_llm"
    assert plan["intent"] == "market_overview"
    assert plan["rewritten_query"] == "今天 A 股行情怎么样"
    assert {"name": "get_index_data", "arguments": {"index_name": "沪深300", "limit": 30}} in plan["mcp_tools"]
    assert "指数数据" in plan["tool_rationale"]


@pytest.mark.asyncio
async def test_intent_llm_can_select_hk_index_tool_without_global_asset():
    captured = {}

    class FakeLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            captured["payload"] = messages[-1]["content"]
            return json.dumps(
                {
                    "intent": "single_asset",
                    "needs_server_mapping": True,
                    "needs_mcp": True,
                    "mcp_tools": [
                        {
                            "name": "get_index_data",
                            "arguments": {
                                "index_name": "恒生科技指数",
                                "sourceTable": "global_index_daily",
                                "limit": 60,
                            },
                        }
                    ],
                    "rewritten_query": "恒生科技指数最新数据和近期走势",
                    "route_summary": "用户要查恒生科技指数事实数据",
                    "tool_rationale": "恒生科技/HSTECH 是港股股票指数，应使用 get_index_data",
                    "data_strategy": "先取 super-66 指数数据，再结合服务端场景映射分析",
                },
                ensure_ascii=False,
            )

    plan = await CLI()._infer_client_intent("HSTECH 最新数据", {}, object(), FakeLLMClient)

    assert "恒生科技指数、恒生指数、HSTECH、HSI、Hang Seng Tech 只能使用 get_index_data" in captured["payload"]
    assert plan["route_source"] == "local_llm"
    assert plan["intent"] == "single_asset"
    assert {
        "name": "get_index_data",
        "arguments": {"limit": 60, "index_name": "恒生科技指数"},
    } in plan["mcp_tools"]
    assert not any(item["name"] == "get_global_asset_data" for item in plan["mcp_tools"])
    assert "港股股票指数" in plan["tool_rationale"]


def test_client_llm_advice_parser_accepts_markdown_wrapped_json():
    raw = """
我会按下面结构返回：
{"example": true}

```json
{
  "view": "先看主线，再看风险。",
  "suggestions": ["跟踪成交额", "观察政策催化"],
  "risk_controls": ["不要追高"],
  "missing_data": [],
  "resource_links": [{"source": "web_search", "link": "政策原文: https://example.com/policy"}]
}
```
"""

    parsed = CLI()._parse_client_llm_advice(raw)

    assert parsed["view"] == "先看主线，再看风险。"
    assert parsed["suggestions"] == ["跟踪成交额", "观察政策催化"]
    assert parsed["risk_controls"] == ["不要追高"]
    assert parsed["resource_links"] == [{"source": "web_search", "link": "政策原文: https://example.com/policy"}]


@pytest.mark.asyncio
async def test_intent_failure_uses_explainable_fallback_route():
    class BrokenLLMClient:
        def __init__(self, settings, timeout=60.0):
            pass

        async def complete(self, messages, temperature=0.7, max_tokens=4096):
            raise RuntimeError("intent service down")

    cli = CLI()

    plan = await cli._infer_client_intent("今天行情怎么样", {}, object(), BrokenLLMClient)

    assert plan["route_source"] == "fallback"
    assert "保守兜底路由" in plan["route_warning"]
    assert plan["needs_mcp"] is True
    assert plan["mcp_tools"]
    assert "本机大模型理解上下文" in plan["route_summary"]
    assert plan["tool_selection_source"] == "client_market_overview_fallback"
    assert "宽泛行情" in plan["tool_selection_note"]
    assert plan["composition_patterns_used"] == ["market_snapshot_to_narrative", "mcp_table_to_chart_artifact"]
    cli._last_agent_plan = {
        "query": "今天行情怎么样",
        "intent": plan["intent"],
        "tone": plan["tone"],
        "route_source": plan["route_source"],
        "route_warning": plan["route_warning"],
        "rewritten_query": plan["rewritten_query"],
        "mapping_query": plan["rewritten_query"],
        "route_summary": plan["route_summary"],
        "tool_rationale": plan["tool_rationale"],
        "tool_selection_source": plan["tool_selection_source"],
        "tool_selection_note": plan["tool_selection_note"],
        "composition_patterns_used": plan["composition_patterns_used"],
        "data_strategy": plan["data_strategy"],
        "data_confidence": plan["data_confidence"],
        "chart_opportunity": plan["chart_opportunity"],
        "chart_rationale": plan["chart_rationale"],
        "artifact_plan": plan["artifact_plan"],
        "provider": "DeepSeek",
        "model": "deepseek-v4-flash",
        "key_boundary": "API Key 仅本机直连供应商，未发送给二郎神服务端",
        "mcp_tools": plan["mcp_tools"],
    }
    output = await cli.dispatch("/plan")

    assert "路由来源: 保守兜底路由" in output
    assert "工具来源: 客户端行情兜底补齐" in output
    assert "工具来源说明: 用户问题是宽泛行情/盘面问题" in output
    assert "编排审计:" in output
    assert "- 决策者: 客户端兜底" in output
    assert "- 客户端兜底: 是 · 用户问题是宽泛行情/盘面问题" in output
    assert "产物与资源: artifact_plan=chart · resource_links=0 · /links 1 或 /open 1 打开" in output
    assert "组合模式: market_snapshot_to_narrative, mcp_table_to_chart_artifact" in output
    assert "组合模式说明:" in output
    assert "- market_snapshot_to_narrative: 用户问今天行情、盘面、市场主线或风险偏好" in output
    assert "工具链: get_index_data -> get_global_asset_data -> web_search -> server map" in output
    assert "读取字段: index_name/asset_name, date, close/latest, change_pct/pct_chg, title/source/url" in output
    assert "降级: 指数数据失败时保留 web_search 事件线索" in output
    assert "- mcp_table_to_chart_artifact: 用户要求图表、报告、走势、对比、收益、回撤或配置比例" in output
    assert "产物: 客户端调用服务端 chart artifact，保存 JSON/HTML，并把链接加入 /links" in output
    assert "本轮 Playbook:" in output
    assert "- market_overview: 回答“今天行情/盘面/市场主线/风险偏好”这类宽泛问题" in output
    assert "- visualization_or_report_followup: 把上一轮分析、MCP 快照或用户数据沉淀成图表/报告" in output
    assert "生成的 HTML/JSON/图片/报告路径都加入 /links" in output
    assert "路由提示: 本机大模型意图理解失败，已降级为保守兜底路由" in output


@pytest.mark.asyncio
async def test_small_talk_is_kept_as_recent_context():
    cli = CLI()
    result = await cli.dispatch("在吗")

    context = cli._recent_conversation_context()

    assert result.startswith("在，我在。")
    assert context[-1]["user"] == "在吗"
    assert "投资问题" in context[-1]["assistant"]


@pytest.mark.asyncio
async def test_context_command_shows_and_clears_recent_context():
    cli = CLI()
    cli._remember_conversation_turn("A股怎么看", "先看成交量和主线。")
    cli._last_mcp_data = {"get_index_data:沪深300": {"index_name": "沪深300", "change_pct": 1.2}}
    cli._last_artifact_results = [
        {
            "title": "指数快照对比",
            "status": "success",
            "type": "chart",
            "data_keys": ["沪深300"],
            "saved": {"html": "/tmp/chart.html", "json": "/tmp/chart.json"},
        }
    ]
    cli._remember_resource_links("A股怎么看", [{"source": "MCP/web_search", "link": "市场新闻: https://example.com"}])

    result = await cli.dispatch("/context")

    assert "【最近对话上下文】" in result
    assert "条数: 1" in result
    assert "本机记忆: 1 条会被预算化注入" in result
    assert "进入本机大模型: recent_conversation、local_memory、previous_mcp_context、recent_artifacts、recent_resources" in result
    assert "上下文来源:" in result
    assert "recent_conversation: 1 条压缩对话" in result
    assert "local_memory: 1 条跨会话压缩记忆" in result
    assert "previous_mcp_context: available · get_index_data:沪深300" in result
    assert "recent_artifacts: 1 个图表/报告摘要" in result
    assert "recent_resources: 1 个网页/图片/图表/报告链接" in result
    assert "最近 MCP 快照:" in result
    assert "get_index_data:沪深300" in result
    assert "最近产物摘要:" in result
    assert "指数快照对比: success · 沪深300 · /tmp/chart.html" in result
    assert "最近可打开资源:" in result
    assert "MCP/web_search · A股怎么看: 市场新闻: https://example.com" in result
    assert "A股怎么看" in result
    assert "先看成交量和主线" in result
    assert "不展示 API Key、token、password、authorization" in result
    assert "继续使用:" in result
    assert "那如果换成港股呢" in result
    assert "把刚才的结论做成图表/报告" in result
    assert "打开刚才那个网页/图片/图表" in result
    assert "/plan" in result
    assert "/links" in result
    assert "/memory" in result
    assert "/clear" in result

    cleared = await cli.dispatch("/context clear")
    empty = await cli.dispatch("/context")

    assert "已清空" in cleared
    assert "条数: 0" in empty


@pytest.mark.asyncio
async def test_memory_command_persists_redacted_local_context(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_MEMORY_FILE", str(tmp_path / "memory.json"))
    cli = CLI()

    cli._remember_conversation_turn(
        "我关注恒生科技指数，key=sk-secret123456789",
        "后续看港股和 AI 主线，不要暴露 npm_abcdef123456789。",
    )
    result = await cli.dispatch("/memory")

    assert "【本机记忆】" in result
    assert "条数: 1" in result
    assert str(tmp_path / "memory.json") in result
    assert "恒生科技指数" in result
    assert "AI" in result
    assert "[hidden-secret]" in result
    assert "sk-secret123456789" not in result
    assert "npm_abcdef123456789" not in result
    assert "记忆不会发送给二郎神服务端" in result

    messages = cli._client_advice_messages(query="继续说", matches=[])
    payload = json.loads(messages[1]["content"])
    assert payload["local_memory"][0]["user"].startswith("我关注恒生科技指数")

    cleared = await cli.dispatch("/memory clear")
    assert "已清空" in cleared
    assert "条数: 0" in await cli.dispatch("/memory")


@pytest.mark.asyncio
async def test_clear_command_starts_clean_session_without_touching_saved_state():
    cli = CLI()
    cli._remember_conversation_turn("A股怎么看", "先看成交量和主线。")
    cli._remember_resource_links("A股怎么看", [{"source": "MCP/web_search", "link": "市场新闻: https://example.com"}])
    cli._last_agent_plan = {"query": "A股怎么看"}
    cli._agent_trace = ["本机理解问题意图"]
    cli._last_mcp_data = {"get_index_data:沪深300": {"change_pct": 1.2}}
    cli._last_artifact_results = [{"title": "指数快照对比"}]

    result = await cli.dispatch("/clear")

    assert "【新会话已开始】" in result
    assert "最近对话上下文" in result
    assert "最近一次 /plan" in result
    assert "登录状态、模型 Key、工作区授权、已保存图表和报告" in result
    assert cli._recent_conversation_context() == []
    assert cli._last_agent_plan is None
    assert cli._agent_trace is None
    assert cli._last_mcp_data is None
    assert cli._last_artifact_results == []
    assert cli._recent_resource_links() == []


@pytest.mark.asyncio
async def test_clear_keeps_authorized_workspace_resource_index(monkeypatch, tmp_path):
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(tmp_path / "workspaces.json"))
    workspace = tmp_path / "project"
    workspace.mkdir()
    approve_workspace(workspace)

    cli = CLI()
    cli._remember_resource_links(
        "今天行情怎么样",
        [{"source": "MCP/web_search", "link": "盘面新闻: https://example.com/market"}],
    )
    index_path = workspace / ".erlangshen" / "artifacts" / "resources.json"
    assert index_path.exists()

    result = await cli.dispatch("/clear")
    links = await cli.dispatch("/links")
    context_result = await cli.dispatch("/context clear")

    assert "本次进程内资源链接" in result
    assert "项目 resources.json 索引" in result
    assert index_path.exists()
    assert "盘面新闻: https://example.com/market" in links
    assert "项目 resources.json 索引" in context_result


@pytest.mark.asyncio
async def test_collect_client_data_supports_local_chrome_search(monkeypatch):
    async def fake_search(query, count=5):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "新闻", "url": "https://example.com"}]}

    monkeypatch.setattr("src.client.chrome_search.chrome_web_search", fake_search)

    data = await CLI()._collect_client_mcp_data(
        "最新政策影响",
        {},
        {
            "needs_mcp": True,
            "mcp_tools": [{"name": "web_search", "arguments": {"query": "最新政策影响", "count": 3}}],
        },
    )

    assert data["web_search:最新政策影响"]["provider"] == "local_chrome"
    assert data["web_search:最新政策影响"]["results"][0]["title"] == "新闻"


@pytest.mark.asyncio
async def test_vague_market_query_fetches_default_market_data(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, **(arguments or {})}

    async def fake_search(self, query, arguments):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "市场新闻"}]}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    plan = {"needs_mcp": False, "mcp_tools": []}
    search_key = cli._mcp_result_key("web_search", {"query": cli._today_market_search_query()}, 5)
    data = await cli._collect_client_mcp_data(
        "今天行情怎么样",
        {},
        plan,
    )

    assert [item[0] for item in calls] == [
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_global_asset_data",
        "get_global_asset_data",
        "get_global_asset_data",
    ]
    assert calls[0][1]["index_name"] == "沪深300"
    assert calls[1][1]["index_name"] == "上证指数"
    assert calls[2][1]["index_name"] == "创业板指"
    assert calls[3][1]["index_name"] == "恒生科技指数"
    assert calls[4][1]["index_name"] == "恒生指数"
    assert calls[5][1]["asset_name"] == "黄金"
    assert calls[6][1]["asset_name"] == "美元指数"
    assert calls[7][1]["asset_name"] == "原油"
    assert "get_index_data:沪深300" in data
    assert "get_index_data:上证指数" in data
    assert "get_index_data:创业板指" in data
    assert "get_index_data:恒生科技指数" in data
    assert "get_index_data:恒生指数" in data
    assert "get_global_asset_data:黄金" in data
    assert "get_global_asset_data:美元指数" in data
    assert "get_global_asset_data:原油" in data
    assert data[search_key]["provider"] == "local_chrome"
    assert data[search_key]["query"].startswith(cli._today_market_search_query()[:10])
    assert plan["tool_selection_source"] == "client_market_overview_fallback"
    assert "宽泛行情/盘面问题" in plan["tool_selection_note"]


@pytest.mark.asyncio
async def test_yesterday_market_query_fetches_default_market_data(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, **(arguments or {})}

    async def fake_search(self, query, arguments):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "昨日市场新闻"}]}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    plan = {"needs_mcp": False, "mcp_tools": []}
    yesterday_query = "A股 昨日行情 资金面 政策 重要新闻"
    search_key = cli._mcp_result_key("web_search", {"query": yesterday_query}, 5)
    data = await cli._collect_client_mcp_data(
        "分析一下昨天的市场",
        {},
        plan,
    )

    assert [item[0] for item in calls] == [
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_global_asset_data",
        "get_global_asset_data",
        "get_global_asset_data",
    ]
    assert "get_index_data:沪深300" in data
    assert "get_index_data:恒生科技指数" in data
    assert "get_index_data:恒生指数" in data
    assert "get_global_asset_data:黄金" in data
    assert "get_global_asset_data:美元指数" in data
    assert "get_global_asset_data:原油" in data
    assert data[search_key]["query"] == yesterday_query
    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "client_market_overview_fallback"


@pytest.mark.asyncio
async def test_collect_client_data_reuses_previous_mcp_for_visualization_followup():
    cli = CLI()
    cli._last_mcp_data = {
        "get_index_data:沪深300": {"index_name": "沪深300", "change_pct": 1.23},
        "get_global_asset_data:黄金": {"asset_name": "黄金", "change_pct": 0.8},
    }
    plan = {
        "intent": "general_investment",
        "needs_mcp": False,
        "mcp_tools": [],
        "artifact_plan": {"type": "chart", "title": "市场快照对比"},
    }

    data = await cli._collect_client_mcp_data("把刚才这个做成图表", {}, plan)

    assert data["get_index_data:沪深300"]["change_pct"] == 1.23
    assert data["get_global_asset_data:黄金"]["change_pct"] == 0.8
    assert "复用上一轮 MCP 数据" in data["note"]
    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "previous_mcp_context"
    assert "承接式追问复用上一轮 MCP 数据" in plan["tool_selection_note"]
    assert {"name": "get_index_data", "arguments": {"index_name": "沪深300"}} in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金"}} in plan["mcp_tools"]


@pytest.mark.asyncio
async def test_market_overview_intent_fetches_default_data_without_keyword_rules(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, **(arguments or {})}

    async def fake_search(self, query, arguments):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "市场新闻"}]}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    search_key = cli._mcp_result_key("web_search", {"query": cli._today_market_search_query()}, 5)
    plan = cli._normalize_intent_plan(
        {"intent": "market_overview", "needs_mcp": False, "mcp_tools": []},
        "帮我过一遍",
    )
    data = await cli._collect_client_mcp_data("帮我过一遍", {}, plan)

    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "client_default_by_intent"
    assert "按 intent/data_recipes 补齐默认 MCP 工具" in plan["tool_selection_note"]
    assert "行情/事件数据" in plan["tool_rationale"]
    assert "super-66 MCP 行情" in plan["data_strategy"]
    assert plan["artifact_plan"]["type"] == "chart"
    assert plan["artifact_plan"]["title"] == "市场快照对比"
    assert "MCP 行情快照" in plan["artifact_plan"]["data_hint"]
    assert [item[0] for item in calls] == [
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_index_data",
        "get_global_asset_data",
        "get_global_asset_data",
        "get_global_asset_data",
    ]
    assert "get_index_data:沪深300" in data
    assert "get_index_data:恒生科技指数" in data
    assert "get_global_asset_data:黄金" in data
    assert search_key in data


def test_intent_plan_accepts_flexible_llm_tool_shapes():
    cli = CLI()

    plan = cli._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "mcp_tools": {
                "get_astock_realtime": {"args": {"code": "600519", "limit": 1}},
                "get_future_market_data": "{\"contract_code\":\"AU\",\"limit\":20}",
            },
            "tools": [
                {"tool": "get_index_data", "args": {"index_name": "沪深300", "limit": 30}},
                {"tool_name": "web_search", "parameters": {"query": "政策影响", "count": 3}},
            ],
            "tool_calls": [
                {
                    "function": {
                        "name": "get_global_asset_data",
                        "arguments": "{\"asset_name\":\"黄金\",\"limit\":60}",
                    }
                },
                {"name": "unsafe_tool", "arguments": {"token": "should-not-pass"}},
            ],
            "data_tools": {"name": "search_products", "input": {"keyword": "红利基金", "limit": 5}},
            "composition_patterns_used": [
                {"name": "market_snapshot_to_narrative"},
                {"name": "product_history_to_risk"},
                "unknown_pattern",
            ],
        },
        "帮我查一下市场和产品",
    )

    assert plan["needs_mcp"] is True
    assert {"name": "get_index_data", "arguments": {"index_name": "沪深300", "limit": 30}} in plan["mcp_tools"]
    assert {"name": "web_search", "arguments": {"query": "政策影响", "count": 3}} in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金", "limit": 60}} in plan["mcp_tools"]
    assert {"name": "search_products", "arguments": {"keyword": "红利基金", "limit": 5}} in plan["mcp_tools"]
    assert {"name": "get_astock_realtime", "arguments": {"code": "600519", "limit": 1}} in plan["mcp_tools"]
    assert {"name": "get_future_market_data", "arguments": {"contract_code": "AU", "limit": 20}} in plan["mcp_tools"]
    assert all(item["name"] != "unsafe_tool" for item in plan["mcp_tools"])
    assert plan["composition_patterns_used"] == ["market_snapshot_to_narrative", "product_history_to_risk"]


def test_openai_tool_calls_hk_index_global_asset_is_routed_to_index_tool():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tool_calls": [
                {
                    "id": "call_hstech",
                    "type": "function",
                    "function": {
                        "name": "get_global_asset_data",
                        "arguments": json.dumps(
                            {
                                "assetName": "global_indices",
                                "sourceTable": "global_index_daily",
                                "code": "HSTECH",
                                "start_date": "2026-05-01",
                                "limit": 60,
                            },
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        },
        "HSTECH 最新数据",
    )

    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "local_llm"
    assert plan["mcp_tools"] == [
        {
            "name": "get_index_data",
            "arguments": {"start_date": "2026-05-01", "limit": 60, "index_name": "恒生科技指数"},
        }
    ]


def test_intent_plan_accepts_string_mcp_tool_shortcuts():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tools": [
                "get_index_data:上证指数",
                "web_search:{\"query\":\"资金面新闻\",\"count\":2}",
                "get_global_asset_data 恒生科技指数",
            ],
        },
        "帮我查一下行情",
    )

    assert {"name": "get_index_data", "arguments": {"index_name": "上证指数"}} in plan["mcp_tools"]
    assert {"name": "web_search", "arguments": {"query": "资金面新闻", "count": 2}} in plan["mcp_tools"]
    assert {"name": "get_index_data", "arguments": {"index_name": "恒生科技指数"}} in plan["mcp_tools"]


def test_hk_index_aliases_are_routed_to_index_tool():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tools": [
                {
                    "name": "get_global_asset_data",
                    "arguments": {
                        "assetName": "HSTECH",
                        "sourceTable": "恒生科技指数",
                        "start_date": "2026-05-01",
                        "end_date": "2026-06-10",
                        "limit": 60,
                    },
                },
                "get_global_asset_data 恒生指数",
                {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金", "limit": 60}},
            ],
        },
        "看一下港股科技和黄金风险",
    )

    assert {
        "name": "get_index_data",
        "arguments": {
            "index_name": "恒生科技指数",
            "start_date": "2026-05-01",
            "end_date": "2026-06-10",
            "limit": 60,
        },
    } in plan["mcp_tools"]
    assert {"name": "get_index_data", "arguments": {"index_name": "恒生指数"}} in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金", "limit": 60}} in plan["mcp_tools"]
    assert not any(
        item["name"] == "get_global_asset_data"
        and item["arguments"].get("asset_name") in {"恒生科技指数", "恒生指数"}
        for item in plan["mcp_tools"]
    )


def test_macro_intent_defaults_include_hk_index_and_global_assets():
    plan = CLI()._normalize_intent_plan(
        {"intent": "macro", "needs_mcp": False, "mcp_tools": []},
        "美元走强对港股和黄金有什么影响",
    )

    assert plan["needs_mcp"] is True
    assert any(
        item["name"] == "get_index_data" and item["arguments"].get("index_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )
    assert any(
        item["name"] == "get_index_data" and item["arguments"].get("index_name") == "沪深300"
        for item in plan["mcp_tools"]
    )
    assert any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "美元指数"
        for item in plan["mcp_tools"]
    )
    assert any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "黄金"
        for item in plan["mcp_tools"]
    )
    assert not any(
        item["name"] == "get_global_asset_data"
        and item["arguments"].get("asset_name") in {"恒生科技指数", "恒生指数", "HSTECH"}
        for item in plan["mcp_tools"]
    )


def test_index_tool_accepts_asset_alias_arguments():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tools": [
                {
                    "name": "get_index_data",
                    "arguments": {
                        "assetName": "global_assets",
                        "sourceTable": "恒生科技指数",
                        "start_date": "2026-05-01",
                        "end_date": "2026-06-10",
                    },
                }
            ],
        },
        "恒生科技最新数据",
    )

    assert {
        "name": "get_index_data",
        "arguments": {
            "index_name": "恒生科技指数",
            "start_date": "2026-05-01",
            "end_date": "2026-06-10",
        },
    } in plan["mcp_tools"]


def test_hk_index_code_aliases_route_to_index_tool():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tools": [
                {
                    "name": "get_global_asset_data",
                    "arguments": {
                        "assetName": "global_indices",
                        "sourceTable": "global_index_daily",
                        "code": "HSTECH",
                        "start_date": "2026-05-01",
                        "limit": 3,
                    },
                },
                {
                    "name": "get_index_data",
                    "arguments": {
                        "sourceTable": "global_index_daily",
                        "indexCode": "HSTECH",
                        "limit": 3,
                    },
                },
            ],
        },
        "HSTECH 最新数据不应该停在 4月30日",
    )

    assert {
        "name": "get_index_data",
        "arguments": {"start_date": "2026-05-01", "limit": 3, "index_name": "恒生科技指数"},
    } in plan["mcp_tools"]
    assert {
        "name": "get_index_data",
        "arguments": {"limit": 3, "index_name": "恒生科技指数"},
    } in plan["mcp_tools"]
    assert not any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") in {"HSTECH", "恒生科技指数"}
        for item in plan["mcp_tools"]
    )


def test_english_hk_index_aliases_route_to_index_tool():
    plan = CLI()._normalize_intent_plan(
        {"intent": "single_asset", "needs_mcp": False, "mcp_tools": []},
        "Hang Seng Tech Index latest data",
    )

    assert plan["needs_mcp"] is True
    assert {
        "name": "get_index_data",
        "arguments": plan["mcp_tools"][0]["arguments"],
    } in plan["mcp_tools"]
    assert any(
        item["name"] == "get_index_data" and item["arguments"].get("index_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )

    plan = CLI()._normalize_intent_plan(
        {"intent": "data_lookup", "needs_mcp": False, "mcp_tools": []},
        "HSCEI latest data",
    )

    assert any(
        item["name"] == "get_index_data" and item["arguments"].get("index_name") == "恒生中国企业指数"
        for item in plan["mcp_tools"]
    )
    assert not any(item["name"] == "get_global_asset_data" for item in plan["mcp_tools"])


def test_cross_asset_hk_index_scenario_dedupes_to_correct_tools():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "macro",
            "needs_mcp": True,
            "tools": (
                "get_global_asset_data:{\"assetName\":\"global_assets\",\"sourceTable\":\"恒生科技指数\",\"limit\":60}\n"
                "get_index_data:{\"assetName\":\"HSTECH\",\"limit\":60}; "
                "get_global_asset_data 美元指数; "
                "get_global_asset_data 黄金"
            ),
        },
        "美元走强的时候，恒生科技指数和黄金应该怎么一起看",
    )

    assert {
        "name": "get_index_data",
        "arguments": {"limit": 60, "index_name": "恒生科技指数"},
    } in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "美元指数"}} in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金"}} in plan["mcp_tools"]
    assert sum(
        1
        for item in plan["mcp_tools"]
        if item["name"] == "get_index_data" and item["arguments"].get("index_name") == "恒生科技指数"
    ) == 1
    assert not any(
        item["name"] == "get_global_asset_data"
        and item["arguments"].get("asset_name") in {"HSTECH", "恒生科技指数"}
        for item in plan["mcp_tools"]
    )


def test_mcp_argument_aliases_keep_cli_keys_readable():
    cli = CLI()
    plan = cli._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tools": [
                {"name": "get_index_data", "arguments": {"indexName": "沪深300", "limit": 30}},
                {"name": "get_index_data", "arguments": {"index_name": "沪深300", "limit": 30}},
                {"name": "get_global_asset_data", "arguments": {"assetName": "黄金", "sourceTable": "global_assets"}},
                {"name": "get_product_history", "arguments": {"productId": "fund-001", "productType": "fund"}},
            ],
        },
        "帮我看沪深300、黄金和这个产品",
    )

    assert plan["mcp_tools"].count({"name": "get_index_data", "arguments": {"limit": 30, "index_name": "沪深300"}}) == 1
    assert {"name": "get_global_asset_data", "arguments": {"source_table": "global_assets", "asset_name": "黄金"}} in plan["mcp_tools"]
    assert {"name": "get_product_history", "arguments": {"product_id": "fund-001", "product_type": "fund"}} in plan["mcp_tools"]
    assert cli._mcp_result_key("get_index_data", plan["mcp_tools"][0]["arguments"], 0) == "get_index_data:沪深300"


def test_specific_single_asset_query_adds_precise_mcp_tool_when_llm_omits_tools():
    plan = CLI()._normalize_intent_plan(
        {"intent": "single_asset", "needs_mcp": False, "mcp_tools": []},
        "恒生科技指数最新数据",
    )

    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "client_default_by_intent"
    assert len(plan["mcp_tools"]) == 1
    assert plan["mcp_tools"][0]["name"] == "get_index_data"
    assert plan["mcp_tools"][0]["arguments"]["index_name"] == "恒生科技指数"
    assert "get_global_asset_data" not in {item["name"] for item in plan["mcp_tools"]}


def test_global_index_daily_table_name_does_not_trigger_ai_event_defaults():
    plan = CLI()._normalize_intent_plan(
        {"intent": "data_lookup", "needs_mcp": False, "mcp_tools": []},
        "恒生科技指数在 global_index_daily 这张全球指数表里，查最新数据",
    )

    assert plan["needs_mcp"] is True
    assert plan["mcp_tools"] == [
        {
            "name": "get_index_data",
            "arguments": {
                **CLI()._recent_market_window_args(days=60),
                "index_name": "恒生科技指数",
            },
        }
    ]


def test_specific_cross_asset_query_adds_index_asset_and_search_tools():
    plan = CLI()._normalize_intent_plan(
        {"intent": "data_lookup", "needs_mcp": False, "mcp_tools": []},
        "战争冲突影响下，恒生科技指数和黄金怎么看",
    )

    assert plan["needs_mcp"] is True
    assert any(
        item["name"] == "get_index_data" and item["arguments"].get("index_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )
    assert any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "黄金"
        for item in plan["mcp_tools"]
    )
    assert any(item["name"] == "web_search" for item in plan["mcp_tools"])
    assert not any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )


def test_risk_event_query_defaults_to_cross_asset_mcp_tools():
    plan = CLI()._normalize_intent_plan(
        {"intent": "risk", "needs_mcp": False, "mcp_tools": []},
        "战争冲突引发油价上涨，但AI利好还在发酵，股票市场和黄金短期怎么博弈？",
    )

    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "client_default_by_intent"
    expected = {
        ("get_index_data", "index_name", "恒生科技指数"),
        ("get_index_data", "index_name", "沪深300"),
        ("get_global_asset_data", "asset_name", "黄金"),
        ("get_global_asset_data", "asset_name", "原油"),
        ("get_global_asset_data", "asset_name", "美元指数"),
    }
    actual = {
        (item["name"], key, item["arguments"].get(key))
        for item in plan["mcp_tools"]
        for key in ("index_name", "asset_name")
        if item["arguments"].get(key)
    }
    assert expected <= actual
    assert any(item["name"] == "web_search" for item in plan["mcp_tools"])
    assert not any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )


def test_general_investment_hk_precious_metals_event_query_fetches_data():
    plan = CLI()._normalize_intent_plan(
        {"intent": "general_investment", "needs_mcp": False, "mcp_tools": []},
        "港股和贵金属在地缘冲突下短期怎么看？",
    )

    assert plan["needs_mcp"] is True
    assert any(
        item["name"] == "get_index_data" and item["arguments"].get("index_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )
    assert any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "黄金"
        for item in plan["mcp_tools"]
    )
    assert any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "原油"
        for item in plan["mcp_tools"]
    )
    assert any(item["name"] == "web_search" for item in plan["mcp_tools"])


def test_geopolitical_easing_query_defaults_to_cross_asset_mcp_tools():
    plan = CLI()._normalize_intent_plan(
        {"intent": "general_investment", "needs_mcp": False, "mcp_tools": []},
        "俄乌缓和迹象后，港股和黄金怎么看？",
    )

    assert plan["needs_mcp"] is True
    expected = {
        ("get_index_data", "index_name", "恒生科技指数"),
        ("get_index_data", "index_name", "沪深300"),
        ("get_global_asset_data", "asset_name", "美元指数"),
        ("get_global_asset_data", "asset_name", "黄金"),
        ("get_global_asset_data", "asset_name", "原油"),
    }
    actual = {
        (item["name"], key, item["arguments"].get(key))
        for item in plan["mcp_tools"]
        for key in ("index_name", "asset_name")
        if item["arguments"].get(key)
    }
    assert expected <= actual
    assert any(item["name"] == "web_search" for item in plan["mcp_tools"])
    assert not any(
        item["name"] == "get_global_asset_data" and item["arguments"].get("asset_name") == "恒生科技指数"
        for item in plan["mcp_tools"]
    )


@pytest.mark.parametrize(
    ("intent", "query", "expected_tools", "needs_search"),
    [
        (
            "single_asset",
            "HSTECH 最新数据为什么不应该停在 4月30日？",
            [("get_index_data", "index_name", "恒生科技指数")],
            True,
        ),
        (
            "market_overview",
            "港股今天行情怎么看？",
            [("get_index_data", "index_name", "恒生科技指数")],
            True,
        ),
        (
            "risk",
            "通胀重新上行时，黄金和股票市场哪个弹性更大？",
            [
                ("get_global_asset_data", "asset_name", "黄金"),
                ("get_index_data", "index_name", "沪深300"),
                ("get_index_data", "index_name", "恒生科技指数"),
            ],
            True,
        ),
        (
            "general_investment",
            "AI利好下美股和港股短期谁更强？",
            [
                ("get_index_data", "index_name", "恒生科技指数"),
                ("get_index_data", "index_name", "标普500"),
                ("get_index_data", "index_name", "纳斯达克指数"),
            ],
            True,
        ),
    ],
)
def test_natural_language_data_calling_scenarios_select_correct_mcp_tools(
    intent,
    query,
    expected_tools,
    needs_search,
):
    plan = CLI()._normalize_intent_plan(
        {"intent": intent, "needs_mcp": False, "mcp_tools": []},
        query,
    )

    actual = {
        (item["name"], key, item["arguments"].get(key))
        for item in plan["mcp_tools"]
        for key in ("index_name", "asset_name")
        if item["arguments"].get(key)
    }
    assert plan["needs_mcp"] is True
    for expected in expected_tools:
        assert expected in actual
    assert any(item["name"] == "web_search" for item in plan["mcp_tools"]) is needs_search
    assert not any(
        item["name"] == "get_global_asset_data"
        and item["arguments"].get("asset_name") in {"HSTECH", "恒生科技指数", "恒生指数"}
        for item in plan["mcp_tools"]
    )


def test_super66_registry_describes_hk_indices_as_index_data():
    tools = {item["name"]: item["description"] for item in Super66MCP().list_registry_tools()}

    assert "恒生科技指数" in tools["get_index_data"]
    assert "港股宽基指数" in tools["get_index_data"]
    assert "港股指数走 get_index_data" in tools["get_global_asset_data"]


def test_display_json_fragments_are_stripped_from_view():
    cli = CLI()
    text = '市场偏弱，先控制仓位。 ```json { "view": "内部结构", "suggestions": []'

    cleaned = cli._strip_display_json_fragments(text)

    assert cleaned == "市场偏弱，先控制仓位。"
    assert "```json" not in cleaned
    assert '"view"' not in cleaned


def test_intent_plan_accepts_multiline_string_mcp_tool_shortcuts():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "market_overview",
            "needs_mcp": True,
            "tools": (
                "get_index_data:沪深300\n"
                "web_search:{\"query\":\"政策影响, 资金面\",\"count\":3}; "
                "get_global_asset_data 黄金"
            ),
        },
        "今天行情怎么样",
    )

    assert {"name": "get_index_data", "arguments": {"index_name": "沪深300"}} in plan["mcp_tools"]
    assert {"name": "web_search", "arguments": {"query": "政策影响, 资金面", "count": 3}} in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金"}} in plan["mcp_tools"]


def test_intent_plan_accepts_markdown_list_mcp_tool_shortcuts():
    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tools": """
- `get_index_data:沪深300`
1. web_search:{"query":"政策影响","count":2}
- [ ] tool:get_global_asset_data 黄金
• get_future_market_data:AU
""",
        },
        "用工具看一下市场",
    )

    assert {"name": "get_index_data", "arguments": {"index_name": "沪深300"}} in plan["mcp_tools"]
    assert {"name": "web_search", "arguments": {"query": "政策影响", "count": 2}} in plan["mcp_tools"]
    assert {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金"}} in plan["mcp_tools"]
    assert {"name": "get_future_market_data", "arguments": {"contract_code": "AU"}} in plan["mcp_tools"]


@pytest.mark.asyncio
async def test_collect_client_data_runs_flexible_llm_tool_shapes(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, **(arguments or {})}

    async def fake_search(self, query, arguments):
        calls.append(("web_search", arguments))
        return {"query": query, "provider": "local_chrome"}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    data = await cli._collect_client_mcp_data(
        "查一下黄金和政策",
        {},
        {
            "needs_mcp": True,
            "mcp_tools": [
                {"tool": "get_global_asset_data", "args": {"asset_name": "黄金", "limit": 60}},
                {"tool_name": "web_search", "parameters": {"query": "黄金 政策 影响", "count": 2}},
            ],
        },
    )

    assert calls == [
        ("get_global_asset_data", {"asset_name": "黄金", "limit": 60}),
        ("web_search", {"query": "黄金 政策 影响", "count": 2}),
    ]
    assert "get_global_asset_data:黄金" in data
    assert "web_search:黄金政策影响" in data


@pytest.mark.asyncio
async def test_collect_client_data_routes_hk_index_aliases_to_reusable_keys(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, "arguments": arguments or {}}

    async def fake_search(self, query, arguments):
        calls.append(("web_search", arguments))
        return {"query": query, "provider": "local_chrome"}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    data = await cli._collect_client_mcp_data(
        "美元走强时恒生科技和黄金怎么一起看",
        {},
        {
            "needs_mcp": True,
            "mcp_tools": [
                {
                    "name": "get_global_asset_data",
                    "arguments": {"assetName": "global_assets", "sourceTable": "恒生科技指数", "limit": 60},
                },
                {"name": "get_index_data", "arguments": {"assetName": "HSTECH", "limit": 60}},
                {"name": "get_global_asset_data", "arguments": {"assetName": "美元指数", "limit": 60}},
                {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金", "limit": 60}},
                {"name": "web_search", "arguments": {"query": "美元 恒生科技 黄金", "count": 3}},
            ],
        },
    )

    assert calls == [
        ("get_index_data", {"limit": 60, "index_name": "恒生科技指数"}),
        ("get_global_asset_data", {"limit": 60, "asset_name": "美元指数"}),
        ("get_global_asset_data", {"asset_name": "黄金", "limit": 60}),
        ("web_search", {"query": "美元 恒生科技 黄金", "count": 3}),
    ]
    assert "get_index_data:恒生科技指数" in data
    assert "get_global_asset_data:美元指数" in data
    assert "get_global_asset_data:黄金" in data
    assert "web_search:美元恒生科技黄金" in data
    assert "get_global_asset_data:恒生科技指数" not in data


@pytest.mark.asyncio
async def test_collect_client_data_routes_openai_tool_call_hstech_to_index(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, "latest": {"date": "2026-06-10", "close": 4724.79}, **(arguments or {})}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)

    plan = CLI()._normalize_intent_plan(
        {
            "intent": "data_lookup",
            "needs_mcp": True,
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_global_asset_data",
                        "arguments": json.dumps(
                            {
                                "assetName": "global_indices",
                                "sourceTable": "global_index_daily",
                                "code": "HSTECH",
                                "limit": 60,
                            },
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        },
        "HSTECH 最新数据",
    )
    data = await CLI()._collect_client_mcp_data("HSTECH 最新数据", {}, plan)

    assert calls == [("get_index_data", {"limit": 60, "index_name": "恒生科技指数"})]
    assert "get_index_data:恒生科技指数" in data
    assert data["get_index_data:恒生科技指数"]["latest"]["date"] == "2026-06-10"
    assert "get_global_asset_data:恒生科技指数" not in data


@pytest.mark.asyncio
async def test_collect_client_data_defaults_specific_asset_when_tools_are_omitted(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, "arguments": arguments or {}}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)

    cli = CLI()
    plan = {"intent": "single_asset", "needs_mcp": False, "mcp_tools": []}
    data = await cli._collect_client_mcp_data("恒生科技指数最新数据", {}, plan)

    assert calls == [("get_index_data", plan["mcp_tools"][0]["arguments"])]
    assert plan["needs_mcp"] is True
    assert plan["tool_selection_source"] == "client_default_by_intent"
    assert plan["mcp_tools"][0]["arguments"]["index_name"] == "恒生科技指数"
    assert "get_index_data:恒生科技指数" in data
    assert "get_global_asset_data:恒生科技指数" not in data


def test_mcp_tool_label_is_readable_for_progress_trace():
    cli = CLI()

    assert cli._mcp_tool_label("get_index_data", {"index_name": "沪深300"}) == "get_index_data / 沪深300"
    assert cli._mcp_tool_label("web_search", {"query": cli._today_market_search_query()}).startswith(
        f"web_search / {cli._today_market_search_query()[:10]}"
    )


@pytest.mark.asyncio
async def test_collect_client_data_keeps_partial_results_when_one_tool_fails(monkeypatch):
    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            return {"tool": tool_name, **(arguments or {})}

    async def failing_search(self, query, arguments):
        raise RuntimeError("chrome missing")

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", failing_search)

    cli = CLI()
    search_key = cli._mcp_result_key("web_search", {"query": cli._today_market_search_query()}, 5)
    data = await cli._collect_client_mcp_data(
        "今天行情怎么样",
        {},
        {"needs_mcp": False, "mcp_tools": []},
    )

    assert "get_index_data:沪深300" in data
    assert "get_global_asset_data:黄金" in data
    assert f"{search_key}:error" in data


@pytest.mark.asyncio
async def test_collect_client_data_keeps_web_search_when_super66_init_fails(monkeypatch):
    class BrokenSuper66MCP:
        def __init__(self):
            raise RuntimeError("super66 auth expired")

    async def fake_search(self, query, arguments):
        return {"query": query, "provider": "local_chrome", "results": [{"title": "政策新闻"}]}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", BrokenSuper66MCP)
    monkeypatch.setattr(CLI, "_run_local_chrome_search", fake_search)

    cli = CLI()
    search_key = cli._mcp_result_key("web_search", {"query": cli._today_market_search_query()}, 5)
    data = await cli._collect_client_mcp_data(
        "今天行情怎么样",
        {},
        {"needs_mcp": False, "mcp_tools": []},
    )

    assert data["super66_error"] == "super66 auth expired"
    assert "get_index_data:沪深300:error" in data
    assert "get_global_asset_data:黄金:error" in data
    assert data[search_key]["provider"] == "local_chrome"
    assert data[search_key]["results"][0]["title"] == "政策新闻"


@pytest.mark.asyncio
async def test_vague_market_query_uses_llm_tools_even_when_needs_mcp_false(monkeypatch):
    calls = []

    class FakeSuper66MCP:
        async def call_tool(self, tool_name, arguments=None, use_cache=True):
            calls.append((tool_name, arguments))
            return {"tool": tool_name, **(arguments or {})}

    monkeypatch.setattr("src.mcp.super66.Super66MCP", FakeSuper66MCP)

    data = await CLI()._collect_client_mcp_data(
        "今天行情怎么样",
        {},
        {
            "needs_mcp": False,
            "mcp_tools": [
                {"name": "get_index_data", "arguments": {"index_name": "沪深300", "limit": 60}},
            ],
        },
    )

    assert calls == [("get_index_data", {"index_name": "沪深300", "limit": 60})]
    assert "get_index_data:沪深300" in data


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
            "next_actions": ["/plan 看本轮数据来源", "继续问：把这个做成图表"],
            "followups": ["你更关心指数还是个股？", "你的持仓周期是日内还是一个月？"],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={
            "mcp_data": ["get_index_data:沪深300", "get_global_asset_data:黄金"],
            "mcp_snapshot": ["get_index_data:沪深300: 日期 2026-06-10，最新 4100，涨跌幅 1.2"],
            "route_source": "local_llm",
            "tool_selection_source": "local_llm",
            "tool_selection_note": "本机大模型选择指数和全球资产工具",
        },
    )

    assert "我已读取 2 个数据源（指数 1、跨资产 1）" in result
    assert "原始明细可用 /plan 查看" in result
    assert "关键数据：" not in result
    assert "日期 2026-06-10" not in result
    assert "涨跌幅 1.2" not in result
    assert "- 先看成交量。" in result
    assert "- 再看主线持续性。" in result
    assert "- 不追高。" in result
    assert "- 控制仓位。" in result
    assert "- 持仓。" in result
    assert "- 周期。" in result
    assert "下一步：" in result
    assert "Agent Trail：" not in result
    assert "快捷操作：" not in result
    assert "- /plan 看本轮数据来源" in result
    assert "- 继续问：把这个做成图表" in result
    assert "你也可以继续问：" not in result
    assert "如果需要图表或报告，可以继续说" not in result
    assert "- 可" not in result


def test_client_side_advice_formats_object_sections_as_natural_items():
    cli = CLI()
    result = cli._format_client_advice(
        query="A股怎么看",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.72}],
        synthesis={
            "view": "先看结构，不急着下结论。",
            "suggestions": [
                {"action": "先看成交量是否扩散", "reason": "确认主线不是单点脉冲"},
                {"title": "跟踪红利和科技的跷跷板", "condition": "利率预期继续下行时"},
            ],
            "risk_controls": [
                {"risk": "不要追高单日涨幅过大的方向", "threshold": "回撤超过 3% 先降仓"},
            ],
            "missing_data": [
                {"missing": "你的持仓周期"},
                {"question": "仓位上限是多少？"},
            ],
            "next_actions": [
                {"command": "/plan", "reason": "查看本轮 MCP 和服务端链路"},
            ],
            "followups": [
                {"question": "你更关心指数还是个股？"},
            ],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={},
    )

    assert "- 先看成交量是否扩散；原因: 确认主线不是单点脉冲" in result
    assert "- 跟踪红利和科技的跷跷板；条件: 利率预期继续下行时" in result
    assert "- 不要追高单日涨幅过大的方向；阈值: 回撤超过 3% 先降仓" in result
    assert "- 你的持仓周期" in result
    assert "- 仓位上限是多少？" in result
    assert "- /plan；原因: 查看本轮 MCP 和服务端链路" in result
    assert "你更关心指数还是个股？" not in result


def test_client_side_advice_keeps_artifact_answer_compact():
    cli = CLI()
    result = cli._format_client_advice(
        query="把今天行情做成图表",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.8}],
        synthesis={
            "view": "图表已经生成，可以打开查看。",
            "suggestions": [],
            "risk_controls": [],
            "missing_data": [],
            "resource_links": [{"source": "server", "title": "行情图", "html_url": "https://cdn.example.com/chart.html"}],
            "artifact_results": [
                {
                    "title": "行情图",
                    "status": "success",
                    "saved": {"html": "/tmp/chart.html", "json": "/tmp/chart.json"},
                    "resource_links": ["行情图: https://cdn.example.com/chart.html"],
                }
            ],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={"mcp_links": ["盘面新闻: https://example.com/news"]},
    )

    assert "图表：" in result
    assert "行情图: 已生成" in result
    assert "快捷操作：" not in result
    assert "产物收件箱：" not in result
    assert "{'action'" not in result
    assert "{'risk'" not in result


def test_client_advice_hides_agent_trail_from_regular_answer():
    result = CLI()._format_client_advice(
        query="今天行情怎么样",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.6}],
        synthesis={
            "view": "先按低确定性看盘。",
            "suggestions": ["先看宽基指数"],
            "risk_controls": ["不要追单日热点"],
            "missing_data": [],
        },
        raw_text="",
        provider="DeepSeek",
        model="deepseek-v4-flash",
        data_inputs={
            "mcp_data": ["get_index_data:沪深300"],
            "tool_selection_source": "client_market_overview_fallback",
            "tool_selection_note": "宽泛行情问题没有工具计划，客户端补齐默认 MCP/web_search",
        },
    )

    assert "Agent Trail：" not in result
    assert "编排: 客户端兜底补齐" not in result


def test_mcp_snapshot_lines_extracts_readable_market_fields():
    cli = CLI()
    lines = cli._mcp_snapshot_lines({
        "get_index_data:沪深300": {
            "data": [
                {"date": "2026-06-09", "close": 4050, "pct_chg": -0.3},
                {"date": "2026-06-10", "close": 4100, "pct_chg": 1.2, "volume": 123456},
            ],
            "api_key": "should-not-render",
        },
        "super66_error": {"error": "network"},
    })

    assert lines == [
        "get_index_data:沪深300: 日期 2026-06-10，最新 4100，成交量 123456，区间收益 1.23%"
    ]
    assert "should-not-render" not in "\n".join(lines)


def test_mcp_snapshot_lines_use_latest_date_for_descending_rows():
    lines = CLI()._mcp_snapshot_lines({
        "get_index_data:恒生科技指数": {
            "data": [
                {"date": "2026-06-10", "close": 4724.79, "pct_chg": 1.2},
                {"date": "2026-04-30", "close": 4300.12, "pct_chg": -0.8},
            ]
        }
    })

    joined = "\n".join(lines)
    assert "日期 2026-06-10" in joined
    assert "最新 4725" in joined
    assert "2026-04-30" not in joined


def test_chart_return_prefers_strict_start_end_close_division():
    cli = CLI()
    data = cli._coerce_chart_artifact_data({
        "指数A": {
            "history": [
                {"date": "2026-01-01", "close": 100, "change_pct": 99},
                {"date": "2026-01-10", "close": 110, "change_pct": -50},
            ]
        },
        "指数B": {
            "start_close": 200,
            "end_close": 190,
            "change_pct": 99,
        },
    })

    assert data["指数A"] == pytest.approx(10.0)
    assert data["指数B"] == pytest.approx(-5.0)


def test_super66_normalizes_supabase_rows_for_market_snapshot():
    payload = {
        "code": 200,
        "data": {
            "result": {
                "data": [
                    {
                        "指数名称": "沪深300",
                        "trade_date": "2026-06-10",
                        "close_price": "4100.5",
                        "pct_chg": "1.2%",
                        "turnover_amount": "123,456",
                    }
                ],
                "count": 1,
            }
        },
    }

    result = Super66MCP()._extract_result(payload, "get_index_data", {"index_name": "沪深300"})
    latest = result["latest"]
    lines = CLI()._mcp_snapshot_lines({"get_index_data:沪深300": result})

    assert result["source_format"] == "supabase_rows"
    assert result["count"] == 1
    assert latest["index_name"] == "沪深300"
    assert latest["date"] == "2026-06-10"
    assert latest["close"] == 4100.5
    assert latest["change_pct"] == 1.2
    assert lines == [
        "get_index_data:沪深300: 名称 沪深300，日期 2026-06-10，最新 4100，成交额 123456，涨跌幅 1.2"
    ]


def test_super66_uses_latest_date_when_rows_are_descending():
    payload = {
        "code": 200,
        "data": {
            "result": {
                "rows": [
                    {"指数名称": "恒生科技指数", "date": "2026-06-10", "close": 4724.79},
                    {"指数名称": "恒生科技指数", "date": "2026-04-30", "close": 4300.12},
                ],
                "count": 2,
            }
        },
    }

    result = Super66MCP()._extract_result(payload, "dc66_get_index_data", {"indexName": "恒生科技指数"})

    assert result["rows"][0]["date"] == "2026-04-30"
    assert result["rows"][-1]["date"] == "2026-06-10"
    assert result["latest"]["date"] == "2026-06-10"
    assert result["latest"]["close"] == 4724.79


def test_super66_uses_latest_tradedate_alias_in_nested_payload():
    payload = {
        "code": 200,
        "data": {
            "result": {
                "payload": {
                    "data": [
                        {"指数名称": "恒生科技指数", "tradedate": "2026/06/10", "close_price": "4724.79"},
                        {"指数名称": "恒生科技指数", "tradedate": "2026/04/30", "close_price": "4300.12"},
                    ]
                },
                "count": 2,
            }
        },
    }

    result = Super66MCP()._extract_result(payload, "dc66_get_index_data", {"indexName": "恒生科技指数"})

    assert result["rows"][0]["date"] == "2026/04/30"
    assert result["rows"][-1]["date"] == "2026/06/10"
    assert result["latest"]["date"] == "2026/06/10"
    assert result["latest"]["close"] == 4724.79


def test_super66_extracts_rows_from_mcp_text_content_json():
    payload = {
        "code": 200,
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "records": [
                            {"指数名称": "恒生科技指数", "trade_date": "2026-06-10", "close": 4724.79},
                            {"指数名称": "恒生科技指数", "trade_date": "2026-04-30", "close": 4300.12},
                        ],
                        "count": 2,
                    },
                    ensure_ascii=False,
                ),
            }
        ],
    }

    result = Super66MCP()._extract_result(payload, "dc66_get_index_data", {"indexName": "恒生科技指数"})

    assert result["source_format"] == "supabase_rows"
    assert result["rows"][0]["date"] == "2026-04-30"
    assert result["rows"][-1]["date"] == "2026-06-10"
    assert result["latest"]["date"] == "2026-06-10"
    assert result["latest"]["close"] == 4724.79


def test_super66_does_not_treat_plain_mcp_text_content_as_market_rows():
    payload = {
        "code": 200,
        "content": [
            {
                "type": "text",
                "text": "没有找到符合条件的行情数据，请调整指数名称。",
            }
        ],
    }

    result = Super66MCP()._extract_result(payload, "dc66_get_index_data", {"indexName": "恒生科技指数"})

    assert result == payload
    assert "latest" not in result
    assert "source_format" not in result


def test_super66_maps_mcp_arguments_to_production_schema():
    mcp = Super66MCP()

    assert mcp._normalize_tool_call(
        "get_global_asset_data",
        {
            "assetName": "global_assets",
            "sourceTable": "恒生科技指数",
            "start_date": "2026-05-01",
            "end_date": "2026-06-10",
            "limit": 3,
        },
    ) == (
        "dc66_get_index_data",
        {"indexName": "恒生科技指数", "startDate": "2026-05-01", "endDate": "2026-06-10", "limit": 3},
    )
    assert mcp._normalize_tool_call(
        "get_index_data",
        {"assetName": "HSTECH", "start_date": "2026-05-01", "limit": 3},
    ) == (
        "dc66_get_index_data",
        {"startDate": "2026-05-01", "limit": 3, "indexName": "恒生科技指数"},
    )
    assert mcp._normalize_tool_call(
        "get_global_asset_data",
        {
            "assetName": "global_indices",
            "sourceTable": "global_index_daily",
            "code": "HSTECH",
            "start_date": "2026-05-01",
            "limit": 3,
        },
    ) == (
        "dc66_get_index_data",
        {"startDate": "2026-05-01", "limit": 3, "indexName": "恒生科技指数"},
    )
    assert mcp._normalize_tool_call(
        "get_index_data",
        {"sourceTable": "global_index_daily", "indexCode": "HSTECH", "start_date": "2026-05-01", "limit": 3},
    ) == (
        "dc66_get_index_data",
        {"startDate": "2026-05-01", "limit": 3, "indexName": "恒生科技指数"},
    )
    assert mcp._normalize_tool_call(
        "get_global_asset_data",
        {"sourceTable": "global_index_daily", "symbol": "Hang Seng Tech Index", "limit": 3},
    ) == (
        "dc66_get_index_data",
        {"limit": 3, "indexName": "恒生科技指数"},
    )
    assert mcp._normalize_tool_call(
        "get_global_asset_data",
        {"sourceTable": "global_index_daily", "ticker": "HSCEI", "limit": 3},
    ) == (
        "dc66_get_index_data",
        {"limit": 3, "indexName": "恒生中国企业指数"},
    )
    assert mcp._normalize_tool_arguments(
        "get_index_data",
        {"index_name": "恒生科技指数", "start_date": "2026-05-01", "end_date": "2026-06-10", "limit": 3},
    ) == {"indexName": "恒生科技指数", "startDate": "2026-05-01", "endDate": "2026-06-10", "limit": 3}
    assert mcp._normalize_tool_arguments(
        "get_global_asset_data",
        {"asset_name": "黄金", "source_table": "黄金", "start_date": "2026-05-01", "limit": 3},
    ) == {"assetName": "黄金", "sourceTable": "黄金", "startDate": "2026-05-01", "limit": 3}


@pytest.mark.asyncio
async def test_super66_call_tool_redirects_hk_index_to_index_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        content = b"{}"

        def json(self):
            return {
                "code": 200,
                "data": {
                    "result": {
                        "rows": [
                            {"date": "2026-06-10", "close": 4724.79, "volume": 83224013000}
                        ]
                    }
                },
            }

    class FakeClient:
        is_closed = False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setenv("SUPER66_MCP_TOKEN", "token")
    mcp = Super66MCP()
    mcp._client = FakeClient()
    mcp._cache.clear()

    result = await mcp.call_tool(
        "get_global_asset_data",
        {
            "assetName": "global_assets",
            "sourceTable": "恒生科技指数",
            "code": "HSTECH",
            "start_date": "2026-05-01",
            "end_date": "2026-06-10",
        },
        use_cache=False,
    )

    assert captured["json"] == {
        "name": "dc66_get_index_data",
        "arguments": {
            "startDate": "2026-05-01",
            "endDate": "2026-06-10",
            "indexName": "恒生科技指数",
        },
    }
    assert result["tool"] == "dc66_get_index_data"
    assert result["arguments"]["indexName"] == "恒生科技指数"
    assert result["latest"]["date"] == "2026-06-10"


def test_super66_normalizes_columnar_market_series():
    payload = {
        "code": 200,
        "data": {
            "result": {
                "dates": ["2026-06-09", "2026-06-10"],
                "closes": [4050, 4100],
                "volumes": [10, 20],
            }
        },
    }

    result = Super66MCP()._extract_result(payload, "get_index_data", {"indexName": "沪深300"})
    lines = CLI()._mcp_snapshot_lines({"get_index_data:沪深300": result})

    assert result["latest"]["index_name"] == "沪深300"
    assert result["latest"]["date"] == "2026-06-10"
    assert result["latest"]["close"] == 4100
    assert lines == ["get_index_data:沪深300: 名称 沪深300，日期 2026-06-10，最新 4100，成交量 20，区间收益 1.23%"]


def test_chrome_search_defaults_to_bing_and_filters_block_pages(monkeypatch):
    monkeypatch.delenv("ERLANGSHEN_SEARCH_ENGINE", raising=False)

    url = build_search_url("今天行情")

    assert "bing.com/search" in url
    assert "mkt=zh-CN" in url
    assert _is_noise_search_result("Why did this happen?", "https://www.google.com/sorry/index")
    assert _is_noise_search_result("Terms of Service", "https://policies.google.com/terms")
    assert _is_noise_search_result("网页", "https://www.bing.com/?scope=web&FORM=HDRSC1")
    assert _is_noise_search_result("学术", "https://www.bing.com/academic/search?q=market")
    assert not _is_noise_search_result("央行释放流动性信号", "https://finance.example.com/news")


def test_mcp_snapshot_lines_extracts_web_search_titles_without_secret_fields():
    cli = CLI()
    lines = cli._mcp_snapshot_lines({
        "web_search:最新政策影响": {
            "query": "最新政策影响",
            "provider": "local_chrome",
            "api_key": "should-not-render",
            "results": [
                {"title": "央行释放流动性信号", "url": "https://www.example.com/news/1"},
                {"title": "科技成长板块成交活跃", "source": "财经网"},
            ],
        },
    })

    joined = "\n".join(lines)
    assert "web_search:最新政策影响: 网页线索 央行释放流动性信号 (example.com) https://www.example.com/news/1，网页线索 科技成长板块成交活跃 (财经网)" in joined
    assert "should-not-render" not in joined
    assert "api_key" not in joined


def test_mcp_resource_links_extract_web_and_image_urls():
    links = CLI()._mcp_resource_links({
        "web_search:政策": {
            "results": [
                {"title": "政策新闻", "url": "https://example.com/news"},
                {"title": "市场图", "image_url": "https://example.com/chart.png"},
                {"title": "重复", "url": "https://example.com/news"},
            ],
            "api_key": "should-not-render",
        },
    })

    joined = "\n".join(links)
    assert "政策新闻: https://example.com/news" in joined
    assert "市场图 图片: https://example.com/chart.png" in joined
    assert joined.count("https://example.com/news") == 1
    assert "should-not-render" not in joined


def test_resource_links_extract_server_web_image_and_file_artifacts():
    cli = CLI()

    links = cli._resource_links_from_value(
        {
            "resources": [
                {"title": "行情网页", "html_url": "https://cdn.example.com/market.html"},
                {"title": "行情图片", "image_url": "https://cdn.example.com/market.png"},
                {"title": "PDF报告", "pdf_url": "https://cdn.example.com/report.pdf"},
                {"title": "本地图表", "file_url": "file:///tmp/erlangshen/chart.html"},
            ],
            "authorization": "should-not-render",
        },
        "服务端资源",
    )

    joined = "\n".join(links)
    assert "行情网页: https://cdn.example.com/market.html" in joined
    assert "行情图片 图片: https://cdn.example.com/market.png" in joined
    assert "PDF报告: https://cdn.example.com/report.pdf" in joined
    assert "本地图表: file:///tmp/erlangshen/chart.html" in joined
    assert "should-not-render" not in joined


def test_collect_turn_resource_links_accepts_named_server_resource_objects():
    cli = CLI()

    links = cli._collect_turn_resource_links(
        {
            "intent_resource_links": [
                {"source": "server", "title": "服务端图表", "html_url": "https://cdn.example.com/chart.html"},
                {"source": "server", "title": "服务端图片", "image_url": "https://cdn.example.com/chart.png"},
            ],
            "mcp_links": [],
        },
        {
            "resource_links": [
                {"source": "LLM resource", "title": "服务端报告", "html_url": "https://cdn.example.com/report.html"},
                "行情图片: https://cdn.example.com/market.png",
            ],
            "resources": [
                {"source": "LLM resource", "title": "延伸阅读", "url": "https://example.com/read"},
            ],
        },
    )

    assert links == [
        {"source": "server", "link": "服务端图表: https://cdn.example.com/chart.html"},
        {"source": "server", "link": "服务端图片: https://cdn.example.com/chart.png"},
        {"source": "LLM resource", "link": "服务端报告: https://cdn.example.com/report.html"},
        {"source": "LLM resource", "link": "行情图片: https://cdn.example.com/market.png"},
        {"source": "LLM resource", "link": "延伸阅读: https://example.com/read"},
    ]


def test_vague_market_answer_removes_empty_data_claim_when_snapshot_exists():
    result = CLI()._format_client_advice(
        query="今天行情怎么样",
        matches=[{"scene": "市场监测与事件响应", "confidence": 1.0}],
        synthesis={
            "view": "目前我手头没有具体的实时市场数据，无法准确描述今天整体行情。科技成长成交活跃。",
            "suggestions": ["先看指数分化", "再看成交额"],
            "risk_controls": ["不要把盘中波动当趋势"],
            "missing_data": ["你的持仓和周期"],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={
            "mcp_data": ["get_index_data:沪深300", "web_search:今日市场行情重要新闻政策资金面"],
            "mcp_snapshot": [
                "get_index_data:沪深300: 日期 2026-06-10，最新 4100，涨跌幅 1.2",
                "web_search:今日市场行情重要新闻政策资金面: 网页线索 科技成长板块成交活跃 (财经网)",
            ],
            "mcp_links": ["科技成长新闻: https://example.com/news"],
        },
    )

    assert "关键数据：" not in result
    assert "我已读取 2 个数据源（指数 1、事件/宏观线索 1）" in result
    assert "可打开资源：" in result
    assert "科技成长新闻: https://example.com/news" in result
    assert "Agent Trail：" not in result
    assert "科技成长成交活跃" in result
    assert "没有具体的实时市场数据" not in result
    assert "无法准确描述今天整体行情" not in result
    assert "方向性盘面判断" in result
    assert "如果要落到你的账户，我还需要知道：" in result
    assert "我还需要你补充：" not in result
    assert "你也可以继续问：" not in result


def test_client_advice_shows_named_resource_links_without_workspace_save():
    result = CLI()._format_client_advice(
        query="把这个做成图表",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.9}],
        synthesis={
            "view": "图表已经由服务端生成。",
            "suggestions": [],
            "risk_controls": [],
            "missing_data": [],
            "artifact_results": [
                {
                    "title": "资产表现",
                    "status": "success",
                    "saved": None,
                    "resource_links": [
                        "资产表现网页: https://cdn.example.com/asset-chart.html",
                        "资产表现图片: https://cdn.example.com/asset-chart.png",
                    ],
                }
            ],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={},
    )

    assert "工作区未授权" in result
    assert "资源: 资产表现网页: https://cdn.example.com/asset-chart.html" in result
    assert "资源: 资产表现图片: https://cdn.example.com/asset-chart.png" in result


def test_saved_advice_report_includes_context_and_resource_links(monkeypatch, tmp_path):
    workspace_file = tmp_path / "workspaces.json"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE_FILE", str(workspace_file))
    monkeypatch.setenv("ERLANGSHEN_WORKSPACE", str(project_dir))
    approve_workspace(project_dir)

    path = CLI()._save_advice_report(
        query="今天行情怎么样",
        content="盘面分化，先看成交和主线。",
        artifact_results=[],
        data_inputs={
            "mcp_data": ["get_index_data:沪深300", "web_search:今日市场"],
            "user_data": [],
            "mcp_snapshot": ["get_index_data:沪深300: 日期 2026-06-10，涨跌幅 1.2"],
            "mcp_links": ["市场新闻: https://example.com/news"],
            "intent_resource_links": ["盘面图片: https://cdn.example.com/market.png"],
            "agent_trace": ["本机理解问题意图", "向服务端确认问题场景", "用本机 Xiaomi MiMo 生成分析"],
        },
    )

    assert path
    report_text = Path(path).read_text(encoding="utf-8")
    assert "## 数据与执行上下文" in report_text
    assert "### MCP 快照" in report_text
    assert "- get_index_data:沪深300: 日期 2026-06-10，涨跌幅 1.2" in report_text
    assert "### 可打开资源" in report_text
    assert "- 市场新闻: https://example.com/news" in report_text
    assert "- 盘面图片: https://cdn.example.com/market.png" in report_text
    assert "### 执行过程" in report_text
    assert "- 本机理解问题意图" in report_text
    assert "## 下一步" in report_text
    assert "`/links`" in report_text
    assert "`/links open 1`" in report_text


def test_vague_market_answer_filters_generic_missing_data_when_snapshot_exists():
    result = CLI()._format_client_advice(
        query="今天行情怎么样",
        matches=[{"scene": "市场监测与事件响应", "confidence": 1.0}],
        synthesis={
            "view": "科技成长成交活跃，指数分化。",
            "suggestions": ["先看主线和成交额"],
            "risk_controls": ["不要基于单日波动追涨杀跌"],
            "missing_data": ["具体市场指数的实时点位", "重大新闻事件", "你的持仓和风险偏好"],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={
            "mcp_data": ["get_index_data:沪深300", "web_search:今日市场行情重要新闻政策资金面"],
            "mcp_snapshot": [
                "get_index_data:沪深300: 日期 2026-06-10，最新 4100，涨跌幅 1.2",
                "web_search:今日市场行情重要新闻政策资金面: 网页线索 科技成长板块成交活跃 (财经网)",
            ],
        },
    )

    assert "关键数据：" not in result
    assert "我已读取 2 个数据源（指数 1、事件/宏观线索 1）" in result
    assert "如果要落到你的账户，我还需要知道：" in result
    assert "你的持仓和风险偏好" in result
    assert "具体市场指数的实时点位" not in result
    assert "重大新闻事件" not in result


def test_vague_market_answer_explains_data_channel_failure():
    result = CLI()._format_client_advice(
        query="今天行情怎么样",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.4}],
        synthesis={
            "view": "先看作低确定性的观察。",
            "suggestions": ["补充关注市场"],
            "risk_controls": ["降低仓位冲动"],
            "missing_data": ["指数快照"],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={
            "mcp_data": ["super66_error", "web_search:今日市场行情重要新闻政策资金面:error"],
            "mcp_snapshot": [],
        },
    )

    assert "super-66 MCP 暂时没有成功返回行情数据" in result
    assert "数据通道没有拿到可用行情" in result
    assert "低确定性的框架" in result


def test_client_advice_shows_partial_data_failures_and_repair_action():
    result = CLI()._format_client_advice(
        query="今天行情怎么样",
        matches=[{"scene": "市场监测与事件响应", "confidence": 0.8}],
        synthesis={
            "view": "科技成长板块成交活跃。",
            "suggestions": ["先看指数和成交额"],
            "risk_controls": ["不要把单条新闻当成趋势"],
            "missing_data": [],
            "next_actions": ["/plan 看本轮数据来源"],
        },
        raw_text="",
        provider="Xiaomi MiMo",
        model="mimo-v2.5",
        data_inputs={
            "mcp_data": [
                "get_index_data:沪深300",
                "web_search:今日市场行情重要新闻政策资金面:error",
            ],
            "mcp_snapshot": ["get_index_data:沪深300: 日期 2026-06-10，最新 4100，涨跌幅 1.2"],
        },
    )

    assert "我已读取 1 个数据源（指数 1）" in result
    assert "另有 1 个数据通道未成功" in result
    assert "- /plan 看本轮数据来源" in result
    assert "执行 /doctor 检查本地 Chrome web_search" in result


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
async def test_interactive_mode_confirms_workspace_before_header(monkeypatch):
    cli = CLI()
    events = []
    monkeypatch.setattr(cli, "_init_hooks", lambda: False)
    monkeypatch.setattr(cli, "_confirm_workspace_sandbox", lambda: events.append("workspace"))
    monkeypatch.setattr(cli, "print_header", lambda: events.append("header"))

    async def stop_after_start():
        events.append("prompt")
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_read_prompt", stop_after_start)

    await cli.interactive_mode()

    assert events == ["workspace", "header", "prompt"]


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
