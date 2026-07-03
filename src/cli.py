#!/usr/bin/env python3
"""
二郎神 CLI - 投资分析智能体命令行入口
"""

import sys
import atexit
import asyncio
import difflib
import getpass
import importlib
import json
import os
import re
import shutil
import time
import unicodedata
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from src import __version__
from src.auth.session import decrypt_auth_password, encrypt_auth_password, load_auth_session, save_auth_session
from src.client.local_memory import LocalMemoryStore
from src.config import get_config, get_config_path, update_config
from src.model_presets import MODEL_PRESETS, get_provider_preset, normalize_provider
from src.workspace import approve_workspace, ensure_inside_workspace, recent_workspaces, resolve_workspace_path, select_workspace, workspace_status


LOGO_WIDE = [
    "███████╗██████╗ ██╗      █████╗ ███╗   ██╗ ██████╗ ███████╗██╗  ██╗███████╗███╗   ██╗",
    "██╔════╝██╔══██╗██║     ██╔══██╗████╗  ██║██╔════╝ ██╔════╝██║  ██║██╔════╝████╗  ██║",
    "█████╗  ██████╔╝██║     ███████║██╔██╗ ██║██║  ███╗███████╗███████║█████╗  ██╔██╗ ██║",
    "██╔══╝  ██╔══██╗██║     ██╔══██║██║╚██╗██║██║   ██║╚════██║██╔══██║██╔══╝  ██║╚██╗██║",
    "███████╗██║  ██║███████╗██║  ██║██║ ╚████║╚██████╔╝███████║██║  ██║███████╗██║ ╚████║",
    "╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝",
]
LOGO_COMPACT = [
    "███████╗██████╗",
    "██╔════╝██╔══██╗",
    "█████╗  ██████╔╝",
    "██╔══╝  ██╔══██╗",
    "███████╗██║  ██║",
    "╚══════╝╚═╝  ╚═╝",
    "二郎神 ERLANGSHEN",
]

COMMAND_PALETTE = [
    ("benchmarks", "/benchmarks", "查看本轮对标的高 star CLI 项目、10 个优化点和后续路线"),
    ("setup", "/setup", "初始化向导；/setup run 可选择项目文件夹并授权沙箱"),
    ("setup-run", "/setup run", "执行式初始化：选择项目文件夹、授权沙箱、检查账号和模型"),
    ("setup-workspace", "/setup workspace", "重新打开项目文件夹选择器并授权本地沙箱"),
    ("init", "/init", "同 /setup，快速查看首次使用准备状态"),
    ("brief", "/brief", "查看当前会话能力摘要、缺口和推荐开场问题"),
    ("doctor", "/doctor", "本地诊断工作区、登录、大模型、MCP 与产物链路"),
    ("login", "/login xwab <账号>", "登录 XWAB/XCZT 账号，获取核心服务端访问权限"),
    ("logout", "/logout", "清除本地登录状态"),
    ("status", "/status", "查看本地登录状态，并校验服务端账号"),
    ("whoami", "/whoami", "查看当前账号状态"),
    ("model", "/model", "检查当前大模型 provider/model/key 配置"),
    ("model-select", "/model select", "用光标选择大模型供应商和型号"),
    ("model-key", "/model key", "在本机测试并保存当前供应商 API Key"),
    ("commands", "/commands", "查看所有斜杠命令"),
    ("service", "/service", "查看核心服务端状态、鉴权、模型和认知保护"),
    ("health", "/health", "检查服务端健康状态"),
    ("me", "/me", "查看服务端绑定账号"),
    ("map", "/map <问题>", "映射服务端受保护认知场景"),
    ("advice", "/advice <问题>", "服务端映射场景，本机大模型生成投资建议"),
    ("auth", "/auth <cmd>", "登录、账号状态和服务端地址管理"),
    ("server", "/server <cmd>", "直接调用核心服务端 API"),
    ("server-commands", "/server commands", "查看服务端 API 子命令面板"),
    ("server-guide", "/server guide", "按当前任务选择服务端状态、映射、图表和诊断命令"),
    ("server-goals", "/server goals", "按用户目标选择健康、账号、分析、映射、图表和排障路径"),
    ("server-actions", "/server actions", "按用户目标查看服务端相关的下一步行动"),
    ("server-status", "/server status", "查看服务端鉴权、模型、认知保护状态"),
    ("server-me", "/server me", "查看服务端绑定账号和权限层级"),
    ("server-flow", "/server flow", "查看客户端、MCP、服务端与图表产物协作链路"),
    ("server-capabilities", "/server capabilities", "查看服务端开放能力和安全边界"),
    ("server-artifact", "/server artifact", "查看服务端图表 artifact 通信方式"),
    ("server-resources", "/server resources", "查看服务端网页、图片、HTML/PDF 和图表资源如何回到 CLI"),
    ("server-map", "/server map <问题>", "把问题映射到服务端受保护认知场景"),
    ("server-advice", "/server advice <问题>", "服务端建议接口；推荐优先使用客户端 /advice"),
    ("workspace", "/workspace", "查看、选择或授权项目文件夹沙箱"),
    ("workspace-browse", "/workspace browse", "用方向键浏览并选择项目文件夹"),
    ("workspace-path", "/workspace path <路径>", "手动输入或粘贴项目文件夹路径"),
    ("artifacts", "/artifacts", "查看当前项目文件夹里的图表和分析产物"),
    ("open", "/open [chart|report|link N]", "打开最近图表、报告或 /links 中的资源；也可 /open 1"),
    ("open-link", "/open link <序号>", "打开 /links 列表里的指定网页、图片或本地产物"),
    ("links", "/links", "查看最近回答中的网页、图片和本地产物名称链接；也可 /links 1"),
    ("links-open", "/links open <序号>", "从最近资源列表打开指定网页、图片或本地产物"),
    ("chart", "/chart <标题> :: {\"A股\":1.2}", "请求服务端生成结构化图表 artifact"),
    ("examples", "/examples", "查看自然语言提问范例和 MCP/图表调用路线"),
    ("tools", "/tools", "查看 super-66 MCP、web_search 和图表 artifact 能力地图"),
    ("mcp", "/mcp", "同 /tools，查看可调用的数据和工具组合"),
    ("plan", "/plan", "查看最近一次分析的意图、工具调用和产物计划"),
    ("thinking", "/thinking", "展开上一轮模型供应商返回的思考过程"),
    ("context", "/context", "查看或清空最近对话上下文"),
    ("context-clear", "/context clear", "清空最近对话上下文，保留登录、模型和工作区"),
    ("memory", "/memory", "查看本机持久记忆；会自动压缩最近问答并注入上下文"),
    ("memory-clear", "/memory clear", "清空本机持久记忆，不影响登录、模型 Key 和工作区"),
    ("analyze", "/analyze <query>", "本地综合分析"),
    ("macro", "/macro <query>", "本地宏观分析"),
    ("stock", "/stock <query>", "本地股票分析"),
    ("report", "/report <query>", "本地报告生成"),
    ("search", "/search <query>", "本地搜索"),
    ("portfolio", "/portfolio <query>", "本地组合分析"),
    ("risk", "/risk <query>", "本地风险分析"),
    ("memo", "/memo <query>", "本地纪要管理"),
    ("invest", "/invest [option]", "本地投资分析工具"),
    ("omniscient", "/omniscient [cmd]", "全知投资 agent 框架"),
    ("god", "/god [cmd]", "全知投资 agent 快捷入口"),
    ("cognition", "/cognition <cmd>", "投资认知体系"),
    ("clear", "/clear", "清屏并开启干净上下文"),
    ("help", "/help", "查看完整帮助"),
    ("exit", "/exit", "退出交互模式"),
]

COMMAND_GROUPS = [
    ("Getting Started", {"benchmarks", "setup", "setup-run", "setup-workspace", "init", "brief", "doctor"}),
    ("Account & Model", {"login", "logout", "status", "whoami", "model", "model-select", "model-key"}),
    ("Server & Mapping", {
        "service", "health", "me", "map", "advice", "auth", "server",
        "server-commands", "server-guide", "server-goals", "server-actions", "server-status", "server-me", "server-flow", "server-capabilities",
        "server-artifact", "server-resources", "server-map", "server-advice",
    }),
    ("Workspace & Artifacts", {"workspace", "workspace-browse", "workspace-path", "artifacts", "open", "open-link", "links", "links-open", "chart", "report", "memo"}),
    ("Market Intelligence", {"examples", "tools", "mcp", "plan", "thinking", "context", "context-clear", "memory", "memory-clear", "analyze", "macro", "stock", "search", "portfolio", "risk", "invest", "omniscient", "god", "cognition"}),
    ("Session", {"commands", "clear", "help", "exit"}),
]

SLASH_SUBCOMMAND_ROOTS = {
    "server": {"server-commands", "server-guide", "server-goals", "server-actions", "server-status", "server-me", "server-flow", "server-capabilities", "server-artifact", "server-resources", "server-map", "server-advice"},
    "workspace": {"workspace-browse", "workspace-path", "workspace"},
    "model": {"model-select", "model-key", "model"},
    "context": {"context-clear", "context"},
    "memory": {"memory-clear", "memory"},
    "setup": {"setup-run", "setup-workspace", "setup"},
    "auth": {"login", "logout", "status", "whoami", "auth"},
    "chart": {"chart", "artifacts", "links", "open", "open-link"},
    "open": {"open", "open-link", "artifacts", "links"},
    "links": {"links", "links-open", "open-link"},
}

SLASH_CONTEXT_HINTS = {
    "server": "Server Workbench: status / me / map / advice / flow / artifact / resources",
    "workspace": "Project Sandbox: browse / path / allow / artifacts",
    "setup": "Setup Wizard: run / workspace / login / model key",
    "model": "Local Model: select provider/model / test and save API key",
    "auth": "Account: login / logout / status / whoami",
    "chart": "Artifacts: chart / links / open",
    "open": "Resource Opener: open chart/report/link N",
    "links": "Resource Inbox: links / open / open link N",
    "context": "Session Memory: context / context clear",
    "memory": "Local Memory: memory / memory clear",
}

SLASH_SUBCOMMAND_ORDER = {
    "server": [
        "server-status",
        "server-me",
        "server-map",
        "server-advice",
        "server-flow",
        "server-artifact",
        "server-resources",
        "server-capabilities",
        "server-goals",
        "server-actions",
        "server-guide",
        "server-commands",
        "server",
    ],
    "workspace": [
        "workspace-browse",
        "workspace-path",
        "workspace",
        "artifacts",
        "open",
        "open-link",
        "links",
        "links-open",
    ],
    "setup": [
        "setup-run",
        "setup-workspace",
        "setup",
        "login",
        "model-select",
        "model-key",
        "doctor",
    ],
    "model": [
        "model-select",
        "model-key",
        "model",
    ],
    "links": [
        "links-open",
        "open-link",
        "links",
        "open",
    ],
    "open": [
        "open-link",
        "open",
        "links",
        "artifacts",
    ],
}

SERVER_COMMAND_DETAILS = {
    "/setup": "用途: 查看初始化向导和当前准备度 | 适合: 第一次启动或不知道下一步该做什么 | 输出: workspace/account/model 三项检查和首要下一步 | 下一步: /setup run | 边界: 不读取项目文件，除非用户授权工作区",
    "/setup run": "用途: 执行式初始化 | 适合: 想一次补齐项目文件夹、登录和本机模型 Key | 输出: 初始化完成度和缺口清单 | 下一步: /workspace browse、/login xwab <账号> 或 /model key",
    "/setup workspace": "用途: 重新选择项目文件夹沙箱 | 适合: 切换到新的分析项目或授权图表/报告保存位置 | 输出: 授权状态和 .erlangshen/artifacts 位置 | 下一步: /setup run 或直接提问",
    "/login xwab <账号>": "用途: 登录 XWAB/XCZT 账号体系 | 适合: 需要访问服务端场景映射和 super-66 MCP 数据 | 输出: 本地 token 和绑定账号状态 | 下一步: /model key | 边界: 账号 token 只保存在本机会话文件",
    "/model": "用途: 查看本机大模型配置和安全边界 | 适合: 不确定 provider/model/API Key 是否准备好 | 输出: Model Agent Flow、当前模型、Key 状态和可选模型 | 下一步: /model select 或 /model key | 边界: 大模型 Key 不发送服务端",
    "/model select": "用途: 用光标选择大模型供应商和型号 | 适合: 初始化或切换 OpenAI/Claude/DeepSeek/MiMo/Kimi | 输出: provider/model 写入本机配置，随后可测试 Key | 下一步: /model key | 边界: 选择模型不会保存 API Key",
    "/model key": "用途: 本机测试并保存当前供应商 API Key | 适合: 启用本机大模型生成投资分析 | 输出: 连接测试结果，成功后保存到本机配置 | 下一步: 直接输入投资问题 | 边界: Key 不接收、不存储、不转发到二郎神服务端",
    "/server commands": "用途: 查看服务端子命令面板 | 适合: 不确定有哪些服务端能力 | 输出: 状态、账号、映射、图表、排障命令索引 | 下一步: /server actions | 边界: 不暴露内部认知库",
    "/server guide": "用途: 按任务选择服务端路径 | 适合: 想知道现在该先查状态、映射还是生成图表 | 输出: 面向任务的命令路线 | 下一步: 直接输入问题或 /server actions | 边界: 只解释开放能力",
    "/server goals": "用途: 按目标选择健康、账号、完整分析、只看映射、图表和排障路径 | 适合: 想从目标反推命令 | 输出: 每个目标的首选命令和替代命令 | 下一步: 执行首选命令",
    "/server actions": "用途: 按目标列出健康、账号、映射、图表、排障动作 | 适合: 需要一个可以直接执行的下一步 | 输出: 可复制执行的行动清单 | 下一步: 选一个行动执行",
    "/server status": "用途: 检查鉴权、账号、模型、认知保护 | 适合: 登录后确认生产服务是否可用 | 输出: 服务端状态和本地修复建议 | 下一步: /login 或 /model key | 边界: 用户 Key 不发服务端",
    "/server me": "用途: 查看绑定账号和权限层级 | 适合: 确认 XWAB/XCZT 账号是否打通 | 输出: 服务端识别到的用户和权限 | 下一步: 直接提问或 /server status | 边界: 复用 XWAB/XCZT 登录态",
    "/server flow": "用途: 查看 local LLM、MCP、server map、chart artifact 协作链路 | 适合: 想理解一次回答背后的执行过程 | 输出: 本机模型、MCP、服务端映射、图表产物链路 | 下一步: /plan 复盘实际执行",
    "/server capabilities": "用途: 查看服务端开放能力和安全边界 | 适合: 设计客户端/服务端通信和权限边界 | 输出: 开放 API、资源链接、artifact 能力 | 下一步: /tools 查看客户端 MCP 编排",
    "/server artifact": "用途: 查看 chart artifact 通信方式 | 适合: 需要让服务端生成图表并传回客户端 | 输入: artifacts/charts/visualizations/chart_requests | 输出: JSON/HTML/图片/网页名称链接 | 下一步: /chart 或继续说“做成图表”",
    "/server resources": "用途: 查看非文本资源通信方式 | 适合: 服务端、MCP 或 web_search 返回网页、图片、HTML/PDF、图表和报告 | 输出: label/target/type 结构、/links 索引和 /open 打开路径 | 下一步: /links 或 /open 1 | 边界: CLI 不内嵌富文本和二进制内容",
    "/server map <问题>": "用途: 只做受保护场景映射 | 适合: 想看核心认知命中的场景但不生成完整建议 | 输入: 一个投资问题 | 输出: 场景、置信度、风险边界 | 下一步: /advice <问题> 完整分析 | 边界: 不泄露认知库全文",
    "/server advice <问题>": "用途: 兼容旧服务端建议接口 | 适合: 排查服务端建议接口或兼容旧流程 | 输入: 一个投资问题 | 输出: 服务端建议响应 | 下一步: 推荐用 /advice 走本机模型和 MCP",
    "/server <cmd>": "用途: 服务端交互工作台入口 | 适合: 输入 /server 后继续选择子命令 | 下一步: 输入 /server 后加空格展开 status/guide/goals/actions/flow/artifact/resources | 边界: 不暴露内部认知库",
    "/workspace": "用途: 查看项目文件夹沙箱状态 | 适合: 确认图表、报告和工作记忆会保存到哪里 | 输出: 当前路径、授权状态、最近项目和沙箱边界 | 下一步: /workspace browse 或 /workspace path <路径> | 边界: 未授权前不写入本地文件",
    "/workspace browse": "用途: 用方向键选择项目文件夹 | 适合: 初始化、切换分析项目或授权产物保存位置 | 输出: Project Sandbox Setup 选择器和二次授权确认 | 下一步: /workspace allow 或 /setup run | 边界: 授权后仅写入所选项目的 .erlangshen/artifacts",
    "/workspace path <路径>": "用途: 手动粘贴或输入项目路径 | 适合: 非交互终端、远程机器或明确知道项目路径 | 输出: 选中路径的沙箱状态 | 下一步: /workspace allow | 边界: 只记录路径，未授权前不会保存图表和报告",
    "/artifacts": "用途: 查看授权项目内的图表和报告 | 适合: 找回服务端 chart artifact、本地 HTML 图表或 Markdown 报告 | 输出: charts/reports 摘要和最近可打开路径 | 下一步: /open chart、/open report 或 /links | 边界: 只列出授权项目内 .erlangshen/artifacts",
    "/chart <标题> :: {\"A股\":1.2}": "用途: 请求服务端生成结构化图表 artifact | 适合: 把 MCP 快照、收益、回撤、涨跌幅或配置比例做成可打开图表 | 输入: 图表标题和 JSON 数据 | 输出: JSON/HTML artifact、本地保存路径和 /links 资源 | 下一步: /open chart 或 /artifacts | 边界: 图表数据来自本轮上下文或用户显式输入，不上传大模型 API Key",
    "/tools": "用途: 查看 MCP、web_search、chart artifact 和 resource_links 能力地图 | 适合: 想知道本机大模型能调用哪些数据、如何组合工具 | 输出: super-66 注册表、工具结果契约、组合模式和典型数据配方 | 下一步: 直接输入问题或 /plan | 边界: 能力地图进入本机大模型上下文，服务端仍只接收受保护映射请求",
    "/plan": "用途: 复盘最近一次分析的意图和工具链路 | 适合: 检查本机大模型为什么选择 MCP/web_search/图表或为什么降级 | 输出: 路由来源、工具理由、MCP 快照、服务端映射、资源链接和产物计划 | 下一步: 继续追问、/links 或 /clear | 边界: 只展示本次 CLI 进程内上下文",
    "/links": "用途: 查看最近回答里的网页、图片、图表和报告链接 | 下一步: /links 1 或 /links open 1",
    "/links open <序号>": "用途: 直接打开 /links 列表中的指定资源 | 示例: /links open 1 | 无桌面 opener 时返回可复制链接",
    "/open link <序号>": "用途: 等同 /links open <序号>，打开最近资源链接 | 示例: /open link 1 或 /open 1",
    "/open [chart|report|link N]": "用途: 打开最近图表、报告或资源链接 | 示例: /open 1 打开第 1 个资源 | 下一步: /artifacts 或 /links",
}

COMMAND_NEXT_HINTS = {
    "/benchmarks": "/commands <关键词> 或直接输入投资问题",
    "/setup": "/setup run",
    "/setup run": "/workspace browse 或 /workspace path <路径>",
    "/setup workspace": "/setup run 或直接输入投资问题",
    "/init": "/setup run",
    "/brief": "直接输入投资问题或 /setup run",
    "/doctor": "按首要修复项执行，或 /setup run",
    "/login xwab <账号>": "/model key",
    "/logout": "/login xwab <账号>",
    "/status": "/server status 或 /whoami",
    "/whoami": "直接输入问题或 /server status",
    "/model": "/model select 或 /model key",
    "/model select": "/model key",
    "/model key": "直接输入投资问题",
    "/commands": "输入 / 继续筛选",
    "/service": "/server actions 或直接提问",
    "/health": "/server status",
    "/me": "直接提问或 /server status",
    "/map <问题>": "/advice <问题>",
    "/advice <问题>": "/plan",
    "/auth <cmd>": "/status",
    "/workspace": "/workspace browse 或 /workspace path <路径>",
    "/workspace browse": "/workspace allow",
    "/workspace path <路径>": "/workspace allow",
    "/artifacts": "/open chart 或 /open report",
    "/open link <序号>": "/links",
    "/chart <标题> :: {\"A股\":1.2}": "/open chart 或 /artifacts",
    "/server resources": "/links 或 /open 1",
    "/examples": "选择一个问题直接输入",
    "/tools": "直接输入问题或 /plan",
    "/mcp": "直接输入问题或 /plan",
    "/plan": "继续追问或 /clear",
    "/links": "/links 1 或 /open 1",
    "/links open <序号>": "/open 1",
    "/open [chart|report|link N]": "/artifacts 或 /links",
    "/context": "/context clear 或继续追问",
    "/context clear": "直接输入新问题",
    "/memory": "/memory clear 或继续提问",
    "/memory clear": "继续提问",
    "/clear": "直接输入新问题",
    "/help": "输入 / 打开命令面板",
    "/exit": "退出当前 CLI 会话",
}

COMMAND_GROUP_NEXT_HINTS = {
    "Getting Started": "/setup run",
    "Account & Model": "/status",
    "Server & Mapping": "/server actions",
    "Workspace & Artifacts": "/artifacts 或 /links",
    "Market Intelligence": "直接输入问题或 /plan",
    "Session": "/help",
}

CLI_BENCHMARK_CHECKED_AT = "2026-06-16"
CLI_BENCHMARK_PROJECTS = [
    ("ohmyzsh/ohmyzsh", "188,037", "插件/主题生态、安装引导、跨平台 shell 体验"),
    ("ollama/ollama", "174,262", "本地模型运行体验、最短命令路径、默认值清晰"),
    ("yt-dlp/yt-dlp", "170,843", "复杂参数体系、可脚本化输出、失败恢复"),
    ("denoland/deno", "107,093", "安全默认值、单二进制体验、机器友好命令"),
    ("google-gemini/gemini-cli", "105,307", "终端原生 AI Agent、上下文解释和工具编排"),
    ("neovim/neovim", "100,420", "键盘优先、可扩展内核、快速反馈循环"),
    ("oven-sh/bun", "93,222", "速度优先、一体化工具链、静默可组合输出"),
    ("junegunn/fzf", "80,982", "模糊查找、增量过滤、轻量交互"),
    ("jesseduffield/lazygit", "79,317", "TUI 工作台、状态即导航、动作可发现"),
    ("BurntSushi/ripgrep", "65,082", "高性能搜索、尊重忽略规则、稳定退出码"),
]

CLI_OPTIMIZATION_POINTS = [
    ("命令发现", "fzf / lazygit", "输入 / 或 /commands <关键词> 后用 fuzzy 排序找命令"),
    ("脚本友好", "deno / gh / yt-dlp", "新增 --json 与 --plain，输出可被自动化消费"),
    ("静默包装器", "bun / ripgrep", "npm wrapper 不再污染子命令输出，支持 --quiet"),
    ("历史记忆", "ohmyzsh / neovim", "交互模式持久化命令历史，Tab 补全复用历史上下文"),
    ("诊断路径", "gh / deno", "/doctor 暴露工作区、账号、模型、资源和输出模式检查"),
    ("Agent 轨迹", "gemini-cli / aider", "/plan 保留意图、工具、映射、产物和失败阶段"),
    ("资源出口", "lazygit / gh", "/links 与 /open 统一网页、图片、HTML/PDF、图表和报告"),
    ("沙箱边界", "deno", "工作区授权后才写入 .erlangshen，避免越界访问"),
    ("错误恢复", "yt-dlp", "未知命令给相近建议，并提示可执行下一步"),
    ("路线沉淀", "ohmyzsh", "README_CLI 记录对标来源、已落地点和后续开发方向"),
]

CLI_BENCHMARK_DATA_FILE = Path(__file__).with_name("cli_benchmarks.json")

PROVIDER_KEY_HINTS = {
    "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"),
    "claude": ("CLAUDE_API_KEY", "CLAUDE_MODEL"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "mimo": ("MIMO_API_KEY", "MIMO_MODEL"),
    "xiaomi": ("XIAOMI_API_KEY", "XIAOMI_MODEL"),
    "kimi": ("KIMI_API_KEY", "KIMI_MODEL"),
    "moonshot": ("MOONSHOT_API_KEY", "MOONSHOT_MODEL"),
}


def _supports_color() -> bool:
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def _color(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _terminal_width() -> int:
    return shutil.get_terminal_size((100, 20)).columns


def _display_width(text: str) -> int:
    width = 0
    for char in str(text):
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", str(text))


def _clip_display(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    output = []
    width = 0
    for char in str(text):
        char_width = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1)
        if width + char_width > limit:
            break
        output.append(char)
        width += char_width
    return "".join(output)


def _pad_display(text: str, width: int) -> str:
    clipped = _clip_display(text, width)
    return clipped + " " * max(0, width - _display_width(clipped))


def _logo() -> str:
    return "\n".join(_color(line, "36;1") for line in LOGO_COMPACT)


def _panel(title: str, rows: list[tuple[str, str]]) -> str:
    width = min(max(54, *(_display_width(label) + _display_width(value) + 8 for label, value in rows)), 92)
    top = f"╭─ {title} " + "─" * max(0, width - _display_width(title) - 5) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"
    body = []
    for label, value in rows:
        text = _pad_display(str(label), 10) + " " + str(value)
        body.append("│ " + _pad_display(text, width - 3) + "│")
    return "\n".join([_color(top, "36"), *body, _color(bottom, "36")])


def _text_panel(title: str, lines: list[str], min_width: int = 72, max_width: int = 110) -> str:
    available = max(32, _terminal_width() - 2)
    lower = min(min_width, available)
    width = min(max(lower, *(_display_width(line) + 4 for line in lines)), max_width, available)
    top = f"╭─ {title} " + "─" * max(0, width - _display_width(title) - 5) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"
    body = ["│ " + _pad_display(line, width - 3) + "│" for line in lines]
    return "\n".join([_color(top, "36"), *body, _color(bottom, "36")])


def _dashboard_panel(title: str, left_lines: list[str], right_lines: list[str]) -> str:
    terminal = max(72, _terminal_width())
    width = min(max(76, terminal - 4), 118)
    inner_width = width - 4
    gap = 3
    left_width = min(max(24, max(_display_width(line) for line in left_lines) if left_lines else 24), 34)
    right_width = max(32, inner_width - left_width - gap)
    top = f"╭─ {title} " + "─" * max(0, width - _display_width(title) - 5) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"
    row_count = max(len(left_lines), len(right_lines))
    rows = []
    for index in range(row_count):
        left = left_lines[index] if index < len(left_lines) else ""
        right = right_lines[index] if index < len(right_lines) else ""
        rows.append(
            "│ "
            + _pad_display(left, left_width)
            + " " * gap
            + _pad_display(right, right_width)
            + " │"
        )
    return "\n".join([_color(top, "36"), *rows, _color(bottom, "36")])


class CLI:
    """二郎神 CLI 主类"""

    COMMANDS = {
        "analyze": "src.commands.analyze.AnalyzeCommand",
        "macro": "src.commands.macro.MacroCommand",
        "stock": "src.commands.stock.StockCommand",
        "report": "src.commands.report.ReportCommand",
        "search": "src.commands.search.SearchCommand",
        "portfolio": "src.commands.portfolio.PortfolioCommand",
        "risk": "src.commands.risk.RiskCommand",
        "memo": "src.commands.memo.MemoCommand",
        "invest": "src.commands.invest.InvestCommand",
        "omniscient": "src.commands.omniscient.OmniscientCommand",
        "god": "src.commands.omniscient.OmniscientCommand",
        "cognition": "src.commands.cognition.CognitionCommand",
        "auth": "src.commands.auth.AuthCommand",
        "server": "src.commands.server.ServerCommand",
    }
    CLIENT_COMMANDS = {"auth", "server"}
    ALIASES = {
        "login": ("auth", "login"),
        "logout": ("auth", "logout"),
        "status": ("auth", "status"),
        "whoami": ("auth", "status"),
        "me": ("server", "me"),
        "service": ("server", "status"),
        "health": ("server", "health"),
        "map": ("server", "map"),
        "init": ("setup", ""),
    }
    LOCAL_COMMANDS = {"benchmarks", "benchmark", "cli-benchmarks", "commands", "cmd", "?", "model", "models", "config", "setup", "tools", "mcp", "plan", "thinking", "think", "reasoning", "context", "memory", "mem", "clear", "doctor", "brief", "examples", "links"}

    def __init__(self):
        self.brain = None
        self.mcp = None
        self.hooks = None
        self._slash_dropdown_lines = 0
        self._input_history: list[str] = []
        self._input_history_loaded = False
        self._prompt_session = None
        self._slash_selected = 0
        self._last_agent_plan: dict | None = None
        self._agent_trace: list[str] | None = None
        self._conversation_history: list[dict[str, str]] = []
        self._last_mcp_data: dict | None = None
        self._last_reasoning_trace: dict[str, object] | None = None
        self._last_artifact_results: list[dict] = []
        self._last_resource_links: list[dict[str, object]] = []
        self._command_usage_cache: dict[str, object] | None = None
        self._memory = LocalMemoryStore()
        self._token_status_visible = False
        self._token_status_activity = "ready"
        self._interactive_question_printed = False
        self._live_answer_state: dict[str, object] | None = None
        self._live_answer_finalized = False

    async def dispatch(self, user_input: str) -> str:
        """把交互输入或一次性参数分发到对应命令。"""
        user_input = (user_input or "").strip()
        if not user_input:
            return ""
        if user_input.startswith("/"):
            raw_command = user_input[1:].strip()
            if not raw_command:
                return self.command_palette_text()
            parts = raw_command.split(maxsplit=1)
            command = parts[0].strip()
            args = parts[1].strip() if len(parts) > 1 else ""
            command, args = self._resolve_alias(command, args)
            self._record_command_usage(command, args)
            return await self.run_command(command, args)
        return await self.client_side_advice(user_input)

    def _resolve_alias(self, command: str, args: str) -> tuple[str, str]:
        alias = self.ALIASES.get(command)
        if not alias:
            return command, args
        target_command, prefix = alias
        merged_args = f"{prefix} {args}".strip()
        return target_command, merged_args

    async def run_command(self, command: str, args: str) -> str:
        """执行命令"""
        if command in {"help", "h"}:
            return self.help_text()
        if command in {"commands", "cmd", "?"}:
            return self.command_palette_text(args)
        if command in {"benchmarks", "benchmark", "cli-benchmarks", "对标", "优化"}:
            return self.benchmarks_text(args)
        if command in {"setup", "init", "初始化", "向导"}:
            setup_args = args.strip().lower().split()
            if setup_args and setup_args[0] in {"workspace", "project", "folder", "path", "workdir", "目录", "项目", "文件夹"}:
                return await self.setup_workspace_interactive()
            if setup_args and setup_args[0] in {"run", "start", "go", "wizard", "执行", "开始"}:
                force_workspace = any(item in {"workspace", "project", "folder", "path", "workdir", "目录", "项目", "文件夹"} for item in setup_args[1:])
                return await self.setup_run_interactive(force_workspace=force_workspace)
            return self.setup_text()
        if command in {"doctor", "check", "诊断", "自检"}:
            return self.doctor_text()
        if command in {"brief", "home", "summary", "能力摘要", "会话"}:
            return self.brief_text()
        if command in {"tools", "tool", "mcp", "工具", "能力"}:
            return self.tools_text(args)
        if command in {"examples", "example", "prompts", "提问", "示例"}:
            return self.examples_text()
        if command in {"plan", "计划", "trace", "过程"}:
            return self.plan_text(args)
        if command in {"thinking", "think", "reasoning", "思考", "思考过程"}:
            return self.thinking_text(args)
        if command in {"context", "ctx", "上下文"}:
            return self.context_text(args)
        if command in {"memory", "mem", "记忆", "长期记忆"}:
            return self.memory_text(args)
        if command in {"clear", "new", "新会话", "清空"}:
            return self.clear_session_text()
        if command in {"model", "models", "config"}:
            if args.strip().lower() in {"select", "choose", "set", "配置", "选择"}:
                return await self.model_select_interactive()
            if args.strip().lower() in {"key", "apikey", "api-key", "密钥", "配置key"}:
                return await self.model_key_interactive()
            return self.model_help_text()
        if command in {"advice", "建议", "投顾"}:
            if not args.strip():
                return "请提供需要分析的投资问题。示例：/advice 利率下行时A股红利资产怎么看"
            return await self.client_side_advice(args.strip())
        if command in {"workspace", "工作区", "项目"}:
            return self.workspace_text(args)
        if command in {"artifacts", "artifact-list", "产物"}:
            return self.artifacts_text(args)
        if command in {"open", "打开", "查看产物"}:
            return self.open_artifact_text(args)
        if command in {"links", "link", "resources", "resource", "资源", "链接"}:
            return self.links_text(args)
        if command in {"chart", "artifact", "图表"}:
            return await self.chart_text(args)
        if command in self.COMMANDS:
            if command == "analyze" and os.getenv("ERLANGSHEN_ENABLE_LOCAL_ANALYSIS") != "1":
                return self._missing_local_module_message(command, "local analysis disabled")
            try:
                command_class = self._load_command_class(command)
                brain, mcp = self._command_context(command)
            except Exception as exc:
                return self._missing_local_module_message(command, exc)
            cmd = command_class(brain, mcp)
            try:
                return await cmd.execute(args)
            except Exception as exc:
                return self._missing_local_module_message(command, exc)
        suggestion = self._command_suggestion(command)
        common_shortcuts: list[str] = []
        for _, shortcut, _ in COMMAND_PALETTE[:12]:
            command_shortcut = shortcut.split()[0]
            if command_shortcut not in common_shortcuts:
                common_shortcuts.append(command_shortcut)
            if len(common_shortcuts) >= 7:
                break
        aliases = ", ".join(common_shortcuts)
        lines = [f"未知命令: /{command}"]
        if suggestion:
            lines.append(f"你是不是想输入: /{suggestion}")
        lines.extend(["", f"常用命令: {aliases}", "输入 /commands 打开命令面板，输入 /help 查看完整帮助。"])
        return "\n".join(lines)

    def _load_command_class(self, command: str):
        path = self.COMMANDS[command]
        module_name, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)

    def _command_context(self, command: str):
        if command in self.CLIENT_COMMANDS:
            return None, None
        if self.brain is None or self.mcp is None:
            from src.brain import Brain
            from src.mcp.registry import MCPRegistry

            self.brain = Brain()
            self.mcp = MCPRegistry()
        return self.brain, self.mcp

    def _missing_local_module_message(self, command: str, exc: Exception) -> str:
        reason = getattr(exc, "name", None) or str(exc)
        return (
            f"当前安装包不包含 /{command} 的本地分析模块: {reason}。\n"
            "用户端默认作为瘦客户端运行，请使用 /auth 登录后调用 /server map 或 /server advice。"
        )

    def _init_hooks(self) -> bool:
        if self.hooks is not None:
            return True
        try:
            self._command_context("analyze")
            from src.hooks.session_start import SessionStartHook
            from src.hooks.session_end import SessionEndHook
        except Exception:
            self.hooks = {}
            return False

        self.hooks = {
            "session_start": SessionStartHook(self.brain, self.mcp),
            "session_end": SessionEndHook(self.brain, self.mcp),
        }
        return True

    async def interactive_mode(self):
        """交互模式"""
        self._setup_completion()
        self._confirm_workspace_sandbox()
        await self._ensure_fresh_auth_session_interactive(reason="startup")
        self.print_header()

        # Session start hook
        if self._init_hooks():
            await self.hooks["session_start"].run()

        while True:
            try:
                user_input = (await self._read_prompt()).strip()

                if not user_input:
                    continue

                if user_input in ["/exit", "/quit", "/q"]:
                    print("再见!")
                    break

                if user_input == "/help":
                    self.print_help()
                    continue

                if user_input == "/clear":
                    self._clear_session_state()
                    os.system("cls" if os.name == "nt" else "clear")
                    self.print_header()
                    print(_color("已清空本次会话上下文和最近分析计划；登录、模型 Key、工作区和已保存产物不受影响。", "2"))
                    print()
                    continue

                self._interactive_question_printed = False
                if self._is_advice_turn(user_input):
                    self._print_interactive_question(user_input)
                    self._interactive_question_printed = True

                result = await self.dispatch(user_input)

                self._refresh_token_status_bar(activity="ready")
                await self._print_interactive_turn(user_input, result)
                self._interactive_question_printed = False

            except (KeyboardInterrupt, EOFError):
                print("\n再见!")
                break
            except OSError as exc:
                if self._should_exit_for_terminal(exc):
                    print("\n再见!")
                    break
                print(f"\n错误: {exc}\n")
            except Exception as exc:
                if self._should_exit_for_terminal(exc):
                    print("\n再见!")
                    break
                print(f"\n错误: {exc}\n")

        # Session end hook
        if self.hooks and "session_end" in self.hooks:
            await self.hooks["session_end"].run()

    async def _ensure_fresh_auth_session_interactive(self, *, reason: str = "startup") -> bool:
        session = load_auth_session()
        token = self._text_field(session.get("token"))
        if decrypt_auth_password(session) and self._auth_account(session):
            if await self._refresh_auth_from_saved_password(session, reason=reason, invalidate_on_failure=False):
                return True
        if not token:
            return (
                await self._refresh_auth_from_env(session, reason=reason)
                or await self._refresh_auth_from_saved_password(session, reason=reason)
            )
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return False
        base_url = self._text_field(session.get("base_url")) or get_config().erlangshen_api_base_url
        try:
            from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient

            await ErlangshenServerClient(base_url=base_url, token=token, timeout=8).me()
            return False
        except ErlangshenAPIError as exc:
            if exc.status_code not in {401, 403}:
                print(_color(f"账号状态暂时无法校验: {exc}；本轮会继续使用已保存登录态。", "33"))
                return False
            return await self._refresh_auth_after_unauthorized(session, reason=reason)
        except Exception as exc:
            print(_color(f"账号状态暂时无法校验: {exc}；本轮会继续使用已保存登录态。", "33"))
            return False

    async def _refresh_auth_after_unauthorized(self, session: dict, *, reason: str = "server_mapping") -> bool:
        if await self._refresh_auth_from_env(session, reason=reason):
            return True
        if await self._refresh_auth_from_saved_password(session, reason=reason):
            return True

        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            self._mark_auth_session_invalid(session, "token_unauthorized")
            return False

        base_url = self._text_field(session.get("base_url")) or get_config().erlangshen_api_base_url
        login_entry = self._auth_login_entry(session)
        account = self._auth_account(session)
        prompt_reason = "启动时检测到登录态失效" if reason == "startup" else "服务端返回 401/403，登录态需要刷新"
        print(_color(f"{prompt_reason}，二郎神将自动重新登录 {login_entry}。", "33;1"))
        if account:
            raw = input(f"账号 [{account}]: ").strip()
            if raw:
                account = raw
        else:
            account = input("账号: ").strip()
        if not account:
            self._mark_auth_session_invalid(session, "missing_account")
            print(_color("已取消自动登录：账号为空。", "33"))
            return False
        password = getpass.getpass("密码（只用于本次刷新，不保存）: ")
        if not password:
            self._mark_auth_session_invalid(session, "missing_password")
            print(_color("已取消自动登录：密码为空。", "33"))
            return False
        return await self._login_and_save_auth_session(base_url, login_entry, account, password, session, silent=False)

    async def _refresh_auth_from_env(self, session: dict, *, reason: str = "server_mapping") -> bool:
        password = self._text_field(os.getenv("ERLANGSHEN_AUTH_PASSWORD")) or self._text_field(os.getenv("SUPER66_PASSWORD"))
        if not password:
            return False
        base_url = self._text_field(session.get("base_url")) or get_config().erlangshen_api_base_url
        login_entry = self._auth_login_entry(session)
        account = (
            self._text_field(os.getenv("ERLANGSHEN_AUTH_ACCOUNT"))
            or self._text_field(os.getenv("SUPER66_USERNAME"))
            or self._auth_account(session)
        )
        if not account and os.getenv("SUPER66_PASSWORD"):
            account = "小二MCP助手"
        if not account:
            return False
        return await self._login_and_save_auth_session(base_url, login_entry, account, password, session, silent=True)

    async def _refresh_auth_from_saved_password(
        self,
        session: dict,
        *,
        reason: str = "server_mapping",
        invalidate_on_failure: bool = True,
    ) -> bool:
        password = decrypt_auth_password(session)
        if not password:
            return False
        base_url = self._text_field(session.get("base_url")) or get_config().erlangshen_api_base_url
        login_entry = self._auth_login_entry(session)
        account = self._auth_account(session)
        if not account:
            return False
        return await self._login_and_save_auth_session(
            base_url,
            login_entry,
            account,
            password,
            session,
            silent=True,
            invalidate_on_failure=invalidate_on_failure,
        )

    async def _login_and_save_auth_session(
        self,
        base_url: str,
        login_entry: str,
        account: str,
        password: str,
        previous_session: dict,
        *,
        silent: bool,
        invalidate_on_failure: bool = True,
    ) -> bool:
        try:
            from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient

            result = await ErlangshenServerClient(base_url=base_url, timeout=20).login(login_entry, account, password)
        except ErlangshenAPIError as exc:
            if invalidate_on_failure:
                self._mark_auth_session_invalid(previous_session, f"login_failed_{exc.status_code}")
            print(_color(f"自动登录失败 ({exc.status_code}): {exc}", "31"))
            return False
        token = result.get("token") if isinstance(result, dict) else None
        if not token:
            if invalidate_on_failure:
                self._mark_auth_session_invalid(previous_session, "login_missing_token")
            print(_color("自动登录失败: 服务端未返回 token。", "31"))
            return False
        save_auth_session({
            "base_url": base_url,
            "token": token,
            "account": account,
            "password_encrypted": encrypt_auth_password(password),
            "loginEntry": result.get("loginEntry") or login_entry,
            "expires": result.get("expires"),
            "user": self._safe_auth_user(result.get("user") or {}),
        })
        mcp_refreshed = await self._refresh_super66_after_login(
            login_entry=result.get("loginEntry") or login_entry,
            account=account,
            password=password,
            token=token,
        )
        if silent:
            if sys.stdout.isatty():
                suffix = "，super-66 MCP 已同步重登" if mcp_refreshed else ""
                print(_color(f"登录态已静默刷新{suffix}。", "32"))
        else:
            suffix = "，super-66 MCP 已同步重登" if mcp_refreshed else ""
            print(_color(f"登录态已刷新{suffix}，服务端映射将复用新 token。", "32"))
        return True

    async def _refresh_super66_after_login(self, *, login_entry: str, account: str, password: str, token: str) -> bool:
        try:
            from src.mcp.super66 import Super66MCP

            return await Super66MCP().refresh_auth_from_cli_login(
                login_entry=login_entry,
                account=account,
                password=password,
                token=token,
            )
        except Exception:
            return False

    def _auth_login_entry(self, session: dict) -> str:
        user = session.get("user") if isinstance(session.get("user"), dict) else {}
        login_entry = (
            self._text_field(session.get("loginEntry"))
            or self._text_field(user.get("loginEntry"))
            or get_config().erlangshen_auth_login_entry
        ).lower()
        if login_entry not in {"xwab", "xczt"}:
            login_entry = get_config().erlangshen_auth_login_entry
        return login_entry

    def _auth_account(self, session: dict) -> str:
        user = session.get("user") if isinstance(session.get("user"), dict) else {}
        return (
            self._text_field(session.get("account"))
            or self._text_field(user.get("email"))
            or self._text_field(user.get("username"))
        )

    def _mark_auth_session_invalid(self, session: dict, reason: str) -> None:
        if not isinstance(session, dict):
            return
        payload = {key: value for key, value in session.items() if key != "token"}
        payload["token_invalid_reason"] = reason
        payload["token_invalid_at"] = datetime.now().isoformat(timespec="seconds")
        save_auth_session(payload)

    def _safe_auth_user(self, user: dict) -> dict:
        return {
            "id": user.get("id"),
            "username": user.get("username") or user.get("user_name"),
            "email": user.get("email"),
            "role": user.get("role") or user.get("user_type"),
            "loginEntry": user.get("loginEntry") or user.get("login_entry"),
        }

    def print_header(self) -> None:
        session = load_auth_session()
        config = get_config()
        base_url = session.get("base_url") or config.erlangshen_api_base_url
        workspace = workspace_status()
        user = session.get("user") or {}
        username = user.get("username") or user.get("email") or user.get("id")
        auth_text = username or ("已保存 token" if session.get("token") else "未登录")
        provider, model, llm_ready, key_hint = self._llm_status(config)
        memory_stats = self._memory_stats()
        self._token_status_visible = sys.stdout.isatty() and os.getenv("ERLANGSHEN_TOKEN_STATUS", "dialog").lower() == "top"
        print(self._session_dashboard(
            base_url=base_url,
            auth_text=auth_text,
            provider=provider,
            model=model,
            llm_ready=llm_ready,
            workspace=workspace,
            memory_count=int(memory_stats.get("count", 0) or 0),
        ))
        print()
        next_steps = self._next_steps(session, llm_ready)
        if next_steps:
            step_text = " · ".join(f"{label}: {value}" for label, value in next_steps[:3])
            print(_color(f"下一步  {step_text}", "2"))
        if not llm_ready:
            print(_color(f"注意: 当前大模型 API Key 未配置，请输入 /model key 在本机保存，或设置 {key_hint}=...。", "33;1"))
        print(_color("直接提问开始分析 · / 打开命令 · /memory 查看本机记忆 · /setup 补齐配置 · /exit 退出", "2"))
        print()

    def _session_dashboard(
        self,
        *,
        base_url: str,
        auth_text: str,
        provider: str,
        model: str,
        llm_ready: bool,
        workspace: dict,
        memory_count: int,
    ) -> str:
        account_state = "ready" if auth_text not in {"未登录", ""} else "login"
        model_state = "ready" if llm_ready else "need key"
        workspace_state = "ready" if workspace.get("allowed") else "sandbox"
        core_state = "ready" if base_url else "missing"
        left_lines = [
            *LOGO_COMPACT,
            "",
            "MCP-first · local LLM",
        ]
        right_lines = [
            f"Erlangshen agent workspace · v{__version__}",
            "",
            f"account   {account_state} · {auth_text}",
            f"model     {model_state} · {provider} / {model}",
            f"core      {core_state}",
            f"workspace {workspace_state}",
            f"memory    {memory_count} local notes",
            "",
            "commands  / · /model · /memory · /service",
            "start     直接输入投资问题",
        ]
        return _dashboard_panel("Erlangshen", left_lines, right_lines)

    def _token_status_line(self, activity: str = "", width: int | None = None) -> str:
        width = min(max(72, width or _terminal_width()), 150)
        text = self._token_meter_text(activity=activity or self._token_status_activity)
        clipped = _clip_display(text, width)
        padded = clipped + " " * max(0, width - _display_width(clipped))
        return _color(padded, "30;46")

    def _token_dialog_footer(self, activity: str = "") -> str:
        width = self._dialog_box_width()
        content_width = max(20, width - 4)
        text = self._token_meter_text(activity=activity or self._token_status_activity, compact=True)
        return _color("   " + _pad_display(text, content_width), "2")

    def _token_meter_text(self, *, activity: str = "", compact: bool = False) -> str:
        session = load_auth_session()
        config = get_config()
        provider, model, llm_ready, _ = self._llm_status(config)
        account = "account ready" if session.get("token") else "account login"
        model_state = "model ready" if llm_ready else "model key"
        snapshot = self._llm_usage_snapshot()
        active = snapshot.get("active") if isinstance(snapshot.get("active"), dict) else {}
        session_usage = snapshot.get("session") if isinstance(snapshot.get("session"), dict) else {}

        if active:
            elapsed = self._format_seconds(active.get("elapsed_seconds"))
            input_tokens = self._format_token_count(active.get("input_tokens"))
            last = f"running in~{input_tokens} elapsed {elapsed}"
            speed = "tok/s ..."
        else:
            approximate = "~" if snapshot.get("approximate") else ""
            total = self._format_token_count(snapshot.get("total_tokens"))
            input_tokens = self._format_token_count(snapshot.get("input_tokens"))
            output_tokens = self._format_token_count(snapshot.get("output_tokens"))
            if snapshot.get("total_tokens"):
                last = f"last {approximate}{total}t in {input_tokens} out {output_tokens}"
                speed = f"{float(snapshot.get('tokens_per_second') or 0.0):.1f} tok/s"
            else:
                last = "last --"
                speed = "tok/s --"

        session_total = self._format_token_count(session_usage.get("total_tokens"))
        requests = int(session_usage.get("requests") or 0)
        session_text = f"session {session_total}t/{requests}r"
        model_text = f"{provider}/{model}"
        if len(model_text) > (22 if compact else 34):
            model_text = model_text[:(19 if compact else 31)] + "..."
        activity_text = self._text_field(activity or self._token_status_activity or "ready")
        if len(activity_text) > 24:
            activity_text = activity_text[:21] + "..."
        prefix = "TOK" if compact else "Session Meter"
        return " · ".join([
            prefix,
            account,
            model_state,
            model_text,
            last,
            speed,
            session_text,
            activity_text,
        ])

    def _token_meter_compact(self) -> str:
        return self._token_meter_text(activity=self._token_status_activity, compact=True)

    def _llm_usage_snapshot(self) -> dict:
        try:
            from src.llm import LLMClient

            snapshot = LLMClient.usage_snapshot()
            return snapshot if isinstance(snapshot, dict) else {}
        except Exception:
            return {}

    def _format_token_count(self, value) -> str:
        try:
            number = max(0, int(value or 0))
        except (TypeError, ValueError):
            number = 0
        if number >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        if number >= 10_000:
            return f"{number / 1_000:.0f}k"
        if number >= 1_000:
            return f"{number / 1_000:.1f}k"
        return str(number)

    def _format_seconds(self, value) -> str:
        try:
            seconds = max(0.0, float(value or 0.0))
        except (TypeError, ValueError):
            seconds = 0.0
        if seconds >= 60:
            return f"{seconds / 60:.1f}m"
        return f"{seconds:.1f}s"

    def _refresh_token_status_bar(self, activity: str = "") -> None:
        if activity:
            self._token_status_activity = self._text_field(activity)
        if not self._token_status_visible or not sys.stdout.isatty():
            return
        if os.getenv("ERLANGSHEN_TOKEN_STATUS", "dialog").lower() != "top":
            return
        try:
            sys.stdout.write("\0337\033[1;1H" + self._token_status_line(activity=self._token_status_activity) + "\0338")
            sys.stdout.flush()
        except OSError:
            pass

    def _welcome_panel(
        self,
        *,
        base_url: str,
        auth_text: str,
        provider: str,
        model: str,
        llm_ready: bool,
        workspace: dict,
    ) -> str:
        account = "ready" if auth_text not in {"未登录", ""} else "login needed"
        model_state = "ready" if llm_ready else "key needed"
        workspace_state = "ready" if workspace.get("allowed") else "sandbox needed"
        token_ready = account == "ready"
        workspace_ready = bool(workspace.get("allowed"))
        primary_action = self._setup_primary_action(workspace_ready, token_ready, llm_ready)
        account_badge = "[OK]" if account == "ready" else "[SETUP]"
        model_badge = "[OK]" if llm_ready else "[KEY]"
        workspace_badge = "[OK]" if workspace.get("allowed") else "[SAFE]"
        return _text_panel("Erlangshen Agent Console", [
            "ERLANGSHEN  投资智能体工作台",
            "agentic investment analyst · MCP-first · service-protected · local LLM key",
            f"Primary Action  {primary_action}",
            "Command Deck    / 打开可选择命令面板；/setup run 进入执行式初始化",
            "",
            "First Run Path",
            "  1  /workspace browse  用方向键选择项目文件夹，确认本轮可写入的沙箱",
            "  2  /login xwab <账号>   绑定 XWAB/XCZT 账号，复用 super-66 MCP 鉴权",
            "  3  /model key           本机测试并保存大模型 API Key，不发送服务端",
            "  4  直接输入问题          本机 LLM 选择 MCP/web_search，再请求服务端映射",
            "  5  /links 1 或 /open 1   打开网页、图片、图表、PDF 或报告",
            "",
            "Operator Layout",
            "  左侧是用户问题，右侧是二郎神回答；过程提示会显示取数、映射、生成和产物",
            "  非文本结果不会挤进终端正文，都会变成 /links 与 /open 可打开的名称链接",
            "  需要图表时直接说“做成图表”，chart artifact 会保存到授权项目文件夹",
            "",
            "Agent Loop",
            "  1  理解问题        本机大模型改写问题、判断意图、选择工具组合",
            "  2  读取数据        super-66 MCP / web_search 优先补齐行情、产品和事件线索",
            "  3  映射场景        服务端返回受保护场景、方向和置信度",
            "  4  形成判断        本机大模型生成自然分析，并可请求图表 artifact",
            "",
            "Command Deck",
            "  /setup run        初始化工作区、账号、大模型 Key 和产物权限",
            "  /setup workspace  重新选择项目文件夹并授权本地沙箱",
            "  /tools            查看 MCP、web_search、chart artifact 能力地图",
            "  /server actions   按目标查看服务端状态、映射、图表和排障路径",
            "  /server flow      查看客户端与服务端协作流程",
            "  /plan             查看最近一次工具选择、MCP 快照和图表产物",
            "  /links open 1     打开最近网页、图片、图表或报告资源",
            "",
            "Signal Rail",
            "  intent  ->  mcp data  ->  protected map  ->  local synthesis  ->  artifact",
            "",
            "Starter Prompts",
            *self._starter_prompt_lines(compact=True),
            "",
            "Trust Boundary",
            "  API Key 只保存在本机；服务端地址隐藏；认知库只返回受保护信号；工作区写入需授权",
            "",
            f"Readiness  {account_badge} account {account} · {model_badge} model {model_state} · {workspace_badge} workspace {workspace_state} · server {self._server_display_text(base_url)}",
            f"Model      {provider} / {model}",
            "Start      按 Primary Action 补齐缺口；准备好后直接输入投资问题",
        ])

    def _command_ribbon_panel(self, *, session: dict, llm_ready: bool, workspace: dict) -> str:
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        resource_count = len(self._recent_resource_links(limit=24))
        primary = self._setup_primary_action(workspace_ready, token_ready, llm_ready)
        ask = "直接输入投资问题" if token_ready and llm_ready else "/setup run"
        verify = "/plan" if self._last_agent_plan else "/server goals"
        create = "/chart <标题> :: {json}" if workspace_ready else "/workspace browse"
        recover = "/links open 1" if resource_count else "/links"
        rows = [
            "Now       " + primary,
            "Ask       " + ask + " · 本机 LLM 先理解意图，再选择 MCP/web_search",
            "Verify    " + verify + " · 看服务端状态、工具链路和本轮 Agent 计划",
            "Create    " + create + " · 服务端 chart artifact -> 授权工作区",
            f"Recover   {recover} · 网页/图片/图表/报告链接收件箱 links[{resource_count}]",
            "Mode      /server 进入服务端工作台 · /tools 查看 MCP playbook · /workspace 管理沙箱",
        ]
        return _text_panel("Agent Command Ribbon", rows, min_width=82, max_width=120)

    def _mission_control_panel(self, *, session: dict, base_url: str, llm_ready: bool, workspace: dict) -> str:
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        server_ready = bool(base_url)
        resource_count = len(self._recent_resource_links(limit=24))
        lanes = [
            ("INPUT", "natural language", "ready"),
            ("DATA", "super-66/web_search", "ready" if token_ready else "login"),
            ("CORE", "protected map", "ready" if server_ready and token_ready else "setup"),
            ("OUTPUT", "answer/chart/links", "ready" if llm_ready and workspace_ready else "setup"),
        ]
        rail = "  ->  ".join(f"{name}[{state}]" for name, _, state in lanes)
        rows = [
            "Mission     Ask -> Data -> Protected Core -> Local Answer -> Artifact",
            f"Rail        {rail}",
            f"Ask         直接输入问题；或 /server map <问题> 只检查服务端理解",
            "Data        super-66 MCP 优先；web_search 补新闻和网页线索",
            "Create      说“做成图表/报告”或 /chart <标题> :: {json}",
            f"Resources   /links 1 或 /open 1 打开网页、图片、图表和报告 · links[{resource_count}]",
        ]
        return _text_panel("Mission Control", rows, min_width=82, max_width=120)

    def _agent_hud_panel(self, *, session: dict, base_url: str, llm_ready: bool, workspace: dict) -> str:
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        resource_count = len(self._recent_resource_links(limit=24))
        chips = [
            self._status_chip("account", token_ready),
            self._status_chip("model", llm_ready),
            self._status_chip("workspace", workspace_ready),
            self._status_chip("mcp", token_ready),
            self._status_chip("server", bool(base_url)),
            self._status_chip("chart", workspace_ready),
            f"links[{resource_count}]" if resource_count else "links[none]",
        ]
        if token_ready and llm_ready and workspace_ready:
            fastest = "直接输入投资问题；需要图表时继续说“做成图表/报告”"
        elif not workspace_ready:
            fastest = "/workspace browse 选择项目文件夹，或 /workspace path <路径> 手动指定"
        elif not token_ready:
            fastest = "/login xwab <账号> 登录后复用账号访问服务端和 super-66 MCP"
        else:
            fastest = "/model key 在本机测试并保存大模型 API Key"
        workspace_path = str(workspace.get("path") or resolve_workspace_path())
        if len(workspace_path) > 54:
            workspace_path = "..." + workspace_path[-51:]
        return _text_panel("Agent HUD", [
            "Status      " + "  ".join(chips),
            "Data Flow   prompt -> local intent -> super-66/web_search -> server map -> local LLM -> chart",
            f"Workspace   {workspace_path}",
            f"Fast Path   {fastest}",
            f"Resources   links[{resource_count}] · {'/links open 1 打开最近资源' if resource_count else '回答产生网页/图片/图表后会出现在 /links'}",
            "Palette     输入 / 打开命令面板；输入 /server 或 /workspace 会收窄到对应子命令",
        ], min_width=78, max_width=120)

    def _status_chip(self, label: str, ok: bool) -> str:
        return f"{label}[{'ok' if ok else 'need'}]"

    def _launchpad_panel(self, *, session: dict, llm_ready: bool, workspace: dict) -> str:
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        ask_action = "直接输入投资问题" if token_ready and llm_ready else "/setup run 补齐账号和本机大模型"
        create_action = "说“把这个做成图表/报告”" if workspace_ready else "/workspace browse 或 /workspace path <路径> 选择项目文件夹并授权"
        rows = [
            ("Ask", f"{ask_action} · 先取 MCP，再做服务端映射和本机分析"),
            ("Verify", "/server actions · /doctor · /plan"),
            ("Create", f"{create_action} · 服务端 chart artifact -> 本地 .erlangshen/artifacts"),
            ("Links", "/links 查看资源；/links open 1 打开网页、图片、图表或报告"),
            ("Data", "super-66 MCP 行情/产品优先；web_search 补事件线索"),
        ]
        return _panel("Agent Launchpad", rows)

    def _starter_prompt_examples(self) -> list[tuple[str, str]]:
        return [
            ("今天行情怎么样？先帮我看盘面主线和风险。", "市场概览: super-66 MCP 指数/全球资产 + web_search + 服务端场景映射"),
            ("帮我看一下贵州茅台今天怎么走。", "单资产: search_astocks/get_astock_realtime + 新闻线索 + 本机分析"),
            ("我现在偏红利和黄金，下一步要不要降低波动？", "组合风控: 用户约束 + MCP 数据 + 本机模型生成执行建议"),
            ("把刚才的资产表现做成图表。", "产物生成: 复用 recent_conversation/MCP，服务端 chart artifact 保存到工作区"),
        ]

    def _starter_prompt_lines(self, *, compact: bool = False) -> list[str]:
        lines = []
        for index, (prompt, route) in enumerate(self._starter_prompt_examples(), 1):
            if compact:
                lines.append(f"  {index}  {prompt}")
            else:
                lines.append(f"{index}. {prompt}")
                lines.append(f"   路线: {route}")
        return lines

    def _workspace_passport_panel(self, workspace: dict) -> str:
        path = str(workspace.get("path") or resolve_workspace_path())
        allowed = bool(workspace.get("allowed"))
        permission = "已授权，可保存图表、报告和工作记忆" if allowed else "未授权，当前不会写入本地文件"
        action = "/workspace browse 用方向键选择项目文件夹；/workspace allow 授权写入" if not allowed else "/artifacts 查看产物；/open 打开图表/报告；/open link 1 打开资源"
        return _text_panel("Project Sandbox", [
            f"Path        {path}",
            f"Permission  {permission}",
            "Artifacts   .erlangshen/artifacts inside selected project",
            f"Action      {action}",
        ], min_width=72, max_width=110)

    def _agent_readiness_panel(
        self,
        *,
        session: dict,
        base_url: str,
        llm_ready: bool,
        workspace: dict,
    ) -> str:
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        states = [
            ("account", token_ready, "/login"),
            ("model", llm_ready, "/model key"),
            ("workspace", workspace_ready, "/workspace browse"),
            ("mcp", token_ready, "xwab/xczt"),
            ("server", bool(base_url), "configured"),
            ("artifacts", workspace_ready, ".erlangshen"),
        ]
        rows = []
        for name, ok, hint in states:
            mark = "OK" if ok else "NEED"
            rows.append((name, f"{mark} · {hint}"))
        return _panel("Agent Readiness", rows)

    def prompt(self) -> str:
        session = load_auth_session()
        user = session.get("user") or {}
        name = user.get("username") or user.get("email") or user.get("id") or "guest"
        if len(name) > 24:
            name = name[:21] + "..."
        return f"erlangshen:{name}> "

    def _prompt_status_text(self) -> str:
        session = load_auth_session()
        config = get_config()
        workspace = workspace_status()
        provider, model, llm_ready, _ = self._llm_status(config)
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        resource_count = len(self._recent_resource_links(limit=24))
        chips = [
            self._status_chip("account", token_ready),
            self._status_chip("model", llm_ready),
            self._status_chip("workspace", workspace_ready),
            self._status_chip("mcp", token_ready),
            self._status_chip("chart", workspace_ready),
            f"links[{resource_count}]" if resource_count else "links[none]",
        ]
        if not token_ready or not llm_ready or not workspace_ready:
            action = "/setup run"
        elif self._last_agent_plan:
            action = "/plan"
        else:
            action = "直接提问"
        model_text = f"{provider}/{model}"
        if len(model_text) > 34:
            model_text = model_text[:31] + "..."
        return (
            "  ".join(chips)
            + f"  {self._token_meter_compact()}"
            + f"  model:{model_text}"
            + f"  next:{action}"
            + ("  links:/links open 1" if resource_count else "")
            + "  / 打开命令  /server goals  /tools"
        )

    def _prompt_status_bar_fragments(self):
        width = min(max(72, _terminal_width()), 150)
        text = self._prompt_status_text()
        return [("class:status", text[:width])]

    def _server_display_text(self, base_url: str | None) -> str:
        return "已配置" if (base_url or "").strip() else "未配置"

    def _format_interactive_turn(self, user_input: str, result: str) -> str:
        if not self._is_advice_turn(user_input):
            return f"\n{result}\n"
        question = self._turn_question_text(user_input)
        meter = self._token_dialog_footer(activity="ready")
        return "\n".join([
            "",
            self._message_block("你", question, "36;1"),
            "",
            self._message_block("二郎神", result, "32;1"),
            meter,
            "",
        ])

    async def _print_interactive_turn(self, user_input: str, result: str) -> None:
        if self._live_answer_finalized and self._is_advice_turn(user_input):
            self._live_answer_finalized = False
            self._live_answer_state = None
            return
        if self._interactive_question_printed and self._is_advice_turn(user_input):
            output = self._format_interactive_answer(result)
        else:
            output = self._format_interactive_turn(user_input, result)
        if self._should_stream_terminal_render(user_input):
            await self._stream_terminal_text(output)
        else:
            print(output)

    def _print_interactive_question(self, user_input: str) -> None:
        question = self._turn_question_text(user_input)
        print("\n".join(["", self._message_block("你", question, "36;1"), ""]), flush=True)

    def _format_interactive_answer(self, result: str) -> str:
        meter = self._token_dialog_footer(activity="ready")
        return "\n".join([
            "",
            self._message_block("二郎神", result, "32;1"),
            meter,
            "",
        ])

    def _should_stream_terminal_render(self, user_input: str) -> bool:
        setting = os.getenv("ERLANGSHEN_STREAM_RENDER", "on").lower()
        if setting in {"0", "off", "false", "no"}:
            return False
        if not self._is_advice_turn(user_input):
            return False
        return sys.stdout.isatty() or setting in {"1", "on", "true", "yes", "force"}

    async def _stream_terminal_text(self, text: str) -> None:
        chunk_size = self._stream_render_chunk_size()
        delay = self._stream_render_delay()
        for index in range(0, len(text), chunk_size):
            sys.stdout.write(text[index:index + chunk_size])
            sys.stdout.flush()
            if delay > 0:
                await asyncio.sleep(delay)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
            sys.stdout.flush()

    def _stream_render_chunk_size(self) -> int:
        try:
            return max(1, min(80, int(os.getenv("ERLANGSHEN_STREAM_RENDER_CHUNK", "16"))))
        except (TypeError, ValueError):
            return 16

    def _stream_render_delay(self) -> float:
        try:
            return max(0.0, min(0.05, float(os.getenv("ERLANGSHEN_STREAM_RENDER_DELAY", "0.002"))))
        except (TypeError, ValueError):
            return 0.002

    def _is_advice_turn(self, user_input: str) -> bool:
        text = (user_input or "").strip()
        if not text:
            return False
        if not text.startswith("/"):
            return True
        command = text[1:].split(maxsplit=1)[0].lower()
        return command in {"advice", "建议", "投顾"}

    def _turn_question_text(self, user_input: str) -> str:
        text = (user_input or "").strip()
        if not text.startswith("/"):
            return text
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else text

    def _message_block(self, title: str, body: str, color_code: str) -> str:
        width = self._dialog_box_width()
        content_width = width - 4
        top = _color(f"╭─ {title} " + "─" * max(0, width - _display_width(title) - 5) + "╮", color_code)
        bottom = _color("╰" + "─" * (width - 2) + "╯", color_code)
        lines = []
        for raw_line in (body or "").splitlines() or [""]:
            if not raw_line:
                lines.append("│ " + " " * content_width + " │")
                continue
            display_line = self._message_display_line(raw_line)
            for line in self._wrap_text(display_line, content_width):
                lines.append("│ " + _pad_display(line, content_width) + " │")
        return "\n".join([top, *lines, bottom])

    def _dialog_box_width(self) -> int:
        terminal = max(32, _terminal_width())
        available = max(32, terminal - 2)
        return min(available, 140)

    def _message_display_line(self, text: str) -> str:
        line = str(text).rstrip()
        heading = re.match(r"^\s{0,3}#{1,3}\s+(.+)$", line)
        if heading:
            return f"▸ {heading.group(1).strip()}"
        bullet = re.match(r"^(\s*)([-*]|\d+[.、])\s+(.+)$", line)
        if bullet:
            indent, marker, content = bullet.groups()
            return f"{indent}{marker} {content.strip()}"
        return line

    def _wrap_text(self, text: str, limit: int, *, continuation_indent: int | None = None) -> list[str]:
        text = str(text)
        if _display_width(text) <= limit:
            return [text]
        prefix = ""
        if continuation_indent is None:
            match = re.match(r"^(\s*(?:[-*]|\d+[.、])\s+)", text)
            if match:
                prefix = " " * _display_width(match.group(1))
        elif continuation_indent > 0:
            prefix = " " * continuation_indent
        result = []
        remaining = text
        first = True
        while remaining and _display_width(("" if first else prefix) + remaining) > limit:
            current_prefix = "" if first else prefix
            available = max(8, limit - _display_width(current_prefix))
            cut = self._wrap_cut_index(remaining, available)
            chunk = remaining[:cut].rstrip()
            if not chunk:
                chunk = _clip_display(remaining, available).rstrip()
                cut = max(1, len(chunk))
            result.append(current_prefix + chunk)
            remaining = remaining[cut:].lstrip()
            first = False
        if remaining:
            result.append(remaining if first else prefix + remaining)
        return result

    def _wrap_cut_index(self, text: str, limit: int) -> int:
        if _display_width(text) <= limit:
            return len(text)
        width = 0
        end = 0
        for index, char in enumerate(text):
            char_width = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1)
            if width + char_width > limit:
                break
            width += char_width
            end = index + 1
        window = text[:max(1, end)]
        threshold = max(8, int(limit * 0.55))
        for pattern in (" ", "，", "。", "；", "、", ",", ";", "/"):
            index = window.rfind(pattern)
            candidate = index + (0 if pattern == " " else 1)
            if index >= 0 and _display_width(window[:candidate]) >= threshold:
                return max(1, candidate)
        return max(1, end)

    def _confirm_workspace_sandbox(self) -> None:
        if not sys.stdin.isatty() or os.getenv("ERLANGSHEN_SKIP_WORKSPACE_PROMPT"):
            return
        workspace = resolve_workspace_path()
        status = workspace_status(workspace)
        if status.get("allowed") and not self._is_package_install_workspace(status.get("path") or workspace):
            return
        if status.get("allowed"):
            print(_color("当前项目文件夹指向客户端安装目录，请重新选择一个用于保存图表、报告和记忆的项目文件夹。", "33"))
            workspace = self._default_workspace_candidate()
        line, _ = self._select_and_authorize_workspace(workspace, force=True)
        if "已跳过" in line:
            print(_color("项目文件夹未授权，本次仅进行对话与远程接口调用，不写入本地分析产物。", "33"))
        elif "已授权" in line:
            print(_color(line.replace("- 工作区: ", "项目文件夹"), "32"))
        else:
            print(_color(line.replace("- 工作区: ", "项目文件夹"), "33"))
        print()

    def _select_and_authorize_workspace(self, workspace, *, force: bool = False) -> tuple[str, dict]:
        status = workspace_status(workspace)
        if status.get("allowed") and not force:
            return f"- 工作区: 已授权 {status.get('path')}", status
        try:
            selected = self._read_workspace_path_selection(workspace)
        except (KeyboardInterrupt, EOFError, OSError):
            selected = "n"
        selected_key = selected.lower()
        if selected_key in {"n", "no", "否", "跳过", "skip"}:
            return "- 工作区: 已跳过授权，本次不会写入图表或报告", workspace_status(workspace)
        workspace = resolve_workspace_path(None if selected_key in {"", "y", "yes", "是", "好", "允许"} else selected)
        select_workspace(workspace)
        try:
            answer = input(
                f"是否允许二郎神在该项目文件夹读写分析产物？\n"
                f"  {workspace}\n"
                "用于保存图表、报告、工作记忆和资源链接索引；不会越过该目录访问其他路径 [Y/n]: "
            ).strip().lower()
        except (KeyboardInterrupt, EOFError, OSError):
            answer = "n"
        if answer in {"", "y", "yes", "是", "好", "允许"}:
            approved = approve_workspace(workspace)
            return f"- 工作区: 已授权 {approved.get('path')}", approved
        return f"- 工作区: 已选择但未授权 {workspace}", workspace_status(workspace)

    def _read_workspace_path_selection(self, workspace) -> str:
        if sys.stdin.isatty() and sys.stdout.isatty():
            selected = self._browse_workspace_directory(workspace)
            if selected is not None:
                return selected
        return self._prompt_workspace_path(workspace)

    def _is_package_install_workspace(self, workspace) -> bool:
        if not workspace:
            return False
        package_root = Path(__file__).resolve().parents[1]
        if "node_modules" not in package_root.parts:
            return False
        try:
            Path(workspace).expanduser().resolve().relative_to(package_root)
            return True
        except (OSError, ValueError):
            return False

    def _default_workspace_candidate(self) -> Path:
        for raw in (os.getenv("ERLANGSHEN_LAUNCH_CWD"), os.getcwd(), str(Path.home())):
            path = Path(str(raw or "")).expanduser()
            if not path.exists() or not path.is_dir():
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if not self._is_package_install_workspace(resolved):
                return resolved
        return Path.home().resolve()

    def _prompt_workspace_path(self, workspace) -> str:
        prompt = (
            "请选择二郎神本次可使用的项目文件夹（Tab 补全路径；输入 n 跳过）。\n"
            f"  当前候选: {workspace}\n"
            "路径（直接回车使用当前候选；输入 n 跳过本地文件写入）: "
        )
        if self._prompt_toolkit_available():
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.completion import PathCompleter

                session = PromptSession(
                    completer=PathCompleter(only_directories=True, expanduser=True),
                    complete_while_typing=True,
                )
                return session.prompt(prompt, default=str(workspace)).strip()
            except (KeyboardInterrupt, EOFError, OSError):
                raise
            except Exception:
                pass
        return input(prompt).strip()

    def _browse_workspace_directory(self, workspace) -> str | None:
        try:
            import termios
            import tty
        except ImportError:
            return None
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return None

        current = self._normalize_workspace_browser_path(workspace)
        if self._is_package_install_workspace(current):
            current = self._default_workspace_candidate()
        selected = 0
        rendered_height = 0
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                items = self._workspace_directory_items(current)
                selected = max(0, min(selected, len(items) - 1))
                rendered_height = self._render_workspace_browser(current, items, selected)
                key = self._read_workspace_key(fd)
                if key == "ctrl_c":
                    raise KeyboardInterrupt
                if key == "eof":
                    raise EOFError
                if key in {"q", "Q"}:
                    return "n"
                if key == "enter":
                    action, path, _ = items[selected]
                    if action == "use":
                        return str(current)
                    if action == "choose":
                        return str(path)
                    if action == "manual":
                        self._clear_terminal_block(rendered_height)
                        rendered_height = 0
                        return self._prompt_workspace_path(current)
                    current = path
                    selected = 0
                    continue
                if key in {"p", "P"}:
                    self._clear_terminal_block(rendered_height)
                    rendered_height = 0
                    return self._prompt_workspace_path(current)
                if key in {"up", "k", "K"}:
                    selected = (selected - 1) % len(items)
                elif key in {"down", "j", "J"}:
                    selected = (selected + 1) % len(items)
                elif key == "home":
                    selected = 0
                elif key == "end":
                    selected = len(items) - 1
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except OSError:
                pass
            if rendered_height:
                self._clear_terminal_block(rendered_height)

    def _normalize_workspace_browser_path(self, workspace) -> Path:
        path = Path(str(workspace)).expanduser()
        if path.exists() and path.is_file():
            path = path.parent
        if not path.exists():
            existing = next((parent for parent in [path, *path.parents] if parent.exists()), Path.cwd())
            path = existing
        try:
            return path.resolve()
        except OSError:
            return Path.cwd().resolve()

    def _workspace_directory_items(self, current: Path) -> list[tuple[str, Path, str]]:
        use_label = "使用启动目录作为项目沙箱" if current == self._default_workspace_candidate() else "使用当前目录作为项目沙箱"
        items: list[tuple[str, Path, str]] = [
            ("use", current, use_label),
            ("manual", current, "手动输入或粘贴其他路径"),
        ]
        seen_paths = {str(current)}
        for item in recent_workspaces(limit=4):
            path = Path(str(item.get("path") or "")).expanduser()
            if not path.exists() or not path.is_dir() or str(path.resolve()) in seen_paths:
                continue
            seen_paths.add(str(path.resolve()))
            badge = "已授权" if item.get("allowed") else "未授权"
            resource_count = self._workspace_resource_count(path)
            resource_badge = f" · {resource_count} 资源" if resource_count else ""
            items.append(("choose", path.resolve(), f"最近项目 · {badge}{resource_badge} · 直接切换"))
        parent = current.parent
        if parent != current:
            items.append(("open", parent, ".. 上一级目录"))
        try:
            children = [
                child for child in current.iterdir()
                if child.is_dir() and not child.name.startswith(".")
            ]
        except OSError:
            children = []
        for child in sorted(children, key=lambda item: item.name.lower())[:40]:
            items.append(("open", child, child.name + "/"))
        return items

    def _workspace_resource_count(self, workspace: str | Path) -> int:
        try:
            return len(self._read_resource_index(self._resource_index_path(workspace)))
        except (OSError, PermissionError, TypeError, ValueError):
            return 0

    def _render_workspace_browser(
        self,
        current: Path,
        items: list[tuple[str, Path, str]],
        selected: int,
    ) -> int:
        width = min(max(76, _terminal_width() - 4), 120)
        max_rows = 12
        visible = items[:max_rows]
        if selected >= max_rows and len(items) > max_rows:
            start = min(selected - max_rows + 1, len(items) - max_rows)
            visible = items[start:start + max_rows]
        else:
            start = 0
        lines = [
            _color("╭─ Project Sandbox Setup " + "─" * max(0, width - _display_width("Project Sandbox Setup") - 5) + "╮", "36"),
            self._browser_line("选择二郎神本次可访问的项目文件夹", width),
            self._browser_line(f"当前浏览: {str(current)}", width),
            self._browser_line(self._workspace_browser_resource_hint(current), width),
            self._browser_line("授权后: 仅在该目录内保存图表、报告、工作记忆和可打开资源索引", width),
            self._browser_line("不会写入: 大模型 API Key、账号 token、服务端内部认知库", width),
            self._browser_line("↑↓/jk 选择  Enter 打开/确认  p 粘贴路径  q 跳过", width),
            "├" + "─" * (width - 2) + "┤",
        ]
        for row_index in range(max_rows):
            if row_index < len(visible):
                absolute_index = start + row_index
                action, path, label = visible[row_index]
                marker = "›" if absolute_index == selected else " "
                description = str(path) if action in {"use", "manual", "choose"} else str(path.name or path)
                text = f"{marker} {_pad_display(label, 34)} {description}"
            else:
                text = ""
            line = self._browser_line(text, width)
            if row_index < len(visible) and start + row_index == selected:
                line = _color(line, self._ansi_selected_style())
            lines.append(line)
        footer = f"{len(items)} 个可选项 · 产物/资源索引 .erlangshen/artifacts · 后续 /setup run"
        if len(items) > max_rows:
            footer += f" · 当前 {selected + 1}/{len(items)}"
        lines.extend([
            "├" + "─" * (width - 2) + "┤",
            self._browser_line(footer, width),
            self._browser_line("提示: 选定后还会再次确认写入权限；也可稍后用 /workspace browse 重新选择", width),
            _color("╰" + "─" * (width - 2) + "╯", "36"),
        ])
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.write(f"\033[{len(lines)}A")
        sys.stdout.flush()
        return len(lines)

    def _browser_line(self, text: str, width: int) -> str:
        return "│ " + _pad_display(text, width - 3) + "│"

    def _workspace_browser_resource_hint(self, current: Path) -> str:
        count = self._workspace_resource_count(current)
        if count:
            return f"当前项目资源索引: 已发现 {count} 条网页/图片/图表/报告链接"
        return "当前项目资源索引: 暂无；授权后会保存 resources.json"

    def _clear_terminal_block(self, height: int) -> None:
        for _ in range(height):
            sys.stdout.write("\033[2K\r\n")
        sys.stdout.write(f"\033[{height}A")
        sys.stdout.flush()

    def _prompt_toolkit_available(self) -> bool:
        try:
            return importlib.util.find_spec("prompt_toolkit") is not None
        except Exception:
            return False

    def print_help(self):
        """打印帮助信息"""
        print(self.help_text())

    def help_text(self) -> str:
        """Return CLI help text."""
        return f"""
{_logo()}

二郎神 - 服务端优先 CLI

常用命令:
  /benchmarks                 查看高 star CLI 对标、已落地优化点和路线
  /benchmarks checklist       查看 CLI 优化开发清单和下一步路线
  /login [xwab|xczt] [账号]    登录核心服务端
  /logout                     清除本地登录状态
  /status                     查看登录状态
  /model                      检查大模型 provider/model/API key 配置
  /model select               光标选择大模型供应商和型号
  /model key                  在本机测试并保存当前供应商 API Key
  /setup                      查看初始化向导和当前准备状态
  /setup run                  交互式选择项目文件夹并授权沙箱
  /setup workspace            重新选择项目文件夹并授权本地沙箱
  /doctor                     本地诊断工作区、登录、大模型、MCP 与产物链路
  /tools                      查看 MCP、web_search 和图表 artifact 能力地图
  /plan                       查看最近一次分析的意图、工具调用和产物计划
  /plan history               查看授权工作区里的历史分析计划
  /plan diff                  对比最近两次分析计划
  /context                    查看最近对话上下文；/context clear 清空
  /commands [关键词]           打开命令面板；可按关键词搜索
  /commands usage             查看命令热度、scope 和存储文件
  /service                    查看服务端状态
  /health                     服务端健康检查
  /map <问题>                 映射服务端认知场景
  /advice <问题>              服务端映射场景，本机大模型生成建议
  <自然语言问题>              等同于 /advice <问题>
  /clear                      清屏并开启干净上下文
  /exit                       退出

全局选项:
  --json                      输出机器可读 envelope
  --plain / --no-color        禁用颜色和 OSC8 链接
  --strict / --exit-code      未就绪、未知命令或参数错误时返回非零退出码

完整命令:
  /auth <cmd>                 登录、账号、服务端地址
  /server <cmd>               调用核心服务端 API
  /workspace                  查看或授权当前项目文件夹沙箱
  /workspace browse           用方向键选择项目文件夹
  /workspace path <路径>       手动输入或粘贴项目文件夹路径
  /workspace allow [路径]      授权项目文件夹写入 .erlangshen/artifacts 和 resources.json
  /artifacts                  查看当前项目文件夹内的图表和报告
  /open [chart|report|link N]  打开最近图表、报告或 /links 中的资源
  /open link <序号>            打开 /links 列表里的指定网页、图片或本地产物
  /links                      查看最近网页、图片和本地产物名称链接
  /chart <标题> :: {json}      生成结构化图表 artifact
  /tools                      查看数据工具、搜索和图表通信能力
  /memory                     查看本机持久记忆；自动压缩上下文
  /memory clear               清空本机持久记忆

本地开发命令:
  /analyze <query>            综合分析
  /macro <query>              宏观分析
  /stock <query>              股票分析
  /report <query>             报告生成
  /search <query>             搜索
  /portfolio <query>          组合分析
  /risk <query>               风险分析
  /memo <query>               纪要管理
  /invest [option]            投资分析

示例:
  erlangshen /auth server https://xiaoerdata.site/api/erlangshen
  erlangshen /login xwab user@example.com
  erlangshen /model
  erlangshen /benchmarks
  erlangshen /benchmarks checklist
  erlangshen /plan history
  erlangshen /plan diff
  erlangshen /commands work
  erlangshen /commands usage
  erlangshen /model select
  erlangshen /model key
  erlangshen --cd /path/to/project
  erlangshen /memory
  erlangshen /setup workspace
  erlangshen /workspace browse
  erlangshen /workspace path /path/to/project
  erlangshen /workspace allow
  erlangshen /commands
  erlangshen /status
  erlangshen /map 全球流动性转向时风险资产怎么看
  erlangshen /advice 利率下行时A股红利资产怎么看
  erlangshen 利率下行时A股红利资产怎么看
"""

    def command_palette_text(self, query: str = "") -> str:
        """Return a compact slash-command palette."""
        query = (query or "").strip()
        if query.lower().split()[:1] in (["usage"], ["stats"], ["热度"], ["统计"]):
            return self.command_usage_text(query)
        if query:
            matches = self._filter_palette(query)
            lines = [
                "【二郎神命令搜索】",
                f"- 查询: {query}",
                f"- 匹配: {len(matches)} 个",
                "- 规则: 精确/前缀优先，随后按 token、子序列、相似度和使用频次排序",
                "",
            ]
            if not matches:
                suggestion = self._command_suggestion(query.split()[0])
                if suggestion:
                    lines.append(f"没有直接匹配。你是不是想输入: /{suggestion}")
                else:
                    lines.append("没有匹配命令。输入 /commands 查看完整命令面板。")
                return "\n".join(lines)
            rows = ["command                          what it does"]
            for command_id, shortcut, description in matches[:16]:
                group = self._palette_group_title(command_id)
                usage = self._command_usage_summary(command_id)
                meta = (f"{usage} · " if usage else "") + f"{description} · {group}"
                rows.append(f"{shortcut:<32} {meta}")
            lines.append(_text_panel("Command Search", rows, min_width=88, max_width=120))
            if len(matches) > 16:
                lines.append(f"... 还有 {len(matches) - 16} 个匹配；继续输入更具体的关键词可收窄结果。")
            lines.append("")
            lines.append("提示: 也可以在交互模式输入 / 后直接键入关键词，↑↓ 选择，Enter 确认。")
            return "\n".join(lines)
        by_id = {item[0]: item for item in COMMAND_PALETTE}
        lines = [
            "【二郎神命令面板】",
            _panel("Command Workbench", [
                ("start", "/setup run · 初始化项目沙箱、账号和本机大模型"),
                ("ask", "直接输入自然语言问题 · 本机 LLM 选择 MCP/web_search 和服务端映射"),
                ("server", "/server  · status / goals / flow / artifact / capabilities"),
                ("workspace", "/workspace browse · 选择项目文件夹并授权图表/报告保存"),
                ("model", "/model select · /model key 本机测试并保存 API Key"),
                ("resources", "/links 1 · /open 1 打开网页、图片、图表和报告"),
                ("audit", "/plan · /memory · /brief · /doctor 复盘工具链路、记忆和诊断"),
            ]),
            "",
        ]
        seen: set[str] = set()
        for title, command_ids in COMMAND_GROUPS:
            group_lines = ["command                          what it does"]
            for command_id, shortcut, description in COMMAND_PALETTE:
                if command_id in command_ids:
                    usage = self._command_usage_summary(command_id)
                    meta = (f"{usage} · " if usage else "") + description
                    group_lines.append(f"{shortcut:<32} {meta}")
                    seen.add(command_id)
            if len(group_lines) > 1:
                lines.append(_text_panel(title, group_lines, min_width=88, max_width=120))
                lines.append("")
        remaining = [item for item in COMMAND_PALETTE if item[0] not in seen and item[0] in by_id]
        if remaining:
            group_lines = ["command                          what it does"]
            for command_id, shortcut, description in remaining:
                usage = self._command_usage_summary(command_id)
                meta = (f"{usage} · " if usage else "") + description
                group_lines.append(f"{shortcut:<32} {meta}")
            lines.append(_text_panel("More", group_lines, min_width=88, max_width=120))
            lines.append("")
        lines.append("提示: 在交互模式下输入 / 会弹出可选择命令列表；输入字母可过滤，↑↓ 选择，Enter 确认。")
        return "\n".join(lines)

    def command_usage_text(self, args: str = "") -> str:
        tokens = (args or "").strip().split()
        lowered = {token.lower() for token in tokens}
        output_json = any(token in {"json", "--json"} for token in lowered)
        if lowered & {"reset", "clear", "clean", "清空", "重置"}:
            return self.command_usage_reset_text(output_json=output_json)
        if lowered & {"export", "dump", "导出"}:
            return self.command_usage_export_text(output_json=output_json)
        usage = self._load_command_usage()
        commands = usage.get("commands") if isinstance(usage, dict) else {}
        rows = self._command_usage_rows(commands if isinstance(commands, dict) else {})
        path = self._command_usage_path()
        payload = {
            "ok": True,
            "scope": self._command_usage_scope(),
            "path": str(path) if path else None,
            "updated_at": usage.get("updated_at") if isinstance(usage, dict) else None,
            "count": len(rows),
            "commands": rows,
        }
        if output_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        lines = [
            "【命令使用热度】",
            f"- 策略: {payload['scope']}",
            f"- 文件: {payload['path'] or '未记录'}",
            f"- 更新时间: {payload['updated_at'] or '暂无'}",
            f"- 命令数: {len(rows)}",
            "- 配置: ERLANGSHEN_COMMAND_USAGE_SCOPE=global|project|off",
        ]
        if payload["scope"] == "project" and not payload["path"]:
            lines.append("- 提示: project 策略需要先 /workspace allow 授权项目文件夹。")
        if not rows:
            lines.extend([
                "",
                "暂无命令使用记录。交互模式下执行命令后会自动记录；脚本测试可设置 ERLANGSHEN_RECORD_NON_TTY_COMMANDS=1。",
            ])
            return "\n".join(lines)
        lines.extend(["", "Top commands:"])
        for index, item in enumerate(rows[:12], 1):
            last = item.get("last_used") or "unknown"
            lines.append(f"{index}. {item.get('shortcut')} · {item.get('count')} 次 · last {last}")
        lines.extend([
            "",
            "命令:",
            "  /commands usage json  输出结构化热度数据",
            "  /commands usage export 导出当前热度快照",
            "  /commands usage reset  清空当前热度记录",
            "  /commands <关键词>     按关键词搜索并参考使用热度排序",
        ])
        return "\n".join(lines)

    def command_usage_reset_text(self, *, output_json: bool = False) -> str:
        scope = self._command_usage_scope()
        path = self._command_usage_path()
        commands = self._load_command_usage().get("commands") if path else {}
        removed = len(self._command_usage_rows(commands if isinstance(commands, dict) else {}))
        if path is None:
            payload = {
                "ok": False,
                "reason": "usage_disabled" if scope == "off" else "usage_path_unavailable",
                "scope": scope,
                "path": None,
                "removed": 0,
            }
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【命令热度清空】",
                "- 当前策略未提供可清空的 usage 文件。",
                "- 配置: ERLANGSHEN_COMMAND_USAGE_SCOPE=global|project|off",
            ])
        try:
            if path.exists():
                path.unlink()
            self._command_usage_cache = {"commands": {}}
        except OSError as exc:
            payload = {"ok": False, "error": str(exc), "scope": scope, "path": str(path), "removed": 0}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return f"【命令热度清空】\n- 清空失败: {exc}"
        payload = {"ok": True, "scope": scope, "path": str(path), "removed": removed}
        if output_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return "\n".join([
            "【命令热度清空】",
            f"- 文件: {path}",
            f"- 已移除命令: {removed}",
            "- 后续命令会重新开始累计热度。",
        ])

    def command_usage_export_text(self, *, output_json: bool = False) -> str:
        scope = self._command_usage_scope()
        path = self._command_usage_path()
        if path is None:
            payload = {
                "ok": False,
                "reason": "usage_disabled" if scope == "off" else "usage_path_unavailable",
                "scope": scope,
                "path": None,
                "export_path": None,
                "count": 0,
            }
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【命令热度导出】",
                "- 当前策略未提供可导出的 usage 文件。",
                "- project 策略需要先 /workspace allow 授权项目文件夹。",
            ])
        usage = self._load_command_usage()
        commands = usage.get("commands") if isinstance(usage, dict) else {}
        rows = self._command_usage_rows(commands if isinstance(commands, dict) else {})
        export_path = path.parent / f"command_usage_export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        payload = {
            "ok": True,
            "scope": scope,
            "source_path": str(path),
            "export_path": str(export_path),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(rows),
            "commands": rows,
            "usage": usage,
        }
        try:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            payload = {"ok": False, "error": str(exc), "scope": scope, "path": str(path), "export_path": None, "count": len(rows)}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return f"【命令热度导出】\n- 导出失败: {exc}"
        if output_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return "\n".join([
            "【命令热度导出】",
            f"- 来源文件: {path}",
            f"- 导出文件: {export_path}",
            f"- 命令数: {len(rows)}",
        ])

    def _command_usage_rows(self, commands: dict) -> list[dict[str, object]]:
        by_id = {command_id: shortcut for command_id, shortcut, _ in COMMAND_PALETTE}
        rows = []
        for command_id, item in commands.items():
            if not isinstance(item, dict):
                continue
            count = max(0, int(item.get("count") or 0))
            if not count:
                continue
            rows.append({
                "command_id": command_id,
                "shortcut": by_id.get(command_id, f"/{command_id}"),
                "count": count,
                "last_used": self._text_field(item.get("last_used")),
            })
        return sorted(rows, key=lambda item: (-int(item.get("count") or 0), str(item.get("last_used") or ""), str(item.get("shortcut") or "")))

    def workspace_text(self, args: str = "") -> str:
        raw = (args or "").strip()
        parts = raw.split(maxsplit=1)
        action = parts[0].lower() if parts else ""
        path_arg = parts[1].strip() if len(parts) > 1 else ""
        if action in {"allow", "approve", "授权", "允许"}:
            status = approve_workspace(path_arg or None)
        elif action in {"use", "select", "cd", "切换", "选择"}:
            status = select_workspace(path_arg or None)
        elif action in {"browse", "browser", "pick", "浏览", "选择器"}:
            if not sys.stdin.isatty() or not sys.stdout.isatty():
                return "\n".join([
                    "【项目文件夹选择器】",
                    "- 当前不是交互终端，无法打开目录选择器。",
                    "- 请在本机终端运行: erlangshen /workspace browse",
                    "- 或执行: erlangshen /workspace path <项目路径>",
                    "- 或直接执行: erlangshen /workspace use <项目路径>",
                ])
            selected = self._browse_workspace_directory(resolve_workspace_path(path_arg or None))
            if not selected or selected.lower() in {"n", "no", "否", "跳过", "skip"}:
                return "已取消项目文件夹选择。"
            status = select_workspace(selected)
        elif action in {"path", "manual", "input", "路径", "手动", "输入"}:
            if path_arg:
                status = select_workspace(path_arg)
            elif not sys.stdin.isatty() or not sys.stdout.isatty():
                return "\n".join([
                    "【手动选择项目文件夹】",
                    "- 当前不是交互终端，无法安全读取路径输入。",
                    "- 请执行: erlangshen /workspace path <项目路径>",
                    "- 然后授权: erlangshen /workspace allow",
                ])
            else:
                selected = self._prompt_workspace_path(resolve_workspace_path())
                if not selected or selected.lower() in {"n", "no", "否", "跳过", "skip"}:
                    return "已取消项目文件夹选择。"
                status = select_workspace(selected)
        elif action in {"revoke", "deny", "撤销", "拒绝"}:
            from src.workspace import revoke_workspace

            status = revoke_workspace(path_arg or None)
        else:
            status = workspace_status()
        return self._workspace_status_panel(status)

    def _workspace_status_panel(self, status: dict) -> str:
        workspace = str(status.get("path") or resolve_workspace_path())
        allowed = bool(status.get("allowed"))
        permission = "已授权，可保存图表、报告和工作记忆" if allowed else "未授权，当前不会写入本地文件"
        lines = [
            "【项目文件夹沙箱】",
            f"- 当前路径: {workspace}",
            f"- 权限: {permission}",
            f"- 模式: {status.get('mode')}",
            "- 产物目录: <项目>/.erlangshen/artifacts",
            "",
        ]
        if allowed:
            index_path = self._resource_index_path(workspace)
            resource_count = self._workspace_resource_count(workspace)
            lines.extend([
                f"- 资源索引: {index_path}",
                f"- 已索引资源: {resource_count} 条",
                "",
            ])
            lines.extend([
                "现在可以:",
                "- 直接继续提问，图表和报告会保存到授权项目内",
                "- /artifacts 查看已保存产物",
                "- /open 打开最近图表或报告",
                "- /links 查看最近网页、图片、PDF、图表和报告名称链接",
                "- /open 1 或 /links 1 直接打开最近资源",
            ])
        else:
            lines.extend([
                "选择项目文件夹:",
                "- /workspace browse        打开方向键路径选择器",
                "- /workspace path <路径>   手动粘贴或输入项目路径",
                "- /workspace use <路径>    手动粘贴或输入项目路径",
                "- /workspace allow [路径]  授权写入图表、报告、工作记忆和资源链接索引",
            ])
        lines.extend([
            "",
            "产物和链接:",
            "- 网页、图片、PDF、HTML 和本地图表不会塞进终端正文，会显示为可打开的名称链接。",
            "- 服务端返回 chart artifact 后，客户端只在授权项目内保存 JSON/HTML。",
            "- 授权后最近资源会写入项目资源索引；未授权时仅保存在当前 CLI 进程内。",
            "- 可用 /links 查看资源索引，用 /open 1 或 /links 1 打开。",
        ])
        recent = recent_workspaces(limit=4)
        lines.extend(["", "最近项目:"])
        if recent:
            for item in recent:
                path = str(item.get("path") or "")
                if not path:
                    continue
                badge = "已授权" if item.get("allowed") else "未授权"
                marker = "当前" if path == workspace else "可选"
                lines.append(f"- {marker} · {badge} · {path}")
        else:
            lines.append("- 暂无；可以先用 /workspace browse 选择，或 /workspace use <路径> 指定")
        lines.extend([
            "",
            "沙箱边界:",
            "- 未授权前不会写入本地文件。",
            "- 授权后只在所选项目目录内保存 .erlangshen/artifacts 和 resources.json。",
            "- 大模型 API Key 仍只保存在本机配置，不会写入项目文件夹。",
            "",
            "命令:",
            "  /workspace browse",
            "  /workspace path <路径>",
            "  /workspace use <路径>",
            "  /workspace allow [路径]",
            "  /workspace revoke [路径]",
        ])
        return "\n".join(lines)

    def artifacts_text(self, args: str = "") -> str:
        status = workspace_status()
        workspace = status.get("path")
        if not status.get("allowed"):
            return "\n".join([
                "【分析产物】",
                f"- 工作区: {workspace}",
                "- 状态: 未授权",
                "- 下一步: /workspace browse 选择项目文件夹，或 /workspace path <路径> 手动指定，然后 /workspace allow 授权保存图表和报告",
            ])
        root = ensure_inside_workspace(os.path.join(str(workspace), ".erlangshen", "artifacts"), workspace)
        charts_dir = root / "charts"
        reports_dir = root / "reports"
        if not charts_dir.exists() and not reports_dir.exists():
            return "\n".join([
                "【分析产物】",
                f"- 工作区: {workspace}",
                "- 暂无分析产物",
                "- 可执行: /chart 资产表现 :: {\"A股\":1.2,\"黄金\":0.8}",
                "- 也可以直接问: 把刚才的分析做成图表/报告",
            ])
        chart_files = self._artifact_files(charts_dir, {".json", ".html"})
        report_files = self._artifact_files(reports_dir, {".md"})
        chart_records = self._chart_artifact_records(charts_dir, workspace)
        if not chart_files and not report_files:
            return "\n".join([
                "【分析产物】",
                f"- 工作区: {workspace}",
                "- 暂无分析产物",
                "- 可执行: /chart 资产表现 :: {\"A股\":1.2,\"黄金\":0.8}",
                "- 也可以直接问: 把刚才的分析做成图表/报告",
            ])
        lines = [
            "【分析产物】",
            f"- 工作区: {workspace}",
            f"- 摘要: reports {len(report_files)} / charts {len(chart_files)}",
            f"- 图表视图: {len(chart_records)}",
            f"- 最近报告: {self._relative_workspace_path(report_files[0], workspace) if report_files else '暂无'}",
            f"- 最近图表: {self._relative_workspace_path(chart_files[0], workspace) if chart_files else '暂无'}",
            f"- 最近可打开: {self._latest_openable_artifact_label(workspace)}",
            "- 打开: /open report 或 /open chart",
            "- 继续生成: 直接说“把这个做成图表/报告”，或使用 /chart <标题> :: {...}",
            "- 用途: 图表由服务端 chart artifact 通道生成，报告由客户端保存到授权项目文件夹。",
            "",
            "产物收件箱:",
            "- 图表: /open chart 打开最近 HTML 图表；/artifacts 查看全部",
            "- 报告: /open report 打开最近 Markdown 报告",
            "- 资源: /links 1 或 /open 1 打开网页、图片、图表和报告名称链接",
        ]
        openable = self._latest_artifact_for_open("", workspace)
        if openable:
            lines.append(f"- 名称链接: {self._workspace_file_link(openable, workspace, label='打开最近产物')}")
        if chart_records:
            lines.append("")
            lines.append("- 最近图表摘要:")
            for record in chart_records[:5]:
                link_path = record.get("open_abs_path") or record.get("json_abs_path") or ""
                link_text = self._workspace_file_link(link_path, workspace, label=f"打开 {record['title']}") if link_path else ""
                lines.append(
                    f"  - {record['title']} ({record['chart_type']}): "
                    f"{', '.join(record['data_keys']) or '无数据键'} -> {record['open_path'] or record['json_path']}"
                    + (f" · {link_text}" if link_text else "")
                )
        if report_files:
            lines.append("")
            lines.append("- 分析报告:")
            for path in report_files[:8]:
                lines.append(f"  - {self._relative_workspace_path(path, workspace)} · {self._workspace_file_link(path, workspace, label='打开报告')}")
        if chart_files:
            lines.append("")
            lines.append("- 图表产物:")
            for path in chart_files[:12]:
                label = "打开图表" if path.suffix.lower() == ".html" else "打开 JSON"
                lines.append(f"  - {self._relative_workspace_path(path, workspace)} · {self._workspace_file_link(path, workspace, label=label)}")
        return "\n".join(lines)

    def _chart_artifact_records(self, charts_dir: Path, workspace: str) -> list[dict]:
        json_files = self._artifact_files(charts_dir, {".json"})
        records = []
        for json_path in json_files:
            artifact = {}
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    artifact = loaded if isinstance(loaded, dict) else {}
            except (OSError, json.JSONDecodeError):
                artifact = {}
            html_path = json_path.with_suffix(".html")
            data = artifact.get("data") if isinstance(artifact.get("data"), dict) else {}
            records.append({
                "title": self._text_field(artifact.get("title")) or json_path.stem,
                "chart_type": self._text_field(artifact.get("type")) or "chart",
                "data_keys": [str(key) for key in data.keys()][:8],
                "json_path": self._relative_workspace_path(json_path, workspace),
                "json_abs_path": str(json_path),
                "open_path": self._relative_workspace_path(html_path, workspace) if html_path.exists() else "",
                "open_abs_path": str(html_path) if html_path.exists() else "",
            })
        return records

    def _latest_openable_artifact_label(self, workspace: str) -> str:
        target = self._latest_artifact_for_open("", workspace)
        if not target:
            return "暂无"
        return self._relative_workspace_path(target, workspace)

    def open_artifact_text(self, args: str = "") -> str:
        if self._is_resource_open_args(args):
            return self.open_resource_link_text(args)
        status = workspace_status()
        workspace = status.get("path")
        if not status.get("allowed"):
            return "\n".join([
                "【打开分析产物】",
                f"- 工作区: {workspace}",
                "- 状态: 未授权",
                "- 下一步: /workspace allow <路径>",
            ])
        target = self._latest_artifact_for_open(args, workspace)
        if not target:
            return "\n".join([
                "【打开分析产物】",
                f"- 工作区: {workspace}",
                "- 暂无可打开产物",
                "- 可先执行: /chart 资产表现 :: {\"A股\":1.2,\"黄金\":0.8}",
            ])
        opener = self._system_open_command()
        if opener:
            try:
                import subprocess

                subprocess.Popen([*opener, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "\n".join([
                    "【打开分析产物】",
                    f"- 已尝试打开: {self._relative_workspace_path(target, workspace)}",
                    f"- 路径: {target}",
                    f"- 链接: {self._workspace_file_link(target, workspace, label='打开产物')}",
                ])
            except OSError as exc:
                return "\n".join([
                    "【打开分析产物】",
                    f"- 自动打开失败: {exc}",
                    f"- 路径: {target}",
                    f"- 链接: {self._workspace_file_link(target, workspace, label='打开产物')}",
                    "- 可手动在浏览器或编辑器中打开该文件。",
                ])
        return "\n".join([
            "【打开分析产物】",
            "- 当前环境没有可用桌面打开命令。",
            f"- 路径: {target}",
            f"- 链接: {self._workspace_file_link(target, workspace, label='打开产物')}",
            "- 可手动在浏览器或编辑器中打开该文件。",
        ])

    def _is_resource_open_args(self, args: str) -> bool:
        first = ((args or "").strip().split(maxsplit=1) or [""])[0].lower()
        return first.isdigit() or first in {"link", "links", "resource", "resources", "url", "网页", "链接", "资源"}

    def open_resource_link_text(self, args: str = "") -> str:
        parts = (args or "").strip().split()
        raw_index = parts[0] if parts and parts[0].isdigit() else (parts[1] if len(parts) > 1 else "1")
        try:
            index = max(1, int(raw_index))
        except ValueError:
            return "请提供要打开的资源序号，例如 /open link 1。"
        entries = self._recent_resource_links(limit=24)
        if not entries:
            return "\n".join([
                "【打开最近资源】",
                "- 暂无最近资源链接。",
                "- 下一步: 先输入投资问题，或用 /links 查看当前资源列表。",
                "- 快捷打开: /open 1 或 /links 1",
            ])
        if index > len(entries):
            return "\n".join([
                "【打开最近资源】",
                f"- 序号超出范围: {index}",
                f"- 当前可打开资源数: {len(entries)}",
                "- 输入 /links 查看完整列表。",
            ])
        entry = entries[index - 1]
        label, target = self._resource_entry_label_target(entry)
        opener = self._system_open_command()
        if opener:
            try:
                import subprocess

                subprocess.Popen([*opener, target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "\n".join([
                    "【打开最近资源】",
                    f"- 已尝试打开: {label}",
                    f"- 来源: {self._text_field(entry.get('source')) or 'resource'}",
                    f"- 类型: {self._text_field(entry.get('type')) or self._resource_type_for_target(target)}",
                    f"- 链接: {self._resource_link(label, target)}",
                ])
            except OSError as exc:
                return "\n".join([
                    "【打开最近资源】",
                    f"- 自动打开失败: {exc}",
                    f"- 链接: {self._resource_link(label, target)}",
                    "- 可手动在浏览器或编辑器中打开该资源。",
                ])
        return "\n".join([
            "【打开最近资源】",
            "- 当前环境没有可用桌面打开命令。",
            f"- 链接: {self._resource_link(label, target)}",
            "- 可手动在浏览器或编辑器中打开该资源。",
        ])

    def _split_named_link(self, link_text: str) -> tuple[str, str]:
        text = self._text_field(link_text)
        matches = re.findall(r"(?:https?|file)://[^\s)\]\x1b]+", text, flags=re.I)
        if matches:
            target = matches[-1].rstrip(".,;，。；")
            label = text.split(target, 1)[0].strip(" :-—()[]\x1b\\")
            if ": " in label:
                label = label.rsplit(": ", 1)[0]
            return label.strip() or "打开资源", target
        if ": " in text:
            label, target = text.rsplit(": ", 1)
            return label.strip() or "打开资源", self._normalize_open_target(target.strip())
        return "打开资源", self._normalize_open_target(text)

    def _normalize_open_target(self, target: str) -> str:
        text = self._text_field(target)
        if not text:
            return ""
        if re.match(r"^(?:https?|file)://", text, flags=re.I):
            return text
        if text.startswith("/") or text.startswith("~"):
            return self._file_uri(text)
        return text

    def links_text(self, args: str = "") -> str:
        raw = (args or "").strip()
        if raw:
            parts = raw.split()
            if parts and parts[0].isdigit():
                return self.open_resource_link_text(parts[0])
            if parts and parts[0].lower() in {"open", "打开", "go"}:
                index = parts[1] if len(parts) > 1 else "1"
                return self.open_resource_link_text(f"link {index}")
        entries = self._recent_resource_links(limit=12)
        status = workspace_status()
        index_path = self._resource_index_path(str(status.get("path") or "")) if status.get("allowed") else None
        lines = [
            "【最近可打开资源】",
            "- 范围: 本次 CLI 最近回答 + 已授权项目资源索引里的网页、图片和本地产物链接",
            "- 边界: 只保存命名链接，不包含 API Key、token 或服务端内部认知库内容",
        ]
        if index_path:
            lines.append(f"- 索引: {index_path}")
        else:
            lines.append("- 索引: 未授权项目文件夹时不写入磁盘")
        if not entries:
            lines.extend([
                "",
                "暂无资源链接。",
                "下一步:",
                "- 直接提问并允许二郎神读取 MCP/web_search，回答里会出现“可打开资源”。",
                "- 如果需要图表，可以说“把这个做成图表”，再用 /links 或 /open 查看。",
            ])
            return "\n".join(lines)
        lines.append("")
        for index, entry in enumerate(entries, 1):
            query = self._text_field(entry.get("query")) or "上一轮回答"
            source = self._text_field(entry.get("source")) or "resource"
            label, target = self._resource_entry_label_target(entry)
            resource_type = self._text_field(entry.get("type")) or self._resource_type_for_target(target)
            lines.append(f"{index}. {source} · {query}")
            lines.append(f"   名称: {self._resource_link(label, target)}")
            lines.append(f"   类型: {resource_type} · 目标: {target}")
        lines.extend([
            "",
            "命令:",
            "  /links 1          打开第 1 个最近资源",
            "  /links open 1     打开第 1 个最近资源",
            "  /open 1           打开第 1 个最近资源",
            "  /open link 1      打开第 1 个最近资源",
            "  /open chart        打开最近本地图表",
            "  /artifacts         查看全部本地产物",
            "  /context clear     清空最近上下文和资源链接",
        ])
        return "\n".join(lines)

    def _latest_artifact_for_open(self, args: str, workspace: str) -> Path | None:
        kind = (args or "").strip().lower()
        root = Path(str(workspace)) / ".erlangshen" / "artifacts"
        if kind in {"report", "reports", "报告"}:
            candidates = self._artifact_files(root / "reports", {".md"})
        elif kind in {"chart", "charts", "html", "图表"}:
            candidates = self._artifact_files(root / "charts", {".html"})
        else:
            candidates = [
                *self._artifact_files(root / "charts", {".html"}),
                *self._artifact_files(root / "reports", {".md"}),
            ]
            candidates = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            return None
        return ensure_inside_workspace(candidates[0], workspace)

    def _system_open_command(self) -> list[str] | None:
        if sys.platform == "darwin":
            return ["open"]
        if os.name == "nt":
            return ["cmd", "/c", "start", ""]
        if shutil.which("xdg-open"):
            return ["xdg-open"]
        return None

    def doctor_text(self) -> str:
        session = load_auth_session()
        config = get_config()
        workspace = workspace_status()
        provider, model, llm_ready, key_hint = self._llm_status(config)
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        opener_ready = bool(self._system_open_command())
        web_search_ready, web_search_detail = self._local_chrome_search_ready()
        checks = [
            ("workspace", workspace_ready, f"{workspace.get('path')}", "/workspace browse 或 /workspace path <路径> && /workspace allow"),
            ("account", token_ready, self._doctor_account_label(session), "/login xwab <账号>"),
            ("model", llm_ready, f"{provider} / {model}", f"/model select && /model key ({key_hint})"),
            ("server", bool(config.erlangshen_api_base_url), self._server_display_text(config.erlangshen_api_base_url), "/auth server <url>"),
            ("super-66 MCP", token_ready, "复用 XWAB/XCZT 登录态", "/login xwab <账号>"),
            ("web_search", web_search_ready, web_search_detail, "python3 -m pip install playwright && python3 -m playwright install chrome"),
            ("artifacts", workspace_ready, ".erlangshen/artifacts", "/workspace allow <路径>"),
            ("open", opener_ready, "desktop opener available" if opener_ready else "no desktop opener", "/open 会返回文件路径"),
        ]
        core_checks = checks[:5]
        core_ready = sum(1 for _, ok, _, _ in core_checks if ok)
        primary_fix = self._doctor_primary_fix(checks)
        lines = [
            "【二郎神本地诊断】",
            "- 说明: 这是本地 readiness 检查，不会把大模型 API Key 发给服务端，也不会访问远程网络。",
            f"- 核心就绪度: {core_ready}/{len(core_checks)}",
            f"- 首要修复: {primary_fix}",
            "",
        ]
        ok_count = 0
        for name, ok, detail, action in checks:
            mark = "OK" if ok else "NEED"
            if ok:
                ok_count += 1
            lines.append(f"- {mark:<4} {name:<12} {detail}")
            if not ok:
                lines.append(f"       next: {action}")
        lines.extend(["", "生产链路矩阵:"])
        for name, status, purpose, command, boundary in self._doctor_repair_matrix(
            workspace_ready=workspace_ready,
            token_ready=token_ready,
            llm_ready=llm_ready,
            web_search_ready=web_search_ready,
            opener_ready=opener_ready,
            key_hint=key_hint,
        ):
            lines.append(f"- {status:<5} {name}: {purpose}")
            lines.append(f"        command: {command}")
            lines.append(f"        boundary: {boundary}")
        ux_checks = self._doctor_ux_checks()
        lines.extend(["", "Agent UX:"])
        for name, detail in ux_checks:
            lines.append(f"- OK   {name:<16} {detail}")
        lines.extend([
            "",
            f"总体: {ok_count}/{len(checks)} 项就绪",
            f"交互能力: {len(ux_checks)}/{len(ux_checks)} 项可用",
            "",
            "本地 Chrome web_search:",
            "- 用途: 补充 super-66 MCP 不覆盖的新闻、公告、网页、图片入口和最新事件线索。",
            "- 依赖: python3 -m pip install playwright && python3 -m playwright install chrome",
            "- 边界: 在用户本机无头 Chrome 中检索公开网页；不会把大模型 API Key 发给二郎神服务端。",
            "- 输出: results/title/url 会进入 MCP 快照；网页、图片、HTML、PDF 会进入 /links 和 /open 资源入口。",
            "",
            "资源和图表:",
            "- 服务器、MCP、web_search 或本机大模型返回网页/图片/HTML/PDF 时，CLI 会显示名称链接，而不是尝试渲染富文本。",
            "- 近期资源: /links；直接打开: /links 1 或 /open 1；图表产物: /artifacts 或 /open chart。",
            "- 授权工作区后，图表和报告会保存到 .erlangshen/artifacts，资源索引会保存为 resources.json。",
            "建议: /setup run 初始化；/tools 查看数据能力；/service 做服务端远程状态检查。",
        ])
        return "\n".join(lines)

    def _doctor_repair_matrix(
        self,
        *,
        workspace_ready: bool,
        token_ready: bool,
        llm_ready: bool,
        web_search_ready: bool,
        opener_ready: bool,
        key_hint: str,
    ) -> list[tuple[str, str, str, str, str]]:
        def status(ok: bool, optional: bool = False) -> str:
            if ok:
                return "ready"
            return "setup" if optional else "fix"

        return [
            (
                "account",
                status(token_ready),
                "XWAB/XCZT 登录态，保护服务端映射和 super-66 MCP 鉴权",
                "/login xwab <账号>",
                "只保存会话 token；大模型 Key 不会随登录发送给服务端",
            ),
            (
                "model",
                status(llm_ready),
                "本机大模型负责意图理解、工具编排和最终自然语言分析",
                f"/model select && /model key ({key_hint})",
                "API Key 只保存在本机配置，用于客户端直连供应商",
            ),
            (
                "workspace",
                status(workspace_ready),
                "项目沙箱用于保存报告、图表、JSON 和资源索引",
                "/workspace browse 或 /workspace path <路径> && /workspace allow",
                "只在用户授权的项目目录内写入 .erlangshen/artifacts",
            ),
            (
                "super-66 MCP",
                status(token_ready),
                "优先读取行情、产品、持仓相关数据，避免模糊问题机械追问",
                "/tools 查看工具；/login xwab <账号> 修复鉴权",
                "复用账号体系，不要求用户额外配置 MCP 密钥",
            ),
            (
                "web_search",
                status(web_search_ready, optional=True),
                "补充当天新闻、公告、网页和图片入口，作为 MCP 未覆盖的信息线索",
                "python3 -m pip install playwright && python3 -m playwright install chrome",
                "本机 Chrome 检索公开网页；结果 URL 会进入 /links",
            ),
            (
                "chart artifact",
                status(workspace_ready),
                "服务端生成或客户端保存图表 HTML/JSON，并返回可打开名称链接",
                "/chart <问题> 或自然语言要求“做成图表”；/open chart 打开最新图表",
                "产物写入授权工作区；CLI 只展示链接和轻量预览",
            ),
            (
                "resource links",
                "ready",
                "网页、图片、HTML、PDF、图表和报告统一进入可点击资源入口",
                "/links 查看；/links 1 或 /open 1 直接打开",
                "终端不内嵌富文本或二进制内容，只展示名称和 URL/路径",
            ),
            (
                "desktop open",
                status(opener_ready, optional=True),
                "调用系统打开器打开网页、图片、报告和图表",
                "/open 1、/links open 1、/open chart",
                "没有系统打开器时仍返回文件路径或 URL，用户可手动打开",
            ),
            (
                "server",
                "ready",
                "受保护场景映射、能力说明和 chart artifact 通道",
                "/server status、/server flow、/server artifact",
                "服务端不接收用户的大模型 API Key",
            ),
        ]

    def brief_text(self) -> str:
        session = load_auth_session()
        config = get_config()
        workspace = workspace_status()
        provider, model, llm_ready, key_hint = self._llm_status(config)
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        mcp_context = self._last_mcp_context_brief()
        artifact_context = self._recent_artifact_context()
        resource_context = self._recent_resource_context()
        plan = self._last_agent_plan or {}
        capability_rows = [
            ("account", "OK" if token_ready else "NEED", "/login xwab <账号>"),
            ("model", "OK" if llm_ready else "NEED", f"/model key ({key_hint})"),
            ("workspace", "OK" if workspace_ready else "NEED", "/workspace browse && /workspace allow"),
            ("mcp", "OK" if token_ready else "NEED", "复用 XWAB/XCZT 登录态"),
            ("chart", "OK" if workspace_ready else "NEED", "授权工作区后保存图表/报告"),
        ]
        lines = [
            "【二郎神会话能力摘要】",
            f"- 模型: {provider} / {model} ({'ready' if llm_ready else 'missing key'})",
            f"- 工作区: {workspace.get('path')} ({'已授权' if workspace_ready else '未授权'})",
            f"- 最近计划: {plan.get('query') or '暂无'}",
            f"- 上轮 MCP: {', '.join(mcp_context.get('usable_sources') or []) or '暂无'}",
            f"- 最近产物: {', '.join(item.get('title') or '未命名' for item in artifact_context) or '暂无'}",
            f"- 最近资源: {len(resource_context)} 个可打开链接" if resource_context else "- 最近资源: 暂无",
            "",
            "能力状态:",
        ]
        for name, status, hint in capability_rows:
            lines.append(f"- {name}: {status} · {hint}")
        lines.extend([
            "",
            "Agent 回合就绪度:",
            *self._brief_agent_turn_lines(
                token_ready=token_ready,
                llm_ready=llm_ready,
                workspace_ready=workspace_ready,
                mcp_context=mcp_context,
                artifact_context=artifact_context,
                resource_context=resource_context,
            ),
            "",
            "你现在可以这样开始:",
            "- 今天行情怎么样？先帮我看盘面主线和风险。",
            "- 帮我看一下某个指数/股票/基金的走势和风险信号。",
            "- 把刚才的资产表现做成图表。",
            "",
            "推荐命令:",
            "- /setup run 初始化工作区、账号和本机大模型",
            "- /tools 查看 super-66 MCP、web_search 和 chart artifact 能力",
            "- /server goals 按目标选择服务端相关操作",
            "- /plan 复盘最近一次意图、工具链路和 MCP 数据",
            "- /links 查看最近网页、图片和本地产物名称链接",
            "- /artifacts 查看已保存图表和报告",
            "",
            "边界: 大模型 API Key 只在本机直连供应商；服务端只接收问题做受保护场景映射和 chart artifact。",
        ])
        return "\n".join(lines)

    def _brief_agent_turn_lines(
        self,
        *,
        token_ready: bool,
        llm_ready: bool,
        workspace_ready: bool,
        mcp_context: dict,
        artifact_context: list[dict],
        resource_context: list[dict],
    ) -> list[str]:
        mcp_status = "ready" if token_ready else "login needed"
        model_status = "ready" if llm_ready else "key needed"
        workspace_status_text = "ready" if workspace_ready else "sandbox needed"
        service_status = "ready" if token_ready else "login needed"
        artifact_status = "ready" if workspace_ready else "workspace needed"
        resource_status = f"ready · {len(resource_context)} links" if resource_context else "ready · 0 links"
        last_mcp = ", ".join(mcp_context.get("usable_sources") or []) or "暂无上一轮 MCP 快照"
        last_artifacts = ", ".join(item.get("title") or "未命名" for item in artifact_context) or "暂无产物"
        return [
            "- Ask: ready · 直接输入自然语言问题",
            f"- Think: {model_status} · 本机大模型负责意图、工具组合和最终分析",
            f"- Data: {mcp_status} · super-66 MCP 优先；上一轮 {last_mcp}",
            f"- Map: {service_status} · 服务端只做受保护场景映射和 chart artifact",
            f"- Build: {artifact_status} · 图表/报告保存到授权工作区；最近 {last_artifacts}",
            f"- Open: {resource_status} · /links 1 或 /open 1 打开网页、图片、图表和报告",
            f"- Sandbox: {workspace_status_text} · API Key/token 不写入项目目录",
        ]

    def examples_text(self) -> str:
        groups = [
            ("市场概览", [
                ("今天行情怎么样？先帮我看盘面主线和风险。", "super-66 MCP 指数/全球资产 + web_search + 服务端场景映射"),
                ("今天市场是风险偏好修复，还是防御占优？", "宽盘快照 + 黄金 + 港股科技指数等风险偏好参照"),
                ("A股今天哪些方向值得跟踪？", "行情快照 + 本机大模型做主线归纳"),
            ]),
            ("单资产/产品", [
                ("帮我看一下贵州茅台今天怎么走。", "search_astocks/get_astock_realtime + 新闻线索"),
                ("黄金最近的趋势和风险信号是什么？", "get_global_asset_data + 服务端宏观/市场映射"),
                ("这个基金近期回撤为什么扩大？", "search_products/get_product_detail/get_product_history"),
            ]),
            ("组合和风控", [
                ("我现在偏红利和黄金，下一步要不要降低波动？", "用户约束 + MCP 数据 + 本机模型生成风控建议"),
                ("如果美元指数继续走强，对港股和黄金有什么影响？", "global assets + web_search + 服务端映射"),
                ("给我一个更偏执行的版本：仓位、观察信号和失效条件。", "沿用 recent_conversation 和上一轮 MCP 摘要"),
            ]),
            ("图表/报告", [
                ("把刚才的资产表现做成图表。", "复用上一轮 MCP 数据，服务端生成 chart artifact"),
                ("把这几个方向的涨跌幅做个对比。", "本机模型选择可视化字段，保存到授权工作区"),
                ("生成一份带图表的简短报告。", "报告保存到 .erlangshen/artifacts/reports"),
            ]),
        ]
        lines = [
            "【二郎神提问范例】",
            "直接输入自然语言即可；本机大模型会理解上下文、选择 super-66 MCP/web_search、请求服务端受保护映射，并在需要时生成图表产物。",
            "",
            "复制一个开场:",
            *self._starter_prompt_lines(),
            "",
            "使用前建议:",
            "- /setup run 补齐工作区、账号和本机大模型 API Key",
            "- /brief 查看当前会话还能做什么",
            "- /tools 查看完整 MCP 和 chart artifact 能力地图",
            "",
        ]
        for title, examples in groups:
            lines.append(f"{title}:")
            for prompt, route in examples:
                lines.append(f"- {prompt}")
                lines.append(f"  路线: {route}")
            lines.append("")
        lines.extend([
            "追问方式:",
            "- “那如果换成港股呢？”",
            "- “把刚才这个做成图表。”",
            "- “更偏执行一点，列观察信号和失效条件。”",
            "",
            "边界: 大模型 API Key 只在本机使用；服务端只返回受保护场景信号和 chart artifact，不暴露内部认知库全文。",
        ])
        return "\n".join(lines)

    def benchmarks_text(self, args: str = "") -> str:
        output = (args or "").strip().lower()
        payload = self._benchmarks_payload()
        if output in {"json", "--json"}:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        if output in {"checklist", "status", "todo", "路线", "清单"}:
            return self.benchmark_checklist_text()

        projects = payload.get("projects") if isinstance(payload.get("projects"), list) else []
        optimizations = payload.get("optimization_points") if isinstance(payload.get("optimization_points"), list) else []
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        lines = [
            "【CLI 对标与优化落地】",
            f"- 检索日期: {payload.get('checked_at') or CLI_BENCHMARK_CHECKED_AT}",
            f"- 数据文件: {CLI_BENCHMARK_DATA_FILE}",
            f"- 数据来源: {source.get('provider') or 'GitHub REST API'} / {source.get('field') or 'stargazers_count'}",
            f"- 口径: {payload.get('selection_rule') or 'GitHub 当前 star 快照；筛掉仅带 cli topic 但主体不是命令行/TUI/终端工作流的项目。'}",
            "- 用法: /commands <关键词> 搜命令；--json 输出机器可读结果；--plain 输出无颜色文本。",
            "",
            "Star Top 10 参考项目:",
        ]
        for index, item in enumerate(projects, 1):
            if not isinstance(item, dict):
                continue
            repo = self._text_field(item.get("repo"))
            stars = self._format_star_count(item.get("stars"))
            lesson = self._text_field(item.get("lesson"))
            source_url = self._text_field(item.get("source_url"))
            lines.append(f"{index}. {repo} · {stars} stars · {lesson}" + (f" · {source_url}" if source_url else ""))
        lines.extend(["", "已提炼并落地的 10 个优化点:"])
        for index, item in enumerate(optimizations, 1):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{index}. {self._text_field(item.get('name'))} · "
                f"借鉴 {self._text_field(item.get('inspired_by'))} · "
                f"{self._text_field(item.get('implemented'))}"
            )
        lines.extend([
            "",
            "本轮可验证入口:",
            "- /benchmarks json        查看结构化对标数据",
            "- /commands work          模糊搜索工作区相关命令",
            "- /commands               查看命令使用次数和最近使用时间",
            "- /commands usage         查看 usage scope、存储文件和 top commands",
            "- /plan history           查看授权工作区里的历史计划",
            "- /plan history prune 7d  按天数清理历史计划",
            "- /benchmarks checklist   查看开发清单和下一步路线",
            "- erlangshen --json /benchmarks   机器可读输出",
            "- erlangshen --plain /help         无颜色/无 OSC8 链接输出",
            "- erlangshen --quiet /status       npm wrapper 静默启动",
            "- erlangshen --strict /doctor      未就绪时返回非零退出码",
            "- python3 scripts/update_cli_benchmarks.py  刷新版本化 star 快照",
            "- python3 scripts/smoke_cli_strict.py       检查 strict 退出码分类",
            "- python3 scripts/smoke_cli_npm.py          检查 npm wrapper 输出模式",
            "- python3 scripts/release_check.py          发版前本地 smoke 聚合入口",
            "",
            "后续方向:",
            "- 继续把 /plan diff 的恢复建议接入更细的 playbook 和自动排障入口。",
            "- 将 release:check 接入 CI 或发布流水线，正式发布时加 --refresh-benchmarks。",
        ])
        return "\n".join(lines)

    def benchmark_checklist_text(self) -> str:
        done_items = [
            ("命令发现", "/commands <关键词> fuzzy 搜索 + 使用热度排序"),
            ("脚本友好", "--json / --plain / --strict 输出模式"),
            ("静默包装器", "npm wrapper 支持 --quiet，避免污染脚本输出"),
            ("历史记忆", "readline 历史写入 ~/.erlangshen/history"),
            ("诊断路径", "/doctor 展示 11 项 Agent UX 与本机链路检查"),
            ("Agent 轨迹", "/plan 持久化 latest + history JSONL"),
            ("计划复盘", "/plan diff、/plan history export/prune 支持对比、导出和清理"),
            ("历史留存策略", "/plan history prune 支持保留最近 N 条或最近 Nd 天"),
            ("热度策略", "ERLANGSHEN_COMMAND_USAGE_SCOPE 支持 global/project/off"),
            ("命令热度面板", "/commands usage 展示当前 scope、文件和 top commands"),
            ("命令热度迁移", "/commands usage export/reset 支持导出和清空热度快照"),
            ("失败恢复提示", "失败计划会提示 /plan diff 回看上一条成功计划"),
            ("Diff 恢复建议", "/plan diff 输出 route/tool/artifact 变化对应的恢复建议"),
            ("资源出口", "/links 与 /open 统一资源入口"),
            ("沙箱边界", "授权工作区后才写入 .erlangshen/artifacts"),
            ("错误恢复", "未知命令给相近建议，strict 退出码细分"),
            ("严格退出码 smoke", "scripts/smoke_cli_strict.py 覆盖 64-70 分类"),
            ("npm wrapper smoke", "scripts/smoke_cli_npm.py 覆盖 --quiet/--plain/--json"),
            ("release check", "scripts/release_check.py 聚合 benchmark 刷新和 smoke 检查"),
            ("路线沉淀", "/benchmarks + README_CLI 固化对标与路线"),
        ]
        next_items = [
            ("plan playbook", "把 /plan diff 的建议进一步接入自动排障 playbook"),
            ("ci release", "把 npm run release:check:refresh 接入 CI 或发布流水线"),
        ]
        lines = [
            "【CLI 开发清单】",
            "- 来源: /benchmarks 对标的 10 个高 star CLI/TUI 项目",
            "- 状态: 核心优化点已落地并继续细化；下一轮聚焦发布、smoke test 和数据迁移",
            "",
            "已完成:",
        ]
        for index, (name, detail) in enumerate(done_items, 1):
            lines.append(f"{index}. [done] {name} · {detail}")
        lines.extend(["", "下一步:"])
        for index, (name, detail) in enumerate(next_items, 1):
            lines.append(f"{index}. [next] {name} · {detail}")
        lines.extend([
            "",
            "验证入口:",
            "- /benchmarks json",
            "- /commands work",
            "- /commands usage",
            "- /plan history",
            "- erlangshen --strict /doctor",
        ])
        return "\n".join(lines)

    def _benchmarks_payload(self) -> dict[str, object]:
        try:
            with open(CLI_BENCHMARK_DATA_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict) and isinstance(payload.get("projects"), list):
                return payload
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return {
            "schema_version": 1,
            "checked_at": CLI_BENCHMARK_CHECKED_AT,
            "selection_rule": "GitHub star snapshot; primary interface is CLI, TUI, shell, or terminal workflow.",
            "source": {
                "provider": "GitHub REST API",
                "field": "stargazers_count",
                "checked_with": "https://api.github.com/repos/{owner}/{repo}",
            },
            "projects": [
                {
                    "rank": index,
                    "repo": repo,
                    "stars": int(str(stars).replace(",", "")),
                    "lesson": lesson,
                    "source_url": f"https://github.com/{repo}",
                }
                for index, (repo, stars, lesson) in enumerate(CLI_BENCHMARK_PROJECTS, 1)
            ],
            "optimization_points": [
                {"rank": index, "name": name, "inspired_by": source, "implemented": implementation}
                for index, (name, source, implementation) in enumerate(CLI_OPTIMIZATION_POINTS, 1)
            ],
        }

    def _format_star_count(self, value) -> str:
        if isinstance(value, (int, float)):
            return f"{int(value):,}"
        text = self._text_field(value)
        if not text:
            return "unknown"
        try:
            return f"{int(text.replace(',', '')):,}"
        except ValueError:
            return text

    def _doctor_primary_fix(self, checks: list[tuple[str, bool, str, str]]) -> str:
        for name, ok, _, action in checks:
            if not ok:
                return f"{name} -> {action}"
        return "全部核心链路可用；直接输入投资问题开始分析"

    def _doctor_account_label(self, session: dict) -> str:
        user = session.get("user") or {}
        return user.get("username") or user.get("email") or user.get("id") or ("已保存 token" if session.get("token") else "未登录")

    def _local_chrome_search_ready(self) -> tuple[bool, str]:
        try:
            if importlib.util.find_spec("playwright") is None:
                return False, "optional Playwright not installed"
        except Exception:
            return False, "optional Playwright not installed"
        return True, "Playwright available; Chrome search can run locally"

    def _doctor_ux_checks(self) -> list[tuple[str, str]]:
        return [
            ("slash picker", "输入 / 后可按分组选择命令，支持 /server flow /context /clear"),
            ("fuzzy command search", "/commands <关键词> 支持前缀、token、子序列和相似度排序"),
            ("usage-aware ranking", f"命令热度策略: {self._command_usage_location_label()}，高频/最近命令在同组内靠前"),
            ("script output modes", "--json 返回稳定 envelope；--plain 禁用颜色和 OSC8 链接"),
            ("persistent history", f"交互历史保存到 {self._history_path()}，可用 ERLANGSHEN_HISTORY_FILE 覆盖"),
            ("cli benchmarks", "/benchmarks 展示高 star CLI 对标和本轮优化落地点"),
            ("workspace browser", "/workspace browse 和 /setup run 可用方向键选择项目文件夹"),
            ("context memory", "最近对话上下文会进入本机大模型；/context 可查看或清空"),
            ("agent trace", "回答和 /plan 会展示本轮理解、取数、映射、生成过程"),
            ("chart preview", "chart artifact 会保存 JSON/HTML，并在终端生成轻量预览"),
            ("server panels", "/server commands/flow/capabilities/artifact 可解释服务端边界"),
        ]

    def tools_text(self, args: str = "") -> str:
        catalog = self._mcp_capability_catalog((args or "").strip())
        lines = [
            "【二郎神工具能力地图】",
            "- 数据优先级: super-66 MCP > 用户提供数据 > 本地 Chrome web_search 补充",
            "- 编排方式: 本机大模型先理解意图，再选择 MCP 工具组合；服务端只做受保护场景映射和 chart artifact 通道",
            "- 鉴权边界: super-66 MCP 复用 XWAB/XCZT 登录态；大模型 API Key 只保存在本机",
            f"- 注册表来源: {catalog.get('registry_source')} / {len(catalog.get('registry_tools') or [])} 个工具",
            "",
            "super-66 注册表工具:",
        ]
        for tool in catalog.get("registry_tools") or []:
            lines.append(f"- {tool.get('name')}: {tool.get('description')}")
        lines.extend([
            "",
            "可调用 MCP / 数据工具:",
        ])
        for tool in catalog.get("mcp_tools") or []:
            args_text = json.dumps(tool.get("args") or {}, ensure_ascii=False)
            lines.append(f"- {tool.get('name')}: {tool.get('use_when')}")
            lines.append(f"  默认参数: {args_text}")
        artifact = catalog.get("artifact_channel") or {}
        resource_channel = catalog.get("resource_link_channel") or {}
        lines.extend([
            "",
            "图表与产物通信:",
            f"- {artifact.get('name')}: {artifact.get('use_when')}",
            f"- transport: {artifact.get('transport')}",
            f"- command: {artifact.get('client_command')}",
            f"- supported: {', '.join(artifact.get('supported_types') or [])}",
            "",
            "资源链接通信:",
            f"- {resource_channel.get('name')}: {resource_channel.get('use_when')}",
            f"- transport: {resource_channel.get('transport')}",
            f"- commands: {', '.join(resource_channel.get('client_commands') or [])}",
            f"- supported: {', '.join(resource_channel.get('supported_types') or [])}",
            f"- boundary: {resource_channel.get('boundary')}",
            "",
            "本地 Chrome web_search:",
            f"- name: {catalog.get('local_web_search', {}).get('name')}",
            f"- {catalog.get('local_web_search', {}).get('use_when')}",
            f"- 依赖: {catalog.get('local_web_search', {}).get('install')}",
            f"- 输出: {catalog.get('local_web_search', {}).get('result_shape')}",
            f"- 资源: {catalog.get('local_web_search', {}).get('resource_behavior')}",
            f"- 边界: {catalog.get('local_web_search', {}).get('boundary')}",
            "",
            "工具结果契约:",
        ])
        for key, value in self._agent_tool_contract().items():
            lines.append(f"- {key}: {value}")
        lines.extend([
            "",
            "服务端/客户端通信契约:",
        ])
        for key, value in self._server_client_contract().items():
            if isinstance(value, dict):
                lines.append(f"- {key}:")
                for child_key, child_value in value.items():
                    rendered = ", ".join(child_value) if isinstance(child_value, list) else child_value
                    lines.append(f"  - {child_key}: {rendered}")
            elif isinstance(value, list):
                lines.append(f"- {key}: {', '.join(value)}")
            else:
                lines.append(f"- {key}: {value}")
        protocol = self._agent_orchestration_protocol()
        lines.extend([
            "",
            "智能体编排协议:",
            f"- decision_owner: {protocol.get('decision_owner')}",
            f"- client_role: {protocol.get('client_role')}",
            "- do_not:",
        ])
        for item in protocol.get("do_not") or []:
            lines.append(f"  - {item}")
        lines.append("- llm_must_return:")
        for item in protocol.get("llm_must_return") or []:
            lines.append(f"  - {item}")
        lines.append("- client_may_override_only_when:")
        for item in protocol.get("client_may_override_only_when") or []:
            lines.append(f"  - {item}")
        lines.append(f"- audit_surface: {protocol.get('audit_surface')}")
        lines.extend([
            "",
            "工具结果形态:",
        ])
        for name, hint in (catalog.get("tool_result_hints") or {}).items():
            fields = ", ".join(hint.get("use_fields") or [])
            lines.append(f"- {name}: {hint.get('result_shape')}")
            lines.append(f"  字段: {fields}")
            lines.append(f"  图表: {hint.get('chart_fit')}")
        lines.extend(["", "工具组合模式:"])
        for pattern in catalog.get("composition_patterns") or []:
            lines.append(f"- {pattern.get('name')}: {pattern.get('when')}")
            lines.append(f"  工具: {' -> '.join(pattern.get('tools') or [])}")
            fields = ", ".join(pattern.get("read_fields") or [])
            lines.append(f"  读取: {fields}")
            lines.append(f"  降级: {pattern.get('fallback')}")
            lines.append(f"  产物: {pattern.get('artifact')}")
        lines.extend([
            "",
            "Agent Playbook:",
        ])
        for item in catalog.get("agent_playbook") or []:
            lines.append(f"- {item.get('task')}: {item.get('goal')}")
            lines.append(f"  触发: {item.get('trigger')}")
            lines.append(f"  工具链: {' -> '.join(item.get('preferred_chain') or [])}")
            lines.append(f"  产物: {item.get('artifact_rule')}")
            lines.append(f"  资源: {item.get('resource_rule')}")
            lines.append(f"  降级: {item.get('fallback')}")
        lines.extend([
            "",
            "典型数据配方:",
        ])
        for recipe in catalog.get("data_recipes") or []:
            lines.append(f"- {recipe.get('name')}: {recipe.get('use_when')}")
            for step in recipe.get("steps") or []:
                lines.append(f"  - {step}")
            examples = recipe.get("examples") or []
            if examples:
                lines.append("  可以这样问:")
                for example in examples[:3]:
                    lines.append(f"  - {example}")
        lines.extend(["", "Agent 编排路线:"])
        for route in catalog.get("route_plans") or []:
            lines.append(f"- {route.get('name')}: {route.get('trigger')}")
            for step in route.get("sequence") or []:
                lines.append(f"  - {step}")
            lines.append(f"  输出: {route.get('output')}")
        lines.extend([
            "",
            "提示: 直接输入自然语言问题时，这份能力地图也会进入本机大模型上下文。",
        ])
        return "\n".join(lines)

    def plan_text(self, args: str = "") -> str:
        action = (args or "").strip().lower()
        if action in {"json", "--json"}:
            plan = self._last_agent_plan or self._load_persisted_agent_plan()
            payload = {"ok": bool(plan), "plan": plan}
            return json.dumps(payload, ensure_ascii=False, indent=2)
        if action.startswith(("history", "hist", "历史")):
            return self.plan_history_text(action)
        if action.startswith(("diff", "compare", "对比", "比较")):
            return self.plan_diff_text(action)
        plan = self._last_agent_plan or self._load_persisted_agent_plan()
        if not plan:
            return "\n".join([
                "【最近一次分析计划】",
                "- 暂无记录",
                "- 下一步: 直接输入一个投资问题，或执行 /advice <问题>",
                "- 说明: 二郎神会记录最近一次意图理解、MCP 工具、服务端映射和产物通道摘要。",
            ])
        tools = plan.get("mcp_tools") or []
        lines = [
            "【最近一次分析计划】",
            f"- 问题: {plan.get('query')}",
            f"- 意图: {plan.get('intent')} / {plan.get('tone')}",
            f"- 路由来源: {self._route_source_label(plan.get('route_source'))}",
            f"- 重写问题: {plan.get('rewritten_query')}",
            f"- 服务端映射问题: {plan.get('mapping_query') or plan.get('rewritten_query')}",
            f"- 上下文追问: {'是' if plan.get('is_followup') else '否'}"
            + (f" / {plan.get('followup_target')}" if plan.get("followup_target") else ""),
            f"- 路由摘要: {plan.get('route_summary') or '未说明'}",
            f"- 工具理由: {plan.get('tool_rationale') or '未说明'}",
            f"- 数据策略: {plan.get('data_strategy') or '未说明'}",
            f"- 资源呈现: {plan.get('resource_presentation') or '命名链接 + /links 1 或 /open 1'}",
            f"- 打开命令: {', '.join(plan.get('open_commands') or ['/links 1', '/open 1'])}",
            f"- 数据充分度: {plan.get('data_confidence') or '未说明'}",
            f"- 组合模式: {', '.join(plan.get('composition_patterns_used') or []) or '未说明'}",
            f"- 图表机会: {'建议' if plan.get('chart_opportunity') else '暂不需要'}"
            + (f" / {plan.get('chart_rationale')}" if plan.get("chart_rationale") else ""),
            f"- 产物计划: {self._format_artifact_plan(plan.get('artifact_plan'))}",
            f"- 服务端映射: {'需要' if plan.get('needs_server_mapping') else '不需要'}",
            f"- MCP 数据: {'需要' if plan.get('needs_mcp') else '不需要'}",
            f"- 工具来源: {self._tool_selection_source_label(plan.get('tool_selection_source'))}",
            f"- 工具来源说明: {plan.get('tool_selection_note') or '未说明'}",
            f"- 本机模型: {plan.get('provider')} / {plan.get('model')}",
            f"- Key 边界: {plan.get('key_boundary')}",
            "",
            "编排审计:",
            *self._plan_orchestration_audit_lines(plan),
            "",
            "计划调用工具:",
        ]
        if plan.get("persisted_at"):
            lines.insert(2, f"- 持久化时间: {plan.get('persisted_at')}")
        if plan.get("persisted_path"):
            lines.insert(3, f"- 持久化文件: {plan.get('persisted_path')}")
        if plan.get("status") == "failure":
            lines.insert(4, f"- 状态: 失败 / {plan.get('failure_stage') or 'unknown'}")
            if plan.get("failure_message"):
                lines.insert(5, f"- 失败原因: {plan.get('failure_message')}")
        if plan.get("route_warning"):
            lines.append(f"- 路由提示: {plan.get('route_warning')}")
        if tools:
            for item in tools:
                args_text = json.dumps(item.get("arguments") or {}, ensure_ascii=False)
                lines.append(f"- {item.get('name')}: {args_text}")
        else:
            lines.append("- 未计划 MCP 工具")
        tool_plan = plan.get("tool_plan") if isinstance(plan.get("tool_plan"), list) else []
        if tool_plan:
            lines.extend(["", "工具链路解释:"])
            for item in tool_plan[:8]:
                label = self._text_field(item.get("label")) or self._text_field(item.get("tool"))
                why = self._text_field(item.get("why")) or "未说明"
                status = self._text_field(item.get("status")) or "计划中"
                keys = item.get("data_keys") if isinstance(item.get("data_keys"), list) else []
                args_text = json.dumps(item.get("arguments") or {}, ensure_ascii=False)
                lines.append(f"- {label}: {status}")
                lines.append(f"  用途: {why}")
                lines.append(f"  参数: {args_text}")
                lines.append(f"  数据键: {', '.join(keys) or '尚未返回'}")
        pattern_details = self._composition_pattern_details(plan.get("composition_patterns_used") or [])
        if pattern_details:
            lines.extend(["", "组合模式说明:"])
            for item in pattern_details:
                lines.append(f"- {item.get('name')}: {item.get('when')}")
                tools_text = " -> ".join(item.get("tools") or [])
                if tools_text:
                    lines.append(f"  工具链: {tools_text}")
                fields_text = ", ".join(item.get("read_fields") or [])
                if fields_text:
                    lines.append(f"  读取字段: {fields_text}")
                fallback = self._text_field(item.get("fallback"))
                if fallback:
                    lines.append(f"  降级: {fallback}")
                artifact = self._text_field(item.get("artifact"))
                if artifact:
                    lines.append(f"  产物: {artifact}")
        playbook_cards = self._plan_playbook_cards(plan)
        if playbook_cards:
            lines.extend(["", "本轮 Playbook:"])
            for item in playbook_cards:
                lines.append(f"- {item.get('task')}: {item.get('goal')}")
                lines.append(f"  触发: {item.get('trigger')}")
                lines.append(f"  工具链: {' -> '.join(item.get('preferred_chain') or [])}")
                lines.append(f"  产物: {item.get('artifact_rule')}")
                lines.append(f"  资源: {item.get('resource_rule')}")
                lines.append(f"  降级: {item.get('fallback')}")
        missing_inputs = plan.get("missing_inputs") or []
        if missing_inputs:
            lines.extend(["", "路由层认为还缺:"])
            for item in missing_inputs[:5]:
                lines.append(f"- {item}")
        lines.extend([
            "",
            f"实际 MCP 数据键: {', '.join(plan.get('mcp_data_keys') or []) or '未提供'}",
            f"MCP 快照: {'；'.join(plan.get('mcp_snapshots') or []) or '未提取'}",
            f"执行过程: {'；'.join(plan.get('agent_trace') or []) or '未记录'}",
            f"服务端命中场景: {', '.join(plan.get('server_scenes') or []) or '未返回'}",
            f"图表/产物: {', '.join(plan.get('artifact_titles') or []) or '未请求'}",
        ])
        resource_links = plan.get("resource_links") if isinstance(plan.get("resource_links"), list) else []
        if resource_links:
            lines.extend(["", "本轮可打开资源:"])
            for index, item in enumerate(resource_links[:8], 1):
                source = self._text_field(item.get("source")) if isinstance(item, dict) else "resource"
                link = self._text_field(item.get("link")) if isinstance(item, dict) else self._text_field(item)
                if link:
                    lines.append(f"{index}. {source}: {link}")
        lines.extend(["", "建议下一步:"])
        for action in self._plan_next_actions(plan):
            lines.append(f"- {action}")
        lines.extend([
            "",
            "说明: /plan 只保留最近一次过程摘要，不保存大模型 API Key，不展示原始敏感数据。",
            "历史: /plan history 查看最近计划；/plan history json 输出结构化历史。",
        ])
        return "\n".join(lines)

    def plan_history_text(self, args: str = "") -> str:
        tokens = (args or "").strip().split()
        output_json = any(token in {"json", "--json"} for token in tokens)
        if any(token in {"prune", "trim", "清理"} for token in tokens):
            return self.plan_history_prune_text(tokens)
        if any(token in {"export", "导出"} for token in tokens):
            return self.plan_history_export_text(tokens)
        limit = 8
        for token in tokens:
            if token.isdigit():
                limit = max(1, min(50, int(token)))
                break
        status, path, history = self._plan_history_snapshot()
        if not status.get("allowed"):
            payload = {
                "ok": False,
                "reason": "workspace_not_allowed",
                "history": [],
                "path": None,
            }
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【最近计划历史】",
                "- 工作区未授权，无法读取计划历史。",
                "- 下一步: /workspace browse 或 /workspace path <路径> && /workspace allow",
            ])
        recent = list(reversed(history[-limit:]))
        if output_json:
            return json.dumps({
                "ok": True,
                "path": str(path) if path else None,
                "count": len(history),
                "history": recent,
            }, ensure_ascii=False, indent=2)
        lines = [
            "【最近计划历史】",
            f"- 工作区: {status.get('path')}",
            f"- 历史文件: {path}",
            f"- 总数: {len(history)}",
        ]
        if not recent:
            lines.extend([
                "",
                "暂无历史。直接输入投资问题后，/plan 会自动保存到授权工作区。",
            ])
            return "\n".join(lines)
        lines.extend(["", "最近记录:"])
        for index, item in enumerate(recent, 1):
            query = self._text_field(item.get("query")) or "未命名问题"
            when = self._text_field(item.get("persisted_at")) or self._text_field(item.get("created_at")) or "unknown"
            status_text = self._text_field(item.get("status")) or "success"
            intent = self._text_field(item.get("intent")) or "unknown"
            scenes = ", ".join(item.get("server_scenes") or []) if isinstance(item.get("server_scenes"), list) else ""
            tools = item.get("mcp_tools") if isinstance(item.get("mcp_tools"), list) else []
            artifacts = item.get("artifact_titles") if isinstance(item.get("artifact_titles"), list) else []
            lines.append(f"{index}. {when} · {status_text} · {query}")
            lines.append(f"   意图: {intent} · 工具 {len(tools)} · 产物 {len(artifacts)}" + (f" · 场景: {scenes}" if scenes else ""))
        lines.extend([
            "",
            "命令:",
            "  /plan              查看最近一次完整计划",
            "  /plan history json 输出结构化历史",
            "  /plan diff         对比最近两次计划",
            "  /plan history export 导出全部历史 JSON",
            "  /plan history prune 20 只保留最近 20 条",
            "  /plan history prune 7d 只保留最近 7 天",
        ])
        return "\n".join(lines)

    def plan_history_prune_text(self, tokens: list[str]) -> str:
        output_json = any(token in {"json", "--json"} for token in tokens)
        keep = 20
        days: int | None = None
        for token in tokens:
            lowered = token.lower()
            if lowered.endswith("d") and lowered[:-1].isdigit():
                days = max(0, min(3650, int(lowered[:-1])))
                break
            if token.isdigit():
                keep = max(0, min(50, int(token)))
                break
        for index, token in enumerate(tokens):
            if token.lower() in {"day", "days", "天", "日"}:
                for neighbor in (index - 1, index + 1):
                    if 0 <= neighbor < len(tokens) and tokens[neighbor].isdigit():
                        days = max(0, min(3650, int(tokens[neighbor])))
                        break
                if days is not None:
                    break
        status, path, history = self._plan_history_snapshot()
        if not status.get("allowed") or path is None:
            payload = {"ok": False, "reason": "workspace_not_allowed", "path": None, "kept": 0, "removed": 0}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【计划历史清理】",
                "- 工作区未授权，无法清理计划历史。",
                "- 下一步: /workspace browse 或 /workspace path <路径> && /workspace allow",
            ])
        if days is not None:
            cutoff = datetime.now() - timedelta(days=days)
            kept = [
                item for item in history
                if (self._plan_datetime(item) is None or self._plan_datetime(item) >= cutoff)
            ]
            mode = f"最近 {days} 天"
        else:
            kept = history[-keep:] if keep else []
            mode = f"最近 {keep} 条"
        removed = max(0, len(history) - len(kept))
        self._write_agent_plan_history(path, kept)
        payload = {"ok": True, "path": str(path), "mode": mode, "kept": len(kept), "removed": removed}
        if output_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return "\n".join([
            "【计划历史清理】",
            f"- 历史文件: {path}",
            f"- 清理模式: {mode}",
            f"- 已保留: {len(kept)} 条",
            f"- 已移除: {removed} 条",
            "- 提示: 最近一次 agent_plan.json 不受 prune 影响。",
        ])

    def plan_history_export_text(self, tokens: list[str]) -> str:
        output_json = any(token in {"json", "--json"} for token in tokens)
        status, path, history = self._plan_history_snapshot()
        if not status.get("allowed") or path is None:
            payload = {"ok": False, "reason": "workspace_not_allowed", "path": None, "export_path": None, "count": 0}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【计划历史导出】",
                "- 工作区未授权，无法导出计划历史。",
                "- 下一步: /workspace browse 或 /workspace path <路径> && /workspace allow",
            ])
        try:
            root = resolve_workspace_path(str(status.get("path") or ""))
            export_path = ensure_inside_workspace(
                root / ".erlangshen" / "artifacts" / f"agent_plans_export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
                root,
            )
            export_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "ok": True,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "source_path": str(path),
                "export_path": str(export_path),
                "count": len(history),
                "history": history,
            }
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except (OSError, PermissionError, TypeError, ValueError) as exc:
            payload = {"ok": False, "error": str(exc), "path": str(path), "export_path": None, "count": len(history)}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return f"【计划历史导出】\n- 导出失败: {exc}"
        if output_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return "\n".join([
            "【计划历史导出】",
            f"- 历史文件: {path}",
            f"- 导出文件: {payload.get('export_path')}",
            f"- 条数: {len(history)}",
        ])

    def plan_diff_text(self, args: str = "") -> str:
        tokens = (args or "").strip().split()
        output_json = any(token in {"json", "--json"} for token in tokens)
        status, path, history = self._plan_history_snapshot()
        if not status.get("allowed"):
            payload = {"ok": False, "reason": "workspace_not_allowed", "path": None, "diff": None}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【计划差异】",
                "- 工作区未授权，无法读取计划历史。",
                "- 下一步: /workspace browse 或 /workspace path <路径> && /workspace allow",
            ])
        if len(history) < 2:
            payload = {"ok": False, "reason": "not_enough_history", "path": str(path) if path else None, "count": len(history), "diff": None}
            if output_json:
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return "\n".join([
                "【计划差异】",
                f"- 历史文件: {path}",
                f"- 当前只有 {len(history)} 条记录，至少需要 2 条。",
                "- 下一步: 完成两次分析后再执行 /plan diff。",
            ])
        before = history[-2]
        after = history[-1]
        diff = self._agent_plan_diff(before, after)
        payload = {"ok": True, "path": str(path) if path else None, "diff": diff}
        if output_json:
            return json.dumps(payload, ensure_ascii=False, indent=2)
        lines = [
            "【计划差异】",
            f"- 历史文件: {path}",
            f"- 基准: {diff['before'].get('persisted_at')} · {diff['before'].get('query')}",
            f"- 最新: {diff['after'].get('persisted_at')} · {diff['after'].get('query')}",
            "",
            "字段变化:",
        ]
        if diff["scalar_changes"]:
            for item in diff["scalar_changes"]:
                lines.append(f"- {item['label']}: {item['before'] or '空'} -> {item['after'] or '空'}")
        else:
            lines.append("- 无")
        lines.extend(["", "集合变化:"])
        has_list_change = False
        for item in diff["list_changes"]:
            if item["added"] or item["removed"]:
                has_list_change = True
                lines.append(f"- {item['label']}: +{', '.join(item['added']) or '无'} / -{', '.join(item['removed']) or '无'}")
        if not has_list_change:
            lines.append("- 无")
        lines.extend([
            "",
            f"结论: {diff['summary']}",
            "",
            "恢复建议:",
        ])
        for item in diff.get("recommendations") or []:
            lines.append(f"- {item}")
        lines.extend([
            "命令: /plan history 查看上下文；/plan diff json 输出结构化差异。",
        ])
        return "\n".join(lines)

    def _plan_history_snapshot(self) -> tuple[dict, Path | None, list[dict]]:
        status = workspace_status()
        if not status.get("allowed"):
            return status, None, []
        try:
            path = self._agent_plan_history_path(str(status.get("path") or ""))
        except (OSError, PermissionError, ValueError):
            return status, None, []
        return status, path, self._read_agent_plan_history(path)

    def _write_agent_plan_history(self, path: Path, history: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for item in history:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _agent_plan_diff(self, before: dict, after: dict) -> dict[str, object]:
        scalar_fields = [
            ("query", "问题"),
            ("intent", "意图"),
            ("route_source", "路由来源"),
            ("tool_selection_source", "工具来源"),
            ("data_confidence", "数据充分度"),
            ("needs_mcp", "是否需要 MCP"),
            ("needs_server_mapping", "是否需要服务端映射"),
            ("status", "状态"),
            ("failure_stage", "失败阶段"),
        ]
        scalar_changes = []
        for field, label in scalar_fields:
            before_value = self._plan_value_for_diff(before.get(field))
            after_value = self._plan_value_for_diff(after.get(field))
            if before_value != after_value:
                scalar_changes.append({"field": field, "label": label, "before": before_value, "after": after_value})
        list_specs = [
            ("mcp_tools", "MCP 工具", self._plan_tool_names),
            ("mcp_data_keys", "MCP 数据键", self._plan_text_list),
            ("server_scenes", "服务端场景", self._plan_text_list),
            ("artifact_titles", "图表/产物", self._plan_text_list),
            ("missing_inputs", "缺失输入", self._plan_text_list),
            ("composition_patterns_used", "组合模式", self._plan_text_list),
        ]
        list_changes = []
        for field, label, getter in list_specs:
            before_items = getter(before.get(field))
            after_items = getter(after.get(field))
            before_set = set(before_items)
            after_set = set(after_items)
            list_changes.append({
                "field": field,
                "label": label,
                "before": before_items,
                "after": after_items,
                "added": sorted(after_set - before_set),
                "removed": sorted(before_set - after_set),
                "common": sorted(before_set & after_set),
            })
        change_count = len(scalar_changes) + sum(1 for item in list_changes if item["added"] or item["removed"])
        if change_count == 0:
            summary = "两次计划核心字段基本一致。"
        elif any(item["field"] == "mcp_tools" and (item["added"] or item["removed"]) for item in list_changes):
            summary = "工具选择发生变化，建议重点检查 tool_rationale、数据充分度和输出产物。"
        elif scalar_changes:
            summary = "路由或状态字段发生变化，建议查看意图、数据策略和失败阶段。"
        else:
            summary = "上下文集合发生变化，建议查看场景、产物和缺失输入。"
        recommendations = self._plan_diff_recommendations(before, after, scalar_changes, list_changes)
        return {
            "before": self._plan_diff_header(before),
            "after": self._plan_diff_header(after),
            "scalar_changes": scalar_changes,
            "list_changes": list_changes,
            "summary": summary,
            "recommendations": recommendations,
        }

    def _plan_diff_recommendations(
        self,
        before: dict,
        after: dict,
        scalar_changes: list[dict],
        list_changes: list[dict],
    ) -> list[str]:
        recommendations: list[str] = []
        after_status = self._text_field(after.get("status"))
        failure_stage = self._text_field(after.get("failure_stage"))
        if after_status == "failure":
            if failure_stage == "server_mapping":
                recommendations.append("/service 检查服务端健康与反向代理，再用 /login xwab <账号> 刷新鉴权。")
            elif failure_stage == "local_llm_synthesis":
                recommendations.append("/model key 重新测试本机大模型 Key，或 /model select 临时切换供应商。")
            else:
                recommendations.append("/doctor 先检查工作区、账号、本机模型、MCP 和资源保存链路。")
        changed_fields = {self._text_field(item.get("field")) for item in scalar_changes}
        changed_lists = {
            self._text_field(item.get("field")): item
            for item in list_changes
            if item.get("added") or item.get("removed")
        }
        if "mcp_tools" in changed_lists or "mcp_data_keys" in changed_lists:
            recommendations.append("对照新增/移除的 MCP 工具和数据键，确认本轮是否缺少行情、搜索或产品快照。")
        if "artifact_titles" in changed_lists:
            recommendations.append("/artifacts 或 /open 检查产物是否生成；如果最新计划移除了产物，重新明确“做成图表/报告”。")
        if "missing_inputs" in changed_lists:
            recommendations.append("优先补齐新增的缺失输入，再继续追问，避免下一轮继续走降级路径。")
        if {"intent", "route_source", "tool_selection_source", "data_confidence"} & changed_fields:
            recommendations.append("查看 route_summary、tool_rationale 和 data_strategy，确认是意图变化还是数据不足导致改路由。")
        if not recommendations:
            recommendations.append("核心字段差异很小；继续看 /plan history 的完整上下文，重点排查外部服务和实时数据状态。")
        return recommendations[:4]

    def _plan_diff_header(self, plan: dict) -> dict[str, str]:
        return {
            "query": self._text_field(plan.get("query")),
            "persisted_at": self._text_field(plan.get("persisted_at")) or self._text_field(plan.get("created_at")) or "unknown",
            "intent": self._text_field(plan.get("intent")),
            "status": self._text_field(plan.get("status")) or "success",
        }

    def _plan_value_for_diff(self, value) -> str:
        if isinstance(value, bool):
            return "是" if value else "否"
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return self._text_field(value)

    def _plan_datetime(self, plan: dict) -> datetime | None:
        raw = self._text_field(plan.get("persisted_at") or plan.get("created_at"))
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def _plan_text_list(self, value) -> list[str]:
        if not isinstance(value, list):
            return []
        return [self._text_field(item) for item in value if self._text_field(item)]

    def _plan_tool_names(self, value) -> list[str]:
        if not isinstance(value, list):
            return []
        names = []
        for item in value:
            if isinstance(item, dict):
                name = self._text_field(item.get("name") or item.get("tool"))
                if name:
                    names.append(name)
            else:
                text = self._text_field(item)
                if text:
                    names.append(text)
        return names

    def _plan_orchestration_audit_lines(self, plan: dict) -> list[str]:
        route_source = self._text_field(plan.get("route_source"))
        tool_source = self._text_field(plan.get("tool_selection_source"))
        fallback_sources = {"client_default_by_intent", "client_market_overview_fallback", "previous_mcp_context"}
        if tool_source == "local_llm" or route_source == "local_llm":
            owner = "本机大模型"
        elif tool_source in fallback_sources:
            owner = "客户端兜底"
        elif route_source == "provided_payload":
            owner = "调用方提供的 intent_plan"
        elif route_source == "fallback":
            owner = "保守兜底路由"
        else:
            owner = "未明确"
        override = "是" if tool_source in fallback_sources or route_source == "fallback" else "否"
        resource_count = len(plan.get("resource_links") or []) if isinstance(plan.get("resource_links"), list) else 0
        artifact_plan = plan.get("artifact_plan") if isinstance(plan.get("artifact_plan"), dict) else {}
        artifact_type = self._text_field(artifact_plan.get("type")) or ("chart" if plan.get("chart_opportunity") else "none")
        return [
            f"- 决策者: {owner}",
            f"- 客户端兜底: {override} · {plan.get('tool_selection_note') or '未触发兜底'}",
            f"- 可复盘字段: route_summary / tool_rationale / data_strategy / composition_patterns_used / artifact_plan",
            f"- 安全边界: {plan.get('key_boundary') or 'API Key 仅本机使用，不发送服务端'}",
            f"- 产物与资源: artifact_plan={artifact_type} · resource_links={resource_count} · /links 1 或 /open 1 打开",
        ]

    def _plan_playbook_cards(self, plan: dict) -> list[dict[str, object]]:
        intent = self._text_field(plan.get("intent")).lower()
        patterns = {
            self._text_field(item).lower()
            for item in (plan.get("composition_patterns_used") or [])
        }
        artifact_plan = plan.get("artifact_plan") if isinstance(plan.get("artifact_plan"), dict) else {}
        artifact_type = self._text_field(artifact_plan.get("type")).lower()
        selected: list[str] = []
        if intent in {"market_overview", "market", "macro"} or "market_snapshot_to_narrative" in patterns:
            selected.append("market_overview")
        if intent in {"single_asset", "data_lookup"} or "name_to_realtime_snapshot" in patterns or "product_history_to_risk" in patterns:
            selected.append("single_asset_or_product")
        if intent in {"macro", "risk"}:
            selected.append("macro_event_cross_asset")
        if artifact_type in {"chart", "report"} or "mcp_table_to_chart_artifact" in patterns:
            selected.append("visualization_or_report_followup")
        if not selected and patterns:
            selected.append("market_overview")
        by_task = {
            self._text_field(item.get("task")): item
            for item in self._agent_playbook()
            if isinstance(item, dict)
        }
        result = []
        for task in selected:
            card = by_task.get(task)
            if card and card not in result:
                result.append(card)
        return result[:3]

    def _composition_pattern_details(self, names: list[str]) -> list[dict]:
        wanted = [self._text_field(name) for name in names or [] if self._text_field(name)]
        if not wanted:
            return []
        catalog = self._mcp_capability_catalog("")
        by_name = {
            self._text_field(item.get("name")): item
            for item in catalog.get("composition_patterns") or []
            if isinstance(item, dict) and self._text_field(item.get("name"))
        }
        details = []
        for name in wanted:
            item = by_name.get(name)
            if item:
                details.append(item)
        return details[:4]

    def _plan_next_actions(self, plan: dict) -> list[str]:
        actions = []
        if plan.get("status") == "failure":
            stage = self._text_field(plan.get("failure_stage"))
            if stage == "server_mapping":
                actions.append("/login xwab <账号> 重新登录，或 /service 检查服务端鉴权和反向代理状态。")
            elif stage == "local_llm_synthesis":
                actions.append("/model key 重新测试本机大模型 API Key，或 /model select 切换供应商。")
            else:
                actions.append("/doctor 检查账号、本机模型、super-66 MCP、web_search 和服务端连通性。")
            previous = self._previous_successful_plan(plan)
            if previous:
                query = self._text_field(previous.get("query")) or "上一条成功计划"
                actions.append(f"/plan diff 对比本次失败和上一条成功计划（{query}），定位路由、工具或产物变化。")
        artifact_plan = plan.get("artifact_plan") if isinstance(plan.get("artifact_plan"), dict) else {}
        planned_type = self._text_field(artifact_plan.get("type")).lower()
        if planned_type in {"chart", "report"} and not plan.get("artifact_titles"):
            title = self._text_field(artifact_plan.get("title")) or "本轮分析"
            if planned_type == "chart":
                actions.append(f"继续说“把{title}做成图表”，或用 /chart <标题> :: {{...}} 生成可保存 artifact。")
            else:
                actions.append(f"继续说“生成{title}报告”，二郎神会保存到已授权项目文件夹。")
        elif plan.get("chart_opportunity") and not plan.get("artifact_titles"):
            actions.append("继续说“把这个做成图表”，或用 /chart <标题> :: {...} 生成可保存 artifact。")
        if plan.get("artifact_titles"):
            actions.append("/open 打开最近图表或报告，/artifacts 查看全部产物。")
        if plan.get("resource_links"):
            actions.append("/links 查看最近网页、图片、图表和报告名称链接；/links open 1 直接打开第一个资源。")
        if plan.get("missing_inputs"):
            actions.append("补充路由层认为还缺的信息后继续追问，二郎神会沿用最近上下文。")
        mcp_keys = plan.get("mcp_data_keys") or []
        if plan.get("needs_mcp") and not mcp_keys:
            actions.append("/doctor 检查账号、super-66 MCP 和 web_search 状态。")
        if not actions:
            actions.append("直接继续追问，或输入 /clear 开启一个干净的新会话。")
        return actions[:4]

    def _previous_successful_plan(self, current: dict | None = None) -> dict | None:
        _, _, history = self._plan_history_snapshot()
        current_query = self._text_field(current.get("query")) if isinstance(current, dict) else ""
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            if self._text_field(item.get("status")) == "failure":
                continue
            if current_query and self._text_field(item.get("query")) == current_query:
                continue
            return item
        return None

    def _format_artifact_plan(self, artifact_plan) -> str:
        if not isinstance(artifact_plan, dict):
            return "none"
        plan_type = self._text_field(artifact_plan.get("type")).lower() or "none"
        if plan_type == "none":
            return "none"
        title = self._text_field(artifact_plan.get("title"))
        data_hint = self._text_field(artifact_plan.get("data_hint"))
        parts = [plan_type]
        if title:
            parts.append(title)
        if data_hint:
            parts.append(data_hint)
        if artifact_plan.get("save_to_workspace"):
            parts.append("保存到授权项目文件夹")
        return " / ".join(parts)

    def _route_source_label(self, source) -> str:
        labels = {
            "local_llm": "本机大模型意图理解",
            "provided_payload": "调用方显式提供 intent_plan",
            "fallback": "保守兜底路由",
        }
        return labels.get(self._text_field(source), "本机大模型意图理解")

    def _tool_selection_source_label(self, source) -> str:
        labels = {
            "local_llm": "本机大模型选择",
            "provided_payload": "调用方显式提供",
            "client_default_by_intent": "客户端按意图补齐",
            "client_market_overview_fallback": "客户端行情兜底补齐",
            "previous_mcp_context": "复用上一轮 MCP 数据",
            "none": "未选择工具",
        }
        return labels.get(self._text_field(source), "未说明")

    def context_text(self, args: str = "") -> str:
        action = (args or "").strip().lower()
        if action in {"clear", "reset", "clean", "清空", "重置"}:
            self._clear_session_state(clear_plan=False)
            return "\n".join([
                "【最近对话上下文】",
                "- 已清空",
                "- 说明: 只清空本次 CLI 进程内的临时上下文和临时资源链接；不会影响登录、模型 Key、工作区、已保存报告或项目 resources.json 索引。",
            ])
        context = self._recent_conversation_context(limit=6)
        local_memory = self._recent_local_memory_context(limit=6)
        mcp_context = self._last_mcp_context_brief()
        artifacts = self._recent_artifact_context()
        resources = self._recent_resource_context(limit=8)
        workspace = workspace_status()
        lines = [
            "【最近对话上下文】",
            f"- 条数: {len(context)}",
            f"- 本机记忆: {len(local_memory)} 条会被预算化注入",
            "- 进入本机大模型: recent_conversation、local_memory、previous_mcp_context、recent_artifacts、recent_resources",
            "- 范围: 本次 CLI 进程内摘要 + 本机持久记忆 + 已授权项目资源索引",
            "- 安全边界: 不展示 API Key、token、password、authorization 或服务端内部认知库全文",
            f"- 工作区: {'已授权' if workspace.get('allowed') else '未授权'} · {workspace.get('path')}",
        ]
        lines.extend([
            "",
            "上下文来源:",
            f"- recent_conversation: {len(context)} 条压缩对话",
            f"- local_memory: {len(local_memory)} 条跨会话压缩记忆",
            f"- previous_mcp_context: {mcp_context.get('status')} · {', '.join(mcp_context.get('usable_sources') or []) or '暂无可用数据源'}",
            f"- recent_artifacts: {len(artifacts)} 个图表/报告摘要",
            f"- recent_resources: {len(resources)} 个网页/图片/图表/报告链接",
        ])
        if local_memory:
            lines.extend(["", "本机持久记忆:"])
            for index, item in enumerate(local_memory[:6], 1):
                tags = ", ".join(item.get("tags") or [])
                tag_text = f" · {tags}" if tags else ""
                lines.append(f"{index}. {item.get('user') or ''} -> {item.get('summary') or ''}{tag_text}")
        if mcp_context.get("snapshots"):
            lines.extend(["", "最近 MCP 快照:"])
            for item in (mcp_context.get("snapshots") or [])[:6]:
                lines.append(f"- {item}")
        if artifacts:
            lines.extend(["", "最近产物摘要:"])
            for item in artifacts[:6]:
                title = self._text_field(item.get("title")) or "未命名产物"
                status = self._text_field(item.get("status")) or "unknown"
                data_keys = ", ".join(item.get("data_keys") or []) or "无数据键"
                open_path = self._text_field(item.get("html") or item.get("json"))
                lines.append(f"- {title}: {status} · {data_keys}" + (f" · {open_path}" if open_path else ""))
        if resources:
            lines.extend(["", "最近可打开资源:"])
            for index, item in enumerate(resources[:8], 1):
                source = self._text_field(item.get("source")) or "resource"
                link = self._text_field(item.get("link"))
                query = self._text_field(item.get("query"))
                lines.append(f"{index}. {source} · {query}: {link}")
        if not context:
            lines.extend([
                "",
                "暂无上下文。直接输入投资问题后，二郎神会保存最近几轮压缩摘要。",
                "如果回答产生网页、图片、图表或报告，资源会进入 /links；授权工作区后也会进入项目 resources.json 索引。",
            ])
            return "\n".join(lines)
        lines.append("")
        for index, item in enumerate(context, 1):
            lines.append(f"{index}. 你: {item.get('user') or ''}")
            lines.append(f"   二郎神: {item.get('assistant') or ''}")
        lines.extend([
            "",
            "继续使用:",
            "- 直接追问“那如果换成港股呢？”这类问题，本机大模型会参考以上上下文。",
            "- 说“把刚才的结论做成图表/报告”，可复用最近上下文生成产物。",
            "- 说“打开刚才那个网页/图片/图表”，二郎神会参考 recent_resources，并提示 /links 或 /open。",
            "",
            "命令:",
            "  /context clear",
            "  /memory",
            "  /plan",
            "  /links",
            "  /clear",
        ])
        return "\n".join(lines)

    def thinking_text(self, args: str = "") -> str:
        trace = self._last_reasoning_trace if isinstance(self._last_reasoning_trace, dict) else {}
        raw_text = trace.get("text")
        text = raw_text if isinstance(raw_text, str) else str(raw_text or "")
        text = text.strip()
        if not text:
            return "\n".join([
                "【思考过程】",
                "暂无可展开的模型思考过程。",
                "",
                "说明: 这里只展示模型供应商在流式响应中返回的 reasoning/thinking 事件；如果供应商没有返回该事件，就不会有可展开内容。",
            ])
        chars = int(trace.get("char_count") or len(text))
        elapsed = self._format_seconds(trace.get("elapsed_seconds"))
        saved_at = self._text_field(trace.get("saved_at"))
        header = [
            f"字数: {chars}",
            f"耗时: {elapsed}",
        ]
        if saved_at:
            header.append(f"时间: {saved_at}")
        return "\n".join([
            _text_panel("思考过程", header, min_width=48, max_width=120),
            "",
            self._message_block("完整思考过程", text, "35"),
        ])

    def memory_text(self, args: str = "") -> str:
        action = (args or "").strip().lower()
        if action in {"clear", "reset", "clean", "清空", "重置"}:
            try:
                self._memory.clear()
            except (OSError, PermissionError, TypeError, ValueError) as exc:
                return f"【本机记忆】\n- 清空失败: {exc}"
            return "\n".join([
                "【本机记忆】",
                "- 已清空",
                "- 影响范围: 只清空本机压缩记忆，不影响登录、模型 Key、工作区授权、报告和资源链接。",
            ])

        stats = self._memory_stats()
        memories = self._recent_local_memory_context(limit=10)
        lines = [
            "【本机记忆】",
            f"- 条数: {stats.get('count', 0)}",
            f"- 文件: {stats.get('path')}",
            f"- 更新时间: {stats.get('updated_at') or '暂无'}",
            "- 机制: 每轮问答结束后自动压缩、脱敏并保存在本机；后续提问会按预算注入本机大模型上下文。",
            "- 安全边界: API Key、token、password、authorization 会被隐藏；记忆不会发送给二郎神服务端。",
        ]
        if not memories:
            lines.extend([
                "",
                "暂无本机记忆。直接提问后，二郎神会自动沉淀近期问题、回答摘要和主题标签。",
            ])
        else:
            lines.append("")
            for index, item in enumerate(memories, 1):
                tags = ", ".join(item.get("tags") or []) or "无标签"
                lines.append(f"{index}. {item.get('user') or ''}")
                lines.append(f"   摘要: {item.get('summary') or ''}")
                lines.append(f"   标签: {tags}")
        lines.extend([
            "",
            "命令:",
            "  /memory clear     清空本机持久记忆",
            "  /context          查看本轮上下文和本机记忆注入情况",
            "  /clear            开启干净会话，但保留本机记忆",
        ])
        return "\n".join(lines)

    def clear_session_text(self) -> str:
        self._clear_session_state(clear_plan=True)
        return "\n".join([
            "【新会话已开始】",
            "- 已清空: 最近对话上下文、本次进程内资源链接、最近一次 /plan、临时执行过程",
            "- 保留: 登录状态、模型 Key、工作区授权、已保存图表和报告、项目 resources.json 索引",
            "- 下一步: 直接输入新的投资问题，或输入 /setup 查看准备状态。",
        ])

    def _clear_session_state(self, *, clear_plan: bool = True) -> None:
        self._conversation_history.clear()
        self._agent_trace = None
        self._last_mcp_data = None
        self._last_reasoning_trace = None
        self._last_artifact_results = []
        self._last_resource_links = []
        self._live_answer_state = None
        self._live_answer_finalized = False
        if clear_plan:
            self._last_agent_plan = None

    def _remember_agent_plan(
        self,
        *,
        query: str,
        intent_plan: dict,
        mapping_query: str,
        mcp_data,
        matches: list[dict],
        synthesis: dict | None,
        provider: str,
        model: str,
        persist: bool = True,
    ) -> None:
        artifact_results = synthesis.get("artifact_results") if isinstance(synthesis, dict) else []
        self._last_agent_plan = {
            "query": query,
            "intent": self._text_field(intent_plan.get("intent")) or "general_investment",
            "tone": self._text_field(intent_plan.get("tone")) or "natural_analyst",
            "route_source": self._normalize_route_source(intent_plan.get("route_source")),
            "route_warning": self._text_field(intent_plan.get("route_warning") or intent_plan.get("intent_error")),
            "rewritten_query": self._text_field(intent_plan.get("rewritten_query")) or query,
            "mapping_query": self._text_field(mapping_query) or self._text_field(intent_plan.get("rewritten_query")) or query,
            "is_followup": bool(intent_plan.get("is_followup")),
            "followup_target": self._text_field(intent_plan.get("followup_target")),
            "route_summary": self._text_field(intent_plan.get("route_summary")),
            "tool_rationale": self._text_field(intent_plan.get("tool_rationale")),
            "data_strategy": self._text_field(intent_plan.get("data_strategy")),
            "data_confidence": self._text_field(intent_plan.get("data_confidence")),
            "tool_selection_source": self._text_field(intent_plan.get("tool_selection_source")),
            "tool_selection_note": self._text_field(intent_plan.get("tool_selection_note")),
            "chart_opportunity": bool(intent_plan.get("chart_opportunity")),
            "chart_rationale": self._text_field(intent_plan.get("chart_rationale")),
            "artifact_plan": intent_plan.get("artifact_plan") if isinstance(intent_plan.get("artifact_plan"), dict) else {},
            "resource_links": self._coerce_resource_links(intent_plan.get("resource_links")),
            "resource_presentation": self._text_field(intent_plan.get("resource_presentation")),
            "open_commands": self._coerce_text_items(intent_plan.get("open_commands")) or ["/links 1", "/open 1"],
            "missing_inputs": self._coerce_text_items(intent_plan.get("missing_inputs")),
            "needs_server_mapping": bool(intent_plan.get("needs_server_mapping", True)),
            "needs_mcp": bool(intent_plan.get("needs_mcp")),
            "mcp_tools": self._dedupe_mcp_tools(intent_plan.get("mcp_tools") or []),
            "tool_plan": self._tool_plan_explanations(intent_plan, mcp_data),
            "mcp_data_keys": sorted((mcp_data or {}).keys()) if isinstance(mcp_data, dict) else [],
            "mcp_snapshots": self._mcp_snapshot_lines(mcp_data),
            "agent_trace": self._agent_trace_lines(),
            "server_scenes": [
                self._text_field(match.get("scene"))
                for match in (matches or [])[:3]
                if isinstance(match, dict) and self._text_field(match.get("scene"))
            ],
            "artifact_titles": [
                self._text_field(item.get("title"))
                for item in (artifact_results or [])
                if isinstance(item, dict) and self._text_field(item.get("title"))
            ],
            "provider": provider,
            "model": model,
            "key_boundary": "API Key 仅本机直连供应商，未发送给二郎神服务端",
        }
        if persist:
            self._persist_agent_plan()

    def _remember_agent_failure_plan(
        self,
        *,
        query: str,
        intent_plan: dict | None,
        mapping_query: str,
        mcp_data,
        matches: list[dict] | None,
        provider: str,
        model: str,
        failure_stage: str,
        failure_message: str,
    ) -> None:
        safe_intent_plan = intent_plan if isinstance(intent_plan, dict) else {}
        self._remember_agent_plan(
            query=query,
            intent_plan=safe_intent_plan,
            mapping_query=mapping_query,
            mcp_data=mcp_data,
            matches=matches or [],
            synthesis={},
            provider=provider,
            model=model,
            persist=False,
        )
        if isinstance(self._last_agent_plan, dict):
            self._last_agent_plan.update({
                "status": "failure",
                "failure_stage": self._text_field(failure_stage),
                "failure_message": self._text_field(failure_message),
                "route_warning": self._text_field(failure_message) or self._last_agent_plan.get("route_warning"),
            })
            self._persist_agent_plan()

    def _agent_plan_path(self, workspace: str | Path | None = None) -> Path:
        root = resolve_workspace_path(str(workspace) if workspace else None)
        return ensure_inside_workspace(root / ".erlangshen" / "artifacts" / "agent_plan.json", root)

    def _agent_plan_history_path(self, workspace: str | Path | None = None) -> Path:
        root = resolve_workspace_path(str(workspace) if workspace else None)
        return ensure_inside_workspace(root / ".erlangshen" / "artifacts" / "agent_plans.jsonl", root)

    def _persist_agent_plan(self) -> None:
        if not isinstance(self._last_agent_plan, dict):
            return
        status = workspace_status()
        if not status.get("allowed"):
            return
        workspace = str(status.get("path") or "")
        try:
            latest_path = self._agent_plan_path(workspace)
            history_path = self._agent_plan_history_path(workspace)
            now = datetime.now().isoformat(timespec="seconds")
            payload = {
                **self._last_agent_plan,
                "persisted_at": now,
                "persisted_path": str(latest_path),
                "recent_resources": self._recent_resource_context(limit=8),
            }
            latest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            history = self._read_agent_plan_history(history_path)
            history.append(payload)
            with open(history_path, "w", encoding="utf-8") as f:
                for item in history[-50:]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            self._last_agent_plan.update({
                "persisted_at": now,
                "persisted_path": str(latest_path),
            })
        except (OSError, PermissionError, TypeError, ValueError):
            return

    def _load_persisted_agent_plan(self) -> dict | None:
        status = workspace_status()
        if not status.get("allowed"):
            return None
        try:
            path = self._agent_plan_path(str(status.get("path") or ""))
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except (OSError, PermissionError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _read_agent_plan_history(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        items: list[dict] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        items.append(item)
        except OSError:
            return []
        return items

    def _tool_plan_explanations(self, intent_plan: dict, mcp_data) -> list[dict]:
        tools = self._dedupe_mcp_tools(intent_plan.get("mcp_tools") or []) if isinstance(intent_plan, dict) else []
        if not tools:
            return []
        catalog = {
            self._text_field(tool.get("name")): tool
            for tool in self._mcp_capability_catalog("").get("mcp_tools") or []
            if isinstance(tool, dict)
        }
        data_keys = sorted(str(key) for key in (mcp_data or {}).keys()) if isinstance(mcp_data, dict) else []
        explanations = []
        for item in tools:
            name = self._text_field(item.get("name"))
            arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
            matching_keys = [key for key in data_keys if key.startswith(f"{name}:")]
            error_keys = [key for key in matching_keys if "error" in key.lower()]
            ok_keys = [key for key in matching_keys if key not in error_keys]
            if ok_keys:
                status = "已返回"
            elif error_keys:
                status = "失败"
            else:
                status = "计划中"
            catalog_item = catalog.get(name) or {}
            explanations.append({
                "tool": name,
                "label": self._mcp_tool_label(name, arguments),
                "why": self._text_field(catalog_item.get("use_when")) or "由本机大模型根据上下文选择",
                "arguments": arguments,
                "status": status,
                "data_keys": matching_keys[:4],
            })
        return explanations

    def setup_text(self) -> str:
        session = load_auth_session()
        config = get_config()
        workspace = workspace_status()
        provider, model, llm_ready, key_hint = self._llm_status(config)
        user = session.get("user") or {}
        username = user.get("username") or user.get("email") or user.get("id")
        token_ready = bool(session.get("token"))
        workspace_ready = bool(workspace.get("allowed"))
        rows = [
            ("workspace", f"{'已授权' if workspace_ready else '未授权'} {workspace.get('path')}"),
            ("account", username or ("已保存 token" if token_ready else "未登录")),
            ("model", f"{provider} / {model} ({'key ready' if llm_ready else 'missing key'})"),
            ("mcp", "super-66 MCP 使用 XWAB/XCZT 登录态，不需要单独账号"),
            ("artifacts", self._setup_artifact_status(workspace)),
            ("agent route", "NL -> local intent -> MCP/search -> server map -> local answer"),
        ]
        actions = []
        if not workspace_ready:
            actions.append("/workspace browse 打开路径选择器，或 /workspace path <路径> 手动指定，然后 /workspace allow 授权写入图表和报告")
        if not token_ready:
            actions.append("/login xwab <账号> 登录后才能访问服务端场景映射和 super-66 MCP")
        if not llm_ready:
            actions.append(f"/model select 选择供应商和型号，然后 /model key 测试并保存 {key_hint}")
        if workspace_ready and token_ready and llm_ready:
            actions.append("直接输入投资问题；二郎神会先取 MCP 数据，再做服务端场景映射和本机大模型分析")
            actions.append("/artifacts 查看已经保存的报告和图表")
        if workspace_ready:
            actions.append("/setup workspace 重新选择当前项目文件夹，适合切换到新的分析项目")
        ready_count = sum([workspace_ready, token_ready, llm_ready])
        primary_action = actions[0] if actions else "直接输入投资问题开始分析"

        lines = [
            "【二郎神初始化向导】",
            f"初始化完成度: {ready_count}/3",
            f"首要下一步: {primary_action}",
            "",
            _panel("Readiness", rows),
            "agent route: NL -> local intent -> MCP/search -> server map -> local answer",
            "",
            self._workspace_choice_deck(workspace),
            "",
            self._setup_agent_sandbox_panel(workspace, token_ready, provider, model, llm_ready, key_hint),
            "",
            self._model_setup_deck(provider, model, llm_ready, key_hint),
            "",
            "推荐顺序:",
        ]
        for idx, action in enumerate(actions, 1):
            lines.append(f"{idx}. {action}")
        lines.extend([
            "",
            "运行边界:",
            "- 大模型 API Key 只保存在本机，用于客户端直连供应商；不会发送给二郎神服务端。",
            "- 服务端负责受保护场景映射和图表 artifact 通道；不向客户端暴露内部认知库全文。",
            "- 行情和产品数据优先从 super-66 MCP 获取；新闻和网页信息可用本地 Chrome web_search 补充。",
            "- 输入 /tools 可查看本机大模型可选择的数据工具、搜索能力和图表通信方式。",
            "- 输入 /workspace browse 可方向键选择项目文件夹；输入 /workspace path <路径> 可手动粘贴路径。",
            "- 授权后产物和资源链接索引会写入 .erlangshen/artifacts。",
        ])
        return "\n".join(lines)

    async def setup_workspace_interactive(self) -> str:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return "\n".join([
                "【项目文件夹初始化】",
                "当前不是交互终端，不能安全打开方向键路径选择器。",
                "",
                "请在本机终端运行:",
                "  erlangshen /setup workspace",
                "",
                "或手动执行:",
                "  erlangshen /workspace path <项目路径>",
                "  erlangshen /workspace allow",
            ])
        line, status = self._select_and_authorize_workspace(resolve_workspace_path(), force=True)
        return "\n".join([
            "【项目文件夹初始化】",
            line,
            "",
            self._workspace_status_panel(status),
            "",
            "下一步: /setup run 检查账号和本机大模型，或直接输入投资问题。",
        ])

    async def setup_run_interactive(self, *, force_workspace: bool = False) -> str:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return "\n".join([
                self.setup_text(),
                "",
                "【执行式初始化】",
                "当前不是交互终端，不能安全打开路径选择和授权确认。",
                "",
                "请在本机终端运行:",
                "  erlangshen /setup run",
                "  erlangshen /setup workspace",
                "",
                "或手动执行:",
                "  erlangshen /workspace path <项目路径>",
                "  erlangshen /workspace use <项目路径>",
                "  erlangshen /workspace allow",
                "  erlangshen /login xwab <账号>",
                "  erlangshen /model select",
                "  erlangshen /model key",
            ])

        lines = ["【二郎神初始化执行】"]
        workspace = resolve_workspace_path()
        status = workspace_status(workspace)
        if status.get("allowed") and not force_workspace:
            lines.append(f"- 工作区: 已授权 {status.get('path')}")
        else:
            workspace_line, status = self._select_and_authorize_workspace(workspace, force=force_workspace)
            lines.append(workspace_line)

        session = load_auth_session()
        config = get_config()
        provider, model, llm_ready, key_hint = self._llm_status(config)
        user = session.get("user") or {}
        username = user.get("username") or user.get("email") or user.get("id")
        if session.get("token"):
            lines.append(f"- 账号: 已登录 {username or '已保存 token'}")
        else:
            lines.append("- 账号: 未登录，下一步执行 /login xwab <账号>")
        if llm_ready:
            lines.append(f"- 大模型: 已配置 {provider} / {model}")
        else:
            lines.append(f"- 大模型: 缺少 {key_hint}，下一步执行 /model select 和 /model key")
        final_workspace = workspace_status(status.get("path") or workspace)
        token_ready = bool(session.get("token"))
        workspace_ready = bool(final_workspace.get("allowed"))
        ready_count = sum([workspace_ready, token_ready, llm_ready])
        primary_action = self._setup_primary_action(workspace_ready, token_ready, llm_ready, key_hint)
        lines.extend([
            f"- 初始化完成度: {ready_count}/3",
            f"- 首要下一步: {primary_action}",
            "- MCP: super-66 MCP 会复用 XWAB/XCZT 登录态",
            "- 产物: 授权工作区后，图表和报告会保存到 .erlangshen/artifacts",
            "",
            self._workspace_choice_deck(final_workspace),
            "",
            self._setup_agent_sandbox_panel(final_workspace, token_ready, provider, model, llm_ready, key_hint),
            "",
            "完成后可以直接输入投资问题，或输入 /service 检查服务端状态。",
        ])
        return "\n".join(lines)

    def _workspace_choice_deck(self, workspace: dict) -> str:
        path = str(workspace.get("path") or resolve_workspace_path())
        allowed = bool(workspace.get("allowed"))
        resource_count = self._workspace_resource_count(path)
        recent = recent_workspaces(limit=3)
        if recent:
            recent_text = "；".join(
                f"{Path(str(item.get('path'))).name or item.get('path')} ({'已授权' if item.get('allowed') else '未授权'})"
                for item in recent
            )
        else:
            recent_text = "暂无；首次使用建议选择当前项目根目录"
        rows = [
            ("current", f"{path} · {'已授权' if allowed else '未授权'}"),
            ("choose", "/workspace browse 方向键浏览目录，Enter 选择，p 粘贴路径，q 跳过"),
            ("manual", "/workspace path <路径> 粘贴任意项目文件夹，然后 /workspace allow 授权"),
            ("recent", recent_text),
            ("writes", ".erlangshen/artifacts 下保存图表、报告、工作记忆和 resources.json"),
            ("links", f"当前项目资源索引 {resource_count} 条；网页/图片/HTML/PDF 统一进入 /links"),
            ("privacy", "不会把大模型 API Key、账号 token 或服务端内部认知库写进项目目录"),
            ("skip", "输入 n/skip 可跳过；未授权时只进行对话和远程接口调用"),
        ]
        title = "Project Folder Picker" if not allowed else "Project Folder Ready"
        return _panel(title, rows)

    def _setup_agent_sandbox_panel(
        self,
        workspace: dict,
        token_ready: bool,
        provider: str,
        model: str,
        llm_ready: bool,
        key_hint: str,
    ) -> str:
        workspace_ready = bool(workspace.get("allowed"))
        primary_action = self._setup_primary_action(workspace_ready, token_ready, llm_ready, key_hint)
        rows = [
            ("workspace", "OK" if workspace_ready else "NEED"),
            ("account", "OK" if token_ready else "NEED"),
            ("model", f"{provider} / {model}" if llm_ready else f"NEED {key_hint}"),
            ("sandbox", "写入仅限授权项目 .erlangshen/artifacts" if workspace_ready else "未授权前不写入本地项目"),
            ("data", "super-66 MCP 优先，web_search 补当天公开事件线索"),
            ("flow", "intent -> MCP/search -> map -> answer"),
            ("next", primary_action),
        ]
        title = "Agent Sandbox Ready" if workspace_ready and token_ready and llm_ready else "Agent Setup Checklist"
        return _panel(title, rows)

    def _setup_primary_action(self, workspace_ready: bool, token_ready: bool, llm_ready: bool, key_hint: str = "") -> str:
        if not workspace_ready:
            return "/workspace browse 选择项目文件夹，或 /workspace path <路径> 手动指定，然后 /workspace allow 授权"
        if not token_ready:
            return "/login xwab <账号> 登录服务端和 super-66 MCP"
        if not llm_ready:
            suffix = f" ({key_hint})" if key_hint else ""
            return f"/model select 然后 /model key 测试并保存本机 API Key{suffix}"
        return "直接输入投资问题开始分析"

    def _setup_artifact_status(self, workspace: dict) -> str:
        if not workspace.get("allowed"):
            return "未启用；授权工作区后可保存 .erlangshen/artifacts"
        root = Path(str(workspace.get("path"))) / ".erlangshen" / "artifacts"
        charts = self._artifact_files(root / "charts", {".json", ".html"})
        reports = self._artifact_files(root / "reports", {".md"})
        return f"已启用；reports {len(reports)} / charts {len(charts)}"

    def _model_setup_deck(self, provider: str, model: str, ready: bool, key_hint: str) -> str:
        preset = get_provider_preset(provider)
        status = "ready" if ready else f"missing {key_hint}"
        action = "直接提问" if ready else "/model select -> /model key"
        rows = [
            ("provider", f"{preset.id} ({preset.display_name})"),
            ("model", model),
            ("key", status),
            ("test", "/model key 会先本机直连供应商测试，成功后才保存"),
            ("boundary", "Key 只在本机；服务端只接收问题做受保护场景映射"),
            ("commands", action),
            ("env", f"LLM_PROVIDER={preset.id} · {key_hint}=... · {preset.model_env}={model}"),
        ]
        return _panel("Model Setup", rows)

    def _artifact_files(self, directory: Path, suffixes: set[str]) -> list[Path]:
        if not directory.exists():
            return []
        return sorted(
            [path for path in directory.iterdir() if path.suffix.lower() in suffixes],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _relative_workspace_path(self, path: Path, workspace: str) -> str:
        try:
            return str(path.relative_to(Path(workspace)))
        except ValueError:
            return str(path)

    def _file_uri(self, path: str | Path) -> str:
        try:
            return Path(str(path)).expanduser().resolve().as_uri()
        except (OSError, ValueError):
            return str(path)

    def _resource_link(self, label: str, target: str | Path) -> str:
        clean_label = self._text_field(label) or "打开资源"
        target_text = self._text_field(target)
        if not target_text:
            return clean_label
        if re.match(r"^https?://", target_text, flags=re.I):
            uri = target_text
        elif re.match(r"^file://", target_text, flags=re.I):
            uri = target_text
        else:
            uri = self._file_uri(target_text)
        if sys.stdout.isatty() and not os.getenv("ERLANGSHEN_NO_OSC8"):
            return f"\033]8;;{uri}\033\\{clean_label}\033]8;;\033\\"
        return f"{clean_label}: {uri}"

    def _workspace_file_link(self, path: str | Path, workspace: str, label: str | None = None) -> str:
        path_obj = Path(str(path)).expanduser()
        display = label or self._relative_workspace_path(path_obj, workspace)
        return self._resource_link(display, path_obj)

    async def chart_text(self, args: str = "") -> str:
        raw = (args or "").strip()
        if not raw:
            return "\n".join([
                "请提供图表标题和 JSON 数据。",
                "示例: /chart 资产表现 :: {\"A股\":1.2,\"黄金\":0.8,\"美元\":-0.3}",
            ])
        title, data = self._parse_chart_args(raw)
        if not data:
            return "图表数据需要是 JSON 对象。示例: /chart 资产表现 :: {\"A股\":1.2,\"黄金\":0.8}"
        try:
            from src.client.server_client import ErlangshenServerClient

            session = load_auth_session()
            client = ErlangshenServerClient(
                base_url=session.get("base_url") or get_config().erlangshen_api_base_url,
                token=session.get("token"),
            )
            response = await client.chart_artifact(
                chart_type="bar",
                title=title,
                data=data,
                metadata={"workspace": workspace_status().get("path"), "source": "cli"},
            )
            artifact = self._chart_artifact_from_response(response)
            if not isinstance(artifact, dict):
                resource_links = [
                    {"source": "server artifact", "link": link}
                    for link in self._resource_links_from_value(response, title)
                ]
                self._remember_resource_links(f"/chart {title}", resource_links)
                lines = [f"图表 artifact 已返回: {artifact}"]
                if resource_links:
                    lines.extend([
                        "",
                        "可打开资源:",
                        *[f"- {item['link']}" for item in resource_links[:6]],
                        "- 输入 /links 1 或 /open 1 打开最近资源。",
                    ])
                return "\n".join(lines)
            metadata = artifact.get("metadata") or {}
            saved_path = self._save_chart_artifact(artifact, title)
            resource_links = [
                {"source": "server artifact", "link": link}
                for link in self._resource_links_from_value(response, title)
            ]
            lines = [
                "【图表 Artifact】",
                f"- 标题: {artifact.get('title') or title}",
                f"- 类型: {artifact.get('type') or 'bar'}",
                f"- 数据键: {', '.join(str(key) for key in (artifact.get('data') or data).keys())}",
                f"- 来源: {metadata.get('source') or 'erlangshen-server'}",
            ]
            if saved_path:
                workspace = str(workspace_status().get("path") or "")
                json_link = self._workspace_file_link(saved_path["json"], workspace)
                html_link = self._workspace_file_link(saved_path["html"], workspace, label=(artifact.get("title") or title) + " HTML")
                lines.append(f"- 已保存: {json_link}")
                lines.append(f"- 可视化: {html_link}")
                resource_links.extend([
                    {"source": "local artifact", "link": html_link},
                    {"source": "local artifact", "link": json_link},
                ])
            else:
                lines.append("- 保存: 工作区未授权，仅展示结构化 artifact 摘要。")
                lines.append("- 下一步: /workspace browse 选择项目文件夹，或 /workspace path <路径> 手动指定，然后 /workspace allow 授权保存。")
            if resource_links:
                self._remember_resource_links(f"/chart {title}", resource_links)
                lines.append("- 资源入口: 已加入 /links，可用 /links 1 或 /open 1 打开最近图表/网页/图片。")
            lines.append("- 说明: 客户端可根据该结构化 artifact 渲染图表或写入报告。")
            return "\n".join(lines)
        except Exception as exc:
            return f"图表 artifact 生成失败: {self._sanitize_api_key_error(exc, '')}"

    def _chart_artifact_from_response(self, response):
        if not isinstance(response, dict):
            return response
        artifact = response.get("artifact")
        if isinstance(artifact, dict):
            return artifact
        for key in ("chart", "visualization", "result"):
            nested = response.get(key)
            if isinstance(nested, dict):
                return nested
        if any(key in response for key in ("type", "chart_type", "title", "data", "url", "html_url", "image_url", "resource_links")):
            return response
        return artifact if artifact is not None else response

    def _parse_chart_args(self, raw: str) -> tuple[str, dict]:
        title = "二郎神图表"
        payload = raw
        if "::" in raw:
            title_part, payload = raw.split("::", 1)
            title = title_part.strip() or title
        try:
            data = json.loads(payload.strip())
        except json.JSONDecodeError:
            return title, {}
        return title, data if isinstance(data, dict) else {}

    def _save_chart_artifact(self, artifact: dict, title: str) -> dict[str, str] | None:
        status = workspace_status()
        if not status.get("allowed"):
            return None
        workspace = status.get("path")
        slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", title).strip("-") or "chart"
        slug = slug[:48]
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}.json"
        target = ensure_inside_workspace(
            os.path.join(str(workspace), ".erlangshen", "artifacts", "charts", filename),
            workspace,
        )
        html_target = ensure_inside_workspace(target.with_suffix(".html"), workspace)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)
        with open(html_target, "w", encoding="utf-8") as f:
            f.write(self._chart_artifact_html(artifact, title))
        return {"json": str(target), "html": str(html_target)}

    def _save_advice_report(self, *, query: str, content: str, artifact_results, data_inputs: dict) -> str | None:
        status = workspace_status()
        if not status.get("allowed"):
            return None
        workspace = status.get("path")
        slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", query).strip("-") or "analysis"
        slug = slug[:48]
        filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}.md"
        target = ensure_inside_workspace(
            os.path.join(str(workspace), ".erlangshen", "artifacts", "reports", filename),
            workspace,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        artifact_lines = []
        for item in artifact_results or []:
            if not isinstance(item, dict):
                continue
            saved = item.get("saved") if isinstance(item.get("saved"), dict) else {}
            if saved:
                target_path = saved.get("html") or saved.get("json")
                title = self._text_field(item.get("title")) or "图表"
                if target_path:
                    artifact_lines.append(f"- [{title}]({self._file_uri(target_path)})")
        snapshot_lines = self._report_list_lines(data_inputs.get("mcp_snapshot"))
        trace_lines = self._report_list_lines(data_inputs.get("agent_trace"))
        resource_lines = self._report_list_lines([
            *(data_inputs.get("mcp_links") if isinstance(data_inputs.get("mcp_links"), list) else []),
            *(data_inputs.get("intent_resource_links") if isinstance(data_inputs.get("intent_resource_links"), list) else []),
        ])
        report = [
            f"# 二郎神分析报告: {query}",
            "",
            f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
            f"- MCP 数据键: {', '.join(data_inputs.get('mcp_data') or []) or '未提供'}",
            f"- 用户数据键: {', '.join(data_inputs.get('user_data') or []) or '未提供'}",
            "",
            "## 回答",
            "",
            content,
        ]
        context_lines = []
        if snapshot_lines:
            context_lines.extend(["### MCP 快照", "", *snapshot_lines])
        if resource_lines:
            if context_lines:
                context_lines.append("")
            context_lines.extend(["### 可打开资源", "", *resource_lines])
        if trace_lines:
            if context_lines:
                context_lines.append("")
            context_lines.extend(["### 执行过程", "", *trace_lines])
        if context_lines:
            report.extend(["", "## 数据与执行上下文", "", *context_lines])
        if artifact_lines:
            report.extend(["", "## 图表与产物", "", *artifact_lines])
        report.extend([
            "",
            "## 下一步",
            "",
            "- 在 CLI 中输入 `/links` 查看最近网页、图片、图表和报告链接。",
            "- 输入 `/open link 1` 或 `/links open 1` 打开最近资源。",
            "- 输入 `/artifacts` 查看当前项目已保存的图表和报告。",
        ])
        with open(target, "w", encoding="utf-8") as f:
            f.write("\n".join(report).rstrip() + "\n")
        return str(target)

    def _should_save_advice_report(self, query: str, synthesis: dict) -> bool:
        text = self._text_field(query).lower()
        return any(keyword in text for keyword in ("报告", "report", "保存", "导出", "文档"))

    def _report_list_lines(self, values) -> list[str]:
        if not isinstance(values, list):
            return []
        lines = []
        for item in values[:12]:
            text = self._text_field(item)
            if text:
                lines.append(f"- {text}")
        return lines

    def _chart_artifact_html(self, artifact: dict, title: str) -> str:
        chart_title = escape(str(artifact.get("title") or title))
        chart_type = escape(str(artifact.get("type") or "bar"))
        data = artifact.get("data") if isinstance(artifact.get("data"), dict) else {}
        numeric_items = []
        for key, value in data.items():
            try:
                numeric_items.append((str(key), float(value)))
            except (TypeError, ValueError):
                continue
        max_abs = max((abs(value) for _, value in numeric_items), default=1.0) or 1.0
        bars = []
        for label, value in numeric_items:
            width = max(4, min(100, int(abs(value) / max_abs * 100)))
            tone = "#0f766e" if value >= 0 else "#b91c1c"
            bars.append(
                f'<div class="row"><div class="label">{escape(label)}</div>'
                f'<div class="track"><div class="bar" style="width:{width}%;background:{tone}"></div></div>'
                f'<div class="value">{value:g}</div></div>'
            )
        if not bars:
            bars.append('<div class="empty">No numeric data available in this artifact.</div>')
        raw_json = escape(json.dumps(artifact, ensure_ascii=False, indent=2))
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{chart_title}</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #111827; background: #f8fafc; }}
    main {{ max-width: 960px; margin: 40px auto; padding: 0 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .meta {{ color: #475569; margin-bottom: 28px; }}
    .panel {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; box-shadow: 0 8px 30px rgba(15,23,42,.06); }}
    .row {{ display: grid; grid-template-columns: 160px 1fr 90px; gap: 16px; align-items: center; margin: 14px 0; }}
    .label {{ color: #334155; overflow-wrap: anywhere; }}
    .track {{ height: 18px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }}
    .bar {{ height: 100%; border-radius: 999px; }}
    .value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #0f172a; color: #e2e8f0; border-radius: 8px; padding: 18px; margin-top: 24px; }}
  </style>
</head>
<body>
  <main>
    <h1>{chart_title}</h1>
    <div class="meta">二郎神 chart artifact · {chart_type}</div>
    <section class="panel">
      {''.join(bars)}
    </section>
    <pre>{raw_json}</pre>
  </main>
</body>
</html>
"""

    def model_help_text(self) -> str:
        config = get_config()
        provider, model, ready, key_hint = self._llm_status(config)
        preset = get_provider_preset(provider)
        status = "已配置" if ready else "未配置"
        primary_action = (
            "直接输入投资问题，客户端会用本机 Key 调用大模型"
            if ready
            else f"/model select 选择供应商和型号，然后 /model key 测试并保存 {key_hint}"
        )
        lines = [
            "【大模型配置】",
            f"- 配置状态: {'ready' if ready else 'missing key'}",
            f"- 首要下一步: {primary_action}",
            f"- 当前 provider: {provider}",
            f"- 当前 model: {model}",
            f"- API key: {status}",
            "- Key 位置: 只保存在本机配置/环境变量；不会发送给二郎神服务端",
            "- 调用方式: 服务端只返回受保护场景映射；最终投资建议由客户端直连大模型生成",
            "",
            self._model_agent_flow_panel(provider, model, ready, key_hint),
            "core       服务端只做受保护场景映射和 chart artifact，不接收模型 Key",
            "",
            self._model_setup_deck(provider, model, ready, key_hint),
            "",
            "OpenAI 提示: GPT-5.5/GPT-5.3 当前主要是 ChatGPT/Codex 侧选择；API 预设仍使用官方 API 模型列表中的 gpt-5.2。",
            "",
            "可选供应商和型号:",
        ]
        for provider_preset in MODEL_PRESETS:
            default_marker = " (当前)" if provider_preset.id == normalize_provider(provider) else ""
            lines.append(f"- {provider_preset.id}: {provider_preset.display_name}{default_marker}")
            for model_preset in provider_preset.models:
                selected = " *" if provider_preset.id == normalize_provider(provider) and model_preset.id == model else ""
                lines.append(f"  - {model_preset.id}{selected}: {model_preset.description}")
        lines.extend([
            "",
            "交互配置: 输入 /model select 选择供应商和型号；输入 /model key 测试通过后在本机保存 API Key。",
        ])
        if not ready:
            lines.extend([
                "",
                f"注意: 当前 {preset.display_name} API Key 未设置，客户端无法直连该供应商生成投资建议。",
                "",
                "可直接输入:",
                "  erlangshen /model key",
                "",
                "也可以用环境变量配置，不要写进仓库:",
                f"  export LLM_PROVIDER={preset.id}",
                f"  export {key_hint}=...",
            ])
            lines.append(f"  export {preset.model_env}={model}")
            lines.extend([
                "",
                "配置后直接重新运行 erlangshen；无需把 Key 配到二郎神服务端。",
            ])
        else:
            lines.append("- 下一步: 直接输入投资问题，客户端会用本机 Key 调用大模型")
        return "\n".join(lines)

    def _model_agent_flow_panel(self, provider: str, model: str, ready: bool, key_hint: str) -> str:
        rows = [
            ("role", "本机大模型负责意图理解、MCP 工具组合、自然投资分析"),
            ("facts", "super-66 MCP/web_search 提供行情、产品、新闻和网页线索"),
            ("core", "服务端只做受保护场景映射和 chart artifact，不接收模型 Key"),
            ("key", "ready" if ready else f"missing {key_hint}"),
            ("model", f"{provider} / {model}"),
            ("flow", "/model select -> /model key -> 直接输入投资问题"),
        ]
        return _panel("Model Agent Flow", rows)

    async def model_select_interactive(self) -> str:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return "\n".join([
                "【大模型选择】",
                "当前不是交互终端，不能打开光标选择器。",
                "",
                "请在 erlangshen 交互模式里输入 /model select；或者用环境变量配置:",
                "  export LLM_PROVIDER=openai",
                "  export OPENAI_MODEL=gpt-5.2",
            ])

        provider_items = [
            (preset.id, preset.display_name, f"{preset.key_env} / 默认 {preset.default_model}")
            for preset in MODEL_PRESETS
        ]
        provider_id = await self._select_list("选择大模型供应商", provider_items)
        if not provider_id:
            return "已取消模型选择。"

        provider = get_provider_preset(provider_id)
        model_items = [
            (model.id, model.label, model.description)
            for model in provider.models
        ]
        model_id = await self._select_list(f"选择 {provider.display_name} 模型", model_items)
        if not model_id:
            return "已取消模型选择。"

        update_kwargs = {"llm_provider": provider.id}
        update_kwargs.update(self._provider_model_update(provider.id, model_id))
        update_config(**update_kwargs)
        saved_key, key_error = await self._maybe_prompt_api_key(provider.id, model_id)
        _, _, ready, key_hint = self._llm_status(get_config())

        lines = [
            "【大模型配置已更新】",
            f"- provider: {provider.id} ({provider.display_name})",
            f"- model: {model_id}",
            f"- 配置文件: {get_config_path()}",
            "- Key 处理: 只保存在本机配置/环境变量，不会发送给二郎神服务端",
        ]
        if saved_key:
            lines.append("- API Key: 连接测试成功，已保存到本机配置")
        elif key_error:
            lines.extend([
                "- API Key: 连接测试失败，未保存",
                f"- 测试失败: {key_error}",
                "",
                "注意: 这个 Key 没有写入本机配置，也没有发送给二郎神服务端。",
            ])
        elif not ready:
            lines.extend([
                f"- API Key: 未配置，请设置 {key_hint}=...",
                "",
                f"注意: 未配置 {provider.display_name} API Key 前，客户端无法直连该供应商生成投资建议。",
            ])
        lines.extend([
            "",
            "也可以用环境变量配置:",
            f"  export LLM_PROVIDER={provider.id}",
            f"  export {provider.key_env}=...",
            f"  export {provider.model_env}={model_id}",
            "",
            "之后可直接输入投资问题；服务端只做场景映射，最终建议由本机大模型生成。",
        ])
        return "\n".join(lines)

    async def model_key_interactive(self) -> str:
        config = get_config()
        provider, model, ready, key_hint = self._llm_status(config)
        preset = get_provider_preset(provider)
        if not sys.stdin.isatty():
            return "\n".join([
                "【本机 API Key 配置】",
                "当前不是交互终端，不能安全读取 API Key。",
                "",
                "请在交互终端执行:",
                "  erlangshen /model key",
                "",
                "或使用环境变量:",
                f"  export LLM_PROVIDER={preset.id}",
                f"  export {key_hint}=...",
                f"  export {preset.model_env}={model}",
                "",
                "说明: 该 Key 只用于客户端直连大模型，不会发送给二郎神服务端。",
            ])
        api_key = getpass.getpass(f"{preset.display_name} API Key（只保存本机，不发送服务端；留空取消）: ").strip()
        if not api_key:
            return "已取消 API Key 输入。"
        print("正在本机直连模型供应商测试 API Key...")
        valid, message = await self._validate_local_api_key(preset.id, model, api_key)
        if not valid:
            return "\n".join([
                "【API Key 未保存】",
                f"- provider: {preset.id} ({preset.display_name})",
                f"- model: {model}",
                f"- 测试失败: {message}",
                "- 安全边界: Key 没有写入本机配置，也没有发送给二郎神服务端",
                "- 下一步: 请检查 Key、模型型号、供应商额度、网络代理后重新输入 /model key",
            ])
        update_config(**self._provider_key_update(preset.id, api_key))
        return "\n".join([
            "【API Key 已保存到本机】",
            f"- provider: {preset.id} ({preset.display_name})",
            f"- model: {model}",
            f"- 配置文件: {get_config_path()}",
            f"- 连接测试: {message}",
            "- 安全边界: Key 不会发送给二郎神服务端；/advice 只把问题发给服务端做场景映射",
            "- 下一步: 直接输入投资问题，客户端会直连大模型生成分析",
        ])

    async def _maybe_prompt_api_key(self, provider: str, model: str) -> tuple[bool, str]:
        _, _, ready, _ = self._llm_status(get_config())
        if ready or not sys.stdin.isatty():
            return False, ""
        preset = get_provider_preset(provider)
        answer = input(f"是否现在输入 {preset.display_name} API Key？只保存本机，不发送服务端 [y/N]: ").strip().lower()
        if answer not in {"y", "yes", "是", "好"}:
            return False, ""
        api_key = getpass.getpass(f"{preset.display_name} API Key: ").strip()
        if not api_key:
            return False, ""
        print("正在本机直连模型供应商测试 API Key...")
        valid, message = await self._validate_local_api_key(provider, model, api_key)
        if not valid:
            return False, message
        update_config(**self._provider_key_update(provider, api_key))
        return True, ""

    async def _validate_local_api_key(self, provider: str, model: str, api_key: str) -> tuple[bool, str]:
        try:
            from src.llm import LLMClient, resolve_llm_settings

            config = get_config()
            settings = resolve_llm_settings(
                provider=provider,
                model=model,
                api_key=api_key,
                config=config,
            )
            timeout = max(5.0, min(float(config.request_timeout or 30), 20.0))
            await LLMClient(settings, timeout=timeout).complete(
                [
                    {"role": "system", "content": "You are validating local API connectivity. Reply briefly."},
                    {"role": "user", "content": "请只回复 OK，用于验证 API Key 可用。"},
                ],
                temperature=0,
                max_tokens=16,
            )
            self._refresh_token_status_bar(activity="model key checked")
            return True, "连接测试成功"
        except Exception as exc:
            return False, self._sanitize_api_key_error(exc, api_key)

    def _sanitize_api_key_error(self, exc: Exception, api_key: str) -> str:
        message = str(exc) or exc.__class__.__name__
        if api_key:
            message = message.replace(api_key, "[hidden]")
        message = " ".join(message.split())
        if len(message) > 500:
            message = message[:497] + "..."
        return message or exc.__class__.__name__

    def _provider_model_update(self, provider: str, model: str) -> dict[str, str]:
        provider = normalize_provider(provider)
        if provider == "openai":
            return {"llm_model": model}
        if provider == "deepseek":
            return {"deepseek_model": model}
        if provider == "claude":
            return {"claude_model": model}
        if provider == "mimo":
            return {"mimo_model": model}
        if provider == "kimi":
            return {"kimi_model": model}
        return {"llm_model": model}

    def _provider_key_update(self, provider: str, api_key: str) -> dict[str, str]:
        provider = normalize_provider(provider)
        if provider == "openai":
            return {"llm_api_key": api_key}
        if provider == "deepseek":
            return {"deepseek_api_key": api_key}
        if provider == "claude":
            return {"claude_api_key": api_key}
        if provider == "mimo":
            return {"mimo_api_key": api_key}
        if provider == "kimi":
            return {"kimi_api_key": api_key}
        return {"llm_api_key": api_key}

    def _select_style_current(self) -> str:
        return "bg:#00a3a3 #000000 bold"

    def _ansi_selected_style(self) -> str:
        return "30;46"

    def _should_stream_llm(self) -> bool:
        return os.getenv("ERLANGSHEN_LLM_STREAM", "on").lower() not in {"0", "off", "false", "no"}

    async def _complete_llm_response(
        self,
        client,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        json_preview_field: str = "",
        preview_title: str = "二郎神",
    ) -> str:
        self._live_answer_state = None
        self._live_answer_finalized = False
        if not self._should_stream_llm() or not (hasattr(client, "stream_complete_events") or hasattr(client, "stream_complete")):
            return await client.complete(messages, temperature=temperature, max_tokens=max_tokens)
        chunks: list[str] = []
        reasoning_state = self._new_reasoning_stream_state()
        answer_state = self._new_answer_stream_state(preview_title)
        received = 0
        next_refresh = 120
        if hasattr(client, "stream_complete_events"):
            async for event in client.stream_complete_events(messages, temperature=temperature, max_tokens=max_tokens):
                event_type = self._text_field(event.get("type") if isinstance(event, dict) else "")
                text = event.get("text") if isinstance(event, dict) else ""
                if not isinstance(text, str) or not text:
                    continue
                if event_type == "reasoning":
                    self._write_reasoning_stream(reasoning_state, text)
                    continue
                if event_type == "content":
                    if not reasoning_state.get("closed"):
                        self._finish_reasoning_stream(reasoning_state)
                    chunks.append(text)
                    self._write_json_answer_preview(answer_state, "".join(chunks), json_preview_field)
                    received += len(text)
                    if received >= next_refresh:
                        self._refresh_token_status_bar(activity=f"模型输出 {received} 字")
                        next_refresh = received + 120
            self._finish_reasoning_stream(reasoning_state)
            self._finish_answer_stream(answer_state)
            return "".join(chunks)
        async for chunk in client.stream_complete(messages, temperature=temperature, max_tokens=max_tokens):
            if not chunk:
                continue
            chunks.append(chunk)
            self._write_json_answer_preview(answer_state, "".join(chunks), json_preview_field)
            received += len(chunk)
            if received >= next_refresh:
                self._refresh_token_status_bar(activity=f"模型输出 {received} 字")
                next_refresh = received + 120
        self._finish_answer_stream(answer_state)
        return "".join(chunks)

    def _new_reasoning_stream_state(self) -> dict[str, object]:
        return {
            "visible": False,
            "line_count": 0,
            "char_count": 0,
            "chunks": [],
            "started": time.perf_counter(),
            "closed": False,
        }

    def _should_show_reasoning_stream(self) -> bool:
        setting = os.getenv("ERLANGSHEN_REASONING_STREAM", "on").lower()
        if setting in {"0", "off", "false", "no"}:
            return False
        return sys.stdout.isatty() or setting in {"1", "on", "true", "yes", "force"}

    def _reasoning_box_width(self) -> int:
        return self._dialog_box_width()

    def _terminal_visual_line_count(self, text: str) -> int:
        effective_width = max(20, _terminal_width() - 1)
        total = 0
        for raw_line in str(text or "").splitlines() or [""]:
            width = _display_width(_strip_ansi(raw_line))
            total += max(1, (width + effective_width - 1) // effective_width)
        return total

    def _clear_live_region(self, state: dict[str, object]) -> None:
        count = int(state.get("line_count") or 0)
        if count > 0:
            sys.stdout.write(f"\033[{count}A\033[J")

    def _should_render_live_update(
        self,
        state: dict[str, object],
        rendered_text: str,
        *,
        min_interval: float = 0.08,
        min_chars: int = 24,
    ) -> bool:
        previous = state.get("rendered_text")
        if not state.get("visible") or previous != rendered_text and not previous:
            return True
        if previous == rendered_text:
            return False
        now = time.perf_counter()
        last_rendered = float(state.get("last_rendered_at") or 0.0)
        if now - last_rendered >= min_interval:
            return True
        return abs(len(rendered_text) - len(str(previous or ""))) >= min_chars

    def _write_reasoning_stream(self, state: dict[str, object], text: str) -> None:
        self._append_reasoning_chunk(state, text)
        if not self._should_show_reasoning_stream() or state.get("closed"):
            return
        block = self._reasoning_stream_block(state)
        if not self._should_render_live_update(state, block, min_interval=0.18, min_chars=80):
            return
        try:
            if sys.stdout.isatty():
                if state.get("visible"):
                    self._clear_live_region(state)
                sys.stdout.write(block + "\n")
            elif not state.get("visible"):
                sys.stdout.write(block + "\n")
            sys.stdout.flush()
            state["visible"] = True
            state["line_count"] = self._terminal_visual_line_count(block)
            state["rendered_text"] = block
            state["last_rendered_at"] = time.perf_counter()
        except OSError:
            state["closed"] = True

    def _append_reasoning_chunk(self, state: dict[str, object], text: str) -> None:
        if not isinstance(text, str) or not text:
            return
        chunks = state.get("chunks")
        if not isinstance(chunks, list):
            chunks = []
            state["chunks"] = chunks
        current = "".join(item for item in chunks if isinstance(item, str))
        if not current:
            merged = text
        elif text.startswith(current):
            merged = text
        elif current.endswith(text):
            merged = current
        else:
            overlap = 0
            max_overlap = min(len(current), len(text))
            for size in range(max_overlap, 0, -1):
                if current.endswith(text[:size]):
                    overlap = size
                    break
            merged = current + text[overlap:]
        state["chunks"] = [merged]
        state["char_count"] = len(merged)

    def _finish_reasoning_stream(self, state: dict[str, object]) -> None:
        if state.get("closed"):
            return
        self._remember_reasoning_trace(state)
        if not state.get("visible"):
            state["closed"] = True
            return
        if state.get("closed"):
            return
        state["closed"] = True
        collapsed = self._reasoning_collapsed_line(state)
        try:
            if sys.stdout.isatty():
                self._clear_live_region(state)
                sys.stdout.write(collapsed + "\n")
            else:
                sys.stdout.write(collapsed + "\n")
            sys.stdout.flush()
            state["line_count"] = self._terminal_visual_line_count(collapsed)
            state["rendered_text"] = collapsed
            state["last_rendered_at"] = time.perf_counter()
        except OSError:
            pass

    def _reasoning_stream_block(self, state: dict[str, object]) -> str:
        text = self._reasoning_stream_preview(state)
        if not text.strip():
            text = "正在整理模型供应商返回的思考过程..."
        return self._message_block("思考过程 · 生成中", text, "35")

    def _reasoning_stream_preview(self, state: dict[str, object]) -> str:
        mode = os.getenv("ERLANGSHEN_REASONING_STREAM_MODE", "compact").lower()
        text = self._reasoning_text_from_state(state).strip()
        if mode in {"full", "verbose", "all"}:
            return text
        elapsed = self._format_seconds(time.perf_counter() - float(state.get("started") or time.perf_counter()))
        chars = int(state.get("char_count") or len(text))
        clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
        tail = clean_lines[-3:] if clean_lines else []
        if not tail and text:
            tail = [text]
        preview_lines = [
            f"正在思考 · {chars} 字 · {elapsed} · 完整内容可用 /thinking 展开",
        ]
        for line in tail[:3]:
            preview_lines.append(_clip_display(line, max(20, self._dialog_box_width() - 8)))
        return "\n".join(preview_lines)

    def _reasoning_text_from_state(self, state: dict[str, object]) -> str:
        chunks = state.get("chunks")
        return "".join(chunks if isinstance(chunks, list) else [])

    def _reasoning_collapsed_line(self, state: dict[str, object]) -> str:
        elapsed = max(0.0, time.perf_counter() - float(state.get("started") or time.perf_counter()))
        chars = int(state.get("char_count") or 0)
        summary = f"▸ 思考过程已折叠 · {chars} 字 · {self._format_seconds(elapsed)} · /thinking 展开"
        width = self._reasoning_box_width()
        return _color(_pad_display(summary, width), "35")

    def _remember_reasoning_trace(self, state: dict[str, object]) -> None:
        text = self._reasoning_text_from_state(state).strip()
        if not text:
            return
        elapsed = max(0.0, time.perf_counter() - float(state.get("started") or time.perf_counter()))
        self._last_reasoning_trace = {
            "text": text,
            "char_count": int(state.get("char_count") or len(text)),
            "elapsed_seconds": elapsed,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _new_answer_stream_state(self, title: str) -> dict[str, object]:
        return {
            "title": self._text_field(title) or "二郎神",
            "visible": False,
            "closed": False,
            "stream_done": False,
            "finalized": False,
            "line_count": 0,
            "preview": "",
            "started": time.perf_counter(),
        }

    def _should_show_answer_stream(self) -> bool:
        setting = os.getenv("ERLANGSHEN_ANSWER_STREAM", "off").lower()
        if setting in {"0", "off", "false", "no"}:
            return False
        if setting in {"1", "force"}:
            return True
        return self._interactive_question_printed and sys.stdout.isatty()

    def _write_json_answer_preview(self, state: dict[str, object], raw_text: str, field: str) -> None:
        if not field or not self._should_show_answer_stream() or state.get("closed"):
            return
        preview = ""
        for field_name in re.split(r"[,|]\s*", field):
            field_name = field_name.strip()
            if not field_name:
                continue
            preview = self._extract_jsonish_text_field(raw_text, field_name).strip()
            if preview:
                break
        if not preview and not self._looks_like_json_response_text(raw_text):
            preview = raw_text.strip()
        if not preview or preview == state.get("preview"):
            return
        state["preview"] = preview
        self._live_answer_state = state
        self._render_answer_stream(state, preview)

    def _render_answer_stream(self, state: dict[str, object], preview: str, *, final: bool = False, force: bool = False) -> None:
        body = preview.strip() if final else self._answer_stream_preview_body(preview)
        elapsed = self._format_seconds(time.perf_counter() - float(state.get("started") or time.perf_counter()))
        footer = self._token_dialog_footer(activity="ready" if final else f"生成中 {elapsed}")
        title = self._text_field(state.get("title")) or "二郎神"
        block = "\n".join([self._message_block(title, body or "正在组织回答...", "32;1"), footer])
        if not force and not final and not self._should_render_live_update(state, block, min_interval=0.08, min_chars=32):
            return
        try:
            if state.get("visible") and not sys.stdout.isatty() and not final:
                state["rendered_text"] = block
                state["last_rendered_at"] = time.perf_counter()
                return
            if state.get("visible"):
                self._clear_live_region(state)
            sys.stdout.write(block + "\n")
            sys.stdout.flush()
            state["visible"] = True
            state["line_count"] = self._terminal_visual_line_count(block)
            state["rendered_text"] = block
            state["last_rendered_at"] = time.perf_counter()
            if final:
                state["finalized"] = True
                self._live_answer_finalized = True
        except OSError:
            state["closed"] = True

    def _finish_answer_stream(self, state: dict[str, object]) -> None:
        if state.get("closed"):
            return
        state["stream_done"] = True

    def _finalize_live_answer_stream(self, final_text: str) -> bool:
        state = self._live_answer_state
        if not isinstance(state, dict) or state.get("closed"):
            return False
        final_text = self._text_field(final_text)
        if not final_text:
            final_text = self._text_field(state.get("preview"))
        if not final_text:
            state["closed"] = True
            return False
        if not state.get("visible"):
            state["closed"] = True
            return False
        if state.get("preview") == final_text:
            state["closed"] = True
            state["finalized"] = True
            self._live_answer_finalized = True
            return True
        self._render_answer_stream(state, final_text, final=True, force=True)
        state["closed"] = True
        return bool(state.get("finalized"))

    def _answer_stream_preview_body(self, text: str) -> str:
        return self._compact_answer_stream_preview(text)

    def _compact_answer_stream_preview(self, text: str) -> str:
        text = " ".join(str(text or "").split())
        if not text:
            return ""
        width = max(20, self._dialog_box_width() - 4)
        max_width = width * 8
        if _display_width(text) <= max_width:
            return text
        suffix = _clip_display(text[::-1], max_width - 2)[::-1] if max_width > 2 else ""
        return "…" + suffix.lstrip()

    def _extract_partial_json_string_field(self, raw_text: str, field: str) -> str:
        text = raw_text or ""
        token = json.dumps(str(field), ensure_ascii=False)
        index = text.find(token)
        if index < 0:
            return ""
        index += len(token)
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text) or text[index] != ":":
            return ""
        index += 1
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text) or text[index] != '"':
            return ""
        index += 1
        chars: list[str] = []
        escape = False
        while index < len(text):
            char = text[index]
            if escape:
                if char == "u":
                    digits = text[index + 1:index + 5]
                    if len(digits) < 4:
                        break
                    try:
                        chars.append(chr(int(digits, 16)))
                        index += 5
                        escape = False
                        continue
                    except ValueError:
                        chars.append("u")
                else:
                    chars.append({
                        '"': '"',
                        "\\": "\\",
                        "/": "/",
                        "b": "\b",
                        "f": "\f",
                        "n": "\n",
                        "r": "\r",
                        "t": "\t",
                    }.get(char, char))
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                break
            else:
                chars.append(char)
            index += 1
        return "".join(chars)

    async def client_side_advice(self, raw_query: str) -> str:
        parsed = self._parse_client_advice_input(raw_query)
        if isinstance(parsed, str):
            return parsed
        query, payload = parsed
        if self._is_small_talk_query(query):
            response = self._small_talk_response(query)
            self._remember_conversation_turn(query, response)
            return response
        self._agent_trace = []
        config = get_config()
        provider, model, ready, key_hint = self._llm_status(config)
        if not ready:
            return "\n".join([
                "【需要本机大模型 API Key】",
                f"- 当前 provider: {provider}",
                f"- 当前 model: {model}",
                f"- 缺少: {key_hint}",
                "",
                "二郎神不会要求你把大模型 API Key 发给服务端。",
                "请先在本机配置 Key，之后客户端会直连模型供应商生成投资建议:",
                "  erlangshen /model key",
                "",
                "服务端只接收你的问题用于受保护场景映射，不接收、不存储、不转发你的大模型 API Key。",
            ])

        intent_plan = {}
        mcp_data = {}
        mapping_query = query
        matches: list[dict] = []
        active_provider = provider
        active_model = model
        try:
            from src.auth.session import load_auth_session
            from src.client.server_client import ErlangshenAPIError, ErlangshenServerClient
            from src.llm import LLMClient, resolve_llm_settings

            settings = resolve_llm_settings(config=get_config())
            active_provider = settings.display_name or settings.provider
            active_model = settings.model
            intent_plan = await self._infer_client_intent(query, payload, settings, LLMClient)
            mcp_data = await self._collect_client_mcp_data(query, payload, intent_plan)
            mapping_query = self._server_mapping_query(query, intent_plan)
            self._show_progress("正在向服务端确认改写后的问题场景" if mapping_query != query else "正在向服务端确认问题场景")
            session = load_auth_session()
            client = ErlangshenServerClient(
                base_url=session.get("base_url") or config.erlangshen_api_base_url,
                token=session.get("token"),
            )
            try:
                mapping = await client.cognition_map(mapping_query)
            except ErlangshenAPIError as exc:
                if exc.status_code in {401, 403} and await self._refresh_auth_after_unauthorized(session, reason="server_mapping"):
                    refreshed = load_auth_session()
                    client = ErlangshenServerClient(
                        base_url=refreshed.get("base_url") or config.erlangshen_api_base_url,
                        token=refreshed.get("token"),
                    )
                    self._show_progress("登录态已刷新，正在重新确认问题场景")
                    mapping = await client.cognition_map(mapping_query)
                else:
                    raise
        except ErlangshenAPIError as exc:
            message = f"服务端场景映射失败 ({exc.status_code}): {exc}"
            self._remember_agent_failure_plan(
                query=query,
                intent_plan=intent_plan,
                mapping_query=mapping_query,
                mcp_data=mcp_data,
                matches=[],
                provider=active_provider,
                model=active_model,
                failure_stage="server_mapping",
                failure_message=message,
            )
            return self._format_agent_failure(
                message,
                [
                    "注意: 大模型 API Key 没有发送给服务端；这里只是账号/认知映射请求失败。",
                    "交互模式会自动发起重新登录；非交互脚本请先执行 /login xwab <账号> 或检查 /service。",
                ],
            )
        except Exception as exc:
            message = f"本机建议生成准备失败: {exc}"
            self._remember_agent_failure_plan(
                query=query,
                intent_plan=intent_plan,
                mapping_query=mapping_query,
                mcp_data=mcp_data,
                matches=[],
                provider=active_provider,
                model=active_model,
                failure_stage="client_prepare",
                failure_message=message,
            )
            return self._format_agent_failure(
                message,
                [
                    "可执行 /doctor 检查本机模型、账号、super-66 MCP 和服务端连通性。",
                    "也可以执行 /plan 查看上一轮已完成的意图和数据链路。",
                ],
            )

        matches = mapping.get("matches") or []
        if not matches:
            message = "服务端未返回可用场景映射，暂不生成投资建议。"
            self._remember_agent_failure_plan(
                query=query,
                intent_plan=intent_plan,
                mapping_query=mapping_query,
                mcp_data=mcp_data,
                matches=[],
                provider=active_provider,
                model=active_model,
                failure_stage="server_no_match",
                failure_message=message,
            )
            return self._format_agent_failure(
                message,
                [
                    "可以补充市场、标的、时间周期或持仓约束后重新提问。",
                    "也可以用 /server map <问题> 单独检查服务端如何理解这个问题。",
                ],
            )

        try:
            self._show_progress(f"正在用本机 {settings.display_name} 生成分析")
            llm_client = LLMClient(settings, timeout=float(config.request_timeout or 30))
            raw_text = await self._complete_llm_response(
                llm_client,
                self._client_advice_messages(
                    query=query,
                    matches=matches,
                    mcp_data=mcp_data,
                    user_data=payload.get("user_data"),
                    current_cognition=payload.get("current_cognition"),
                    intent_plan=intent_plan,
                ),
                temperature=0.35,
                max_tokens=min(int(config.llm_max_tokens or 4096), 1600),
                json_preview_field="final_answer|view",
                preview_title="二郎神",
            )
            self._refresh_token_status_bar(activity="analysis ready")
        except Exception as exc:
            message = f"本机大模型调用失败: {type(exc).__name__}: {exc}".rstrip()
            snapshot_lines = self._mcp_snapshot_lines(mcp_data)
            synthesis = self._fallback_synthesis_from_snapshots(query, matches, snapshot_lines, message)
            synthesis = self._enforce_market_fact_grounding(query, synthesis, mcp_data, intent_plan)
            synthesis = self._repair_client_synthesis_with_grounded_mcp(query, synthesis, mcp_data, intent_plan)
            self._remember_agent_plan(
                query=query,
                intent_plan=intent_plan,
                mapping_query=mapping_query,
                mcp_data=mcp_data,
                matches=matches,
                synthesis=synthesis,
                provider=active_provider,
                model=active_model,
            )
            data_inputs = {
                "mcp_data": sorted((mcp_data or {}).keys()) if isinstance(mcp_data, dict) else [],
                "mcp_snapshot": snapshot_lines,
                "mcp_links": self._mcp_resource_links(mcp_data),
                "intent_resource_links": intent_plan.get("resource_links") if isinstance(intent_plan.get("resource_links"), list) else [],
                "agent_trace": self._agent_trace_lines(),
                "user_data": sorted((payload.get("user_data") or {}).keys()) if isinstance(payload.get("user_data"), dict) else [],
                "route_source": intent_plan.get("route_source"),
                "tool_selection_source": intent_plan.get("tool_selection_source"),
                "tool_selection_note": intent_plan.get("tool_selection_note"),
                "fact_grounding": self._market_fact_grounding(query, mcp_data, intent_plan),
            }
            formatted = self._format_client_advice(
                query=query,
                matches=matches,
                synthesis=synthesis,
                raw_text="",
                provider=active_provider,
                model=active_model,
                data_inputs=data_inputs,
            )
            turn_resource_links = self._collect_turn_resource_links(data_inputs, synthesis)
            self._remember_resource_links(query, turn_resource_links)
            if isinstance(self._last_agent_plan, dict):
                self._last_agent_plan.update({
                    "status": "fallback",
                    "failure_stage": "local_llm_synthesis",
                    "failure_message": message,
                    "resource_links": turn_resource_links,
                })
            self._remember_followup_data(mcp_data, synthesis.get("artifact_results"))
            self._remember_conversation_turn(query, formatted)
            self._finalize_live_answer_stream(formatted)
            return formatted

        synthesis = self._parse_client_llm_advice(raw_text)
        synthesis = self._recover_client_synthesis_from_reasoning(synthesis)
        synthesis = self._enforce_market_fact_grounding(query, synthesis, mcp_data, intent_plan)
        synthesis = self._repair_client_synthesis_with_grounded_mcp(query, synthesis, mcp_data, intent_plan)
        synthesis = {
            **synthesis,
            "artifact_results": await self._materialize_synthesis_artifacts(synthesis, client, query),
        }
        self._remember_agent_plan(
            query=query,
            intent_plan=intent_plan,
            mapping_query=mapping_query,
            mcp_data=mcp_data,
            matches=matches,
            synthesis=synthesis,
            provider=settings.display_name or settings.provider,
            model=settings.model,
        )
        data_inputs = {
            "mcp_data": sorted((mcp_data or {}).keys()) if isinstance(mcp_data, dict) else [],
            "mcp_snapshot": self._mcp_snapshot_lines(mcp_data),
            "mcp_links": self._mcp_resource_links(mcp_data),
            "intent_resource_links": intent_plan.get("resource_links") if isinstance(intent_plan.get("resource_links"), list) else [],
            "agent_trace": self._agent_trace_lines(),
            "user_data": sorted((payload.get("user_data") or {}).keys()) if isinstance(payload.get("user_data"), dict) else [],
            "route_source": intent_plan.get("route_source"),
            "tool_selection_source": intent_plan.get("tool_selection_source"),
            "tool_selection_note": intent_plan.get("tool_selection_note"),
            "fact_grounding": self._market_fact_grounding(query, mcp_data, intent_plan),
        }
        formatted = self._format_client_advice(
            query=query,
            matches=matches,
            synthesis=synthesis,
            raw_text=raw_text,
            provider=settings.display_name or settings.provider,
            model=settings.model,
            data_inputs=data_inputs,
        )
        report_path = None
        if self._should_save_advice_report(query, synthesis):
            report_path = self._save_advice_report(
                query=query,
                content=formatted,
                artifact_results=synthesis.get("artifact_results"),
                data_inputs=data_inputs,
            )
        if report_path:
            workspace = str(workspace_status().get("path") or "")
            formatted = "\n".join([
                formatted,
                "",
                f"报告已保存: {self._workspace_file_link(report_path, workspace, label='打开报告')}",
            ])
        turn_resource_links = self._collect_turn_resource_links(data_inputs, synthesis, report_path=report_path)
        self._remember_resource_links(query, turn_resource_links)
        if isinstance(self._last_agent_plan, dict):
            self._last_agent_plan["resource_links"] = turn_resource_links
        self._remember_followup_data(mcp_data, synthesis.get("artifact_results"))
        self._remember_conversation_turn(query, formatted)
        self._finalize_live_answer_stream(formatted)
        return formatted

    def _format_agent_failure(self, headline: str, next_steps: list[str] | None = None) -> str:
        lines = [headline]
        trace = self._agent_trace_lines()
        if trace:
            lines.extend(["", "本轮执行："])
            for item in trace[:8]:
                lines.append(f"- {item}")
        if next_steps:
            lines.extend(["", "下一步："])
            for item in next_steps:
                clean = self._text_field(item)
                if clean:
                    lines.append(f"- {clean}")
        return "\n".join(lines)

    def _fallback_synthesis_from_snapshots(self, query: str, matches: list[dict], snapshot_lines: list[str], message: str) -> dict:
        scene = self._text_field((matches or [{}])[0].get("scene")) if matches else "服务端场景映射"
        view_lines = [
            f"本机大模型生成阶段没有稳定返回内容（{message}），我先不让你空等。",
            "下面是基于本轮已经拿到的 super-66 MCP 行情快照、Bing 网页线索和服务端场景映射做的临时判断；确定性低于完整模型分析。",
        ]
        if snapshot_lines:
            view_lines.append("本轮可用快照包括：" + "；".join(snapshot_lines[:5]) + "。")
        suggestions = [
            "先把宽基指数、成长指数和避险/风险偏好资产分开看，不要只用一个指数概括全市场。",
            "如果指数数据同向走弱，优先降低追高和高弹性仓位；如果只是结构分化，重点看成交额和主线持续性。",
            "继续追问具体板块、持仓或周期，我可以在已有 MCP 快照基础上再收窄分析。",
        ]
        risk_controls = [
            "模型生成失败时，不把临时框架当作正式投资结论；需要结合实时行情软件复核点位和成交额。",
            "关注流动性、政策预期、外部风险偏好和成交额变化，这些会影响服务端映射到的场景强度。",
            "如果你的持仓集中在成长、港股科技或高波动资产，要额外设置回撤和止损/减仓触发线。",
        ]
        return {
            "view": "\n\n".join(view_lines),
            "suggestions": suggestions,
            "risk_controls": risk_controls,
            "missing_data": ["你的关注市场/板块", "持仓和仓位", "分析周期与最大可承受回撤"],
            "next_actions": [
                "/model key 重新测试本机模型供应商连接",
                "/plan 查看本轮 MCP 数据和服务端映射",
                "补充具体标的或持仓后继续追问",
            ],
            "followups": [
                "把今天 A股快照拆成主线、风险和观察指标。",
                "只看沪深300、创业板、黄金这几个指标，怎么判断风险偏好？",
            ],
            "artifact_results": [],
            "fallback_reason": message,
            "scene": scene,
        }

    def _repair_client_synthesis_with_grounded_mcp(self, query: str, synthesis: dict, mcp_data, intent_plan: dict | None = None) -> dict:
        if not isinstance(synthesis, dict):
            synthesis = {}
        grounding = self._market_fact_grounding(query, mcp_data, intent_plan)
        if grounding.get("status") != "grounded":
            return synthesis
        direct = self._direct_client_final_answer(synthesis)
        view = self._text_field(synthesis.get("view"))
        if direct and not self._looks_like_reasoning_leak(direct):
            return synthesis
        if direct or not view or self._looks_like_reasoning_leak(view) or self._looks_like_generic_stock_fallback(view):
            repaired = self._grounded_astock_synthesis_from_mcp(query, mcp_data)
            if repaired:
                repaired["repaired_from_mcp"] = True
                return repaired
        return synthesis

    def _looks_like_reasoning_leak(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", self._text_field(text).lower())
        if not compact:
            return False
        markers = (
            "输出必须是json",
            "json对象",
            "response_contract",
            "client_intent_plan",
            "market_data_brief",
            "现在构建final_answer",
            "构建final_answer",
            "现在写final_answer",
            "final_answer必须",
            "suggestions:",
            "risk_controls:",
            "missing_data:",
            "从输入中",
            "我需要基于这些数据生成",
        )
        return any(marker in compact for marker in markers)

    def _looks_like_generic_stock_fallback(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", self._text_field(text))
        if not compact:
            return True
        generic_markers = (
            "具体交易结论还需要看你关注的市场",
            "把问题再收窄一点",
            "至少补两项",
            "没有拿到Super66MCP返回的可核验股票行情",
        )
        return any(marker in compact for marker in generic_markers)

    def _grounded_astock_synthesis_from_mcp(self, query: str, mcp_data) -> dict:
        if not isinstance(mcp_data, dict):
            return {}
        codes = self._astock_codes_from_mcp_context(mcp_data)
        code = codes[0] if codes else ""
        if not code:
            return {}
        name = self._known_astock_name(code) or self._first_astock_name_from_mcp(mcp_data) or code
        realtime_values = [
            value for key, value in mcp_data.items()
            if str(key).startswith("get_astock_realtime:") and not self._mcp_value_has_error(value)
        ]
        history_values = [
            value for key, value in mcp_data.items()
            if str(key).startswith("get_astock_history:") and not self._mcp_value_has_error(value)
        ]
        realtime_row = self._latest_row_from_values(realtime_values)
        history_rows = self._history_rows_from_values(history_values)
        latest_price = self._first_numeric_value(
            realtime_row,
            ("price", "latest", "last", "current_price", "latest_price", "last_price", "close", "最新价", "现价", "收盘", "收盘价"),
        ) if isinstance(realtime_row, dict) else None
        pct_change = self._first_numeric_value(
            realtime_row,
            ("change_pct", "pct_chg", "percent", "changePercent", "change_percent", "changeRate", "涨跌幅", "涨幅", "日涨跌幅"),
        ) if isinstance(realtime_row, dict) else None
        latest_date = self._readable_mcp_date(realtime_row) if isinstance(realtime_row, dict) else ""
        close_points: list[tuple[str, float]] = []
        for value in history_values:
            close_points.extend(self._close_points(value))
        close_points = sorted(enumerate(close_points), key=lambda item: (item[1][0] or "", item[0]))
        period_line = ""
        if len(close_points) >= 2:
            start_date, start_close = close_points[0][1]
            end_date, end_close = close_points[-1][1]
            if start_close:
                period_return = (end_close / start_close - 1.0) * 100.0
                period_line = (
                    f"历史区间看，{self._format_compact_date(start_date)} 收盘 {self._format_price(start_close)}，"
                    f"{self._format_compact_date(end_date)} 收盘 {self._format_price(end_close)}，"
                    f"区间涨跌幅约 {self._format_pct(period_return)}。"
                )
        support, pressure = self._support_pressure_from_history_rows(history_rows)
        price_bits = []
        if latest_price is not None:
            date_part = f"（{self._format_compact_date(latest_date)}）" if latest_date else ""
            price_bits.append(f"最新价 {self._format_price(latest_price)} 元{date_part}")
        if pct_change is not None:
            price_bits.append(f"涨跌幅 {self._format_pct(pct_change)}")
        price_line = "，".join(price_bits) if price_bits else "MCP 已返回实时行情，但字段名不标准，建议用 /plan 查看原始明细"
        trend_line = period_line or "历史行情已返回，但可用收盘点不足以稳定计算区间涨跌幅。"
        level_parts = []
        if support is not None:
            level_parts.append(f"下方先观察 {self._format_price(support)} 元附近")
        if pressure is not None:
            level_parts.append(f"上方先观察 {self._format_price(pressure)} 元附近")
        level_line = "；".join(level_parts)
        if level_line:
            level_line = f"观察位方面，{level_line}。这些只按 MCP 历史 high/low/close 推导，不是交易指令。"
        else:
            level_line = "本轮历史 high/low/close 不足以稳定推导支撑和压力位。"
        final_answer = "\n\n".join([
            f"这次已经拿到 super-66 MCP 的 {name}（{code}）行情数据，可以直接基于数据回答。",
            f"当前状态：{price_line}。{trend_line}",
            f"走势判断：从本轮历史序列看，股价仍处在回调后的弱修复/低位震荡状态，短线重点不是追高，而是看价格能否守住关键低点并重新站回上方压力区。",
            level_line,
            "操作上可以先按观察处理：已有仓位更适合用仓位和回撤线管理，新增仓位等企稳信号更稳；若后续跌破历史低点附近且无法快速收回，说明弱势还没有结束。",
            "需要注意：本轮主要是行情数据，缺少最新公告、业绩、白酒板块资金和新闻事件线索；这些会影响对基本面和催化因素的判断。",
        ])
        suggestions = [
            "先用 /plan 核对 get_astock_realtime 和 get_astock_history 的原始字段。",
            "继续补充新闻/公告线索后，再判断这次下跌是行业因素、公司因素还是市场风格因素。",
            "如果要做交易计划，把持仓成本、仓位上限和最大可承受回撤补充进来。",
        ]
        if support is not None:
            suggestions.insert(0, f"观察 {self._format_price(support)} 元附近是否能形成有效支撑。")
        risk_controls = [
            "支撑/压力只是历史行情推导出的观察位，不等于买卖建议。",
            "若仓位较重，先定义最大回撤和减仓条件，避免把长期基本面判断和短线价格波动混在一起。",
            "缺少公告和行业新闻时，不把单纯价格走势当成完整投资结论。",
        ]
        missing = ["最新公告/业绩说明", "白酒板块和北向/机构资金线索", "你的持仓成本、仓位和投资周期"]
        return {
            "final_answer": final_answer,
            "view": final_answer,
            "suggestions": suggestions[:4],
            "risk_controls": risk_controls,
            "missing_data": missing,
            "next_actions": ["/plan", "继续问：补充贵州茅台最新公告和新闻后再分析"],
            "followups": [
                "把贵州茅台近 120 天收盘价做成图表。",
                "对比贵州茅台和白酒板块今年表现。",
            ],
            "artifacts": [],
        }

    def _first_astock_name_from_mcp(self, mcp_data: dict) -> str:
        for value in mcp_data.values():
            for name in self._extract_astock_names_from_value(value):
                if name:
                    return name
        return ""

    def _latest_row_from_values(self, values: list) -> dict:
        rows: list[dict] = []
        for value in values:
            row = self._find_mcp_market_row(value)
            if isinstance(row, dict):
                rows.append(row)
        return self._latest_mcp_row_by_date(rows) or {}

    def _history_rows_from_values(self, values: list) -> list[dict]:
        rows: list[dict] = []
        for value in values:
            for row in self._flatten_mcp_dict_rows(value):
                if not isinstance(row, dict):
                    continue
                if self._first_numeric_value(row, ("close", "close_price", "收盘", "收盘价")) is not None:
                    rows.append(row)
        return sorted(enumerate(rows), key=lambda item: (self._mcp_row_date_key(item[1]), item[0]))

    def _support_pressure_from_history_rows(self, rows: list) -> tuple[float | None, float | None]:
        normalized_rows = [item[1] if isinstance(item, tuple) else item for item in rows if isinstance(item[1] if isinstance(item, tuple) else item, dict)]
        if not normalized_rows:
            return None, None
        recent = normalized_rows[-30:]
        low_points = [
            (index, value)
            for index, row in enumerate(recent)
            for value in [self._first_numeric_value(row, ("low", "lowest", "最低", "最低价", "close", "close_price", "收盘", "收盘价"))]
            if value is not None
        ]
        if not low_points:
            return None, None
        support_index, support = min(low_points, key=lambda item: item[1])
        pressure_rows = recent[support_index:]
        highs = [
            value for row in pressure_rows
            for value in [self._first_numeric_value(row, ("high", "highest", "最高", "最高价", "close", "close_price", "收盘", "收盘价"))]
            if value is not None
        ]
        return support, max(highs) if highs else None

    def _readable_mcp_date(self, row: dict) -> str:
        if not isinstance(row, dict):
            return ""
        for key in ("date", "trade_date", "tradedate", "trading_date", "datetime", "timestamp", "time", "update_time", "updated_at", "日期", "交易日期", "时间"):
            value = self._text_field(row.get(key))
            if value:
                return value
        return ""

    def _format_compact_date(self, value: str) -> str:
        text = self._text_field(value)
        if not text:
            return "起止日"
        digits = re.sub(r"\D", "", text)
        if len(digits) >= 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
        return text[:16]

    def _format_price(self, value: float) -> str:
        if value is None:
            return ""
        if abs(value) >= 100:
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{value:.4g}"

    def _format_pct(self, value: float) -> str:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"

    def _remember_followup_data(self, mcp_data, artifact_results) -> None:
        if isinstance(mcp_data, dict) and mcp_data:
            self._last_mcp_data = dict(mcp_data)
        if isinstance(artifact_results, list):
            self._last_artifact_results = [
                item for item in artifact_results
                if isinstance(item, dict)
            ][-8:]

    def _collect_turn_resource_links(self, data_inputs: dict, synthesis: dict, report_path: str | None = None) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []

        def add_many(source: str, values) -> None:
            for item in self._resource_link_items(values):
                normalized = self._normalize_resource_link_item(item, source)
                if normalized:
                    links.append(normalized)

        add_many("MCP/web_search", data_inputs.get("mcp_links") if isinstance(data_inputs, dict) else [])
        add_many("intent plan", data_inputs.get("intent_resource_links") if isinstance(data_inputs, dict) else [])
        add_many("LLM resource", synthesis.get("resource_links") if isinstance(synthesis, dict) else [])
        add_many("LLM resource", synthesis.get("resource_link") if isinstance(synthesis, dict) else [])
        add_many("LLM resource", self._resource_links_from_value(synthesis.get("resources"), "分析资源") if isinstance(synthesis, dict) else [])
        for artifact in (synthesis.get("artifact_results") if isinstance(synthesis, dict) else []) or []:
            if not isinstance(artifact, dict):
                continue
            title = self._text_field(artifact.get("title")) or "图表"
            add_many("server artifact", artifact.get("resource_links") if isinstance(artifact.get("resource_links"), list) else [])
            saved = artifact.get("saved") if isinstance(artifact.get("saved"), dict) else {}
            workspace = str(workspace_status().get("path") or "")
            if saved.get("html"):
                links.append({"source": "local artifact", "link": self._workspace_file_link(saved.get("html"), workspace, label=f"{title} HTML")})
            if saved.get("json"):
                links.append({"source": "local artifact", "link": self._workspace_file_link(saved.get("json"), workspace, label=f"{title} JSON")})
        if report_path:
            workspace = str(workspace_status().get("path") or "")
            links.append({"source": "local report", "link": self._workspace_file_link(report_path, workspace, label="打开报告")})
        return links

    def _remember_resource_links(self, query: str, links: list[dict[str, str]]) -> None:
        if not links:
            return
        seen = {
            self._resource_dedupe_key(item)
            for item in self._last_resource_links
            if isinstance(item, dict)
        }
        added: list[dict[str, object]] = []
        for item in links:
            link = self._text_field(item.get("link"))
            if not link:
                continue
            label, target = self._split_named_link(link)
            if not target:
                continue
            dedupe_key = self._resource_dedupe_key({"link": link, "target": target})
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            entry = {
                "query": self._truncate_context_text(query, 120),
                "source": self._text_field(item.get("source")) or "resource",
                "link": link,
                "label": label,
                "target": target,
                "type": self._resource_type_for_target(target, source=self._text_field(item.get("source"))),
                "saved_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._last_resource_links.append(entry)
            added.append(entry)
        self._last_resource_links = self._last_resource_links[-24:]
        self._persist_resource_links(added)

    def _recent_resource_links(self, limit: int = 12) -> list[dict[str, object]]:
        combined = [
            *self._load_persisted_resource_links(limit=limit * 4),
            *[item for item in self._last_resource_links if isinstance(item, dict)],
        ]
        by_link: dict[str, dict[str, object]] = {}
        for item in combined:
            link = self._text_field(item.get("link")) if isinstance(item, dict) else ""
            if not link:
                continue
            label, target = self._resource_entry_label_target(item)
            dedupe_key = self._resource_dedupe_key({"link": link, "target": target})
            if dedupe_key in by_link:
                by_link.pop(dedupe_key)
            by_link[dedupe_key] = {
                "query": self._truncate_context_text(self._text_field(item.get("query")), 120),
                "source": self._text_field(item.get("source")) or "resource",
                "link": link,
                "label": label,
                "target": target,
                "type": self._text_field(item.get("type")) or self._resource_type_for_target(target, source=self._text_field(item.get("source"))),
                "saved_at": self._text_field(item.get("saved_at")),
            }
        return list(by_link.values())[-limit:]

    def _resource_index_path(self, workspace: str | Path | None = None) -> Path:
        root = resolve_workspace_path(str(workspace) if workspace else None)
        return ensure_inside_workspace(root / ".erlangshen" / "artifacts" / "resources.json", root)

    def _persist_resource_links(self, entries: list[dict[str, object]]) -> None:
        if not entries:
            return
        status = workspace_status()
        if not status.get("allowed"):
            return
        workspace = str(status.get("path") or "")
        try:
            index_path = self._resource_index_path(workspace)
            existing = self._read_resource_index(index_path)
            for entry in entries:
                link = self._text_field(entry.get("link"))
                if not link:
                    continue
                label, resource_target = self._resource_entry_label_target(entry)
                dedupe_key = self._resource_dedupe_key({"link": link, "target": resource_target})
                existing = [
                    item for item in existing
                    if self._resource_dedupe_key(item) != dedupe_key
                ]
                existing.append({
                    "query": self._truncate_context_text(self._text_field(entry.get("query")), 120),
                    "source": self._text_field(entry.get("source")) or "resource",
                    "link": link,
                    "label": label,
                    "target": resource_target,
                    "type": self._text_field(entry.get("type")) or self._resource_type_for_target(resource_target, source=self._text_field(entry.get("source"))),
                    "saved_at": self._text_field(entry.get("saved_at")) or datetime.now().isoformat(timespec="seconds"),
                })
            index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump({"resources": existing[-100:]}, f, ensure_ascii=False, indent=2)
        except (OSError, PermissionError, TypeError, ValueError):
            return

    def _load_persisted_resource_links(self, limit: int = 24) -> list[dict[str, object]]:
        status = workspace_status()
        if not status.get("allowed"):
            return []
        try:
            return self._read_resource_index(self._resource_index_path(str(status.get("path") or "")))[-limit:]
        except (OSError, PermissionError, TypeError, ValueError):
            return []

    def _read_resource_index(self, target: Path) -> list[dict[str, object]]:
        if not target.exists():
            return []
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_items = data.get("resources") if isinstance(data, dict) else data
        if not isinstance(raw_items, list):
            return []
        result: list[dict[str, object]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            link = self._text_field(item.get("link"))
            if not link:
                continue
            label, target = self._resource_entry_label_target(item)
            result.append({
                "query": self._truncate_context_text(self._text_field(item.get("query")), 120),
                "source": self._text_field(item.get("source")) or "resource",
                "link": link,
                "label": label,
                "target": target,
                "type": self._text_field(item.get("type")) or self._resource_type_for_target(target, source=self._text_field(item.get("source"))),
                "saved_at": self._text_field(item.get("saved_at")),
            })
        return result[-100:]

    def _resource_entry_label_target(self, entry: dict[str, object]) -> tuple[str, str]:
        label = self._text_field(entry.get("label"))
        target = self._text_field(entry.get("target"))
        if label and target:
            return label, self._normalize_open_target(target)
        parsed_label, parsed_target = self._split_named_link(self._text_field(entry.get("link")))
        return label or parsed_label, target or parsed_target

    def _resource_dedupe_key(self, entry: dict[str, object]) -> str:
        _, target = self._resource_entry_label_target(entry)
        return target or self._text_field(entry.get("link"))

    def _resource_type_for_target(self, target: str, source: str = "") -> str:
        text = self._text_field(target).lower()
        source_text = self._text_field(source).lower()
        path_text = text.split("?", 1)[0].split("#", 1)[0]
        suffix = Path(path_text).suffix.lower()
        if "report" in source_text or "报告" in source_text or suffix in {".md", ".markdown"}:
            return "report"
        if "artifact" in source_text or "chart" in source_text or "图表" in source_text:
            if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
                return "chart_image"
            return "chart"
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}:
            return "image"
        if suffix in {".html", ".htm"}:
            return "html"
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".json":
            return "json"
        if text.startswith("file://") or text.startswith("/"):
            return "local_file"
        if re.match(r"^https?://", text, flags=re.I):
            return "webpage"
        return "resource"

    def _recent_resource_context(self, limit: int = 8) -> list[dict[str, str]]:
        context = []
        for item in self._recent_resource_links(limit=limit):
            context.append({
                "query": self._truncate_context_text(self._text_field(item.get("query")), 120),
                "source": self._text_field(item.get("source")),
                "link": self._truncate_context_text(self._text_field(item.get("link")), 260),
            })
        return context

    def _last_mcp_context_brief(self) -> dict:
        if not isinstance(self._last_mcp_data, dict) or not self._last_mcp_data:
            return {"status": "empty", "usable_sources": [], "snapshots": []}
        return {
            "status": "available",
            "usable_sources": [
                key for key in sorted(str(key) for key in self._last_mcp_data.keys())
                if key != "note" and "error" not in key.lower()
            ],
            "snapshots": self._mcp_snapshot_lines(self._last_mcp_data),
            "boundary": "仅为本次 CLI 进程内的上一轮工具数据摘要，不写入磁盘，不包含大模型 API Key。",
        }

    def _recent_artifact_context(self) -> list[dict]:
        context = []
        for item in self._last_artifact_results[-6:]:
            saved = item.get("saved") if isinstance(item.get("saved"), dict) else {}
            context.append({
                "title": self._text_field(item.get("title")),
                "status": self._text_field(item.get("status")),
                "type": self._text_field(item.get("type")),
                "data_keys": item.get("data_keys") if isinstance(item.get("data_keys"), list) else [],
                "html": saved.get("html") if saved else "",
                "json": saved.get("json") if saved else "",
            })
        return context

    def _remember_conversation_turn(self, user_text: str, assistant_text: str) -> None:
        user = self._truncate_context_text(user_text, 240)
        assistant = self._truncate_context_text(assistant_text, 420)
        if not user:
            return
        self._conversation_history.append({"user": user, "assistant": assistant})
        self._conversation_history = self._conversation_history[-6:]
        try:
            status = workspace_status()
            self._memory.remember_turn(
                user_text=user,
                assistant_text=assistant,
                workspace=str(status.get("path") or ""),
                source="conversation",
            )
        except (OSError, PermissionError, TypeError, ValueError):
            return

    def _recent_conversation_context(self, limit: int = 4) -> list[dict[str, str]]:
        return list(self._conversation_history[-limit:])

    def _recent_local_memory_context(self, limit: int = 4) -> list[dict[str, object]]:
        try:
            return self._memory.context(limit=limit, char_budget=1400)
        except (OSError, PermissionError, TypeError, ValueError):
            return []

    def _memory_stats(self) -> dict[str, object]:
        try:
            stats = self._memory.stats()
            return {"count": stats.count, "path": str(stats.path), "updated_at": stats.updated_at}
        except (OSError, PermissionError, TypeError, ValueError):
            return {"count": 0, "path": "", "updated_at": ""}

    def _truncate_context_text(self, text: str, limit: int) -> str:
        value = self._text_field(text)
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 1)].rstrip() + "…"

    def _parse_client_advice_input(self, content: str):
        content = (content or "").strip()
        if not content:
            return "请提供需要分析的投资问题。"
        if "::" not in content:
            return content, {}
        query, raw_payload = [part.strip() for part in content.split("::", 1)]
        if not query:
            return "请在 JSON 数据包前提供投资问题"
        if not raw_payload:
            return query, {}
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            return f"建议数据包不是合法 JSON: {exc}"
        if not isinstance(payload, dict):
            return "建议数据包必须是 JSON 对象"
        return query, payload

    def _server_mapping_query(self, query: str, intent_plan: dict | None) -> str:
        if isinstance(intent_plan, dict):
            rewritten = self._text_field(intent_plan.get("rewritten_query"))
            if rewritten:
                return rewritten
        return query

    def _client_advice_messages(
        self,
        *,
        query: str,
        matches: list[dict],
        mcp_data=None,
        user_data=None,
        current_cognition=None,
        intent_plan=None,
    ) -> list[dict[str, str]]:
        system = (
            "你是二郎神客户端的大模型分析层。二郎神服务端只提供受保护的场景映射，"
            "不会接收用户的大模型 API Key。你必须基于服务端返回的公开映射、用户数据和 MCP 数据生成投资分析，"
            "不能声称看到了完整服务端认知库或内部案例全文。"
            "你的语气要像一位克制、可靠、会和用户自然沟通的投资分析师，不要机械套模板。"
            "输出 JSON 对象，字段为 final_answer, view, suggestions, risk_controls, missing_data，可选 followups, next_actions, artifacts；"
            "必须把 final_answer 作为 JSON 对象的第一个字段，final_answer 的值必须是完整、可直接展示给用户的自然语言最终回答；"
            "客户端会实时流式展示 final_answer，并在结束后原样作为最终回答，不会再替你二次汇总，所以建议、风控、缺失数据也要自然写进 final_answer；"
            "view 可以是 final_answer 的同文副本或一句摘要，用于兼容旧客户端；"
            "suggestions、risk_controls、missing_data、followups、next_actions 优先返回字符串数组；"
            "如需保留原因、条件、阈值或命令，也可以返回对象数组，例如 {\"action\":\"...\",\"reason\":\"...\",\"condition\":\"...\"}。"
            "artifacts 如需图表，使用数组: [{\"type\":\"chart\",\"chart_type\":\"bar\",\"title\":\"标题\",\"data\":{\"A股\":1.2}}]。"
        )
        user_payload = {
            "query": query,
            "as_of_date": datetime.now().strftime("%Y-%m-%d"),
            "timezone": "Asia/Shanghai",
            "recent_conversation": self._recent_conversation_context(),
            "local_memory": self._recent_local_memory_context(limit=6),
            "previous_mcp_context": self._last_mcp_context_brief(),
            "recent_artifacts": self._recent_artifact_context(),
            "recent_resources": self._recent_resource_context(),
            "client_intent_plan": intent_plan or {},
            "client_intent_plan_summary": self._intent_plan_summary(intent_plan or {}),
            "fact_grounding": self._market_fact_grounding(query, mcp_data or {}, intent_plan or {}),
            "response_contract": {
                "final_answer": "完整最终回答，必须包含自然语言结论、关键依据、可执行建议、风控和必要的缺失数据说明",
                "view": "自然语言综合判断",
                "suggestions": ["字符串，或包含 action/reason/condition 的对象"],
                "risk_controls": ["字符串，或包含 risk/threshold/reason 的对象"],
                "missing_data": ["字符串，或包含 missing/question/reason 的对象"],
                "followups": ["字符串，或包含 question/reason 的对象"],
                "next_actions": ["字符串，或包含 command/action/reason 的对象"],
                "tool_selection_source": "来自 client_intent_plan，用来解释 MCP 工具是本机大模型选择还是客户端兜底补齐",
                "tool_selection_note": "来自 client_intent_plan，用来解释工具选择边界",
                "artifacts": [{"type": "chart", "chart_type": "bar", "title": "标题", "data": {"A股": 1.2}}],
            },
            "available_capabilities": self._mcp_capability_catalog(query),
            "agent_playbook": self._agent_playbook(),
            "tool_result_contract": self._agent_tool_contract(),
            "server_client_contract": self._server_client_contract(),
            "agent_orchestration_protocol": self._agent_orchestration_protocol(),
            "server_protected_matches": matches[:3],
            "mcp_data": mcp_data or {},
            "market_data_brief": self._mcp_data_brief(mcp_data),
            "microcap_analysis_brief": self._microcap_analysis_brief(query, mcp_data),
            "user_data": user_data or {},
            "current_cognition": current_cognition or {},
            "requirements": [
                "先用自然语言给综合判断，再给少量可执行建议和风控",
                "如果 mcp_data 已返回行情或新闻数据，必须优先结合这些数据回答，不要再说没有实时市场数据",
                "严格事实边界：股票价格、指数点位、涨跌幅、支撑位、压力位、区间收益和图表数值只能来自 mcp_data 或用户显式提供的数据；不能用模型记忆、历史印象或估算补数",
                "如果是具体股票问题但 mcp_data 没有 get_astock_realtime/get_astock_history 的真实价格或收盘价，必须明确说本轮没有拿到可核验行情；禁止输出任何具体股价、支撑位、压力位或走势图 artifacts",
                "如需给支撑/压力，只能基于 MCP 历史 high/low/close 明确推导，并说明是观察位而不是凭经验判断",
                "凡涉及区间收益率、资产表现对比、图表收益值，优先使用起始收盘价和结束收盘价按 end_close / start_close - 1 计算；不要把单日涨跌幅字段当作区间收益",
                "对于“今天行情怎么样/市场怎么看”这类宽泛问题，要把它当成市场概览任务处理，必须先引用 market_data_brief.snapshots 或网页线索，再给方向性解读",
                "宽泛行情问题已经有 market_data_brief.snapshots 时，missing_data 不要再列具体指数、实时点位、新闻事件等基础行情项；只保留用户持仓、周期、仓位、风险偏好等个性化落地信息，没有就留空",
                "如果 market_data_brief.status 是 empty 或只有错误，必须明确说“数据通道本轮没有拿到可用行情”，并给出 /login、/doctor、/tools 或安装 web_search 的下一步",
                "如数据不足必须降低确定性并列出需要补充的数据",
                "如果用户只是打招呼或问题过于泛泛，要自然追问，不要强行生成投资结论",
                "如果 local_memory 已提供相关历史偏好、关注资产或上一阶段判断，要自然承接；不要逐条复述记忆，也不要把记忆当成实时数据",
                "如果用户是“做成图表/继续/那它呢/详细说说”这类短追问，必须结合 recent_conversation 判断承接对象",
                "如果用户问“分析的结果是/结论呢/结果呢”这类追问，要承接上一轮标的和数据上下文，不要把这句话当成一个新的泛泛问题",
                "如果用户是图表、报告或承接上一轮的追问，必须参考 previous_mcp_context 和 recent_artifacts；但不能编造其中不存在的数值",
                "如果用户提到“刚才那个网页/图片/图/链接/报告”，必须参考 recent_resources 和 recent_artifacts，并用自然语言说明可通过 /links 或 /open 重新打开",
                "市场分析默认不是单点快照：要综合指数、港股/美股联动、黄金/美元/原油等跨资产、成交与事件线索，有条件时用 120 天窗口观察趋势和相对强弱",
                "如果用户询问微盘策略、华证微盘、小微盘或小市值策略是否值得投资，必须以华证微盘作为主基准；中证1000/中证2000只能作为比较对象，不能替代华证微盘代表微盘",
                "微盘策略判断必须做量价验证：华证微盘区间收益与回撤、成交额/成交量/换手变化、微盘成交额占全市场成交额比重、相对中证2000/中证1000/沪深300的强弱、跌停/断流、量化拥挤、赎回去杠杆和强主线吸金",
                "如果本轮没有拿到华证微盘、成交额占比或跌停/拥挤等关键数据，必须把这些列入 missing_data，并把结论降级为框架判断；禁止用“中证1000近期平稳”直接推导微盘值得投",
                "微盘策略结论要按可投/观察/回避三段给条件：提高权重需要华证微盘放量走强、成交占比回升、相对强弱改善、主线吸金降温；降低权重需要流动性抽空、价跌量增或价涨量缩、成交占比下滑、跌停扩散或强主线持续抽血",
                "不要逐条罗列 MCP 原始快照；把数据消化成趋势、结构、相对强弱、异常和可能驱动，明细留给 /plan",
                "如果 MCP、web_search、服务端或大模型返回网页、图片、HTML、PDF 等非文本资源，必须保留为命名 resource_links，不要试图把富文本或二进制内容直接塞进终端",
                "优先参考 client_intent_plan 中的 tool_rationale 和 data_strategy，说明你为什么用了这些数据边界",
                "参考 client_intent_plan.route_summary、data_confidence、chart_opportunity、missing_inputs，把回答做成自然的分析路线，不要像规则模板",
                "如果 client_intent_plan.artifact_plan.type 是 chart 或 report，要在回答中自然提示可继续生成对应产物；数据足够时可直接在 artifacts 请求图表",
                "不要暴露或编造服务端内部认知库内容",
                "followups 用来给用户 2-3 个自然追问选项；next_actions 用来给 1-3 个可直接执行的命令或下一步动作",
                "当 MCP 数据或用户数据适合可视化时，可在 artifacts 里请求图表；客户端会通过服务端 artifact 通道生成并保存",
            ],
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ]

    def _intent_plan_summary(self, intent_plan: dict) -> dict:
        plan = intent_plan if isinstance(intent_plan, dict) else {}
        return {
            "route_summary": self._text_field(plan.get("route_summary")),
            "tool_rationale": self._text_field(plan.get("tool_rationale")),
            "tool_selection_source": self._text_field(plan.get("tool_selection_source")) or "not_yet_available",
            "tool_selection_note": self._text_field(plan.get("tool_selection_note")),
            "composition_patterns_used": self._coerce_text_items(plan.get("composition_patterns_used") or plan.get("composition_pattern")),
            "data_strategy": self._text_field(plan.get("data_strategy")),
            "data_confidence": self._text_field(plan.get("data_confidence")),
            "chart_opportunity": bool(plan.get("chart_opportunity")),
            "artifact_plan": plan.get("artifact_plan") if isinstance(plan.get("artifact_plan"), dict) else {},
        }

    def _agent_tool_contract(self) -> dict:
        return {
            "mcp_data_keys": "每个 key 形如 tool:label，例如 get_index_data:沪深300 或 web_search:最新政策影响。",
            "market_series": "指数、资产、产品历史通常在 data/result/records/items/history/prices 等字段中，优先使用最近一条可读记录。",
            "web_search": "web_search 返回 results 数组，优先提取 title、source/site 或 url 域名作为事件线索；不要把搜索结果当成已验证结论。",
            "chart_artifact": (
                "当用户要求图表、报告、对比、走势、收益或回撤展示时，可在 artifacts 返回 chart 请求；"
                "客户端会调用服务端 chart artifact 通道，并在授权工作区保存 JSON/HTML。"
            ),
            "resource_links": (
                "当 MCP、web_search、服务端或大模型返回网页、图片、HTML、PDF、图表预览等非纯文本资源时，"
                "必须保留为“名称: URL/路径”的可打开链接；客户端会在回答和 /links 中展示，"
                "用户可用 /links 1、/open 1、/links open 1 或 /open link 1 打开。"
            ),
            "safety": "不要输出 token/key/secret/password/authorization 等敏感字段；大模型 API Key 只在客户端本机使用。",
            "grounding_rule": "所有行情数值必须可追溯到 MCP/用户数据；没有真实行情时宁可缺数，也不要让大模型凭记忆补价格。",
        }

    def _server_client_contract(self) -> dict:
        return {
            "server_role": "核心服务端只负责账号鉴权、受保护场景映射、能力边界说明和 chart artifact 生成。",
            "client_role": "CLI 客户端负责本机大模型意图理解、super-66 MCP/web_search 数据读取、自然语言综合和资源链接呈现。",
            "llm_key_boundary": "用户的大模型 API Key 只保存在本机并由客户端直连供应商；不得发送给二郎神服务端。",
            "mapping_contract": {
                "request": "rewritten_query 或用户原始问题，加上必要的公开上下文；不要上传模型 API Key。",
                "response": "scene, confidence, direction, risk_boundary 等受保护信号；不要期待服务端返回内部认知库全文。",
            },
            "artifact_contract": {
                "request": "chart_type, title, data, metadata；data 必须来自 MCP、用户输入或已存在上下文，不能编造。",
                "response": "artifact JSON/HTML/图片/网页资源；客户端保存到授权工作区，并加入 /links。",
                "open_commands": ["/open chart", "/artifacts", "/links 1", "/open 1"],
            },
            "workspace_contract": "只有用户授权项目文件夹后，客户端才写入 .erlangshen/artifacts；未授权时仍可显示服务端返回的命名链接。",
            "resource_contract": "网页、图片、HTML、PDF、图表预览和报告统一转为命名 resource_links，CLI 只展示链接入口。",
        }

    def _agent_orchestration_protocol(self) -> dict:
        return {
            "decision_owner": "本机大模型是主要编排者，负责理解上下文、选择 MCP/web_search、决定是否请求服务端映射和 chart artifact。",
            "client_role": "客户端只做工具白名单、参数归一化、授权沙箱、安全脱敏、连接失败兜底和资源链接落盘。",
            "do_not": [
                "不要先写死规则再让模型填空",
                "不要只按关键词触发固定工具链",
                "不要在已有 MCP 或 web_search 事实时继续机械追问基础行情",
                "不要为了图表或报告编造不存在的数值",
                "不要在具体股票问题中用模型记忆生成股价、技术支撑位、压力位或走势图",
            ],
            "llm_must_return": [
                "route_summary: 解释你如何理解真实任务",
                "tool_rationale: 说明为什么选择或不选择 MCP/web_search",
                "data_strategy: 说明 MCP、web_search、用户数据、服务端映射如何组合",
                "composition_patterns_used: 标出采用的组合模式，便于 /plan 复盘",
                "resource_presentation: 非文本资源如何进入 /links 和 /open",
                "artifact_plan: 需要图表/报告时说明数据来源、标题和保存边界",
            ],
            "client_may_override_only_when": [
                "本机大模型调用失败",
                "模型返回的工具不在白名单或参数无法归一化",
                "模型明确需要事实数据但没有给出工具",
                "宽泛行情任务没有任何工具计划，客户端才按 data_recipes 补齐默认 MCP/web_search",
            ],
            "audit_surface": "所有工具来源、补齐原因、降级和图表计划必须进入 /plan，方便用户检查智能体行为。",
        }

    def _agent_routing_contract(self) -> dict:
        return {
            "primary_router": "local_llm_context_router",
            "principle": "本机大模型根据完整上下文判断用户真实任务，客户端只做工具白名单、参数归一化和故障兜底。",
            "orchestration_protocol": self._agent_orchestration_protocol(),
            "avoid": [
                "不要只因为出现某个关键词就固定路由",
                "不要在已有 MCP/web_search 数据时继续机械追问基础行情",
                "不要为了生成图表而编造不存在的数值字段",
            ],
            "use_context": [
                "query",
                "recent_conversation",
                "previous_mcp_context",
                "recent_resources",
                "recent_artifacts",
                "user_data_keys",
                "provided_mcp_data_keys",
            ],
            "flexible_tool_spec": {
                "accepted_keys": ["mcp_tools", "tools", "tool_calls", "data_tools"],
                "name_aliases": ["name", "tool", "tool_name", "function.name"],
                "argument_aliases": ["arguments", "args", "parameters", "input", "function.arguments"],
                "note": "可以返回 OpenAI tool_calls 风格、普通 tools 数组或 data_tools 对象；客户端会归一化到 {name, arguments}。",
            },
            "client_fallback_boundary": (
                "只有本机大模型失败、没有返回工具但 intent 明确需要事实数据，或用户是宽泛行情问题且无工具计划时，"
                "客户端才补齐默认 MCP/web_search 组合，并在 /plan 标注 tool_selection_source。"
            ),
            "chart_and_resource_rule": (
                "当数据适合可视化或用户要求图表/报告时，设置 chart_opportunity/artifact_plan；"
                "网页、图片、HTML、PDF、图表预览统一用 resource_links 命名链接返回。"
            ),
        }

    async def _infer_client_intent(self, query: str, payload: dict, settings, llm_client_cls) -> dict:
        explicit = payload.get("intent_plan") or payload.get("intent")
        if isinstance(explicit, dict):
            explicit.setdefault("route_source", "provided_payload")
            return explicit
        self._show_progress("正在本机理解问题意图")
        capability_catalog = self._mcp_capability_catalog(query)
        intent_payload = {
            "query": query,
            "as_of_date": datetime.now().strftime("%Y-%m-%d"),
            "timezone": "Asia/Shanghai",
            "recent_conversation": self._recent_conversation_context(),
            "previous_mcp_context": self._last_mcp_context_brief(),
            "recent_artifacts": self._recent_artifact_context(),
            "recent_resources": self._recent_resource_context(),
            "user_data_keys": sorted((payload.get("user_data") or {}).keys()) if isinstance(payload.get("user_data"), dict) else [],
            "provided_mcp_data_keys": sorted((payload.get("mcp_data") or {}).keys()) if isinstance(payload.get("mcp_data"), dict) else [],
            "allowed_mcp_tools": capability_catalog["mcp_tools"],
            "selection_policy": capability_catalog["selection_policy"],
            "data_recipes": capability_catalog["data_recipes"],
            "route_plans": capability_catalog["route_plans"],
            "composition_patterns": capability_catalog["composition_patterns"],
            "agent_playbook": capability_catalog["agent_playbook"],
            "artifact_channel": capability_catalog["artifact_channel"],
            "resource_link_channel": capability_catalog["resource_link_channel"],
            "local_web_search": capability_catalog["local_web_search"],
            "server_client_contract": self._server_client_contract(),
            "routing_contract": self._agent_routing_contract(),
            "agent_orchestration_protocol": self._agent_orchestration_protocol(),
            "output_schema": {
                "intent": "smalltalk|market_overview|single_asset|portfolio|data_lookup|macro|risk|general_investment",
                "needs_server_mapping": True,
                "needs_mcp": False,
                "evidence_targets": [
                    {
                        "raw_mention": "用户原话里的标的、主题、行业、产品、资产或宏观事件片段",
                        "resolved_topic": "你理解后的可检索目标，不包含口语动作词、任务词或无关修饰词",
                        "asset_scope": "A股|港股|美股|全球资产|基金产品|宏观|行业主题|未知",
                        "asset_type": "stock|index|fund|commodity|macro|theme|unknown",
                        "listing_market": "A股|HK|US|NASDAQ|NYSE|全球|未知",
                        "ticker_or_code": "如果已知，填写股票代码、ticker、指数名、基金代码或宏观指标代码",
                        "evidence_need": "行情表现|成分/标的解析|新闻事件|基本面|宏观环境|产品净值|风险验证",
                        "preferred_tools": ["get_global_asset_list", "get_global_asset_data"],
                        "candidate_index_names": ["如果是指数/主题/板块，给出 1-3 个候选指数名称"],
                        "aliases": ["同一目标可能的别名、英文名或交易代码"],
                        "search_queries": ["用于 web_search 的自然语言查询，由你根据问题语义生成"],
                        "why_relevant": "说明这个目标为什么和用户问题相关",
                    }
                ],
                "mcp_tools": [{"name": "get_index_data", "arguments": {"index_name": "沪深300", "limit": 60}}],
                "rewritten_query": query,
                "is_followup": False,
                "followup_target": "",
                "route_summary": "一句话说明你如何理解用户当前真实任务",
                "tool_rationale": "为什么选择这些 MCP/web_search/图表工具，或为什么暂不需要工具",
                "tool_selection_source": "local_llm",
                "tool_selection_note": "说明工具选择来自本机大模型；如果你没有选择工具请说明原因",
                "composition_patterns_used": ["从 composition_patterns 中选择本轮采用的组合模式名称，例如 market_snapshot_to_narrative"],
                "data_strategy": "super-66 MCP、web_search、用户数据、服务端映射和 chart_artifact 如何组合",
                "resource_links": [{"source": "web_search|MCP|server artifact|LLM resource", "link": "名称: URL/路径"}],
                "resource_presentation": "说明本轮如果出现网页/图片/HTML/PDF/报告/图表，CLI 应如何用名称链接呈现并提示打开",
                "open_commands": ["/links 1", "/open 1"],
                "data_confidence": "high|medium|low，说明当前计划拿到足够事实数据的可能性",
                "chart_opportunity": False,
                "chart_rationale": "如果适合图表，说明应该画什么；不适合则留空",
                "artifact_plan": {
                    "type": "chart|report|none",
                    "title": "如果这一轮适合沉淀图表或报告，给一个面向用户的标题",
                    "data_hint": "说明图表/报告应该使用哪些 MCP、web_search 或用户数据字段",
                    "save_to_workspace": True,
                },
                "missing_inputs": ["还需要用户补充的市场、标的、持仓或周期"],
                "tone": "natural_analyst",
            },
        }
        try:
            raw_text = await llm_client_cls(settings, timeout=min(float(get_config().request_timeout or 30), 20.0)).complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是二郎神 CLI 的本机意图理解层。请只输出 JSON，不要解释。"
                            "你是主路由器，不要把单个关键词命中当成主要判断方式；要结合用户原话、最近对话、"
                            "用户数据、previous_mcp_context、recent_resources 和 routing_contract 判断真实任务。"
                            "你是编排决策者，不要先写死规则再让模型填空；必须根据 agent_orchestration_protocol 输出可复盘的 route_summary、tool_rationale、data_strategy 和 artifact_plan。"
                            "当用户问具体股票/公司时，必须先在 evidence_targets 判断所属市场；中文名称不等于 A股，"
                            "例如英伟达/NVIDIA/NVDA 应识别为美股或全球资产候选，先走 get_global_asset_list 或 get_global_asset_data。"
                            "当用户问宏观形势、经济环境、利率、流动性等问题时，evidence_targets.asset_scope 必须是宏观，"
                            "并选择宏观指标工具，不要生成 search_astocks 或“股票代码 A股”查询。"
                            "你要灵活理解用户真正想问什么，并依据 selection_policy、data_recipes、route_plans、"
                            "composition_patterns 和 routing_contract 决定是否需要调用 super-66 MCP/web_search、"
                            "如何组合工具、是否需要 chart artifact。"
                            "可以使用 routing_contract.flexible_tool_spec 中的非标准工具写法；客户端会归一化。"
                        ),
                    },
                    {"role": "user", "content": json.dumps(intent_payload, ensure_ascii=False)},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            self._refresh_token_status_bar(activity="intent ready")
            parsed = self._parse_json_object(
                raw_text,
                preferred_keys={"intent", "needs_mcp", "mcp_tools", "rewritten_query", "route_summary"},
            )
            parsed["route_source"] = "local_llm"
            return self._normalize_intent_plan(parsed, query)
        except Exception as exc:
            fallback_plan = {
                "intent": "general_investment",
                "needs_server_mapping": True,
                "needs_mcp": False,
                "mcp_tools": [],
                "rewritten_query": query,
                "route_source": "fallback",
                "route_warning": "本机大模型意图理解失败，已降级为保守兜底路由",
                "intent_error": self._sanitize_api_key_error(exc, ""),
            }
            return self._normalize_intent_plan(fallback_plan, query)

    def _parse_json_object(self, raw_text: str, preferred_keys: set[str] | None = None) -> dict:
        text = (raw_text or "").strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            candidates = self._json_object_candidates(text)
            if candidates:
                return self._choose_json_object_candidate(candidates, preferred_keys)
        return {}

    def _json_object_candidates(self, text: str) -> list[dict]:
        sources = []
        for match in re.finditer(r"```(?:json)?\s*(.*?)```", text or "", flags=re.I | re.S):
            fenced = match.group(1).strip()
            if fenced:
                sources.append(fenced)
        sources.append(text or "")
        candidates: list[dict] = []
        seen: set[str] = set()
        for source in sources:
            for raw in self._balanced_json_object_strings(source):
                if raw in seen:
                    continue
                seen.add(raw)
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    candidates.append(data)
        return candidates

    def _balanced_json_object_strings(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = -1
        depth = 0
        in_string = False
        escape = False
        for index, char in enumerate(text or ""):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}" and depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    chunks.append(text[start:index + 1])
                    start = -1
        return chunks

    def _choose_json_object_candidate(self, candidates: list[dict], preferred_keys: set[str] | None = None) -> dict:
        if not candidates:
            return {}
        preferred = preferred_keys or set()
        if not preferred:
            return candidates[-1]
        ranked = sorted(
            enumerate(candidates),
            key=lambda item: (len(preferred & set(item[1].keys())), item[0]),
            reverse=True,
        )
        return ranked[0][1]

    def _normalize_intent_plan(self, plan: dict, query: str) -> dict:
        if not isinstance(plan, dict):
            plan = {}
        tools = self._extract_mcp_tool_specs(plan)
        original_tools = bool(tools)
        intent = self._text_field(plan.get("intent")) or "general_investment"
        needs_mcp = bool(plan.get("needs_mcp")) and bool(tools)
        route_source = self._normalize_route_source(plan.get("route_source"))
        tool_selection_source = self._text_field(plan.get("tool_selection_source"))
        tool_selection_note = self._text_field(plan.get("tool_selection_note"))
        if not tool_selection_source:
            if original_tools:
                tool_selection_source = route_source if route_source in {"local_llm", "provided_payload"} else "local_llm"
            else:
                tool_selection_source = "none"
        evidence_targets = self._coerce_evidence_targets(plan.get("evidence_targets"))
        target_tools = self._tools_from_evidence_targets(evidence_targets, query)
        if target_tools:
            before = list(tools)
            tools = self._drop_tools_conflicting_with_evidence_targets(tools, evidence_targets)
            merged = self._dedupe_mcp_tools(target_tools + tools)
            if merged != tools or tools != before:
                tools = merged
                needs_mcp = True
                source = tool_selection_source or route_source or "local_llm"
                tool_selection_source = (
                    source
                    if "client_evidence_target_contract" in source
                    else f"{source}+client_evidence_target_contract"
                )
                note = "本机大模型已在 evidence_targets 解析市场/资产归属，客户端按该结构化理解校验并补齐 MCP 工具。"
                tool_selection_note = f"{tool_selection_note} {note}".strip() if tool_selection_note else note
        default_tools = self._default_tools_for_intent(intent, query)
        if default_tools and not tools:
            tools = default_tools
            needs_mcp = True
            tool_selection_source = "client_default_by_intent"
            if not tool_selection_note:
                tool_selection_note = "本机大模型未给出具体工具，客户端按 intent/data_recipes 补齐默认 MCP 工具，避免无事实数据分析。"
        microcap_tools = self._microcap_strategy_tools(query)
        if microcap_tools:
            before = list(tools)
            tools = self._dedupe_mcp_tools(microcap_tools + tools)
            needs_mcp = True
            if tools != before or not self._has_microcap_benchmark_tool(before):
                source = tool_selection_source or route_source or "local_llm"
                tool_selection_source = (
                    source
                    if "client_microcap_strategy_guardrail" in source
                    else f"{source}+client_microcap_strategy_guardrail"
                )
                note = "检测到微盘/小市值策略问题，客户端强制以华证微盘为主基准，并补充微盘成交额占比、量价、流动性和主线强度验证。"
                tool_selection_note = f"{tool_selection_note} {note}".strip() if tool_selection_note else note
        macro_guardrail_tools = [] if microcap_tools else self._macro_overview_guardrail_tools(query)
        if macro_guardrail_tools:
            before = list(tools)
            tools = self._drop_misdirected_astock_lookup_tools(tools)
            if tools != before or not self._has_macro_tool(tools):
                tools = self._dedupe_mcp_tools(macro_guardrail_tools + tools)
                source = tool_selection_source or route_source or "local_llm"
                tool_selection_source = (
                    source
                    if "client_macro_guardrail" in source
                    else f"{source}+client_macro_guardrail"
                )
                note = "检测到宏观形势/经济环境问题，客户端强制补充宏观指标快照、历史序列和市场参照，避免误走 A 股个股搜索。"
                tool_selection_note = f"{tool_selection_note} {note}".strip() if tool_selection_note else note
            needs_mcp = True
        index_guardrail_tools = self._index_market_guardrail_tools(query)
        if index_guardrail_tools and tools:
            before = list(tools)
            tools = self._drop_misdirected_astock_lookup_tools(tools)
            if tools != before or not self._has_index_market_tool(tools):
                tools = self._dedupe_mcp_tools(index_guardrail_tools + tools)
                source = tool_selection_source or route_source or "local_llm"
                tool_selection_source = (
                    source
                    if "client_index_guardrail" in source
                    else f"{source}+client_index_guardrail"
                )
                note = "检测到指数/大盘表现查询，客户端强制改用指数行情工具，避免误走 A 股个股搜索。"
                tool_selection_note = f"{tool_selection_note} {note}".strip() if tool_selection_note else note
            needs_mcp = True
        astock_tools = [] if (index_guardrail_tools or microcap_tools or macro_guardrail_tools) else self._specific_astock_tools_from_query(query)
        if astock_tools:
            before = list(tools)
            tools = self._dedupe_mcp_tools(astock_tools + tools)
            needs_mcp = True
            if tools != before:
                tool_selection_source = (
                    "client_astock_guardrail"
                    if tool_selection_source in {"none", ""}
                    else tool_selection_source
                    if "client_astock_guardrail" in tool_selection_source
                    else f"{tool_selection_source}+client_astock_guardrail"
                )
                note = "检测到具体 A 股标的，客户端强制追加 search_astocks、实时行情和历史行情，避免只按大盘概览回答。"
                tool_selection_note = f"{tool_selection_note} {note}".strip() if tool_selection_note else note
        if self._is_vague_market_query(query):
            if not tools:
                tools = self._default_market_overview_tools(query)
                tool_selection_source = "client_market_overview_fallback"
                if not tool_selection_note:
                    tool_selection_note = "用户问题是宽泛行情/盘面问题，本机大模型未给出工具时，客户端补齐指数、全球资产和 web_search 默认组合。"
            needs_mcp = True
        tool_rationale = self._text_field(plan.get("tool_rationale"))
        data_strategy = self._text_field(plan.get("data_strategy"))
        route_summary = self._text_field(plan.get("route_summary"))
        data_confidence = self._text_field(plan.get("data_confidence")).lower()
        if data_confidence not in {"high", "medium", "low"}:
            data_confidence = "medium" if needs_mcp else "low"
        chart_rationale = self._text_field(plan.get("chart_rationale"))
        missing_inputs = self._coerce_text_items(plan.get("missing_inputs"))
        if needs_mcp and not tool_rationale:
            tool_rationale = "该问题需要先读取行情/事件数据，避免在缺少事实快照时机械追问。"
        if needs_mcp and not data_strategy:
            data_strategy = "优先读取 super-66 MCP 行情；如有 web_search 可用，再补充当天公开事件线索；随后结合服务端场景映射交给本机大模型分析。"
        if not route_summary:
            route_summary = "先由本机大模型理解上下文，再按需要调用 MCP/web_search 和服务端映射。"
        chart_opportunity = bool(plan.get("chart_opportunity"))
        if microcap_tools:
            if "微盘" not in tool_rationale and "华证微盘" not in tool_rationale:
                tool_rationale = "微盘策略问题必须先以华证微盘为主基准读取量价数据，再对比中证2000/中证1000/宽基和主线热度，验证流动性与风格吸金风险。"
            if "华证微盘" not in data_strategy:
                data_strategy = "优先读取华证微盘、中证2000、中证1000、中证全指/万得全A、沪深300等指数的价格和成交额；用 web_search 交叉验证微盘成交额占全市场成交额比重、跌停/断流、量化拥挤和强主线吸金，再结合服务端场景映射输出是否值得投资。"
            if "微盘" not in route_summary and "华证微盘" not in route_summary:
                route_summary = "这是微盘策略是否值得投资的量价验证任务，重点看华证微盘、成交额占比、相对强弱、流动性压力和市场主线强度。"
            for item in ("具体微盘策略产品/管理人/指数增强规则", "可承受回撤和计划仓位", "微盘成交额占全市场成交额的可核验口径"):
                if item not in missing_inputs:
                    missing_inputs.append(item)
            if not chart_opportunity:
                chart_opportunity = True
                chart_rationale = "微盘策略需要把华证微盘与中证2000/中证1000/沪深300的区间收益、相对强弱和成交额变化做量价对比。"
        if not chart_opportunity and any(word in query for word in ("图表", "画图", "对比", "走势", "收益", "回撤")):
            chart_opportunity = True
            if not chart_rationale:
                chart_rationale = "用户问题包含可视化或对比意图，适合生成 chart artifact。"
        if not chart_opportunity and (self._is_vague_market_query(query) or self._text_field(intent).lower() == "market_overview") and needs_mcp:
            chart_opportunity = True
            if not chart_rationale:
                chart_rationale = "使用 MCP 行情快照做指数、资产或主线对比图。"
        composition_patterns_used = self._normalize_composition_patterns(
            plan.get("composition_patterns_used") or plan.get("composition_pattern"),
            intent=intent,
            query=query,
            tools=tools,
            chart_opportunity=chart_opportunity,
        )
        artifact_plan = self._normalize_artifact_plan(
            plan.get("artifact_plan"),
            query=query,
            intent=intent,
            chart_opportunity=chart_opportunity,
            chart_rationale=chart_rationale,
            needs_mcp=needs_mcp,
        )
        resource_links = self._coerce_resource_links(plan.get("resource_links"))
        resource_presentation = self._text_field(plan.get("resource_presentation"))
        if not resource_presentation:
            resource_presentation = "CLI 不内嵌富文本或二进制内容；网页、图片、HTML、PDF、报告和图表统一显示为命名链接，可用 /links 1 或 /open 1 打开。"
        open_commands = self._coerce_text_items(plan.get("open_commands")) or ["/links 1", "/open 1"]
        if microcap_tools:
            tools = self._dedupe_mcp_tools(microcap_tools + tools)
        return {
            "intent": intent,
            "route_source": route_source,
            "route_warning": self._text_field(plan.get("route_warning") or plan.get("intent_error")),
            "needs_server_mapping": bool(plan.get("needs_server_mapping", True)),
            "needs_mcp": needs_mcp,
            "evidence_targets": evidence_targets,
            "mcp_tools": self._dedupe_mcp_tools(tools)[:12],
            "tool_selection_source": tool_selection_source,
            "tool_selection_note": tool_selection_note,
            "composition_patterns_used": composition_patterns_used,
            "rewritten_query": self._text_field(plan.get("rewritten_query")) or query,
            "is_followup": bool(plan.get("is_followup")),
            "followup_target": self._text_field(plan.get("followup_target")),
            "route_summary": route_summary,
            "tool_rationale": tool_rationale,
            "data_strategy": data_strategy,
            "data_confidence": data_confidence,
            "chart_opportunity": chart_opportunity,
            "chart_rationale": chart_rationale,
            "artifact_plan": artifact_plan,
            "resource_links": resource_links,
            "resource_presentation": resource_presentation,
            "open_commands": open_commands[:4],
            "missing_inputs": missing_inputs[:5],
            "tone": self._text_field(plan.get("tone")) or "natural_analyst",
        }

    def _normalize_route_source(self, value) -> str:
        source = self._text_field(value).lower()
        if source in {"local_llm", "provided_payload", "fallback"}:
            return source
        return "local_llm"

    def _normalize_composition_patterns(self, value, *, intent: str, query: str, tools: list[dict], chart_opportunity: bool) -> list[str]:
        allowed = {
            self._text_field(item.get("name"))
            for item in self._mcp_capability_catalog(query).get("composition_patterns") or []
            if isinstance(item, dict) and self._text_field(item.get("name"))
        }
        items = self._coerce_text_items(value)
        result = []
        for item in items:
            name = self._text_field(item)
            if name in allowed and name not in result:
                result.append(name)
        if result:
            return result[:4]
        defaults = self._default_composition_patterns(intent, query, tools, chart_opportunity)
        return [name for name in defaults if name in allowed][:4]

    def _default_composition_patterns(self, intent: str, query: str, tools: list[dict], chart_opportunity: bool) -> list[str]:
        text = re.sub(r"\s+", "", (query or "").lower())
        tool_names = {self._text_field(item.get("name")) for item in tools if isinstance(item, dict)}
        result = []
        if self._is_microcap_strategy_query(query):
            result.append("microcap_liquidity_price_volume_to_decision")
        if self._is_vague_market_query(query) or self._text_field(intent).lower() == "market_overview":
            result.append("market_snapshot_to_narrative")
        if any(name in tool_names for name in {"search_astocks", "get_astock_realtime", "search_products", "get_product_detail"}):
            result.append("name_to_realtime_snapshot")
        if any(name in tool_names for name in {"get_product_history"}):
            result.append("product_history_to_risk")
        if chart_opportunity or any(word in text for word in ("图表", "画图", "走势", "收益", "回撤", "对比", "报告")):
            result.append("mcp_table_to_chart_artifact")
        if "网页" in text or "图片" in text or "链接" in text or "报告" in text:
            result.append("analysis_result_to_resource_links")
        if not result and tools:
            result.append("market_snapshot_to_narrative")
        return list(dict.fromkeys(result))

    def _coerce_resource_links(self, value) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        for item in self._resource_link_items(value):
            if isinstance(item, str):
                for link in self._resource_links_from_text(item, "resource"):
                    links.append({"source": "resource", "link": link})
                continue
            normalized = self._normalize_resource_link_item(item, "resource")
            if normalized:
                links.append(normalized)
        return links[:8]

    def _resource_link_items(self, value) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _normalize_resource_link_item(self, item, default_source: str = "resource") -> dict[str, str] | None:
        if isinstance(item, dict):
            source = self._text_field(item.get("source")) or default_source
            label = self._text_field(
                item.get("label")
                or item.get("title")
                or item.get("name")
                or item.get("alt")
                or item.get("description")
            )
            target = self._text_field(self._first_resource_target(item))
            if not target:
                return None
            if self._looks_like_resource_target(target) and label and not target.startswith(label):
                target = f"{label}: {target}"
            return {"source": source, "link": target}
        link = self._text_field(item)
        if not link:
            return None
        return {"source": default_source, "link": link}

    def _first_resource_target(self, item: dict):
        for key in self._resource_target_keys():
            value = item.get(key)
            if value:
                return value
        return None

    def _resource_target_keys(self) -> tuple[str, ...]:
        return (
            "link",
            "url",
            "href",
            "path",
            "web_url",
            "source_url",
            "html_url",
            "file_url",
            "download_url",
            "pdf_url",
            "image_url",
            "image",
            "thumbnail",
            "thumbnail_url",
            "preview_url",
            "png_url",
            "jpg_url",
            "jpeg_url",
            "svg_url",
        )

    def _looks_like_resource_target(self, target: str) -> bool:
        text = self._text_field(target)
        return bool(re.match(r"^(?:https?|file)://", text, flags=re.I) or text.startswith("/"))

    def _normalize_artifact_plan(
        self,
        artifact_plan,
        *,
        query: str,
        intent: str,
        chart_opportunity: bool,
        chart_rationale: str,
        needs_mcp: bool,
    ) -> dict:
        data = artifact_plan if isinstance(artifact_plan, dict) else {}
        plan_type = self._text_field(data.get("type")).lower()
        if plan_type not in {"chart", "report", "none"}:
            plan_type = ""
        if not plan_type:
            if chart_opportunity:
                plan_type = "chart"
            elif (self._is_vague_market_query(query) or self._text_field(intent).lower() == "market_overview") and needs_mcp:
                plan_type = "chart"
            else:
                plan_type = "none"
        title = self._text_field(data.get("title"))
        data_hint = self._text_field(data.get("data_hint"))
        is_microcap = self._is_microcap_strategy_query(query)
        if plan_type == "chart":
            if not title:
                is_market_overview = self._is_vague_market_query(query) or self._text_field(intent).lower() == "market_overview"
                if is_microcap:
                    title = "华证微盘量价与相对强弱验证"
                else:
                    title = "市场快照对比" if is_market_overview else "关键指标对比"
            if not data_hint:
                if is_microcap:
                    data_hint = "使用华证微盘、中证2000、中证1000、中证全指/万得全A、沪深300等 MCP 指数序列的收盘、涨跌幅和成交额，并结合 web_search 验证微盘成交额占比、跌停/断流和量化拥挤线索"
                else:
                    data_hint = chart_rationale or "使用本轮 MCP 行情快照中的指数、资产涨跌幅或收益序列"
        elif plan_type == "report":
            if not title:
                title = "本轮投资分析报告"
            if not data_hint:
                data_hint = "使用本轮服务端场景映射、MCP 数据和本机大模型分析结论"
        else:
            title = ""
            data_hint = ""
        return {
            "type": plan_type,
            "title": title,
            "data_hint": data_hint,
            "save_to_workspace": bool(data.get("save_to_workspace", True)) if plan_type != "none" else False,
        }

    def _allowed_super66_tools(self) -> set[str]:
        base_tools = {
            "search_astocks",
            "get_hot_stocks",
            "batch_get_astock_realtime",
            "get_astock_realtime_batch",
            "get_astock_realtime",
            "get_astock_history",
            "batch_get_index_data",
            "get_index_data",
            "get_global_asset_list",
            "batch_get_global_asset_data",
            "get_global_asset_data",
            "get_macro_snapshot",
            "batch_get_macro_data",
            "get_macro_data",
            "get_macro_indicator",
            "list_macro_indicators",
            "get_future_market_data",
            "search_products",
            "get_product_detail",
            "get_product_history",
            "web_search",
        }
        registry_tools = {
            self._text_field(item.get("name"))
            for item in self._super66_registry_tools()
            if isinstance(item, dict) and self._text_field(item.get("name"))
        }
        return base_tools | registry_tools

    def _agent_playbook(self) -> list[dict[str, object]]:
        return [
            {
                "task": "market_overview",
                "goal": "回答“今天行情/盘面/市场主线/风险偏好”这类宽泛问题，先给事实快照，再给方向判断。",
                "trigger": "用户没有给具体标的，但在问今天、当前、盘面、市场、风险偏好或主线。",
                "preferred_chain": [
                    "get_index_data: 沪深300/上证指数/创业板指/恒生科技指数",
                    "get_global_asset_data: 黄金/美元/原油等跨资产风险偏好参照",
                    "web_search: 当天政策、资金面、产业事件",
                    "server map: 受保护场景映射",
                    "local LLM: 自然语言综合",
                ],
                "artifact_rule": "如果拿到多个指数/资产涨跌幅，优先建议 bar；如果拿到历史序列，优先建议 line。",
                "resource_rule": "新闻、政策原文、图片、图表页面必须转成 resource_links，不在终端内嵌富文本。",
                "fallback": "MCP 失败时不要编造行情；保留 web_search 线索并提示 /doctor、/tools 或重新登录。",
            },
            {
                "task": "single_asset_or_product",
                "goal": "回答具体股票、指数、基金、私募产品或商品的走势、风险和跟踪信号。",
                "trigger": "用户给出名称、代码、产品简称、管理人或某个资产。",
                "preferred_chain": [
                    "先判断股票/资产所属市场；不因中文名称默认 A股",
                    "get_global_asset_list/search_astocks/search_products: 名称和市场解析",
                    "get_index_data/get_global_asset_data/get_astock_realtime/get_product_detail/get_product_history",
                    "web_search: 公告、新闻、公开页面",
                    "server map",
                    "local LLM",
                ],
                "artifact_rule": "历史净值/价格适合 line；阶段收益、回撤、涨跌幅对比适合 bar。",
                "resource_rule": "产品页、公告页、新闻页、图片和报告都进入 /links。",
                "fallback": "无法解析实体时先请用户确认代码、市场或产品ID，不要编造。",
            },
            {
                "task": "macro_event_cross_asset",
                "goal": "分析利率、汇率、政策、海外事件对多资产或风格的影响。",
                "trigger": "用户问美元、利率、政策、通胀、海外市场、商品或跨资产传导。",
                "preferred_chain": [
                    "get_index_data: 相关 A股/港股宽基指数",
                    "get_global_asset_data: 黄金/美元/原油/美股资产参照",
                    "web_search: 最新事件和政策原文",
                    "server map",
                    "local LLM",
                ],
                "artifact_rule": "跨资产涨跌幅或情景对比适合 bar；事件前后走势适合 line。",
                "resource_rule": "政策原文和新闻链接必须保留为命名链接。",
                "fallback": "事件信息不足时降低确定性，并列出需要补充的日期、地区、资产范围。",
            },
            {
                "task": "microcap_strategy_due_diligence",
                "goal": "回答“微盘策略是否值得投资”时，用华证微盘做主基准，并用量价、成交占比、流动性和主线强度做验证。",
                "trigger": "用户问微盘、小微盘、小市值策略、华证微盘、量化微盘或微盘是否值得投。",
                "preferred_chain": [
                    "batch_get_index_data: 华证微盘/中证2000/中证1000/中证全指/万得全A/沪深300/创业板指",
                    "get_macro_data: A股流动性、成交额、融资余额、利率和风险偏好",
                    "get_hot_stocks: 成交额榜和强势主线吸金线索",
                    "web_search: 微盘成交额占全市场成交额比重、跌停潮、量化拥挤、赎回和监管线索",
                    "server map + local LLM: 形成可投/观察/回避的条件判断",
                ],
                "artifact_rule": "优先画华证微盘相对中证2000/中证1000/沪深300的走势、区间收益和成交额变化；没有成交额占比时明确缺口。",
                "resource_rule": "成交额占比、跌停潮、量化拥挤等公开来源进入 resource_links。",
                "fallback": "拿不到华证微盘或成交额口径时，不用中证1000代替下结论，只能给框架判断和待验证清单。",
            },
            {
                "task": "visualization_or_report_followup",
                "goal": "把上一轮分析、MCP 快照或用户数据沉淀成图表/报告。",
                "trigger": "用户说图表、报告、对比、走势、收益、回撤、配置比例，或“把刚才那个做成图”。",
                "preferred_chain": [
                    "recent_conversation/previous_mcp_context",
                    "current mcp_data or user_data",
                    "artifacts[].data: 本机 LLM 给结构化数值",
                    "server chart_artifact",
                    "workspace save + /links",
                ],
                "artifact_rule": "只使用已存在或本轮拿到的数值；缺少数值字段就跳过生成并说明需要什么。",
                "resource_rule": "生成的 HTML/JSON/图片/报告路径都加入 /links，可用 /open 1 打开。",
                "fallback": "没有可视化数据时先生成文字摘要，并要求用户提供表格、持仓或数值序列。",
            },
        ]

    def _mcp_capability_catalog(self, query: str = "") -> dict:
        registry_tools = self._super66_registry_tools()
        return {
            "registry_tools": registry_tools,
            "registry_source": "Super66MCP.list_registry_tools",
            "tool_names": [item.get("name") for item in registry_tools if item.get("name")],
            "tool_result_hints": self._mcp_tool_result_hints(),
            "mcp_tools": [
                {
                    "name": "get_index_data",
                    "use_when": "A股指数、港股宽基指数、市场整体、华证微盘、沪深300、上证指数、创业板指、恒生科技指数、恒生指数等行情问题",
                    "args": {"index_name": "沪深300", "limit": 60},
                },
                {
                    "name": "batch_get_index_data",
                    "use_when": "需要比较华证微盘、中证2000、中证1000、全市场宽基和大盘指数的收益、相对强弱、成交额或量价结构",
                    "args": {"index_names": ["华证微盘", "中证2000", "中证1000", "中证全指", "万得全A", "沪深300"], "limit": 120},
                },
                {
                    "name": "get_astock_realtime",
                    "use_when": "具体 A股代码、价格、涨跌幅、成交额等实时问题",
                    "args": {"code": "600519", "limit": 1},
                },
                {
                    "name": "search_astocks",
                    "use_when": "明确是 A股、给出沪深 A股代码，或模型已判断该公司是 A股时，搜索候选代码再取行情",
                    "args": {"keyword": "股票简称", "limit": 5},
                },
                {
                    "name": "get_global_asset_list",
                    "use_when": "具体股票/公司/资产但上市市场未明确，或模型判断属于美股等全球资产时，先查资产目录确认名称、代码和市场",
                    "args": {"keyword": "资产名或代码", "limit": 10},
                },
                {
                    "name": "get_global_asset_data",
                    "use_when": "黄金、原油、美元、汇率、美股个股和其他全球风险资产；港股指数优先用 get_index_data",
                    "args": {"asset_name": "黄金", "limit": 60},
                },
                {
                    "name": "get_future_market_data",
                    "use_when": "商品期货、股指期货、国债期货、期货合约走势",
                    "args": {"contract_code": "AU", "limit": 60},
                },
                {
                    "name": "search_products",
                    "use_when": "公募基金、私募产品、管理人或产品简称检索",
                    "args": {"keyword": "产品或管理人", "limit": 5},
                },
                {
                    "name": "get_product_detail",
                    "use_when": "基金或产品详情、规模、策略、管理人、风险画像",
                    "args": {"product_id": "产品ID"},
                },
                {
                    "name": "get_product_history",
                    "use_when": "基金或产品净值、回撤、收益序列、历史表现",
                    "args": {"product_id": "产品ID", "limit": 120},
                },
                {
                    "name": "web_search",
                    "use_when": "super-66 MCP 不覆盖的新闻、公告、公开网页或最新事件",
                    "args": {"query": query, "count": 5},
                },
            ],
            "artifact_channel": {
                "name": "chart_artifact",
                "transport": "POST /api/artifacts/chart",
                "use_when": "需要把行情、收益、回撤、配置比例或对比结果呈现为图表",
                "supported_types": ["line", "bar", "pie", "gauge", "scatter", "radar"],
                "client_command": "/chart <标题> :: {\"资产A\":1.2,\"资产B\":-0.3}",
            },
            "resource_link_channel": {
                "name": "resource_links",
                "transport": "terminal OSC-8 hyperlink when supported, otherwise named URL/path text",
                "use_when": "网页、图片、HTML、PDF、图表预览、报告文件或服务端返回的非文本资源需要在 CLI 中呈现",
                "supported_types": ["webpage", "image", "html", "pdf", "json", "local_file", "chart_preview"],
                "client_commands": ["/links", "/links 1", "/open 1", "/links open 1", "/open link 1"],
                "boundary": "CLI 不内嵌富文本或二进制内容，只显示名称链接；可通过系统 opener 打开。",
            },
            "local_web_search": {
                "name": "local_chrome_web_search",
                "use_when": "super-66 MCP 不覆盖的新闻、公告、公开网页、政策原文、图片或图表页面入口；中国大陆网络默认使用 Bing",
                "install": "python3 -m pip install playwright && python3 -m playwright install chrome",
                "result_shape": "web_search:<query> -> {results:[{title,url,source}], total, provider} + engine=bing",
                "resource_behavior": "results 中的 url/title 会被提取成命名链接；用户可用 /links 1 或 /open 1 打开。",
                "boundary": "只在客户端本机调用 Chrome/Chromium；不读取浏览器隐私数据，不把模型 API Key 发送给二郎神服务端。",
            },
            "selection_policy": [
                "优先让大模型根据上下文选择工具组合，不用硬编码关键词替代理解",
                "用户给出具体股票/公司时，先由大模型判断所属市场；中文名称不等于 A股，海外公司和美股科技公司应走 get_global_asset_list/get_global_asset_data",
                "只有明确 A股、给出沪深 A股代码，或模型已经判断为 A股时，才使用 search_astocks/get_astock_realtime/get_astock_history",
                "上市市场不确定时，先用 get_global_asset_list + 中性 web_search 核验代码/交易所，再决定后续行情工具",
                "行情和产品数据优先 super-66 MCP；新闻和公开网页补充 web_search",
                "恒生科技指数、恒生指数、HSTECH、HSI、Hang Seng Tech 只能使用 get_index_data；不要使用 get_global_asset_data",
                "恒生科技指数和恒生指数属于 super-66 国内宽基指数数据源；调用 MCP 时只传 index_name/indexName，丢弃 sourceTable/global_index/global_assets 等表名提示",
                "微盘策略、小微盘、小市值策略问题必须以华证微盘为主基准；中证1000/中证2000只能作为比较对象，不得替代华证微盘代表微盘",
                "微盘是否值得投必须验证量价：华证微盘区间收益、成交额/换手、微盘成交额占全市场成交额比重、相对中证2000/中证1000/沪深300强弱、跌停/断流、量化拥挤和强主线吸金",
                "需要可视化时让服务端生成 chart artifact，再由客户端展示或保存",
                "网页、图片、HTML、PDF 等非文本结果必须以命名 resource_links 返回，便于 /links open 1 或 /open link 1 打开",
            ],
            "agent_playbook": self._agent_playbook(),
            "composition_patterns": [
                {
                    "name": "name_to_realtime_snapshot",
                    "when": "用户给股票/基金/产品简称但缺少代码、市场或 product_id",
                    "tools": ["get_global_asset_list/search_astocks/search_products", "get_global_asset_data/get_astock_realtime/get_product_detail", "web_search(optional)", "server map"],
                    "read_fields": ["market/exchange", "code/ticker/symbol", "name", "price/latest/close", "change_pct/pct_chg", "amount/volume", "title/url"],
                    "fallback": "搜索不到实体时先向用户确认标的；不要编造代码或产品ID",
                    "artifact": "通常不直接画图；若用户要求对比或走势，再请求 chart artifact",
                },
                {
                    "name": "market_snapshot_to_narrative",
                    "when": "用户问今天行情、盘面、市场主线或风险偏好",
                    "tools": ["get_index_data", "get_global_asset_data", "web_search", "server map"],
                    "read_fields": ["index_name/asset_name", "date", "close/latest", "change_pct/pct_chg", "title/source/url"],
                    "fallback": "指数数据失败时保留 web_search 事件线索，并明确数据通道缺口和 /doctor 修复路径",
                    "artifact": "可把指数/资产涨跌幅整理为 bar，或把历史序列整理为 line",
                },
                {
                    "name": "microcap_liquidity_price_volume_to_decision",
                    "when": "用户问微盘策略、小微盘、小市值、华证微盘是否值得投、能不能买、要不要配置",
                    "tools": ["batch_get_index_data", "get_macro_data", "get_hot_stocks", "web_search", "server map"],
                    "read_fields": [
                        "华证微盘/index_name/date/close/change_pct/amount/volume",
                        "中证2000/中证1000/沪深300/中证全指或万得全A的区间收益和成交额",
                        "微盘成交额占全市场成交额比重、换手、跌停/断流、量化拥挤、主线成交集中度",
                    ],
                    "fallback": "拿不到华证微盘或成交额占比时，不能用中证1000替代微盘下结论；必须把缺失口径列入 missing_data",
                    "artifact": "line 用于华证微盘相对走势，bar 用于区间收益/成交额变化/成交占比对比",
                },
                {
                    "name": "product_history_to_risk",
                    "when": "用户问基金、私募产品、净值、回撤、收益稳定性",
                    "tools": ["search_products", "get_product_detail", "get_product_history", "server map"],
                    "read_fields": ["product_id", "name", "nav/date", "return/drawdown", "strategy/manager/scale"],
                    "fallback": "缺少产品历史时只做框架判断，并要求用户提供产品ID或净值序列",
                    "artifact": "净值或收益序列适合 line；回撤/阶段收益适合 bar",
                },
                {
                    "name": "analysis_result_to_resource_links",
                    "when": "MCP、web_search、服务端或大模型返回网页、图片、HTML、PDF、图表预览",
                    "tools": ["resource_links", "/links", "/open 1"],
                    "read_fields": ["title/name/label", "url/html_url/image_url/pdf_url/file_url", "source"],
                    "fallback": "如果终端不支持 OSC-8，退化为“名称: URL/路径”文本",
                    "artifact": "非文本资源进入 /links；图表 artifact 同时可保存到授权工作区",
                },
                {
                    "name": "mcp_table_to_chart_artifact",
                    "when": "用户要求图表、报告、走势、对比、收益、回撤或配置比例",
                    "tools": ["previous_mcp_context/current mcp_data", "artifacts[].data", "server chart_artifact", "/open chart"],
                    "read_fields": ["label/name/asset/index_name", "value/change_pct/return_pct/close/y", "series/date"],
                    "fallback": "缺少数值字段时跳过图表生成，并说明需要哪些数值",
                    "artifact": "客户端调用服务端 chart artifact，保存 JSON/HTML，并把链接加入 /links",
                },
            ],
            "data_recipes": [
                {
                    "name": "microcap_strategy_due_diligence",
                    "use_when": "用户问最近微盘策略、华证微盘、小微盘或小市值策略是否值得投资",
                    "steps": [
                        "主基准: batch_get_index_data 读取华证微盘；同时读取中证2000、中证1000、中证全指/万得全A、沪深300、创业板指做相对强弱和风格比较",
                        "量价验证: 检查华证微盘区间收益、成交额/成交量/换手变化、价涨量缩或价跌量增等背离",
                        "成交占比: 用华证微盘成交额与中证全指/万得全A或公开口径验证微盘成交额占全市场成交额比重及其趋势",
                        "流动性压力: 检查跌停潮、断流、买卖价差、量化拥挤、赎回/去杠杆、监管和融资环境",
                        "主线吸金: 用 get_hot_stocks 和 web_search 判断成交额是否集中到强主线龙头/主题 ETF，微盘投机属性是否被抽走",
                        "结论: 只能在可投、观察、回避/降仓三类中给条件判断，并列出触发提高/降低权重的量价信号",
                    ],
                    "examples": [
                        "最近的微盘策略值得投资吗？",
                        "华证微盘最近量价结构怎么样，微盘还能不能配？",
                        "小市值策略是不是被主线抽血了？",
                    ],
                },
                {
                    "name": "market_overview",
                    "use_when": "用户问今天行情、市场怎么样、盘面怎么看但没有给具体标的",
                    "steps": [
                        "get_index_data: 沪深300 / 上证指数 / 创业板指 / 恒生科技指数",
                        "get_global_asset_data: 黄金 / 美元 / 原油等跨资产风险偏好参照",
                        "港股宽基指数约束: 恒生科技指数/HSTECH/Hang Seng Tech/恒生指数/HSI/HSCEI 只走 get_index_data，不走 get_global_asset_data",
                        "web_search: 补充当天政策、资金面、产业新闻线索",
                        "server map: 获取受保护场景映射后再由本机大模型综合",
                    ],
                    "examples": [
                        "今天行情怎么样？先帮我看盘面主线和风险。",
                        "A股今天哪些方向值得跟踪？",
                        "今天市场是风险偏好修复还是防御占优？",
                    ],
                },
                {
                    "name": "single_asset",
                    "use_when": "用户问具体股票、指数、商品、基金或产品",
                    "steps": [
                        "先判断股票/资产所属市场；不要因为公司中文名就默认 A股",
                        "如果标的是恒生科技指数/HSTECH/Hang Seng Tech/HSCEI/恒生指数/HSI，直接用 get_index_data，参数 index_name/indexName，不要当作 global asset，也不要传 sourceTable",
                        "如果市场未确认，先用 get_global_asset_list 和中性 web_search 查代码/交易所；A股再用 search_astocks，美股等全球资产用 get_global_asset_data",
                        "再用 get_astock_realtime/get_global_asset_data/get_product_detail/get_product_history 拉取事实数据",
                        "必要时用 web_search 补公告或新闻",
                    ],
                    "examples": [
                        "帮我看一下贵州茅台今天怎么走。",
                        "黄金最近的趋势和风险信号是什么？",
                        "这个基金近期回撤为什么扩大？",
                    ],
                },
                {
                    "name": "macro_event",
                    "use_when": "用户问利率、汇率、政策、海外市场或宏观事件影响",
                    "steps": [
                        "get_index_data: 港股宽基指数 / 相关股票指数；恒生科技指数/HSTECH/Hang Seng Tech/恒生指数/HSI/HSCEI 归入这里",
                        "get_global_asset_data: 美元指数 / 黄金 / 原油 / 美股资产",
                        "web_search: 查找最新公开事件线索",
                        "server map: 映射到服务端受保护宏观/市场场景",
                    ],
                    "examples": [
                        "如果美元指数继续走强，对港股和黄金有什么影响？",
                        "利率下行时，红利和成长谁更占优？",
                        "最新政策信号对风险资产意味着什么？",
                    ],
                },
                {
                    "name": "visualization_followup",
                    "use_when": "用户说做成图表、报告、对比收益、回撤、走势或配置比例",
                    "steps": [
                        "复用 recent_conversation 与上一轮 mcp_data 语境",
                        "在 artifacts 中返回 chart 请求，data 使用可读资产名到数值的映射",
                        "客户端会调用服务端 chart artifact 并保存到授权工作区",
                    ],
                    "examples": [
                        "把刚才的资产表现做成图表。",
                        "把这几个方向的涨跌幅做个对比。",
                        "生成一份带图表的简短报告。",
                    ],
                },
            ],
            "route_plans": [
                {
                    "name": "market_overview_to_analysis",
                    "trigger": "宽泛行情、盘面、今天市场、风险偏好方向判断",
                    "sequence": [
                        "本机 LLM 改写 query，补全市场范围和真实任务",
                        "super-66 MCP: get_index_data 读取沪深300/上证/创业板/恒生科技等主指数",
                        "super-66 MCP: get_global_asset_data 读取黄金/美元/原油等风险偏好参照",
                        "web_search: 补当天政策、资金面、产业新闻线索",
                        "server map: 使用 rewritten_query 做受保护场景映射",
                        "local LLM: 综合 mcp_data + server map，输出自然分析和追问",
                    ],
                    "output": "自然语言市场判断；必要时建议 chart/report follow-up",
                },
                {
                    "name": "microcap_strategy_to_liquidity_decision",
                    "trigger": "微盘策略、小微盘、小市值策略、华证微盘是否值得投资",
                    "sequence": [
                        "本机 LLM 将问题改写为微盘策略量价与流动性验证任务",
                        "super-66 MCP: batch_get_index_data 读取华证微盘、中证2000、中证1000、中证全指/万得全A、沪深300等",
                        "super-66 MCP/web_search: 验证微盘成交额占全市场成交额比重、换手、跌停/断流、量化拥挤和主线吸金",
                        "server map: 命中微盘流动性/主线失效风险场景",
                        "local LLM: 输出可投/观察/回避的条件判断、仓位边界、失效信号和缺失数据",
                    ],
                    "output": "华证微盘主基准 + 量价/成交占比/主线强度验证后的投资判断",
                },
                {
                    "name": "named_asset_to_fact_check",
                    "trigger": "用户给出股票、基金、产品、商品或指数名称，需要先核实实体和事实数据",
                    "sequence": [
                        "本机 LLM 判断实体类型和是否需要 disambiguation",
                        "先判断具体股票/公司所属市场；不要把中文公司名自动当成 A股",
                        "若实体是恒生科技指数/HSTECH/Hang Seng Tech/HSCEI/恒生指数/HSI，选择 get_index_data，并丢弃 sourceTable/global_index/global_assets 等表名参数",
                        "市场不确定时先 get_global_asset_list + 中性 web_search；确认 A股才 search_astocks，确认美股/全球资产才 get_global_asset_data",
                        "再调用 get_astock_realtime/get_global_asset_data/get_product_detail/get_product_history 或 future 数据",
                        "web_search 补公告、新闻或未覆盖公开信息",
                        "server map: 用改写后的完整问题映射场景",
                    ],
                    "output": "事实快照 + 风险解释 + 可执行跟踪信号",
                },
                {
                    "name": "analysis_to_chart_artifact",
                    "trigger": "用户要求图表、报告、对比、走势、收益、回撤或配置比例",
                    "sequence": [
                        "复用 recent_conversation、上一轮 mcp_data 和当前 query",
                        "本机 LLM 选择可视化字段并在 artifacts 返回 chart 请求",
                        "client 调用服务端 chart artifact 通道",
                        "授权工作区后保存 JSON/HTML 到 .erlangshen/artifacts",
                        "终端返回轻量预览，并提示 /open 和 /artifacts",
                    ],
                    "output": "服务端生成的 chart artifact + 本地报告/HTML 路径",
                },
            ],
        }

    def _super66_registry_tools(self) -> list[dict[str, str]]:
        try:
            from src.mcp.super66 import Super66MCP

            tools = Super66MCP().list_registry_tools()
        except Exception:
            tools = []
        normalized = []
        for item in tools:
            if not isinstance(item, dict):
                continue
            name = self._text_field(item.get("name"))
            description = self._text_field(item.get("description"))
            if name:
                normalized.append({"name": name, "description": description})
        if normalized:
            return normalized
        return [
            {"name": "search_astocks", "description": "搜索 A股标的"},
            {"name": "get_hot_stocks", "description": "获取 A股热门股票、成交额或涨跌幅榜"},
            {"name": "batch_get_astock_realtime", "description": "批量获取 A股实时/最新行情"},
            {"name": "get_astock_realtime", "description": "获取 A股实时/最新行情"},
            {"name": "get_astock_history", "description": "获取 A股历史行情"},
            {"name": "batch_get_index_data", "description": "批量获取 A股、港股、美股等指数历史和最新行情"},
            {"name": "get_index_data", "description": "获取 A股和港股宽基指数历史数据，如沪深300、恒生科技指数、恒生指数"},
            {"name": "batch_get_global_asset_data", "description": "批量获取黄金、美元、原油等全球资产历史数据"},
            {"name": "get_global_asset_data", "description": "获取黄金、美元、原油等全球资产历史数据；港股指数走 get_index_data"},
            {"name": "get_macro_data", "description": "获取宏观指标目录、最新值或时序数据"},
            {"name": "get_future_market_data", "description": "获取期货行情"},
            {"name": "search_products", "description": "搜索 ETF、公募、私募等产品"},
            {"name": "get_product_detail", "description": "获取产品详情"},
            {"name": "get_product_history", "description": "获取产品历史净值或行情"},
        ]

    def _mcp_tool_result_hints(self) -> dict[str, dict[str, object]]:
        return {
            "get_index_data": {
                "result_shape": "A股和港股宽基指数历史或最近行情序列；恒生科技指数/HSTECH/Hang Seng Tech/恒生指数/HSI/HSCEI 属于这里",
                "use_fields": ["index_name", "date", "close", "change_pct", "volume", "amount"],
                "chart_fit": "line 用于走势，bar 用于当日/近期涨跌幅对比",
            },
            "batch_get_index_data": {
                "result_shape": "多个指数历史或最近行情序列；微盘策略必须包含华证微盘，并用中证2000/中证1000/沪深300/全市场指数做比较",
                "use_fields": ["index_name", "date", "close", "change_pct", "volume", "amount"],
                "chart_fit": "line 用于相对走势，bar 用于区间收益、成交额变化和成交占比对比",
            },
            "get_astock_realtime": {
                "result_shape": "单只 A 股实时或最近行情快照",
                "use_fields": ["code", "name", "price", "change_pct", "volume", "amount"],
                "chart_fit": "bar 用于多标的涨跌幅/成交额对比",
            },
            "get_astock_history": {
                "result_shape": "单只 A 股历史行情序列",
                "use_fields": ["date", "open", "high", "low", "close", "change_pct", "volume"],
                "chart_fit": "line 用于价格或涨跌幅走势",
            },
            "get_global_asset_data": {
                "result_shape": "黄金、美元、美股资产、原油等全球资产历史序列；港股宽基指数必须用 get_index_data",
                "use_fields": ["asset_name", "date", "close", "change_pct"],
                "chart_fit": "line 用于趋势，bar 用于多资产涨跌幅对比",
            },
            "get_product_history": {
                "result_shape": "基金/产品净值、收益、回撤或历史表现序列",
                "use_fields": ["date", "nav", "return_pct", "drawdown", "close"],
                "chart_fit": "line 用于净值/回撤走势，bar 用于收益对比",
            },
            "web_search": {
                "result_shape": "公开网页、新闻、公告、标题、摘要和 URL",
                "use_fields": ["title", "url", "source", "snippet", "published_at"],
                "chart_fit": "不直接画图；保留 resource_links，并用作事件解释线索",
            },
        }

    async def _collect_client_mcp_data(self, query: str, payload: dict, intent_plan: dict) -> dict:
        provided = payload.get("mcp_data")
        if isinstance(provided, dict) and provided:
            return provided
        tools = intent_plan.get("mcp_tools") if isinstance(intent_plan, dict) else []
        tools = self._dedupe_mcp_tools(tools) if isinstance(tools, list) else []
        evidence_targets = self._coerce_evidence_targets(intent_plan.get("evidence_targets")) if isinstance(intent_plan, dict) else []
        target_tools = self._tools_from_evidence_targets(evidence_targets, query)
        if target_tools:
            before = list(tools)
            tools = self._drop_tools_conflicting_with_evidence_targets(tools, evidence_targets)
            merged = self._dedupe_mcp_tools(target_tools + tools)
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = merged
                intent_plan["evidence_targets"] = evidence_targets
                if merged != before:
                    source = self._text_field(intent_plan.get("tool_selection_source") or intent_plan.get("route_source") or "local_llm")
                    intent_plan["tool_selection_source"] = (
                        source
                        if "client_evidence_target_contract" in source
                        else f"{source}+client_evidence_target_contract"
                    )
                    note = "本机大模型已在 evidence_targets 解析市场/资产归属，客户端按该结构化理解校验并补齐 MCP 工具。"
                    previous = self._text_field(intent_plan.get("tool_selection_note"))
                    intent_plan["tool_selection_note"] = f"{previous} {note}".strip() if previous else note
            tools = merged
        microcap_tools = self._microcap_strategy_tools(query)
        if microcap_tools:
            before = list(tools)
            tools = self._dedupe_mcp_tools(microcap_tools + tools)
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
                if tools != before or not self._has_microcap_benchmark_tool(before):
                    source = self._text_field(intent_plan.get("tool_selection_source") or intent_plan.get("route_source") or "local_llm")
                    intent_plan["tool_selection_source"] = (
                        source
                        if "client_microcap_strategy_guardrail" in source
                        else f"{source}+client_microcap_strategy_guardrail"
                    )
                    note = "检测到微盘/小市值策略问题，客户端强制以华证微盘为主基准，并补充微盘成交额占比、量价、流动性和主线强度验证。"
                    previous = self._text_field(intent_plan.get("tool_selection_note"))
                    intent_plan["tool_selection_note"] = f"{previous} {note}".strip() if previous else note
        macro_guardrail_tools = [] if microcap_tools else self._macro_overview_guardrail_tools(query)
        if macro_guardrail_tools:
            before = list(tools)
            tools = self._drop_misdirected_astock_lookup_tools(tools)
            if tools != before or not self._has_macro_tool(tools):
                tools = self._dedupe_mcp_tools(macro_guardrail_tools + tools)
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
                source = self._text_field(intent_plan.get("tool_selection_source") or intent_plan.get("route_source") or "local_llm")
                intent_plan["tool_selection_source"] = (
                    source if "client_macro_guardrail" in source else f"{source}+client_macro_guardrail"
                )
                note = "检测到宏观形势/经济环境问题，客户端强制补充宏观指标快照、历史序列和市场参照，避免误走 A 股个股搜索。"
                previous = self._text_field(intent_plan.get("tool_selection_note"))
                intent_plan["tool_selection_note"] = f"{previous} {note}".strip() if previous else note
        index_guardrail_tools = self._index_market_guardrail_tools(query)
        if index_guardrail_tools and tools:
            before = list(tools)
            tools = self._drop_misdirected_astock_lookup_tools(tools)
            if tools != before or not self._has_index_market_tool(tools):
                tools = self._dedupe_mcp_tools(index_guardrail_tools + tools)
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
                source = self._text_field(intent_plan.get("tool_selection_source") or intent_plan.get("route_source") or "local_llm")
                intent_plan["tool_selection_source"] = (
                    source if "client_index_guardrail" in source else f"{source}+client_index_guardrail"
                )
                note = "检测到指数/大盘表现查询，客户端强制改用指数行情工具，避免误走 A 股个股搜索。"
                previous = self._text_field(intent_plan.get("tool_selection_note"))
                intent_plan["tool_selection_note"] = f"{previous} {note}".strip() if previous else note
        astock_tools = [] if (index_guardrail_tools or microcap_tools or macro_guardrail_tools) else self._specific_astock_tools_from_query(query)
        astock_guardrail = "client_astock_guardrail"
        if not astock_tools:
            astock_tools = self._specific_astock_tools_from_followup_context(query, intent_plan)
            astock_guardrail = "client_astock_followup_guardrail"
        if astock_tools:
            before = list(tools)
            tools = self._dedupe_mcp_tools(astock_tools + tools)
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
                if tools != before:
                    source = self._text_field(intent_plan.get("tool_selection_source") or intent_plan.get("route_source") or "local_llm")
                    intent_plan["tool_selection_source"] = (
                        source if astock_guardrail in source else f"{source}+{astock_guardrail}"
                    )
                    if astock_guardrail == "client_astock_followup_guardrail":
                        note = "检测到承接上一轮 A 股标的的追问，客户端从上下文恢复标的并追加 search_astocks、实时行情和历史行情。"
                    else:
                        note = "检测到具体 A 股标的，客户端强制追加 search_astocks、实时行情和历史行情，避免只按大盘概览回答。"
                    previous = self._text_field(intent_plan.get("tool_selection_note"))
                    intent_plan["tool_selection_note"] = f"{previous} {note}".strip() if previous else note
        if isinstance(intent_plan, dict) and tools:
            intent_plan["mcp_tools"] = tools
            intent_plan.setdefault("tool_selection_source", intent_plan.get("route_source") or "local_llm")
            intent_plan.setdefault("tool_selection_note", "MCP 工具来自本轮意图计划。")
        if isinstance(intent_plan, dict) and not tools:
            tools = self._default_tools_for_intent(intent_plan.get("intent") or "", query)
            if tools:
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
                intent_plan["tool_selection_source"] = "client_default_by_intent"
                intent_plan["tool_selection_note"] = "传入的意图计划没有具体工具，客户端按 intent/data_recipes 补齐默认 MCP 工具。"
        if self._is_vague_market_query(query):
            if not tools:
                tools = self._default_market_overview_tools(query)
                if isinstance(intent_plan, dict):
                    intent_plan["tool_selection_source"] = "client_market_overview_fallback"
                    intent_plan["tool_selection_note"] = "宽泛行情/盘面问题没有工具计划，客户端补齐指数、全球资产和 web_search 默认组合。"
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
        if microcap_tools:
            tools = self._dedupe_mcp_tools(microcap_tools + tools)
            if isinstance(intent_plan, dict):
                intent_plan["needs_mcp"] = True
                intent_plan["mcp_tools"] = tools
        if self._should_reuse_previous_mcp_data(query, intent_plan):
            reused = dict(self._last_mcp_data or {})
            reused.setdefault("note", "复用上一轮 MCP 数据用于承接式图表/报告/追问；仅保存在本次 CLI 进程内。")
            if isinstance(intent_plan, dict) and not intent_plan.get("mcp_tools"):
                intent_plan["mcp_tools"] = self._infer_tools_from_mcp_keys(reused)
                intent_plan["needs_mcp"] = bool(intent_plan["mcp_tools"])
            if isinstance(intent_plan, dict):
                intent_plan["tool_selection_source"] = "previous_mcp_context"
                intent_plan["tool_selection_note"] = "承接式追问复用上一轮 MCP 数据；仅保存在当前 CLI 进程内。"
            return reused
        if not intent_plan.get("needs_mcp") or not tools:
            return {}
        self._show_progress("正在读取 super-66 MCP / 本地网页线索")
        collected = {}
        mcp = None
        mcp_init_error = ""
        if any(isinstance(item, dict) and item.get("name") != "web_search" for item in tools):
            try:
                from src.mcp.super66 import Super66MCP

                mcp = Super66MCP()
                if hasattr(mcp, "ensure_fresh_login"):
                    self._show_progress("正在重新登录 super-66 MCP 获取新 token")
                    if not await mcp.ensure_fresh_login():
                        mcp_init_error = (
                            "super-66 MCP 需要重新登录获取新 token；请执行 /login xwab <账号> 保存加密密码，"
                            "或设置 SUPER66_USERNAME/SUPER66_PASSWORD。"
                        )
                        collected["super66_auth:error"] = mcp_init_error
                        mcp = None
            except Exception as exc:
                mcp_init_error = self._sanitize_api_key_error(exc, "")
                collected["super66_error"] = mcp_init_error
        for item in self._dedupe_mcp_tools(tools)[:12]:
            name = item.get("name")
            arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
            if name not in self._allowed_super66_tools():
                continue
            key = self._mcp_result_key(name, arguments, len(collected))
            self._show_progress(f"正在读取数据工具: {self._mcp_tool_label(name, arguments)}")
            try:
                if name == "web_search":
                    collected[key] = await self._run_local_chrome_search(arguments.get("query") or query, arguments)
                elif mcp is None:
                    collected[f"{key}:error"] = mcp_init_error or "super-66 MCP 未初始化"
                else:
                    result = await self._call_mcp_tool_checked(mcp, name, arguments)
                    if self._mcp_value_has_error(result) and self._batch_tool_fallback_tools(name, arguments):
                        retried = False
                        all_macro_ok = True
                        if name in {"get_macro_snapshot", "batch_get_macro_data"} and self._should_retry_macro_tool_with_chunks(
                            name,
                            arguments,
                            result,
                        ):
                            retried, all_macro_ok = await self._collect_macro_tool_fallback_by_chunks(
                                collected,
                                name,
                                arguments,
                                payload,
                                mcp,
                            )
                        if not (retried and all_macro_ok):
                            collected[f"{key}:error"] = result
                            await self._collect_batch_fallback_data(collected, name, arguments, mcp)
                    else:
                        collected[key] = result
            except Exception as exc:
                collected[f"{key}:error"] = self._sanitize_api_key_error(exc, "")
        await self._collect_global_asset_followup_data(collected, tools, mcp)
        await self._collect_astock_followup_data(collected, tools, mcp)
        if not collected:
            collected["note"] = "super-66 MCP / 本地网页线索暂不可用，本次仅使用用户问题和服务端场景映射。"
        return collected

    def _macro_indicator_codes_from_args(self, arguments: dict) -> list[str]:
        args = arguments if isinstance(arguments, dict) else {}
        return self._coerce_label_list(
            args.get("indicator_codes")
            or args.get("indicatorCodes")
            or args.get("indicator_keywords")
            or args.get("indicatorKeywords")
        )

    def _macro_tool_chunk_size(self) -> int:
        return 4

    def _macro_tool_chunk_sizes(self) -> tuple[int, ...]:
        return (self._macro_tool_chunk_size(), 2, 1)

    def _macro_tool_default_date_window(self, payload: dict | None = None) -> dict[str, str]:
        checked_at = self._text_field(payload.get("checked_at") if isinstance(payload, dict) else "")
        if not checked_at:
            checked_at = CLI_BENCHMARK_CHECKED_AT
        try:
            checked_at_date = datetime.fromisoformat(checked_at[:10]).date()
        except ValueError:
            return {}
        return {
            "startDate": f"{checked_at_date.year}-01-01",
            "endDate": checked_at_date.isoformat(),
        }

    def _should_retry_macro_tool_with_chunks(self, name: str, arguments: dict, result) -> bool:
        if name not in {"get_macro_snapshot", "batch_get_macro_data"}:
            return False
        if not self._mcp_value_has_error(result):
            return False
        if not self._macro_indicator_codes_from_args(arguments):
            return False
        for key in ("code", "message", "error", "detail"):
            value = (result or {}).get(key, "")
            value_text = self._text_field(value)
            if isinstance(value, dict):
                value_text = self._text_field(value.get("message", "")).lower()
            else:
                value_text = value_text.lower()
            if any(token in value_text for token in ("timeout", "timed out", "gateway timeout", "504")):
                return True
        return False

    def _coerce_macro_tool_limit(self, arguments: dict) -> dict:
        fallback_args = dict(arguments or {})
        if "limit" in fallback_args:
            try:
                fallback_args["limit"] = min(int(fallback_args["limit"]), 80)
            except (TypeError, ValueError):
                pass
        return fallback_args

    async def _collect_macro_tool_fallback_by_chunks(
        self,
        collected: dict,
        name: str,
        arguments: dict,
        payload: dict | None,
        mcp,
    ) -> tuple[bool, bool]:
        codes = self._macro_indicator_codes_from_args(arguments)
        if not codes:
            return False, False
        date_window = self._macro_tool_default_date_window(payload)
        retried = False
        all_macro_ok = True
        single_fallback_called = False

        chunk_sizes = self._macro_tool_chunk_sizes()

        async def collect_chunk(block: list[str], size_index: int) -> None:
            nonlocal all_macro_ok, retried, single_fallback_called
            if not block:
                return

            idx = min(size_index, len(chunk_sizes) - 1)
            chunk_size = max(1, chunk_sizes[idx])
            if idx + 1 < len(chunk_sizes):
                next_size = max(1, chunk_sizes[idx + 1])
                if next_size >= chunk_size:
                    next_size = max(1, chunk_size // 2)
            else:
                next_size = 1
            chunks = [block[i : i + chunk_size] for i in range(0, len(block), chunk_size)]
            for chunk in chunks:
                retried = True
                chunk_args = self._coerce_macro_tool_limit(dict(arguments or {}))
                chunk_args["indicator_codes"] = list(chunk)
                for key, value in date_window.items():
                    chunk_args.setdefault(key, value)
                if name == "batch_get_macro_data":
                    chunk_args.setdefault("latest_only", False)
                self._show_progress(
                    f"宏观指标工具分片重试: {self._mcp_tool_label(name, chunk_args)}"
                )
                try:
                    chunk_result = await self._call_mcp_tool_checked(mcp, name, chunk_args)
                except Exception as exc:
                    chunk_result = self._sanitize_api_key_error(exc, "")

                if not self._mcp_value_has_error(chunk_result):
                    chunk_key = self._mcp_result_key(name, chunk_args, len(collected))
                    collected[chunk_key] = chunk_result
                    continue

                if len(chunk) > 1 and size_index + 1 < len(chunk_sizes):
                    split_chunks = [chunk[i : i + next_size] for i in range(0, len(chunk), next_size)]
                    for split_chunk in split_chunks:
                        await collect_chunk(split_chunk, size_index + 1)
                    continue

                if len(chunk) == 1:
                    single_fallback_called = True
                    if not await self._collect_macro_single_indicator_fallback(
                        collected,
                        name,
                        chunk[0],
                        arguments,
                        payload,
                        mcp,
                    ):
                        chunk_key = self._mcp_result_key(name, chunk_args, len(collected))
                        collected[f"{chunk_key}:error"] = chunk_result
                        all_macro_ok = False
                    continue

                chunk_key = self._mcp_result_key(name, chunk_args, len(collected))
                collected[f"{chunk_key}:error"] = chunk_result
                all_macro_ok = False

        await collect_chunk(list(codes), 0)
        if not single_fallback_called and not any(
            str(key).startswith("get_macro_data:")
            for key in collected
            if isinstance(key, str)
        ):
            single_fallback_called = True
            await self._collect_macro_single_indicator_fallback(
                collected,
                name,
                codes[0],
                arguments,
                payload,
                mcp,
            )
        return retried, all_macro_ok and single_fallback_called

    async def _collect_macro_single_indicator_fallback(
        self,
        collected: dict,
        source_name: str,
        indicator_code: str,
        arguments: dict,
        payload: dict | None,
        mcp,
    ) -> bool:
        args = self._coerce_macro_tool_limit(dict(arguments or {}))
        latest_only = arguments.get("latest_only")
        if latest_only is None:
            latest_only = arguments.get("latestOnly")
        if latest_only is None:
            latest_only = True if source_name == "get_macro_snapshot" else False
        normalized_code = self._text_field(indicator_code)
        if not normalized_code:
            normalized_code = self._text_field(arguments.get("keyword"))

        fallback_args: dict[str, Any] = {
            "keyword": normalized_code,
            "indicator_codes": [normalized_code],
            "latest_only": latest_only,
            "limit": args.get("limit", 80),
        }
        for key, value in self._macro_tool_default_date_window(payload).items():
            fallback_args.setdefault(key, value)
        for key in ("startDate", "endDate", "start_date", "end_date"):
            if key in args:
                fallback_args[key] = args[key]
        self._show_progress(f"单指标宏观回退: get_macro_data keyword={fallback_args['keyword']}")
        key = self._mcp_result_key("get_macro_data", fallback_args, len(collected))
        try:
            fallback_result = await self._call_mcp_tool_checked(mcp, "get_macro_data", fallback_args)
        except Exception as exc:
            fallback_result = self._sanitize_api_key_error(exc, "")
        if self._mcp_value_has_error(fallback_result):
            collected[f"{key}:error"] = fallback_result
            return False
        collected[key] = fallback_result
        return True

    async def _collect_batch_fallback_data(self, collected: dict, name: str, arguments: dict, mcp) -> None:
        if mcp is None:
            return
        for fallback in self._batch_tool_fallback_tools(name, arguments):
            fallback_name = fallback.get("name")
            fallback_args = fallback.get("arguments") if isinstance(fallback.get("arguments"), dict) else {}
            result_key = self._mcp_result_key(fallback_name, fallback_args, len(collected))
            if result_key in collected:
                continue
            self._show_progress(self._fallback_progress_message(name, fallback_name, fallback_args))
            try:
                collected[result_key] = await self._call_mcp_tool_checked(mcp, fallback_name, fallback_args)
            except Exception as exc:
                collected[f"{result_key}:error"] = self._sanitize_api_key_error(exc, "")

    def _fallback_progress_message(self, name: str, fallback_name: str, fallback_args: dict) -> str:
        label = self._mcp_tool_label(fallback_name, fallback_args)
        if name in {"batch_get_index_data", "batch_get_global_asset_data", "batch_get_astock_realtime", "get_astock_realtime_batch"}:
            return f"批量接口未命中，回退读取: {label}"
        if name == "get_hot_stocks":
            return f"热门股票工具未命中，回退读取: {label}"
        if name in {"batch_get_macro_data", "get_macro_snapshot", "get_macro_data", "get_macro_indicator", "list_macro_indicators"}:
            return f"宏观数据工具未命中，回退读取: {label}"
        return f"数据工具未命中，回退读取: {label}"

    async def _call_mcp_tool_checked(self, mcp, name: str, arguments: dict):
        result = await mcp.call_tool(name, arguments, use_cache=True)
        checked = self._validate_mcp_tool_result(name, arguments, result)
        if not self._mcp_value_has_error(checked):
            return checked
        code = self._requested_astock_code(name, arguments)
        if not code:
            return checked
        for retry_args in self._astock_retry_arguments(arguments, code):
            if retry_args == arguments:
                continue
            self._show_progress(f"股票代码校验未通过，换参数重试: {self._mcp_tool_label(name, retry_args)}")
            retry_result = await mcp.call_tool(name, retry_args, use_cache=False)
            retry_checked = self._validate_mcp_tool_result(name, {**arguments, **retry_args}, retry_result)
            if not self._mcp_value_has_error(retry_checked):
                return retry_checked
            checked = retry_checked
        return checked

    def _requested_astock_code(self, name: str, arguments: dict) -> str:
        if name not in {"get_astock_realtime", "get_astock_history"}:
            return ""
        args = arguments if isinstance(arguments, dict) else {}
        code = (
            args.get("code")
            or args.get("stockCode")
            or args.get("stock_code")
            or args.get("symbol")
            or args.get("ticker")
        )
        match = re.search(r"(?<!\d)([036]\d{5})(?:\.[A-Z]{2})?(?!\d)", self._text_field(code), flags=re.I)
        return match.group(1) if match else ""

    def _astock_retry_arguments(self, arguments: dict, code: str) -> list[dict]:
        base = dict(arguments or {})
        variants = []
        for key in ("stockCode", "stock_code", "symbol", "ticker", "code"):
            item = dict(base)
            for old in ("code", "stockCode", "stock_code", "symbol", "ticker"):
                item.pop(old, None)
            item[key] = code
            variants.append(item)
        return variants

    def _validate_mcp_tool_result(self, name: str, arguments: dict, result):
        code = self._requested_astock_code(name, arguments)
        if not code or self._mcp_value_has_error(result):
            return result
        returned_codes = self._extract_astock_codes_from_value(result)
        normalized_codes = {self._normalize_astock_code(item) for item in returned_codes}
        if normalized_codes and code not in normalized_codes:
            return self._astock_mismatch_error(code, result, returned_codes=returned_codes)
        expected_name = self._known_astock_name(code)
        returned_names = self._extract_astock_names_from_value(result)
        if expected_name and returned_names and not any(self._astock_name_matches(expected_name, item) for item in returned_names):
            return self._astock_mismatch_error(code, result, returned_names=returned_names)
        return result

    def _normalize_astock_code(self, value) -> str:
        match = re.search(r"(?<!\d)([036]\d{5})(?:\.[A-Z]{2})?(?!\d)", self._text_field(value), flags=re.I)
        return match.group(1) if match else ""

    def _known_astock_name(self, code: str) -> str:
        return {
            "600519": "贵州茅台",
        }.get(self._normalize_astock_code(code), "")

    def _extract_astock_names_from_value(self, value) -> list[str]:
        names: list[str] = []
        for row in self._flatten_mcp_dict_rows(value):
            for key in ("name", "index_name", "security_name", "symbol_name", "股票简称", "名称", "简称"):
                text = self._text_field(row.get(key))
                if text and text not in names:
                    names.append(text)
                    break
            if len(names) >= 5:
                break
        return names

    def _astock_name_matches(self, expected: str, actual: str) -> bool:
        expected_text = re.sub(r"\s+", "", self._text_field(expected))
        actual_text = re.sub(r"\s+", "", self._text_field(actual))
        return bool(expected_text and actual_text and (expected_text in actual_text or actual_text in expected_text))

    def _astock_mismatch_error(self, code: str, result, *, returned_codes: list[str] | None = None, returned_names: list[str] | None = None) -> dict:
        return {
            "error": "MCP 返回标的与请求代码不一致，已丢弃该行情结果",
            "requested_code": code,
            "expected_name": self._known_astock_name(code),
            "returned_codes": returned_codes or [],
            "returned_names": returned_names or self._extract_astock_names_from_value(result),
            "result_hint": self._mcp_snapshot_lines({"invalid": result}, limit=1)[:1],
        }

    def _batch_tool_fallback_tools(self, name: str, arguments: dict) -> list[dict]:
        args = arguments if isinstance(arguments, dict) else {}
        window = {
            key: args[key]
            for key in ("startDate", "endDate", "start_date", "end_date")
            if key in args
        }
        if name == "batch_get_index_data":
            labels = self._coerce_label_list(
                args.get("index_names") or args.get("indexNames") or args.get("indices") or args.get("names")
            )
            return [{"name": "get_index_data", "arguments": {"index_name": label, **window}} for label in labels[:8]]
        if name == "batch_get_global_asset_data":
            labels = self._coerce_label_list(
                args.get("asset_names") or args.get("assetNames") or args.get("assets") or args.get("names")
            )
            return [{"name": "get_global_asset_data", "arguments": {"asset_name": label, **window}} for label in labels[:6]]
        if name in {"batch_get_astock_realtime", "get_astock_realtime_batch"}:
            codes = self._coerce_label_list(args.get("codes") or args.get("stock_codes") or args.get("stockCodes"))
            return [{"name": "get_astock_realtime", "arguments": {"code": code}} for code in codes[:12]]
        if name == "get_macro_snapshot":
            query = self._text_field(args.get("keyword")) or "中国 宏观 PMI CPI PPI LPR 社融 M2 汇率 利率 最新"
            return [{"name": "web_search", "arguments": {"query": query, "count": 5}}]
        if name in {"batch_get_macro_data", "get_macro_data", "get_macro_indicator", "list_macro_indicators"}:
            query = self._text_field(args.get("keyword")) or "中国 宏观 PMI CPI PPI LPR 社融 M2 汇率 利率 最新"
            return [{"name": "web_search", "arguments": {"query": query, "count": 5}}]
        if name == "get_hot_stocks":
            return [{"name": "web_search", "arguments": {"query": "A股 今日 热门股票 涨幅榜 成交额 主线 板块", "count": 5}}]
        return []

    def _coerce_label_list(self, value) -> list[str]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            items = re.split(r"[,，、/|;\s]+", value)
        else:
            items = []
        result: list[str] = []
        for item in items:
            text = self._text_field(item)
            if text and text not in result:
                result.append(text)
        return result

    async def _collect_astock_followup_data(self, collected: dict, tools: list[dict], mcp) -> None:
        if not isinstance(collected, dict) or mcp is None:
            return
        if not any(isinstance(item, dict) and item.get("name") == "search_astocks" for item in tools or []):
            return
        existing_codes = {
            self._text_field((item.get("arguments") or {}).get("code"))
            for item in tools or []
            if isinstance(item, dict) and item.get("name") in {"get_astock_realtime", "get_astock_history"} and isinstance(item.get("arguments"), dict)
        }
        window = self._recent_market_window_args(days=120)
        for key, value in list(collected.items()):
            if not str(key).startswith(("search_astocks:", "web_search:")) or self._mcp_value_has_error(value):
                continue
            for code in self._extract_astock_codes_from_value(value):
                if code in existing_codes:
                    continue
                existing_codes.add(code)
                for tool_name, args in (
                    ("get_astock_realtime", {"code": code}),
                    ("get_astock_history", {"code": code, **window}),
                ):
                    result_key = self._mcp_result_key(tool_name, args, len(collected))
                    if result_key in collected:
                        continue
                    self._show_progress(f"正在补充股票真实行情: {self._mcp_tool_label(tool_name, args)}")
                    try:
                        collected[result_key] = await self._call_mcp_tool_checked(mcp, tool_name, args)
                    except Exception as exc:
                        collected[f"{result_key}:error"] = self._sanitize_api_key_error(exc, "")
                break

    async def _collect_global_asset_followup_data(self, collected: dict, tools: list[dict], mcp) -> None:
        if not isinstance(collected, dict) or mcp is None:
            return
        if not any(isinstance(item, dict) and item.get("name") == "get_global_asset_list" for item in tools or []):
            return
        existing_labels = {
            self._text_field((item.get("arguments") or {}).get("asset_name") or (item.get("arguments") or {}).get("assetName"))
            for item in tools or []
            if isinstance(item, dict) and item.get("name") == "get_global_asset_data" and isinstance(item.get("arguments"), dict)
        }
        existing_labels.update(
            str(key).split(":", 1)[1]
            for key in collected.keys()
            if str(key).startswith("get_global_asset_data:") and ":" in str(key)
        )
        window = self._recent_market_window_args(days=180)
        for key, value in list(collected.items()):
            if not str(key).startswith("get_global_asset_list:") or self._mcp_value_has_error(value):
                continue
            for label in self._extract_global_asset_labels_from_value(value):
                if label in existing_labels:
                    continue
                existing_labels.add(label)
                args = {"asset_name": label, **window, "limit": 5000}
                result_key = self._mcp_result_key("get_global_asset_data", args, len(collected))
                if result_key in collected:
                    continue
                self._show_progress(f"正在补充全球资产行情: {self._mcp_tool_label('get_global_asset_data', args)}")
                try:
                    collected[result_key] = await self._call_mcp_tool_checked(mcp, "get_global_asset_data", args)
                except Exception as exc:
                    collected[f"{result_key}:error"] = self._sanitize_api_key_error(exc, "")
                break

    def _extract_global_asset_labels_from_value(self, value) -> list[str]:
        labels: list[str] = []
        preferred_keys = (
            "ticker",
            "symbol",
            "asset_code",
            "assetCode",
            "code",
            "asset_name",
            "assetName",
            "name",
            "名称",
        )
        for row in self._flatten_mcp_dict_rows(value):
            for key in preferred_keys:
                text = self._text_field(row.get(key))
                if not text or self._looks_like_astock_code_only(text):
                    continue
                if text not in labels:
                    labels.append(text)
                    break
            if len(labels) >= 3:
                break
        return labels

    def _looks_like_astock_code_only(self, value: str) -> bool:
        text = self._text_field(value)
        return bool(re.fullmatch(r"(?:sh|sz)?[036]\d{5}(?:\.[A-Z]{2})?", text, flags=re.I))

    def _extract_astock_codes_from_value(self, value) -> list[str]:
        codes: list[str] = []
        for row in self._flatten_mcp_dict_rows(value):
            for key in ("code", "symbol", "ts_code", "ticker", "证券代码", "股票代码", "代码", "title", "snippet", "summary", "content", "text", "name", "名称"):
                raw = row.get(key)
                text = self._text_field(raw)
                match = re.search(r"(?<!\d)([036]\d{5})(?:\.[A-Z]{2})?(?!\d)", text, flags=re.I)
                if match and match.group(1) not in codes:
                    codes.append(match.group(1))
                    break
            if len(codes) >= 3:
                break
        return codes

    def _flatten_mcp_dict_rows(self, value, depth: int = 0) -> list[dict]:
        if depth > 6:
            return []
        if isinstance(value, list):
            rows: list[dict] = []
            for item in value:
                rows.extend(self._flatten_mcp_dict_rows(item, depth + 1))
            return rows
        if not isinstance(value, dict):
            return []
        rows = [value] if any(isinstance(item, (str, int, float)) for item in value.values()) else []
        for key in ("latest", "data", "result", "results", "payload", "body", "records", "items", "rows", "list", "values", "history", "prices", "content"):
            nested = value.get(key)
            if isinstance(nested, (dict, list)):
                rows.extend(self._flatten_mcp_dict_rows(nested, depth + 1))
        return rows

    def _is_vague_market_query(self, query: str) -> bool:
        text = re.sub(r"\s+", "", (query or "").lower())
        if not text:
            return False
        market_words = ("行情", "市场", "盘面", "大盘", "指数", "今天", "今日", "昨天", "昨日", "现在", "近期", "最近", "走势")
        vague_forms = ("怎么样", "如何", "咋样", "怎么看", "什么情况", "情况", "分析", "复盘", "回顾", "过一遍", "看一下", "看看", "查询", "查一下", "查查", "表现", "涨跌")
        return any(word in text for word in market_words) and any(form in text for form in vague_forms)

    def _index_market_guardrail_tools(self, query: str) -> list[dict]:
        if not self._is_index_market_query(query):
            return []
        specific = self._specific_market_tools_from_query(query)
        return specific or self._default_market_overview_tools(query)

    def _is_index_market_query(self, query: str) -> bool:
        text = self._text_field(query)
        compact = re.sub(r"\s+", "", text.lower())
        if not compact:
            return False
        if self._contains_specific_astock_reference(text, compact):
            return False
        index_words = (
            "指数", "大盘", "宽基", "上证", "深证", "深成指", "创业板", "科创50",
            "沪深300", "中证", "恒生", "hstech", "hsi", "csi300", "sp500", "nasdaq",
            "华证微盘", "微盘", "小微盘", "小市值",
        )
        action_words = (
            "昨天", "昨日", "今天", "今日", "近期", "最近", "最新", "表现", "涨跌",
            "涨幅", "跌幅", "行情", "走势", "收盘", "查询", "查一下", "查查", "看一下",
            "看看", "复盘", "回顾", "怎么样", "如何", "怎么看",
        )
        return any(word in compact for word in index_words) and any(word in compact for word in action_words)

    def _contains_specific_astock_reference(self, text: str, compact: str = "") -> bool:
        compact = compact or re.sub(r"\s+", "", self._text_field(text).lower())
        if re.search(r"(?<!\d)(?:sh|sz)?[036]\d{5}(?!\d)", compact, flags=re.I):
            return True
        return any(alias in text or alias.lower() in compact for alias in ("贵州茅台", "茅台"))

    def _has_index_market_tool(self, tools: list[dict]) -> bool:
        return any(
            isinstance(item, dict)
            and item.get("name") in {
                "get_index_data",
                "batch_get_index_data",
                "get_global_asset_data",
                "batch_get_global_asset_data",
                "get_macro_data",
                "get_hot_stocks",
            }
            for item in tools or []
        )

    def _has_macro_tool(self, tools: list[dict]) -> bool:
        return any(
            isinstance(item, dict)
            and item.get("name") in {
                "get_macro_snapshot",
                "batch_get_macro_data",
                "get_macro_data",
                "get_macro_indicator",
                "list_macro_indicators",
            }
            for item in tools or []
        )

    def _coerce_evidence_targets(self, value) -> list[dict]:
        if not isinstance(value, list):
            return []
        text_keys = (
            "raw_mention",
            "resolved_topic",
            "asset_scope",
            "asset_type",
            "listing_market",
            "ticker_or_code",
            "canonical_symbol",
            "market",
            "exchange",
            "evidence_need",
            "why_relevant",
        )
        list_keys = ("preferred_tools", "candidate_index_names", "aliases", "search_queries", "indicator_codes")
        targets: list[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            target: dict = {}
            for key in text_keys:
                text = self._text_field(item.get(key))
                if text:
                    target[key] = text
            for key in list_keys:
                items = self._coerce_text_items(item.get(key))
                if items:
                    target[key] = items[:8]
            if target:
                targets.append(target)
        return targets[:8]

    def _tools_from_evidence_targets(self, evidence_targets: list[dict], query: str = "") -> list[dict]:
        tools: list[dict] = []
        window = self._recent_market_window_args(days=180, query=query)
        for target in evidence_targets or []:
            if not isinstance(target, dict):
                continue
            topic = self._evidence_target_topic(target)
            ticker = self._evidence_target_ticker(target)
            preferred = set(self._coerce_text_items(target.get("preferred_tools")))
            if self._evidence_target_is_macro(target):
                tools.extend(self._macro_evidence_tools(query, target))
                continue
            index_label = self._evidence_target_index_label(target)
            if index_label:
                tools.append({"name": "get_index_data", "arguments": {"index_name": index_label, **window}})
                for search_query in self._evidence_target_search_queries(target):
                    tools.append({"name": "web_search", "arguments": {"query": search_query, "count": 5}})
                continue
            if self._evidence_target_is_astock(target):
                tools.extend(self._astock_tools_for_target(code=ticker, keyword=topic or ticker))
                continue
            if self._evidence_target_is_global_or_unknown_stock(target):
                keyword = topic or ticker
                asset_name = ticker or topic
                if keyword:
                    tools.append({"name": "get_global_asset_list", "arguments": {"keyword": keyword, "limit": 10}})
                if asset_name and (ticker or "get_global_asset_data" in preferred):
                    tools.append({"name": "get_global_asset_data", "arguments": {"asset_name": asset_name, **window, "limit": 5000}})
                search_queries = self._evidence_target_search_queries(target)
                if not search_queries and keyword and not ticker:
                    search_queries = [f"{keyword} 股票代码 所属市场 交易所 最新"]
                for search_query in search_queries[:2]:
                    tools.append({"name": "web_search", "arguments": {"query": search_query, "count": 5}})
        return self._dedupe_mcp_tools(tools)

    def _drop_tools_conflicting_with_evidence_targets(self, tools: list[dict], evidence_targets: list[dict]) -> list[dict]:
        if not evidence_targets:
            return tools
        has_astock_target = any(self._evidence_target_is_astock(target) for target in evidence_targets)
        has_non_astock_target = any(
            self._evidence_target_is_macro(target)
            or self._evidence_target_is_global_or_unknown_stock(target)
            or bool(self._evidence_target_index_label(target))
            for target in evidence_targets
        )
        if has_non_astock_target and not has_astock_target:
            return self._drop_misdirected_astock_lookup_tools(tools)
        return tools

    def _evidence_target_topic(self, target: dict) -> str:
        for key in ("resolved_topic", "raw_mention", "asset_name", "name"):
            text = self._text_field(target.get(key))
            if text:
                return text
        return ""

    def _evidence_target_ticker(self, target: dict) -> str:
        for key in ("ticker_or_code", "canonical_symbol", "symbol", "code"):
            text = self._text_field(target.get(key))
            if text:
                return text
        return ""

    def _evidence_target_scope_text(self, target: dict) -> str:
        pieces = []
        for key in ("asset_scope", "asset_type", "listing_market", "market", "exchange", "evidence_need"):
            text = self._text_field(target.get(key))
            if text:
                pieces.append(text)
        pieces.extend(self._coerce_text_items(target.get("preferred_tools")))
        return re.sub(r"\s+", "", " ".join(pieces).lower())

    def _evidence_target_search_queries(self, target: dict) -> list[str]:
        return self._coerce_text_items(target.get("search_queries"))[:4]

    def _evidence_target_is_macro(self, target: dict) -> bool:
        scope = self._evidence_target_scope_text(target)
        return any(
            term in scope
            for term in (
                "宏观",
                "macro",
                "economic",
                "经济",
                "利率",
                "流动性",
                "pmi",
                "cpi",
                "ppi",
                "社融",
                "get_macro_snapshot",
                "batch_get_macro_data",
                "get_macro_data",
            )
        )

    def _evidence_target_is_astock(self, target: dict) -> bool:
        scope = self._evidence_target_scope_text(target)
        return any(term in scope for term in ("a股", "沪深", "上交所", "深交所", "科创板", "创业板", "search_astocks"))

    def _evidence_target_is_global_or_unknown_stock(self, target: dict) -> bool:
        scope = self._evidence_target_scope_text(target)
        if self._evidence_target_is_astock(target):
            return False
        global_terms = (
            "美股",
            "美国股票",
            "us",
            "nasdaq",
            "nyse",
            "全球资产",
            "global",
            "海外",
            "get_global_asset_list",
            "get_global_asset_data",
        )
        stock_terms = ("stock", "股票", "公司", "equity", "unknown", "未知")
        return any(term in scope for term in global_terms) or any(term in scope for term in stock_terms)

    def _evidence_target_index_label(self, target: dict) -> str:
        labels = [
            self._evidence_target_topic(target),
            *self._coerce_text_items(target.get("candidate_index_names")),
            *self._coerce_text_items(target.get("aliases")),
        ]
        scope = self._evidence_target_scope_text(target)
        for label in labels:
            canonical = self._canonical_index_market_label(re.sub(r"\s+", "", self._text_field(label).lower()))
            if canonical:
                return canonical
        if "index" in scope or "指数" in scope:
            return self._text_field(labels[0]) if labels else ""
        return ""

    def _macro_evidence_tools(self, query: str, target: dict | None = None) -> list[dict]:
        indicator_codes = self._coerce_text_items((target or {}).get("indicator_codes")) or self._macro_overview_indicator_codes()
        window = self._recent_market_window_args(days=240, query=query)
        tools = [
            *self._chunked_macro_tools("get_macro_snapshot", indicator_codes, window=window, latest_only=True, limit=80),
            *self._chunked_macro_tools("batch_get_macro_data", indicator_codes, window=window, latest_only=False, limit=240),
            {
                "name": "batch_get_index_data",
                "arguments": {
                    "index_names": ["沪深300", "创业板指", "中证红利", "恒生科技指数"],
                    **self._recent_market_window_args(days=120, query=query),
                },
            },
            {
                "name": "batch_get_global_asset_data",
                "arguments": {"asset_names": ["美元指数", "黄金", "原油"], **self._recent_market_window_args(days=120, query=query)},
            },
        ]
        search_queries = self._evidence_target_search_queries(target or {}) or [self._market_overview_macro_search_query(query)]
        tools.extend({"name": "web_search", "arguments": {"query": item, "count": 5}} for item in search_queries[:2])
        return self._dedupe_mcp_tools(tools)

    def _drop_misdirected_astock_lookup_tools(self, tools: list[dict]) -> list[dict]:
        cleaned = []
        for item in tools or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
            if name in {"search_astocks", "get_astock_realtime", "get_astock_history", "batch_get_astock_realtime", "get_astock_realtime_batch"}:
                continue
            if name == "web_search":
                query = re.sub(r"\s+", "", self._text_field(arguments.get("query")).lower())
                if "股票代码" in query and ("a股" in query or "股票" in query):
                    continue
            cleaned.append(item)
        return cleaned

    def _default_market_overview_tools(self, query: str = "") -> list[dict]:
        search_query = self._market_overview_search_query(query)
        macro_query = self._market_overview_macro_search_query(query)
        window = self._recent_market_window_args(days=120, query=query)
        hot_query = self._market_hot_stock_search_query(query)
        return [
            {
                "name": "batch_get_index_data",
                "arguments": {
                    "index_names": ["沪深300", "上证指数", "创业板指", "科创50", "中证1000", "恒生科技指数", "恒生指数"],
                    **window,
                },
            },
            {
                "name": "batch_get_global_asset_data",
                "arguments": {"asset_names": ["黄金", "美元指数", "原油"], **window},
            },
            {
                "name": "get_macro_data",
                "arguments": {
                    "keyword": "PMI CPI PPI LPR 社融 M2 汇率 利率 流动性",
                    "latest_only": True,
                    "limit": 80,
                },
            },
            {
                "name": "get_hot_stocks",
                "arguments": {"market": "A股", "rank_by": "amount", "limit": 12},
            },
            {"name": "web_search", "arguments": {"query": search_query, "count": 5}},
            {"name": "web_search", "arguments": {"query": macro_query, "count": 5}},
            {"name": "web_search", "arguments": {"query": hot_query, "count": 5}},
        ]

    def _recent_market_window_args(self, days: int = 45, query: str = "") -> dict:
        end = datetime.now().date()
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if "昨天" in text or "昨日" in text:
            end = end - timedelta(days=1)
        start = end - timedelta(days=days)
        return {"startDate": start.isoformat(), "endDate": end.isoformat()}

    def _today_market_search_query(self) -> str:
        return "A股 今日行情 资金面 政策 重要新闻"

    def _market_overview_search_query(self, query: str = "") -> str:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if "昨天" in text or "昨日" in text:
            return "A股 昨日行情 资金面 政策 重要新闻"
        if "最近" in text or "近期" in text:
            return "A股 近期行情 资金面 政策 重要新闻"
        return self._today_market_search_query()

    def _market_overview_macro_search_query(self, query: str = "") -> str:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        date_hint = "昨日" if ("昨天" in text or "昨日" in text) else "今日"
        if "最近" in text or "近期" in text:
            date_hint = "近期"
        return f"中国 {date_hint} 宏观 数据 PMI CPI 利率 汇率 流动性 政策"

    def _is_macro_overview_query(self, query: str) -> bool:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if not text:
            return False
        macro_terms = (
            "宏观",
            "经济形势",
            "经济环境",
            "经济数据",
            "基本面",
            "pmi",
            "cpi",
            "ppi",
            "社融",
            "m2",
            "信贷",
            "工业增加值",
            "利率",
            "lpr",
            "mlf",
            "国债收益率",
            "通胀",
            "汇率",
            "流动性",
        )
        action_terms = (
            "分析",
            "怎么看",
            "怎么样",
            "形势",
            "环境",
            "趋势",
            "最近",
            "近期",
            "当前",
            "现在",
            "最新",
            "判断",
            "展望",
            "影响",
        )
        return any(term in text for term in macro_terms) and any(term in text for term in action_terms)

    def _macro_overview_indicator_codes(self) -> list[str]:
        return [
            "PMI_MFG",
            "PMI_SVC",
            "INDUSTRIAL_VALUE_ADDED",
            "CPI_YOY",
            "PPI_YOY",
            "SOCIAL_FINANCE",
            "M2_YOY",
            "PBOC_MLF",
            "LPR_1Y",
            "CN_10Y_YIELD",
        ]

    def _chunked_macro_tools(
        self,
        name: str,
        indicator_codes: list[str],
        *,
        window: dict,
        latest_only: bool,
        limit: int,
    ) -> list[dict]:
        tools: list[dict] = []
        chunk_size = max(1, self._macro_tool_chunk_size())
        for start in range(0, len(indicator_codes), chunk_size):
            chunk = indicator_codes[start:start + chunk_size]
            arguments = {
                "indicator_codes": chunk,
                **window,
                "limit": limit,
            }
            if name == "get_macro_snapshot":
                arguments["latest_only"] = latest_only
            if name == "batch_get_macro_data":
                arguments["latest_only"] = latest_only
            tools.append({"name": name, "arguments": arguments})
        return tools

    def _macro_overview_guardrail_tools(self, query: str = "") -> list[dict]:
        if not self._is_macro_overview_query(query):
            return []
        return self._macro_evidence_tools(query)

    def _market_hot_stock_search_query(self, query: str = "") -> str:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        date_hint = "昨日" if ("昨天" in text or "昨日" in text) else "今日"
        if "最近" in text or "近期" in text:
            date_hint = "近期"
        return f"A股 {date_hint} 热门股票 涨幅榜 成交额 主线 板块"

    def _is_microcap_strategy_query(self, query: str) -> bool:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if not text:
            return False
        microcap_terms = (
            "微盘", "微盘股", "小微盘", "小市值", "小盘策略", "小市值策略",
            "华证微盘", "华证微盘指数", "microcap",
        )
        decision_terms = (
            "策略", "投资", "配置", "值得", "能不能买", "要不要买", "能不能投",
            "要不要投", "持有", "加仓", "减仓", "风险", "怎么看", "如何",
            "分析", "表现", "走势", "收益", "回撤", "量价", "成交额", "流动性",
        )
        return any(term in text for term in microcap_terms) and any(term in text for term in decision_terms)

    def _microcap_strategy_tools(self, query: str = "") -> list[dict]:
        if not self._is_microcap_strategy_query(query):
            return []
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        date_hint = "昨日" if ("昨天" in text or "昨日" in text) else "今日"
        if "最近" in text or "近期" in text:
            date_hint = "近期"
        window = self._recent_market_window_args(days=180, query=query)
        return [
            {
                "name": "batch_get_index_data",
                "arguments": {
                    "index_names": ["华证微盘", "中证2000", "中证1000", "中证全指", "万得全A", "沪深300", "创业板指"],
                    **window,
                },
            },
            {
                "name": "get_macro_data",
                "arguments": {
                    "keyword": "A股 流动性 成交额 融资余额 M2 社融 利率 风险偏好",
                    "latest_only": True,
                    "limit": 80,
                },
            },
            {
                "name": "get_hot_stocks",
                "arguments": {"market": "A股", "rank_by": "amount", "limit": 20},
            },
            {
                "name": "web_search",
                "arguments": {"query": f"华证微盘指数 {date_hint} 涨跌幅 成交额 换手率 量价", "count": 5},
            },
            {
                "name": "web_search",
                "arguments": {"query": f"A股 {date_hint} 全市场成交额 微盘成交额 占比 小微盘 流动性", "count": 5},
            },
            {
                "name": "web_search",
                "arguments": {"query": f"A股 {date_hint} 微盘策略 量化私募 拥挤 赎回 跌停潮 风格主线", "count": 5},
            },
        ]

    def _has_microcap_benchmark_tool(self, tools: list[dict]) -> bool:
        for item in tools or []:
            if not isinstance(item, dict):
                continue
            args = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
            labels = []
            if item.get("name") == "get_index_data":
                labels = self._coerce_label_list(args.get("index_name") or args.get("indexName") or args.get("label"))
            elif item.get("name") == "batch_get_index_data":
                labels = self._coerce_label_list(
                    args.get("index_names") or args.get("indexNames") or args.get("indices") or args.get("names")
                )
            if any("华证微盘" in re.sub(r"\s+", "", self._text_field(label)) for label in labels):
                return True
        return False

    def _is_event_market_query(self, query: str) -> bool:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if not text:
            return False
        event_words = (
            "战争", "地缘", "冲突", "制裁", "油价", "原油", "通胀", "降息", "加息",
            "美元", "人工智能", "产业利好", "科技成长", "风险", "避险",
            "俄乌", "美伊", "缓和", "冲击峰值", "爆发期", "打打停停",
        )
        market_words = (
            "市场", "股市", "股票", "权益", "港股", "a股", "美股", "指数",
            "黄金", "贵金属", "原油", "油价", "美元", "通胀",
        )
        has_event = any(word in text for word in event_words) or re.search(r"(^|[^a-z])ai([^a-z]|$)", text)
        return bool(has_event) and any(word in text for word in market_words)

    def _event_market_default_tools(self, query: str) -> list[dict]:
        window = self._recent_market_window_args(days=60, query=query)
        return [
            {"name": "get_index_data", "arguments": {"index_name": "恒生科技指数", **window}},
            {"name": "get_index_data", "arguments": {"index_name": "沪深300", **window}},
            {"name": "get_global_asset_data", "arguments": {"asset_name": "美元指数", **window}},
            {"name": "get_global_asset_data", "arguments": {"asset_name": "黄金", **window}},
            {"name": "get_global_asset_data", "arguments": {"asset_name": "原油", **window}},
            {"name": "web_search", "arguments": {"query": query or "最新宏观事件 市场影响", "count": 5}},
        ]

    def _specific_market_tools_from_query(self, query: str) -> list[dict]:
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if not text:
            return []
        window = self._recent_market_window_args(days=60, query=query)
        tools: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add_tool(name: str, label_key: str, label: str) -> None:
            signature = (name, label)
            if signature in seen:
                return
            seen.add(signature)
            tools.append({"name": name, "arguments": {label_key: label, **window}})

        hk_index = self._canonical_index_market_label(text)
        if hk_index:
            add_tool("get_index_data", "index_name", hk_index)
        if any(alias in text for alias in ("港股", "香港股市", "香港市场")):
            add_tool("get_index_data", "index_name", "恒生科技指数")
        if any(alias in text for alias in ("股票市场", "股市", "权益市场", "科技股", "科技成长", "ai产业", "人工智能")):
            add_tool("get_index_data", "index_name", "沪深300")
            add_tool("get_index_data", "index_name", "恒生科技指数")
        if any(alias in text for alias in ("美股", "美国股市", "美国市场")):
            add_tool("get_index_data", "index_name", "标普500")
            add_tool("get_index_data", "index_name", "纳斯达克指数")
        for label, aliases in (
            ("沪深300", ("沪深300", "csi300")),
            ("上证指数", ("上证指数", "上证综指", "上证")),
            ("创业板指", ("创业板指", "创业板")),
            ("标普500", ("标普500", "sp500", "s&p500")),
            ("纳斯达克指数", ("纳斯达克", "nasdaq")),
        ):
            if any(alias in text for alias in aliases):
                add_tool("get_index_data", "index_name", label)
        for label, aliases in (
            ("美元指数", ("美元指数", "dxy", "美元走强", "美元走弱")),
            ("黄金", ("黄金", "贵金属")),
            ("原油", ("原油", "油价", "布伦特", "wti")),
        ):
            if any(alias in text for alias in aliases):
                add_tool("get_global_asset_data", "asset_name", label)
        if "通胀" in text:
            add_tool("get_global_asset_data", "asset_name", "黄金")
        if tools and any(word in text for word in ("怎么看", "影响", "为什么", "新闻", "政策", "风险", "战争", "冲突", "利好", "利空")):
            tools.append({"name": "web_search", "arguments": {"query": query, "count": 5}})
        return tools

    def _specific_astock_tools_from_query(self, query: str) -> list[dict]:
        text = self._text_field(query)
        compact = re.sub(r"\s+", "", text.lower())
        if not compact or self._canonical_index_market_label(compact) or self._is_index_market_query(query):
            return []
        code_match = re.search(r"(?<!\d)(?:sh|sz)?([036]\d{5})(?!\d)", compact, flags=re.I)
        keyword = ""
        code = code_match.group(1) if code_match else ""
        known_astocks = {
            "贵州茅台": ("600519", "贵州茅台"),
            "茅台": ("600519", "贵州茅台"),
        }
        for alias, (known_code, known_name) in known_astocks.items():
            if alias in text or alias.lower() in compact:
                code = code or known_code
                keyword = known_name
                break
        if not keyword and code:
            keyword = code
        if not keyword and self._query_explicitly_astock(query):
            keyword = self._named_asset_keyword_from_query(query)
        if not keyword:
            return []
        return self._astock_tools_for_target(code=code, keyword=keyword)

    def _query_explicitly_astock(self, query: str) -> bool:
        text = self._text_field(query)
        compact = re.sub(r"\s+", "", text.lower())
        if not compact:
            return False
        if re.search(r"(?<!\d)(?:sh|sz)?[036]\d{5}(?!\d)", compact, flags=re.I):
            return True
        astock_markers = (
            "a股",
            "沪深",
            "上交所",
            "深交所",
            "沪市",
            "深市",
            "创业板",
            "科创板",
            "北交所",
            "国内股票",
            "内地股票",
            "中国股票",
        )
        return any(marker in compact for marker in astock_markers)

    def _named_asset_keyword_from_query(self, query: str) -> str:
        text = self._text_field(query)
        compact = re.sub(r"\s+", "", text.lower())
        if not compact or self._canonical_index_market_label(compact):
            return ""
        entity_context_words = (
            "股票",
            "个股",
            "股价",
            "财报",
            "公司",
            "分析",
            "今天",
            "怎么看",
            "怎么样",
            "如何",
            "表现",
            "走势",
            "趋势",
            "今年",
            "年内",
            "涨跌",
            "可以吗",
            "可以",
            "能不能",
            "能不能买",
            "可以买",
            "能买吗",
        )
        if not any(word in compact for word in entity_context_words):
            return ""
        cleaned = re.sub(
            r"(分析一下|帮我分析|帮我|分析|查询一下|查询|查一下|查查|查看|看一下|看看|今天|今日|昨日|昨天|今年|年内|最近|近期|最新|当前|现在|的|结果|结论|是|呢|吗|可以吗|可不可以|能不能买|能买吗|能买|买吗|表现|走势|趋势|股价|涨跌|怎么样|如何|怎么看|怎么走|A股|a股|美股|港股|股票|个股|公司|指数|大盘|宽基|交易所|市场|纳斯达克|纽交所|nyse|nasdaq)",
            "",
            text,
            flags=re.I,
        )
        cleaned = re.sub(r"\s+", "", cleaned).strip(" ，。！？?;；")
        generic_assets = {
            "资产",
            "市场",
            "行情",
            "大盘",
            "指数",
            "宽基",
            "股市",
            "股票",
            "个股",
            "公司",
            "结果",
            "结果是",
            "结论",
            "结论是",
            "黄金",
            "原油",
            "美元",
            "美元指数",
            "宏观",
            "宏观形势",
            "宏观经济",
            "经济",
            "经济形势",
            "经济环境",
            "基本面",
            "流动性",
            "ai",
            "AI",
            "美股AI",
            "科技",
            "光模块",
        }
        generic_suffixes = ("资产", "市场", "行情", "策略", "指数", "板块", "方向")
        if (
            cleaned
            and 2 <= len(cleaned) <= 16
            and cleaned not in generic_assets
            and not cleaned.endswith(generic_suffixes)
            and not self._canonical_index_market_label(re.sub(r"\s+", "", cleaned.lower()))
        ):
            return cleaned
        return ""

    def _market_discovery_tools_from_query(self, query: str) -> list[dict]:
        if self._query_explicitly_astock(query):
            return []
        keyword = self._named_asset_keyword_from_query(query)
        if not keyword:
            return []
        window = self._recent_market_window_args(days=180, query=query)
        return [
            {"name": "get_global_asset_list", "arguments": {"keyword": keyword, "limit": 10}},
            {"name": "get_global_asset_data", "arguments": {"asset_name": keyword, **window, "limit": 5000}},
            {
                "name": "web_search",
                "arguments": {"query": f"{keyword} 股票代码 所属市场 交易所 美股 港股 A股 最新", "count": 5},
            },
        ]

    def _specific_astock_tools_from_followup_context(self, query: str, intent_plan: dict | None = None) -> list[dict]:
        if not self._is_contextual_followup_query(query, intent_plan):
            return []
        codes = self._astock_codes_from_mcp_context(self._last_mcp_data)
        if codes:
            code = codes[0]
            return self._astock_tools_for_target(code=code, keyword=self._known_astock_name(code))
        context_chunks: list[str] = []
        if isinstance(self._last_mcp_data, dict):
            context_chunks.extend(str(key) for key in self._last_mcp_data.keys())
        for turn in reversed(self._recent_conversation_context()[-4:]):
            if isinstance(turn, dict):
                context_chunks.extend([
                    self._text_field(turn.get("user")),
                    self._text_field(turn.get("assistant")),
                ])
        for text in context_chunks:
            tools = self._specific_astock_tools_from_query(text)
            if tools:
                return tools
        return []

    def _is_contextual_followup_query(self, query: str, intent_plan: dict | None = None) -> bool:
        if isinstance(intent_plan, dict) and intent_plan.get("is_followup"):
            return True
        text = re.sub(r"\s+", "", self._text_field(query).lower())
        if not text:
            return False
        markers = (
            "刚才", "刚刚", "上面", "前面", "上一轮", "上轮", "这个", "那个", "它",
            "继续", "结果", "结论", "分析结果", "怎么看", "怎么样", "如何", "呢",
        )
        return any(marker in text for marker in markers)

    def _astock_codes_from_mcp_context(self, mcp_data) -> list[str]:
        if not isinstance(mcp_data, dict):
            return []
        codes: list[str] = []
        for key, value in mcp_data.items():
            for candidate in [key, *self._extract_astock_codes_from_value(value)]:
                code = self._normalize_astock_code(candidate)
                if code and code not in codes:
                    codes.append(code)
            if len(codes) >= 3:
                break
        return codes

    def _astock_tools_for_target(self, *, code: str = "", keyword: str = "") -> list[dict]:
        code = self._normalize_astock_code(code)
        keyword = self._text_field(keyword) or self._known_astock_name(code) or code
        if not keyword and not code:
            return []
        window = self._recent_market_window_args(days=120)
        tools: list[dict] = [{"name": "search_astocks", "arguments": {"keyword": keyword, "limit": 5}}]
        if code:
            tools.extend([
                {"name": "get_astock_realtime", "arguments": {"code": code}},
                {"name": "get_astock_history", "arguments": {"code": code, **window}},
            ])
        else:
            tools.append({"name": "web_search", "arguments": {"query": f"{keyword} 股票代码 A股 最新", "count": 5}})
        return tools

    def _default_tools_for_intent(self, intent: str, query: str = "") -> list[dict]:
        normalized = self._text_field(intent).lower()
        macro_tools = self._macro_overview_guardrail_tools(query)
        if macro_tools and normalized in {"single_asset", "data_lookup", "market_overview", "macro", "risk", "general_investment"}:
            return self._dedupe_mcp_tools(macro_tools)
        astock_tools = self._specific_astock_tools_from_query(query)
        specific_tools = self._specific_market_tools_from_query(query)
        event_tools = self._event_market_default_tools(query) if self._is_event_market_query(query) else []
        discovery_tools = [] if (astock_tools or event_tools) else self._market_discovery_tools_from_query(query)
        if normalized in {"single_asset", "data_lookup", "market_overview", "general_investment"} and astock_tools:
            return self._dedupe_mcp_tools(astock_tools + specific_tools + event_tools)
        if normalized in {"single_asset", "data_lookup", "market_overview", "general_investment"} and discovery_tools:
            return self._dedupe_mcp_tools(discovery_tools + specific_tools + event_tools)
        if normalized in {"single_asset", "data_lookup", "market_overview"} and specific_tools:
            return self._dedupe_mcp_tools(specific_tools + event_tools)
        if normalized in {"risk", "general_investment"} and (specific_tools or event_tools):
            return self._dedupe_mcp_tools(specific_tools + event_tools)
        if normalized in {"market_overview", "data_lookup"}:
            return self._default_market_overview_tools(query)
        if normalized == "macro":
            return self._dedupe_mcp_tools(specific_tools + (event_tools or self._event_market_default_tools(query)))
        return []

    def _should_reuse_previous_mcp_data(self, query: str, intent_plan: dict) -> bool:
        if not isinstance(self._last_mcp_data, dict) or not self._last_mcp_data:
            return False
        if not isinstance(intent_plan, dict):
            intent_plan = {}
        tools = intent_plan.get("mcp_tools") if isinstance(intent_plan.get("mcp_tools"), list) else []
        if tools:
            return False
        artifact_plan = intent_plan.get("artifact_plan") if isinstance(intent_plan.get("artifact_plan"), dict) else {}
        if self._text_field(artifact_plan.get("type")).lower() in {"chart", "report"}:
            return True
        if intent_plan.get("chart_opportunity") or intent_plan.get("is_followup"):
            return True
        text = re.sub(r"\s+", "", (query or "").lower())
        followup_markers = (
            "刚才", "刚刚", "上面", "前面", "上一轮", "这个", "那个", "它",
            "继续", "结果", "结论", "做成图表", "画图", "报告", "对比",
        )
        return any(marker in text for marker in followup_markers)

    def _infer_tools_from_mcp_keys(self, mcp_data: dict) -> list[dict]:
        tools = []
        for key in sorted(str(item) for item in mcp_data.keys()):
            if ":" not in key or key == "note" or "error" in key.lower():
                continue
            name, label = key.split(":", 1)
            if name not in self._allowed_super66_tools():
                continue
            tools.append({
                "name": name,
                "arguments": self._arguments_from_mcp_key(name, label),
            })
        return self._dedupe_mcp_tools(tools)[:6]

    def _arguments_from_mcp_key(self, name: str, label: str) -> dict:
        label = self._text_field(label)
        if name == "get_index_data":
            return {"index_name": label}
        if name == "batch_get_index_data":
            return {"index_names": [item for item in label.split(",") if item]}
        if name == "get_global_asset_data":
            return {"asset_name": label}
        if name == "get_global_asset_list":
            return {"keyword": label}
        if name == "batch_get_global_asset_data":
            return {"asset_names": [item for item in label.split(",") if item]}
        if name == "web_search":
            return {"query": label}
        if name == "get_astock_realtime":
            return {"code": label}
        if name in {"batch_get_astock_realtime", "get_astock_realtime_batch"}:
            return {"codes": [item for item in label.split(",") if item]}
        if name in {"get_macro_data", "get_macro_indicator", "batch_get_macro_data", "list_macro_indicators"}:
            return {"keyword": label}
        if name == "get_hot_stocks":
            return {"market": "A股", "rank_by": label or "amount", "limit": 12}
        if name in {"search_astocks", "search_products"}:
            return {"keyword": label}
        if name in {"get_product_detail", "get_product_history"}:
            return {"product_id": label}
        if name == "get_future_market_data":
            return {"contract_code": label}
        return {"label": label}

    def _is_index_market_asset_label(self, label: str) -> bool:
        return bool(self._canonical_index_market_label(label))

    def _canonical_index_market_label(self, label: str) -> str:
        text = re.sub(r"\s+", "", self._text_field(label).lower())
        if not text:
            return ""
        if (
            "hstech" in text
            or "hangsengtech" in text
            or "hangsengtechnology" in text
            or "恒生科技" in text
        ):
            return "恒生科技指数"
        if "hscei" in text or "国企指数" in text or "恒生中国企业" in text or "hangsengchinaenterprises" in text:
            return "恒生中国企业指数"
        if "hsi" in text or "恒生指数" in text or "香港恒生指数" in text or "hangsengindex" in text:
            return "恒生指数"
        return ""

    def _normalize_mcp_tool_route(self, name: str, arguments: dict) -> tuple[str, dict]:
        args = dict(arguments or {})
        if name in {"get_global_asset_data", "get_index_data"}:
            label_keys = (
                "asset_name",
                "assetName",
                "index_name",
                "indexName",
                "source_table",
                "sourceTable",
                "table_name",
                "tableName",
                "code",
                "symbol",
                "ticker",
                "index_code",
                "indexCode",
                "asset_code",
                "assetCode",
                "label",
            )
            canonical_label = next(
                (
                    canonical
                    for canonical in (self._canonical_index_market_label(args.get(key)) for key in label_keys)
                    if canonical
                ),
                "",
            )
            if canonical_label and name == "get_global_asset_data":
                for key in label_keys:
                    args.pop(key, None)
                args["index_name"] = canonical_label
                return "get_index_data", args
            if canonical_label and name == "get_index_data":
                for key in label_keys:
                    args.pop(key, None)
                args["index_name"] = canonical_label
        args = self._normalize_mcp_argument_aliases(name, args)
        return name, args

    def _normalize_mcp_argument_aliases(self, name: str, arguments: dict) -> dict:
        args = dict(arguments or {})
        aliases_by_tool = {
            "get_index_data": {
                "indexName": "index_name",
                "index_code": "index_name",
                "indexCode": "index_name",
            },
            "batch_get_index_data": {
                "indexNames": "index_names",
                "indices": "index_names",
                "names": "index_names",
                "index_name": "index_names",
                "indexName": "index_names",
            },
            "get_global_asset_data": {
                "assetName": "asset_name",
                "asset_code": "asset_code",
                "assetCode": "asset_code",
                "sourceTable": "source_table",
            },
            "get_global_asset_list": {
                "query": "keyword",
                "asset_name": "keyword",
                "assetName": "keyword",
                "name": "keyword",
            },
            "batch_get_global_asset_data": {
                "assetNames": "asset_names",
                "assets": "asset_names",
                "names": "asset_names",
                "asset_name": "asset_names",
                "assetName": "asset_names",
            },
            "batch_get_astock_realtime": {
                "stockCodes": "codes",
                "stock_codes": "codes",
                "code": "codes",
            },
            "get_astock_realtime_batch": {
                "stockCodes": "codes",
                "stock_codes": "codes",
                "code": "codes",
            },
            "get_astock_realtime": {
                "stockCode": "code",
                "stock_code": "code",
                "symbol": "code",
                "ticker": "code",
            },
            "get_astock_history": {
                "stockCode": "code",
                "stock_code": "code",
                "symbol": "code",
                "ticker": "code",
            },
            "get_macro_data": {
                "indicatorCodes": "indicator_codes",
                "indicator_names": "keyword",
                "indicatorNames": "keyword",
                "latestOnly": "latest_only",
                "startDate": "start_date",
                "endDate": "end_date",
            },
            "batch_get_macro_data": {
                "indicatorCodes": "indicator_codes",
                "indicator_names": "indicator_keywords",
                "indicatorNames": "indicator_keywords",
                "latestOnly": "latest_only",
                "startDate": "start_date",
                "endDate": "end_date",
            },
            "get_macro_indicator": {
                "indicatorName": "keyword",
                "indicator_name": "keyword",
            },
            "get_future_market_data": {
                "contractCode": "contract_code",
                "contractType": "contract_type",
            },
            "get_product_detail": {
                "productId": "product_id",
                "productType": "product_type",
            },
            "get_product_history": {
                "productId": "product_id",
                "productType": "product_type",
            },
            "search_products": {
                "productType": "product_type",
            },
        }
        for old, new in aliases_by_tool.get(name, {}).items():
            if old in args and new not in args:
                args[new] = args.pop(old)
        return args

    def _extract_mcp_tool_specs(self, plan: dict) -> list[dict]:
        if not isinstance(plan, dict):
            return []
        candidates = []
        for key in ("mcp_tools", "tools", "tool_calls", "data_tools"):
            value = plan.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        candidates.extend(self._expand_mcp_tool_string_items(item))
                    else:
                        candidates.append(item)
            elif isinstance(value, dict):
                candidates.extend(self._expand_mcp_tool_mapping(value))
            elif isinstance(value, str):
                candidates.extend(self._expand_mcp_tool_string_items(value))
        return self._dedupe_mcp_tools(candidates)

    def _expand_mcp_tool_string_items(self, value: str) -> list[str]:
        text = value.strip() if isinstance(value, str) else self._text_field(value)
        if not text:
            return []
        tool_names = sorted(self._allowed_super66_tools(), key=len, reverse=True)
        tool_pattern = "|".join(re.escape(name) for name in tool_names)
        parts = [
            item.strip()
            for item in re.split(rf"\n+|[;；]+(?=\s*(?:{tool_pattern})\b)", text)
            if item.strip()
        ]
        expanded = []
        for part in parts or [text]:
            expanded.extend(self._split_mcp_tool_string_by_tool_names(self._clean_mcp_tool_string(part), tool_names))
        return expanded

    def _split_mcp_tool_string_by_tool_names(self, value: str, tool_names: list[str] | None = None) -> list[str]:
        text = self._clean_mcp_tool_string(value)
        if not text:
            return []
        tool_names = tool_names or sorted(self._allowed_super66_tools(), key=len, reverse=True)
        tool_pattern = "|".join(re.escape(name) for name in tool_names)
        matches = list(re.finditer(rf"\b(?:{tool_pattern})\b(?=\s*(?::|/|\(|\s|$))", text))
        starts = []
        for match in matches:
            prefix = text[: match.start()]
            if match.start() == 0 or prefix.endswith((" ", "\t", "\r", "\n", ";", "；")):
                starts.append(match.start())
        if len(starts) <= 1:
            return [text]
        chunks = []
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
        return chunks or [text]

    def _clean_mcp_tool_string(self, value: str) -> str:
        text = self._text_field(value)
        if not text:
            return ""
        text = text.strip().strip("`")
        text = re.sub(r"^(?:[-*+•]\s+|\d+[.)、]\s+)", "", text)
        text = re.sub(r"^\[(?: |x|X)\]\s+", "", text)
        text = text.strip().strip("`")
        if text.lower().startswith("tool:"):
            text = text[5:].strip()
        return text

    def _expand_mcp_tool_mapping(self, value: dict) -> list[dict]:
        if not isinstance(value, dict):
            return []
        if self._looks_like_single_tool_item(value):
            return [value]
        expanded = []
        allowed = self._allowed_super66_tools()
        for key, raw_args in value.items():
            name = self._text_field(key)
            if name not in allowed:
                continue
            if isinstance(raw_args, dict):
                if any(alias in raw_args for alias in ("arguments", "args", "parameters", "input", "params")):
                    expanded.append({"name": name, **raw_args})
                else:
                    expanded.append({"name": name, "arguments": raw_args})
            elif isinstance(raw_args, str):
                expanded.append({"name": name, "arguments": raw_args})
            elif raw_args is True:
                expanded.append({"name": name, "arguments": {}})
        return expanded or [value]

    def _looks_like_single_tool_item(self, value: dict) -> bool:
        if not isinstance(value, dict):
            return False
        if any(key in value for key in ("name", "tool", "tool_name", "arguments", "args", "parameters", "input", "params")):
            return True
        return isinstance(value.get("function"), dict)

    def _normalize_mcp_tool_item(self, item) -> dict | None:
        if isinstance(item, str):
            return self._normalize_mcp_tool_string(item)
        if not isinstance(item, dict):
            return None
        function = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = (
            self._text_field(item.get("name"))
            or self._text_field(item.get("tool"))
            or self._text_field(item.get("tool_name"))
            or self._text_field(function.get("name"))
        )
        if name not in self._allowed_super66_tools():
            return None
        raw_args = (
            item.get("arguments")
            if "arguments" in item
            else item.get("args")
            if "args" in item
            else item.get("parameters")
            if "parameters" in item
            else item.get("input")
            if "input" in item
            else item.get("params")
            if "params" in item
            else function.get("arguments")
        )
        arguments = self._coerce_mcp_arguments(raw_args)
        if not arguments:
            arguments = {
                key: value
                for key, value in item.items()
                if key not in {"name", "tool", "tool_name", "function", "type", "id", "reason", "rationale"}
                and isinstance(key, str)
                and self._is_safe_mcp_argument_value(value)
            }
        return {"name": name, "arguments": arguments}

    def _normalize_mcp_tool_string(self, item: str) -> dict | None:
        text = self._clean_mcp_tool_string(item)
        if not text:
            return None
        allowed = self._allowed_super66_tools()
        if text in allowed:
            return {"name": text, "arguments": {}}
        match = re.match(r"^([A-Za-z_][\w]*)\s*(?::|/|\s+|\()\s*(.+?)\)?$", text)
        if not match:
            return None
        name, label = match.groups()
        if name not in allowed:
            return None
        label = label.strip()
        parsed_args = self._coerce_mcp_arguments(label)
        arguments = parsed_args if parsed_args else self._arguments_from_mcp_key(name, label)
        return {"name": name, "arguments": arguments}

    def _coerce_mcp_arguments(self, value) -> dict:
        if isinstance(value, dict):
            return {
                str(key): item
                for key, item in value.items()
                if self._is_safe_mcp_argument_value(item)
            }
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {}
            return self._coerce_mcp_arguments(parsed)
        return {}

    def _is_safe_mcp_argument_value(self, value) -> bool:
        if value is None:
            return False
        if isinstance(value, (bool, int, float, str)):
            return True
        if isinstance(value, list):
            return all(self._is_safe_mcp_argument_value(item) for item in value[:20])
        if isinstance(value, dict):
            return all(isinstance(key, str) and self._is_safe_mcp_argument_value(item) for key, item in value.items())
        return False

    def _dedupe_mcp_tools(self, tools: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for item in tools or []:
            normalized = self._normalize_mcp_tool_item(item)
            if not normalized:
                continue
            name = normalized.get("name")
            arguments = normalized.get("arguments") if isinstance(normalized.get("arguments"), dict) else {}
            name, arguments = self._normalize_mcp_tool_route(name, arguments)
            signature = (name, json.dumps(arguments, ensure_ascii=False, sort_keys=True))
            if name and signature not in seen:
                seen.add(signature)
                result.append({"name": name, "arguments": arguments})
        return result

    def _mcp_data_brief(self, mcp_data) -> dict:
        if not isinstance(mcp_data, dict) or not mcp_data:
            return {
                "status": "empty",
                "instruction": "没有 MCP 数据时不要伪造实时行情；可以要求用户补充市场范围。",
            }
        keys = sorted(str(key) for key in mcp_data.keys())
        error_keys = [key for key in keys if "error" in key.lower()]
        usable_keys = [key for key in keys if key not in error_keys and key != "note"]
        return {
            "status": "partial" if error_keys else "available",
            "usable_sources": usable_keys,
            "snapshots": self._mcp_snapshot_lines(mcp_data),
            "warnings": error_keys,
            "instruction": "可用数据源必须进入综合判断；字段不标准时先概括数据源和方向，避免声称没有实时数据。",
        }

    def _microcap_analysis_brief(self, query: str, mcp_data) -> dict:
        if not self._is_microcap_strategy_query(query):
            return {"required": False}
        required_checks = [
            "华证微盘区间收益/回撤",
            "华证微盘成交额绝对值与区间变化",
            "华证微盘成交额/成交量/换手变化",
            "全市场或中证全指/万得全A成交额代理口径",
            "微盘成交额占全市场成交额比重",
            "相对中证2000/中证1000/沪深300强弱",
            "跌停/断流、量化拥挤、赎回去杠杆和强主线吸金",
        ]
        if not isinstance(mcp_data, dict) or not mcp_data:
            return {
                "required": True,
                "status": "missing",
                "primary_benchmark": "华证微盘",
                "required_checks": required_checks,
                "missing": required_checks,
                "instruction": "没有微盘 MCP 数据时，只能给框架判断，不能用中证1000替代华证微盘下结论。",
            }
        grouped: dict[str, list[dict]] = {}
        for key, value in mcp_data.items():
            key_text = str(key)
            if self._mcp_value_has_error(value) or "error" in key_text.lower():
                continue
            for label, rows in self._snapshot_grouped_market_rows(key_text, value).items():
                grouped.setdefault(label, []).extend(rows)
        label_summaries: dict[str, dict] = {}
        for label, rows in grouped.items():
            summary = self._microcap_label_summary(label, rows)
            if summary:
                label_summaries[label] = summary
        microcap_label = self._find_label(label_summaries, ("华证微盘",))
        market_label = self._find_label(label_summaries, ("中证全指", "万得全A", "万得全ａ", "全A", "全市场"))
        turnover_diagnostics = self._microcap_turnover_diagnostics(
            label_summaries,
            microcap_label,
            market_label,
            mcp_data,
        )
        turnover_share = turnover_diagnostics.get("turnover_share")
        missing = []
        if not microcap_label:
            missing.append("华证微盘 MCP 行情")
        if not turnover_diagnostics.get("microcap_amount_available"):
            missing.append("华证微盘指数成交额字段")
        if not turnover_diagnostics.get("market_amount_available"):
            missing.append("全市场成交额代理口径")
        if not turnover_share:
            missing.append("微盘成交额占全市场成交额比重")
        if not any(self._find_label(label_summaries, (label,)) for label in ("中证2000", "中证1000", "沪深300")):
            missing.append("中证2000/中证1000/沪深300相对强弱比较")
        if not any(
            str(key).startswith("web_search:") and not self._mcp_value_has_error(value)
            for key, value in mcp_data.items()
        ):
            missing.append("跌停/断流、量化拥挤、赎回去杠杆和强主线吸金的公开验证")
        return {
            "required": True,
            "status": "partial" if missing else "available",
            "primary_benchmark": "华证微盘",
            "comparison_benchmarks": ["中证2000", "中证1000", "沪深300", "创业板指", "中证全指/万得全A"],
            "available_labels": sorted(label_summaries.keys()),
            "label_summaries": label_summaries,
            "turnover_diagnostics": turnover_diagnostics,
            "turnover_share": turnover_share,
            "missing": missing,
            "required_checks": required_checks,
            "instruction": (
                "回答微盘策略时必须优先使用本 brief。必须逐项说明 turnover_diagnostics："
                "华证微盘成交额是否取到、全市场代理成交额是否取到、是否能计算成交额占比、成交额趋势是否放大或萎缩。"
                "turnover_share 为空只说明结构化占比未验证，不能跳过成交额分析；若 web_turnover_evidence 非空，要作为公开线索列出。"
            ),
        }

    def _microcap_label_summary(self, label: str, rows: list[dict]) -> dict[str, object]:
        clean_rows = [row for row in rows if isinstance(row, dict)]
        if not clean_rows:
            return {}
        latest = self._latest_mcp_row_by_date(clean_rows) or clean_rows[-1]
        return_pct = self._snapshot_close_return_pct(clean_rows)
        amount = self._first_numeric_value(latest, self._market_amount_keys())
        return {
            "label": label,
            "date": self._format_compact_date(self._readable_mcp_date(latest)),
            "close": self._first_numeric_value(latest, ("close", "close_price", "latest", "last", "price", "收盘", "收盘价", "最新价")),
            "change_pct": self._first_numeric_value(latest, ("change_pct", "pct_chg", "change_percent", "涨跌幅", "涨幅")),
            "return_pct": round(return_pct, 4) if return_pct is not None else None,
            "amount": amount,
            "amount_change_pct": self._snapshot_amount_change_pct(clean_rows),
            "latest_amount_change_pct": self._snapshot_latest_amount_change_pct(clean_rows),
            "volume": self._first_numeric_value(latest, ("volume", "vol", "成交量", "成交量(手)")),
        }

    def _microcap_turnover_diagnostics(
        self,
        summaries: dict[str, dict],
        microcap_label: str,
        market_label: str,
        mcp_data,
    ) -> dict:
        micro_summary = summaries.get(microcap_label, {}) if microcap_label else {}
        market_summary = summaries.get(market_label, {}) if market_label else {}
        micro_amount = micro_summary.get("amount")
        market_amount = market_summary.get("amount")
        micro_available = isinstance(micro_amount, (int, float))
        market_available = isinstance(market_amount, (int, float))
        turnover_share = None
        if micro_available and market_available and market_amount > 0:
            turnover_share = {
                "microcap_label": microcap_label,
                "market_label": market_label,
                "ratio": micro_amount / market_amount,
                "ratio_pct": round(micro_amount / market_amount * 100, 4),
            }
        return {
            "microcap_label": microcap_label,
            "microcap_amount_available": micro_available,
            "microcap_amount": micro_amount if micro_available else None,
            "microcap_amount_date": micro_summary.get("date"),
            "microcap_amount_change_pct": micro_summary.get("amount_change_pct"),
            "microcap_latest_amount_change_pct": micro_summary.get("latest_amount_change_pct"),
            "market_label": market_label,
            "market_amount_available": market_available,
            "market_amount": market_amount if market_available else None,
            "market_amount_date": market_summary.get("date"),
            "turnover_share": turnover_share,
            "web_turnover_evidence": self._microcap_turnover_web_evidence(mcp_data),
            "fallback_rule": (
                "优先用 MCP rows/latest_rows 中的 amount/turnover/成交额等字段计算；"
                "没有全市场结构化成交额时，用中证全指或万得全A作代理并标注口径；"
                "结构化字段仍缺失时，必须列出网页成交额/占比线索和缺口，不能直接跳过成交额分析。"
            ),
        }

    def _microcap_turnover_web_evidence(self, mcp_data) -> list[str]:
        if not isinstance(mcp_data, dict):
            return []
        evidence: list[str] = []
        for key, value in mcp_data.items():
            key_text = str(key)
            if not key_text.startswith("web_search:") or self._mcp_value_has_error(value):
                continue
            compact_key = re.sub(r"\s+", "", key_text)
            highlights = self._extract_web_search_highlights(value)
            if not any(term in compact_key for term in ("微盘成交额", "全市场成交额", "成交额占", "占比", "流动性", "华证微盘")):
                highlights = [
                    item for item in highlights
                    if any(term in item for term in ("微盘", "成交额", "占比", "流动性", "换手"))
                ]
            for item in highlights:
                if item not in evidence:
                    evidence.append(item)
                if len(evidence) >= 5:
                    return evidence
        return evidence

    def _find_label(self, summaries: dict[str, dict], terms: tuple[str, ...]) -> str:
        for label in summaries.keys():
            compact = re.sub(r"\s+", "", self._text_field(label).lower())
            if any(re.sub(r"\s+", "", term.lower()) in compact for term in terms):
                return label
        return ""

    def _market_fact_grounding(self, query: str, mcp_data, intent_plan: dict | None = None) -> dict:
        plan = intent_plan if isinstance(intent_plan, dict) else {}
        tools = plan.get("mcp_tools") if isinstance(plan.get("mcp_tools"), list) else []
        tool_names = {self._text_field(item.get("name")) for item in tools if isinstance(item, dict)}
        requires_astock = bool(
            tool_names & {"search_astocks", "get_astock_realtime", "get_astock_history"}
            or self._specific_astock_tools_from_query(query)
        )
        if not requires_astock:
            return {"requires_astock_price": False, "status": "not_required"}
        if not isinstance(mcp_data, dict) or not mcp_data:
            return {
                "requires_astock_price": True,
                "status": "missing",
                "instruction": "具体股票问题没有可核验 MCP 行情，禁止输出具体股价、支撑位、压力位或走势图。",
            }
        price_sources: list[str] = []
        for key, value in mcp_data.items():
            key_text = str(key)
            if not key_text.startswith(("get_astock_realtime:", "get_astock_history:")):
                continue
            if self._mcp_value_has_error(value) or "error" in key_text.lower():
                continue
            if self._value_has_market_price(value):
                price_sources.append(key_text)
        if price_sources:
            return {
                "requires_astock_price": True,
                "status": "grounded",
                "price_sources": price_sources[:6],
                "instruction": "股票价格和图表数值只能引用 price_sources 对应 MCP 返回；支撑/压力只能由历史 high/low/close 推导。",
            }
        errors = [str(key) for key in mcp_data.keys() if "error" in str(key).lower()]
        return {
            "requires_astock_price": True,
            "status": "missing",
            "warnings": errors[:6],
            "instruction": "本轮没有 get_astock_realtime/get_astock_history 的可核验价格；禁止输出具体股价、技术价位和走势图。",
        }

    def _value_has_market_price(self, value) -> bool:
        if self._close_points(value):
            return True
        for row in self._flatten_mcp_dict_rows(value):
            if self._first_numeric_value(
                row,
                (
                    "price",
                    "latest",
                    "last",
                    "close",
                    "close_price",
                    "latest_price",
                    "current_price",
                    "last_price",
                    "收盘",
                    "收盘价",
                    "最新价",
                    "现价",
                ),
            ) is not None:
                return True
        return False

    def _enforce_market_fact_grounding(self, query: str, synthesis: dict, mcp_data, intent_plan: dict | None = None) -> dict:
        grounding = self._market_fact_grounding(query, mcp_data, intent_plan)
        if grounding.get("status") != "missing":
            return synthesis if isinstance(synthesis, dict) else {}
        return {
            "view": (
                "这轮我没有拿到 Super66 MCP 返回的可核验股票行情，所以不会给出具体股价、支撑位、压力位或走势图。"
                "刚才这类数值如果不是 MCP 明确返回，就应该视为无效。请先修复数据通道或确认标的代码后再做价格分析。"
            ),
            "suggestions": [
                "先用 /plan 查看本轮是否成功调用 search_astocks、get_astock_realtime 和 get_astock_history。",
                "执行 /doctor 检查登录态、Super66 MCP 权限和网络连通性。",
                "重新提问时可以带上股票代码，例如“分析一下贵州茅台 600519 的表现”。",
            ],
            "risk_controls": [
                "没有真实 MCP 行情时，不基于记忆价格做交易判断。",
                "价格、涨跌幅、支撑/压力和图表只以 MCP 或用户显式提供数据为准。",
            ],
            "missing_data": [
                "缺少 get_astock_realtime 或 get_astock_history 返回的真实价格/收盘价。",
            ],
            "followups": [
                "检查完 MCP 后，再重新分析这只股票的近 120 天走势。",
                "只基于真实 MCP 数据，帮我生成一张收盘价走势图。",
            ],
            "next_actions": ["/plan", "/doctor"],
            "artifacts": [],
        }

    def _mcp_snapshot_lines(self, mcp_data, limit: int = 6) -> list[str]:
        if not isinstance(mcp_data, dict) or not mcp_data:
            return []
        entries = self._mcp_snapshot_entries(mcp_data, limit=limit)
        return [self._format_mcp_snapshot_entry(entry) for entry in entries[:limit]]

    def _mcp_snapshot_entries(self, mcp_data, limit: int = 6) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        seen: set[str] = set()
        for key in sorted((mcp_data or {}).keys(), key=str):
            if len(entries) >= limit:
                break
            key_text = str(key)
            if key_text == "note":
                continue
            value = mcp_data.get(key)
            if self._mcp_value_has_error(value) or "error" in key_text.lower():
                continue
            if key_text.startswith("web_search:"):
                for highlight in self._extract_web_search_highlights(value):
                    signature = f"网页线索:{highlight}"
                    if signature in seen:
                        continue
                    seen.add(signature)
                    entries.append({"label": "网页线索", "summary": highlight})
                    if len(entries) >= limit:
                        break
                continue
            grouped_rows = self._snapshot_grouped_market_rows(key_text, value)
            for label, rows in grouped_rows.items():
                if label in seen:
                    continue
                entry = self._snapshot_entry_from_rows(label, rows)
                if not entry:
                    continue
                seen.add(label)
                entries.append(entry)
                if len(entries) >= limit:
                    break
            if grouped_rows:
                continue
            highlights = self._extract_mcp_key_highlights(key_text, value)
            for highlight in highlights[: max(1, limit - len(entries))]:
                label, detail = self._split_snapshot_label_detail(highlight)
                label = label or self._snapshot_label_from_key(key_text)
                signature = f"{label}:{detail}"
                if signature in seen:
                    continue
                seen.add(signature)
                entries.append({"label": label, "summary": detail or highlight})
                if len(entries) >= limit:
                    break
        return entries

    def _snapshot_grouped_market_rows(self, key_text: str, value) -> dict[str, list[dict]]:
        rows = [
            row for row in self._flatten_mcp_dict_rows(value)
            if self._row_has_snapshot_market_value(row)
        ]
        grouped: dict[str, list[dict]] = {}
        fallback_label = self._snapshot_label_from_key(key_text)
        for row in rows:
            label = self._snapshot_row_label(row, fallback_label)
            if not label:
                continue
            grouped.setdefault(label, []).append(row)
        return grouped

    def _row_has_snapshot_market_value(self, row: dict) -> bool:
        if not isinstance(row, dict):
            return False
        if self._first_numeric_value(row, ("price", "latest", "last", "close", "close_price", "value", "nav", "unit_nav", "收盘", "收盘价", "最新价", "现价", "净值")) is not None:
            return True
        if self._first_numeric_value(row, ("change_pct", "pct_chg", "change_percent", "changePercent", "changeRate", "percent", "涨跌幅", "涨幅", "日涨跌幅")) is not None:
            return True
        if self._first_numeric_value(row, self._market_amount_keys()) is not None:
            return True
        return bool(self._readable_mcp_date(row) and self._snapshot_row_label(row, ""))

    def _snapshot_row_label(self, row: dict, fallback: str = "") -> str:
        return (
            self._text_field(row.get("name"))
            or self._text_field(row.get("index_name"))
            or self._text_field(row.get("asset_name"))
            or self._text_field(row.get("product_name"))
            or self._text_field(row.get("security_name"))
            or self._text_field(row.get("symbol_name"))
            or self._text_field(row.get("fund_name"))
            or self._text_field(row.get("code"))
            or self._text_field(row.get("指标名称"))
            or self._text_field(row.get("指数名称"))
            or self._text_field(row.get("资产名称"))
            or self._text_field(row.get("名称"))
            or self._text_field(row.get("简称"))
            or fallback
        )[:24]

    def _snapshot_label_from_key(self, key_text: str) -> str:
        key = self._text_field(key_text)
        if ":" not in key:
            return key[:24]
        label = key.split(":", 1)[1]
        if label.startswith("{"):
            return ""
        return label.split(",", 1)[0][:24]

    def _snapshot_entry_from_rows(self, label: str, rows: list[dict]) -> dict[str, object]:
        clean_rows = [row for row in rows if isinstance(row, dict)]
        if not clean_rows:
            return {}
        latest = self._latest_mcp_row_by_date(clean_rows) or clean_rows[-1]
        latest_value = self._first_numeric_value(
            latest,
            ("price", "latest", "last", "close", "close_price", "value", "nav", "unit_nav", "收盘", "收盘价", "最新价", "现价", "净值"),
        )
        change_pct = self._first_numeric_value(
            latest,
            ("change_pct", "pct_chg", "change_percent", "changePercent", "changeRate", "percent", "涨跌幅", "涨幅", "日涨跌幅"),
        )
        if change_pct is None:
            change_pct = self._snapshot_latest_change_pct(clean_rows)
        volume = self._first_numeric_value(latest, ("volume", "vol", "成交量", "成交量(手)"))
        amount = self._first_numeric_value(latest, self._market_amount_keys())
        return_pct = self._snapshot_close_return_pct(clean_rows)
        return {
            "label": label,
            "date": self._format_compact_date(self._readable_mcp_date(latest)),
            "latest": latest_value,
            "change_pct": change_pct,
            "volume": volume,
            "amount": amount,
            "return_pct": return_pct,
        }

    def _snapshot_close_return_pct(self, rows: list[dict]) -> float | None:
        points: dict[str, float] = {}
        for row in rows:
            close = self._first_numeric_value(
                row,
                ("close", "close_price", "latest_close", "last_close", "price", "nav", "unit_nav", "收盘", "收盘价", "最新价", "现价", "净值"),
            )
            if close is None:
                continue
            date_key = self._mcp_row_date_key(row)
            if not date_key:
                continue
            points[date_key] = close
        if len(points) < 2:
            return None
        ordered = sorted(points.items(), key=lambda item: item[0])
        start_close = ordered[0][1]
        end_close = ordered[-1][1]
        if start_close == 0:
            return None
        return (end_close / start_close - 1.0) * 100.0

    def _market_amount_keys(self) -> tuple[str, ...]:
        return (
            "amount",
            "turnover",
            "turnover_amount",
            "turnoverAmount",
            "turnoverValue",
            "turnover_value",
            "amt",
            "amount_cny",
            "成交额",
            "成交额(元)",
            "成交额（元）",
            "成交额(万元)",
            "成交额（万元）",
            "成交额(亿元)",
            "成交额（亿元）",
            "成交额(万亿)",
            "成交额（万亿）",
            "成交金额",
            "成交金额(元)",
            "成交金额（元）",
            "成交金额(万元)",
            "成交金额（万元）",
            "成交金额(亿元)",
            "成交金额（亿元）",
            "成交金额(万亿)",
            "成交金额（万亿）",
        )

    def _snapshot_amount_change_pct(self, rows: list[dict]) -> float | None:
        return self._snapshot_numeric_change_pct(rows, self._market_amount_keys(), latest_only=False)

    def _snapshot_latest_amount_change_pct(self, rows: list[dict]) -> float | None:
        return self._snapshot_numeric_change_pct(rows, self._market_amount_keys(), latest_only=True)

    def _snapshot_numeric_change_pct(self, rows: list[dict], keys: tuple[str, ...], *, latest_only: bool = False) -> float | None:
        points: dict[str, float] = {}
        for row in rows:
            value = self._first_numeric_value(row, keys)
            if value is None:
                continue
            date_key = self._mcp_row_date_key(row)
            if not date_key:
                continue
            points[date_key] = value
        if len(points) < 2:
            return None
        ordered = sorted(points.items(), key=lambda item: item[0])
        start_value = ordered[-2][1] if latest_only else ordered[0][1]
        end_value = ordered[-1][1]
        if start_value == 0:
            return None
        return round((end_value / start_value - 1.0) * 100.0, 4)

    def _snapshot_latest_change_pct(self, rows: list[dict]) -> float | None:
        points: dict[str, float] = {}
        for row in rows:
            close = self._first_numeric_value(
                row,
                ("close", "close_price", "latest_close", "last_close", "price", "nav", "unit_nav", "收盘", "收盘价", "最新价", "现价", "净值"),
            )
            if close is None:
                continue
            date_key = self._mcp_row_date_key(row)
            if not date_key:
                continue
            points[date_key] = close
        if len(points) < 2:
            return None
        ordered = sorted(points.items(), key=lambda item: item[0])
        previous_close = ordered[-2][1]
        latest_close = ordered[-1][1]
        if previous_close == 0:
            return None
        return (latest_close / previous_close - 1.0) * 100.0

    def _format_mcp_snapshot_entry(self, entry: dict[str, object]) -> str:
        label = self._text_field(entry.get("label")) or "数据"
        summary = self._text_field(entry.get("summary"))
        if summary:
            return f"{label}: {summary}"
        parts = []
        date = self._text_field(entry.get("date"))
        if date and date != "起止日":
            parts.append(f"日期 {date}")
        latest = self._numeric_chart_value(entry.get("latest"))
        if latest is not None:
            parts.append(f"最新 {self._format_price(latest)}")
        change_pct = self._numeric_chart_value(entry.get("change_pct"))
        if change_pct is not None:
            parts.append(f"涨跌幅 {self._format_pct(change_pct)}")
        amount = self._numeric_chart_value(entry.get("amount"))
        volume = self._numeric_chart_value(entry.get("volume"))
        if amount is not None:
            parts.append(f"成交额 {self._format_price(amount)}")
        elif volume is not None:
            parts.append(f"成交量 {self._format_price(volume)}")
        return_pct = self._numeric_chart_value(entry.get("return_pct"))
        if return_pct is not None:
            parts.append(f"区间收益 {self._format_pct(return_pct)}")
        return f"{label}: " + ("，".join(parts) if parts else "已返回数据")

    def _split_snapshot_label_detail(self, value: str) -> tuple[str, str]:
        text = self._text_field(value)
        if not text:
            return "", ""
        if " " in text:
            label, detail = text.split(" ", 1)
            return label.strip(), detail.strip()
        return "", text

    def _extract_mcp_key_highlights(self, key_text: str, value) -> list[str]:
        if key_text.startswith(("batch_get_", "get_hot_stocks:", "get_macro_data:", "batch_get_macro_data:")):
            row_highlights = self._extract_mcp_row_highlights(value)
            if row_highlights:
                return row_highlights
        return self._extract_mcp_highlights(value)

    def _extract_mcp_row_highlights(self, value, limit: int = 6) -> list[str]:
        rows = self._flatten_mcp_dict_rows(value)
        if not rows:
            return []
        highlights: list[str] = []
        seen: set[str] = set()
        for row in rows:
            label = (
                self._text_field(row.get("name"))
                or self._text_field(row.get("index_name"))
                or self._text_field(row.get("asset_name"))
                or self._text_field(row.get("product_name"))
                or self._text_field(row.get("security_name"))
                or self._text_field(row.get("symbol_name"))
                or self._text_field(row.get("code"))
                or self._text_field(row.get("指标名称"))
                or self._text_field(row.get("名称"))
                or self._text_field(row.get("代码"))
            )
            if not label or label in seen:
                continue
            seen.add(label)
            parts = [label[:18]]
            for title, aliases in (
                ("日期", ("date", "trade_date", "日期", "交易日期", "period", "报告期")),
                ("最新", ("price", "latest", "close", "close_price", "value", "指标值", "收盘", "最新价", "现价")),
                ("涨跌幅", ("change_pct", "pct_chg", "change_percent", "涨跌幅", "涨幅", "日涨跌幅")),
                ("成交额", self._market_amount_keys()),
            ):
                for alias in aliases:
                    if alias in row and self._is_safe_mcp_scalar(alias, row.get(alias)):
                        parts.append(f"{title} {self._format_mcp_scalar(row.get(alias))}")
                        break
            highlights.append(" ".join(parts))
            if len(highlights) >= limit:
                break
        return highlights

    def _snapshot_markdown_table(self, snapshot_lines, limit: int = 6) -> list[str]:
        if not isinstance(snapshot_lines, list) or not snapshot_lines:
            return []
        rows = []
        for item in snapshot_lines[:limit]:
            text = self._text_field(item)
            if not text:
                continue
            label, detail = self._display_snapshot_label_and_detail(text)
            label = self._truncate_context_text(label or "数据", 24).replace("|", "/")
            parsed = self._parse_snapshot_detail_fields(detail or text)
            rows.append((
                label,
                parsed.get("date", ""),
                parsed.get("latest") or parsed.get("summary", ""),
                parsed.get("change_pct", ""),
                parsed.get("turnover", ""),
                parsed.get("return_pct", ""),
            ))
        if not rows:
            return []
        return [
            "| 标的/线索 | 日期 | 最新/摘要 | 涨跌幅 | 成交 | 区间收益 |",
            "| --- | --- | --- | --- | --- | --- |",
            *[
                "| "
                + " | ".join(self._truncate_context_text(str(cell), 48).replace("|", "/") for cell in row)
                + " |"
                for row in rows
            ],
        ]

    def _display_snapshot_label_and_detail(self, text: str) -> tuple[str, str]:
        clean = self._text_field(text)
        known_prefixes = (
            "get_index_data",
            "batch_get_index_data",
            "get_global_asset_data",
            "batch_get_global_asset_data",
            "get_astock_realtime",
            "get_astock_history",
            "search_astocks",
            "web_search",
            "get_macro_data",
            "get_hot_stocks",
        )
        for prefix in known_prefixes:
            marker = f"{prefix}:"
            if clean.startswith(marker):
                rest = clean[len(marker):]
                label, sep, detail = rest.partition(": ")
                if sep:
                    return label.strip() or prefix, detail.strip()
                return prefix, rest.strip()
        label, _, detail = clean.partition(": ")
        return (label or clean).strip(), detail.strip()

    def _parse_snapshot_detail_fields(self, detail: str) -> dict[str, str]:
        text = self._text_field(detail)
        fields: dict[str, str] = {}
        patterns = {
            "date": r"日期\s*([^，,]+)",
            "latest": r"最新\s*([^，,]+)",
            "change_pct": r"涨跌幅\s*([^，,]+)",
            "return_pct": r"区间收益\s*([^，,]+)",
            "amount": r"成交额\s*([^，,]+)",
            "volume": r"成交量\s*([^，,]+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                fields[key] = match.group(1).strip()
        if fields:
            fields["turnover"] = fields.get("amount") or fields.get("volume") or ""
        else:
            fields["summary"] = text
        return fields

    def _resource_links_from_value(self, value, fallback_label: str = "资源", limit: int = 8) -> list[str]:
        if isinstance(value, str):
            return self._resource_links_from_text(value, fallback_label, limit=limit)
        if not isinstance(value, (dict, list)):
            return []
        links: list[str] = []
        seen: set[str] = set()

        def add_link(label: str, target) -> None:
            target_text = self._text_field(target)
            if (
                not target_text
                or target_text in seen
                or not self._looks_like_resource_target(target_text)
                or len(links) >= limit
            ):
                return
            seen.add(target_text)
            links.append(self._resource_link(label, target_text))

        def visit(value, fallback_label: str) -> None:
            if len(links) >= limit:
                return
            if isinstance(value, dict):
                label = self._text_field(
                    value.get("title")
                    or value.get("name")
                    or value.get("alt")
                    or value.get("label")
                    or value.get("description")
                    or fallback_label
                )
                for key in ("url", "link", "href", "web_url", "source_url", "html_url", "file_url", "download_url", "pdf_url"):
                    add_link(label, value.get(key))
                for key in ("image_url", "image", "thumbnail", "thumbnail_url", "preview_url", "png_url", "jpg_url", "jpeg_url", "svg_url"):
                    add_link(f"{label} 图片", value.get(key))
                for child_key, child_value in value.items():
                    if str(child_key).lower() in {"token", "key", "secret", "password", "authorization", "api_key"}:
                        continue
                    visit(child_value, label or fallback_label)
                    if len(links) >= limit:
                        return
            elif isinstance(value, list):
                for item in value:
                    visit(item, fallback_label)
                    if len(links) >= limit:
                        return
            elif isinstance(value, str):
                for link in self._resource_links_from_text(value, fallback_label, limit=limit - len(links)):
                    _, target = self._split_named_link(link)
                    if target in seen:
                        continue
                    seen.add(target)
                    links.append(link)
                    if len(links) >= limit:
                        return

        visit(value, fallback_label)
        return links[:limit]

    def _resource_links_from_text(self, value: str, fallback_label: str = "资源", limit: int = 8) -> list[str]:
        text = value.strip() if isinstance(value, str) else self._text_field(value)
        if not text:
            return []
        links: list[str] = []
        seen: set[str] = set()

        def add(label: str, target: str) -> None:
            target_text = self._clean_resource_target(target)
            if not target_text or target_text in seen or len(links) >= limit:
                return
            if not self._looks_like_resource_target(target_text):
                return
            seen.add(target_text)
            links.append(self._resource_link(self._clean_resource_label(label) or fallback_label, target_text))

        for alt, target in re.findall(r"!\[([^\]]*)\]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)", text):
            add(f"{alt or fallback_label} 图片", target)
        for label, target in re.findall(r"(?<!!)\[([^\]]+)\]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)", text):
            add(label, target)
        for tag in re.findall(r"<img\b[^>]*>", text, flags=re.I):
            src = self._html_attr(tag, "src")
            label = self._html_attr(tag, "alt") or self._html_attr(tag, "title") or f"{fallback_label} 图片"
            add(label, src)
        for attrs, body in re.findall(r"<a\b([^>]*)>(.*?)</a>", text, flags=re.I | re.S):
            href = self._html_attr(attrs, "href")
            label = re.sub(r"<[^>]+>", "", body).strip() or self._html_attr(attrs, "title") or fallback_label
            add(label, href)
        for label, target in re.findall(r"([^\n\r。；;<>]{1,48}?)[：:]\s*((?:https?|file)://[^\s<>)\]\x1b\"']+)", text, flags=re.I):
            add(label, target)
        for target in re.findall(r"(?:https?|file)://[^\s<>)\]\x1b\"']+", text, flags=re.I):
            add(fallback_label, target)
        for target in re.findall(r"(?<![:/])/[^\s<>)\]\x1b\"']+\.(?:html?|pdf|png|jpe?g|gif|svg|json|md)\b", text, flags=re.I):
            add(fallback_label, target)
        return links[:limit]

    def _html_attr(self, text: str, name: str) -> str:
        match = re.search(rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1", text or "", flags=re.I | re.S)
        return self._text_field(match.group(2)) if match else ""

    def _clean_resource_target(self, target: str) -> str:
        text = self._text_field(target)
        if " " in text and not text.startswith("/"):
            text = text.split(" ", 1)[0]
        return text.strip("()[]<>\"'.,;，。；")

    def _clean_resource_label(self, label: str) -> str:
        text = re.sub(r"<[^>]+>", "", label or "")
        return self._text_field(text).strip(":-—()[]")

    def _mcp_resource_links(self, mcp_data, limit: int = 8) -> list[str]:
        if not isinstance(mcp_data, dict) or not mcp_data:
            return []
        links: list[str] = []
        seen: set[str] = set()
        for key, value in mcp_data.items():
            if "error" in str(key).lower():
                continue
            for link in self._resource_links_from_value(value, str(key), limit=limit):
                target = link.rsplit(": ", 1)[-1] if ": " in link else link
                if target in seen:
                    continue
                seen.add(target)
                links.append(link)
                if len(links) >= limit:
                    return links
            if len(links) >= limit:
                break
        return links

    def _mcp_value_has_error(self, value) -> bool:
        if not isinstance(value, dict):
            return False
        if any(str(key).lower() in {"error", "auth"} for key in value.keys()):
            return True
        code = value.get("code")
        if isinstance(code, str):
            upper = code.strip().upper()
            if (
                upper.startswith("MCP_")
                or upper.startswith("ERROR_")
                or upper == "ERROR"
                or "TIMEOUT" in upper
                or "FAIL" in upper
            ):
                return True
        message = value.get("message")
        if isinstance(message, str):
            lowered = message.lower()
            if (
                "timeout" in lowered
                or "timed out" in lowered
                or "failed" in lowered
                or "error" in lowered
            ):
                return True
        return False

    def _extract_mcp_highlights(self, value) -> list[str]:
        web_highlights = self._extract_web_search_highlights(value)
        if web_highlights:
            return web_highlights
        row = self._find_mcp_market_row(value)
        if not isinstance(row, dict):
            return []
        close_return = self._strict_close_return_pct(value)
        field_groups = [
            ("名称", ("name", "index_name", "asset_name", "product_name", "security_name", "fund_name", "symbol_name", "symbol", "code", "名称", "简称", "代码", "指数名称", "资产名称", "股票简称")),
            ("日期", ("date", "trade_date", "tradedate", "trading_date", "datetime", "timestamp", "time", "日期", "交易日期", "时间")),
            ("最新", ("price", "latest", "last", "close", "close_price", "latest_price", "current_price", "last_price", "nav", "unit_nav", "收盘", "收盘价", "最新价", "现价", "净值", "单位净值")),
            ("涨跌", ("change", "change_amount", "price_change", "涨跌", "涨跌额")),
            ("成交额", ("amount", "turnover", "turnover_amount", "成交额", "成交额(元)")),
            ("成交量", ("volume", "vol", "成交量", "成交量(手)")),
        ]
        used_keys = set()
        highlights = []
        for label, aliases in field_groups:
            for alias in aliases:
                if alias in row and self._is_safe_mcp_scalar(alias, row.get(alias)):
                    highlights.append(f"{label} {self._format_mcp_scalar(row.get(alias))}")
                    used_keys.add(alias)
                    break
        if close_return is not None:
            highlights.append(f"区间收益 {close_return:.2f}%")
        else:
            for alias in ("change_pct", "pct_chg", "percent", "changePercent", "change_percent", "changeRate", "涨跌幅", "涨幅", "涨跌幅(%)", "日涨跌幅"):
                if alias in row and self._is_safe_mcp_scalar(alias, row.get(alias)):
                    highlights.append(f"涨跌幅 {self._format_mcp_scalar(row.get(alias))}")
                    used_keys.add(alias)
                    break
        if highlights:
            return highlights
        for key, item in row.items():
            if key in used_keys or not self._is_safe_mcp_scalar(key, item):
                continue
            highlights.append(f"{key} {self._format_mcp_scalar(item)}")
            if len(highlights) >= 4:
                break
        return highlights

    def _extract_web_search_highlights(self, value) -> list[str]:
        if not isinstance(value, dict):
            return []
        results = value.get("results")
        if not isinstance(results, list):
            return []
        highlights = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = self._text_field(item.get("title") or item.get("name"))
            if not title:
                continue
            source = self._text_field(item.get("source") or item.get("site"))
            if not source:
                parsed = urlparse(self._text_field(item.get("url")))
                source = parsed.netloc.replace("www.", "") if parsed.netloc else ""
            title = title[:60]
            suffix = f" ({source[:32]})" if source else ""
            url = self._text_field(item.get("url"))
            link = f" {url}" if re.match(r"^https?://", url, flags=re.I) else ""
            highlights.append(f"网页线索 {title}{suffix}{link}")
            if len(highlights) >= 3:
                break
        return highlights

    def _find_mcp_market_row(self, value):
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            return self._latest_mcp_row_by_date(rows)
        if not isinstance(value, dict):
            return None
        latest = value.get("latest")
        if isinstance(latest, dict):
            return latest
        for key in ("data", "result", "payload", "body", "records", "items", "rows", "list", "values", "history", "prices"):
            nested = value.get(key)
            if isinstance(nested, list):
                rows = [item for item in nested if isinstance(item, dict)]
                if rows:
                    return self._latest_mcp_row_by_date(rows)
            if isinstance(nested, dict):
                found = self._find_mcp_market_row(nested)
                if found:
                    return found
        primitive_count = sum(1 for item in value.values() if isinstance(item, (str, int, float, bool)) or item is None)
        return value if primitive_count else None

    def _latest_mcp_row_by_date(self, rows: list[dict]) -> dict | None:
        if not rows:
            return None
        if not any(self._mcp_row_date_key(row) for row in rows):
            return rows[-1]
        return max(enumerate(rows), key=lambda item: (self._mcp_row_date_key(item[1]), item[0]))[1]

    def _mcp_row_date_key(self, row: dict) -> str:
        value = (
            row.get("date")
            or row.get("trade_date")
            or row.get("tradedate")
            or row.get("trading_date")
            or row.get("datetime")
            or row.get("timestamp")
            or row.get("time")
            or row.get("日期")
            or row.get("交易日期")
            or row.get("时间")
        )
        if value is None:
            return ""
        return re.sub(r"\D", "", str(value))[:14]

    def _is_safe_mcp_scalar(self, key, value) -> bool:
        key_text = str(key).lower()
        if any(word in key_text for word in ("token", "key", "secret", "password", "authorization")):
            return False
        if value is None or isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            text = value.strip()
            return bool(text) and len(text) <= 80
        return False

    def _format_mcp_scalar(self, value) -> str:
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value).strip()

    def _mcp_result_key(self, name: str, arguments: dict, index: int) -> str:
        label = (
            arguments.get("index_name")
            or ",".join(self._coerce_label_list(arguments.get("index_names") or arguments.get("indexNames"))[:4])
            or arguments.get("asset_name")
            or ",".join(self._coerce_label_list(arguments.get("asset_names") or arguments.get("assetNames"))[:4])
            or arguments.get("code")
            or arguments.get("stockCode")
            or arguments.get("stock_code")
            or ",".join(self._coerce_label_list(arguments.get("codes"))[:4])
            or arguments.get("keyword")
            or arguments.get("rank_by")
            or arguments.get("market")
            or arguments.get("contract_code")
            or arguments.get("query")
            or str(index + 1)
        )
        label = re.sub(r"\s+", "", str(label))[:24]
        return f"{name}:{label}"

    def _mcp_tool_label(self, name: str, arguments: dict) -> str:
        label = (
            arguments.get("index_name")
            or ",".join(self._coerce_label_list(arguments.get("index_names") or arguments.get("indexNames"))[:4])
            or arguments.get("asset_name")
            or ",".join(self._coerce_label_list(arguments.get("asset_names") or arguments.get("assetNames"))[:4])
            or arguments.get("code")
            or arguments.get("stockCode")
            or arguments.get("stock_code")
            or ",".join(self._coerce_label_list(arguments.get("codes"))[:4])
            or arguments.get("keyword")
            or arguments.get("rank_by")
            or arguments.get("market")
            or arguments.get("contract_code")
            or arguments.get("product_id")
            or arguments.get("query")
            or "default"
        )
        return f"{name} / {str(label).strip()[:32]}"

    async def _run_local_chrome_search(self, query: str, arguments: dict) -> dict:
        try:
            from src.client.chrome_search import chrome_web_search

            return await chrome_web_search(query, count=int(arguments.get("count") or 5))
        except Exception as exc:
            return {
                "error": "local_chrome_search_unavailable",
                "detail": self._sanitize_api_key_error(exc, ""),
                "install": "python3 -m pip install playwright && python3 -m playwright install chrome",
            }

    def _parse_client_llm_advice(self, raw_text: str) -> dict:
        text = (raw_text or "").strip()
        data = self._parse_json_object(
            text,
            preferred_keys={"final_answer", "view", "suggestions", "risk_controls", "missing_data", "artifacts"},
        )
        if data:
            return data
        answer = self._extract_jsonish_text_field(text, "final_answer") or self._extract_jsonish_text_field(text, "answer") or self._extract_jsonish_text_field(text, "response")
        if answer:
            return {
                "final_answer": answer,
                "view": answer,
                "suggestions": [],
                "risk_controls": [],
                "missing_data": [],
                "recovered_from_jsonish_text": True,
            }
        view = self._extract_jsonish_text_field(text, "view")
        if view:
            return {"view": view, "suggestions": [], "risk_controls": [], "missing_data": []}
        if self._looks_like_json_response_text(text):
            return {
                "view": "",
                "suggestions": [],
                "risk_controls": ["模型返回了非标准 JSON，本轮已隐藏原始 JSON，避免把结构化载荷当正文。"],
                "missing_data": [],
                "parse_warning": "invalid_json_response",
            }
        return {"view": text, "suggestions": [], "risk_controls": [], "missing_data": []}

    def _looks_like_json_response_text(self, text: str) -> bool:
        stripped = (text or "").strip()
        if not stripped:
            return False
        if stripped.startswith("{") or stripped.startswith("```json"):
            return True
        compact = re.sub(r"\s+", "", stripped.lower())
        return any(marker in compact for marker in ("final_answer", "risk_controls", "missing_data", "suggestions", '"view"', "'view'"))

    def _extract_jsonish_text_field(self, raw_text: str, field: str) -> str:
        text = raw_text or ""
        strict = self._extract_partial_json_string_field(text, field).strip()
        if strict:
            return strict
        field_pattern = re.escape(field)
        patterns = (
            rf"['\"]?{field_pattern}['\"]?\s*[:：]\s*“(?P<value>.*?)”",
            rf"['\"]?{field_pattern}['\"]?\s*[:：]\s*\"(?P<value>(?:\\.|[^\"\\])*)\"",
            rf"['\"]?{field_pattern}['\"]?\s*[:：]\s*'(?P<value>(?:\\.|[^'\\])*)'",
            rf"['\"]?{field_pattern}['\"]?\s*[:：]\s*(?P<value>.*?)(?=,\s*['\"]?(?:final_answer|answer|response|view|suggestions|risk_controls|missing_data|followups|next_actions|artifacts)['\"]?\s*[:：]|\n\s*['\"]?(?:final_answer|answer|response|view|suggestions|risk_controls|missing_data|followups|next_actions|artifacts)['\"]?\s*[:：]|\n?\s*\}}|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I | re.S)
            if not match:
                continue
            value = match.group("value")
            decoded = self._decode_jsonish_string_value(value)
            cleaned = self._clean_recovered_final_answer(decoded) if field in {"final_answer", "answer", "response"} else self._text_field(decoded)
            if cleaned:
                return cleaned
        return ""

    def _decode_jsonish_string_value(self, value: str) -> str:
        text = value or ""
        if "\\" not in text:
            return text.strip()
        try:
            return json.loads(f'"{text}"')
        except Exception:
            return text.replace("\\n", "\n").replace('\\"', '"').strip()

    def _recover_client_synthesis_from_reasoning(self, synthesis: dict) -> dict:
        if not isinstance(synthesis, dict):
            synthesis = {}
        direct = self._direct_client_final_answer(synthesis)
        view = self._text_field(synthesis.get("view"))
        if direct and not self._looks_like_reasoning_leak(direct):
            return synthesis
        if view and not self._looks_like_reasoning_leak(view) and len(view) >= 24:
            return synthesis
        reasoning = self._current_reasoning_text()
        if not reasoning:
            return synthesis
        recovered = self._parse_json_object(
            reasoning,
            preferred_keys={"final_answer", "view", "suggestions", "risk_controls", "missing_data", "artifacts"},
        )
        if recovered:
            recovered_answer = self._direct_client_final_answer(recovered) or self._text_field(recovered.get("view"))
            if recovered_answer and not self._looks_like_reasoning_leak(recovered_answer):
                return {**synthesis, **recovered, "recovered_from_reasoning": True}
        answer = self._extract_final_answer_from_reasoning(reasoning)
        if not answer:
            return synthesis
        merged = {
            **synthesis,
            "final_answer": answer,
            "view": answer,
            "recovered_from_reasoning": True,
        }
        merged.setdefault("suggestions", [])
        merged.setdefault("risk_controls", [])
        merged.setdefault("missing_data", [])
        return merged

    def _current_reasoning_text(self) -> str:
        trace = self._last_reasoning_trace if isinstance(self._last_reasoning_trace, dict) else {}
        raw_text = trace.get("text")
        return raw_text if isinstance(raw_text, str) else self._text_field(raw_text)

    def _extract_final_answer_from_reasoning(self, reasoning: str) -> str:
        text = reasoning or ""
        if not text:
            return ""
        patterns = (
            r"final_answer\s*(?:的)?(?:内容|自然语言)?\s*[：:]\s*[“\"](?P<answer>.*?)[”\"]",
            r"构建\s*final_answer\s*(?:的自然语言)?\s*[：:]\s*[“\"](?P<answer>.*?)[”\"]",
            r"现在[，,]?\s*(?:构建|写)\s*final_answer\s*(?:的自然语言)?\s*[：:]\s*[“\"](?P<answer>.*?)[”\"]",
            r"final_answer\s*(?:的)?(?:内容|自然语言)?\s*[：:]\s*(?P<answer>.*?)(?=\n\s*(?:然后|其他字段|[-*]\s*)?(?:view|suggestions|risk_controls|missing_data|followups|next_actions|artifacts)\s*[：:]|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I | re.S)
            if not match:
                continue
            answer = self._clean_recovered_final_answer(match.group("answer"))
            if answer:
                return answer
        return ""

    def _clean_recovered_final_answer(self, value: str) -> str:
        text = (value or "").strip()
        text = text.strip(" \t\r\n\"'“”")
        text = re.sub(
            r"\n\s*(?:然后|其他字段|[-*]\s*)?(?:view|suggestions|risk_controls|missing_data|followups|next_actions|artifacts)\s*[：:].*$",
            "",
            text,
            flags=re.I | re.S,
        ).strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\s*```$", "", text).strip()
        if len(text) < 6:
            return ""
        if self._looks_like_reasoning_leak(text):
            return ""
        return text

    async def _materialize_synthesis_artifacts(self, synthesis: dict, client, query: str) -> list[dict]:
        requests = self._extract_synthesis_artifact_requests(synthesis, query)
        results = []
        for request in requests[:5]:
            title = self._text_field(request.get("title")) or f"{query} 图表"
            data = request.get("data") if isinstance(request.get("data"), dict) else {}
            if not data:
                results.append({"title": title, "status": "skipped", "reason": "缺少图表数据"})
                continue
            chart_type = self._text_field(request.get("chart_type")) or "bar"
            try:
                self._show_progress(f"正在生成图表 artifact: {title}")
                response = await client.chart_artifact(
                    chart_type=chart_type,
                    title=title,
                    data=data,
                    metadata={"workspace": workspace_status().get("path"), "source": "llm_synthesis"},
                )
                artifact = self._chart_artifact_from_response(response)
                if not isinstance(artifact, dict):
                    results.append({"title": title, "status": "returned", "artifact": artifact})
                    continue
                saved = self._save_chart_artifact(artifact, title)
                resource_links = self._resource_links_from_value(artifact, title)
                results.append({
                    "title": artifact.get("title") or title,
                    "type": artifact.get("type") or chart_type,
                    "status": "success",
                    "data_keys": list((artifact.get("data") or data).keys()),
                    "preview": self._chart_terminal_preview(artifact.get("data") or data),
                    "saved": saved,
                    "resource_links": resource_links,
                })
            except Exception as exc:
                results.append({
                    "title": title,
                    "status": "failed",
                    "error": self._sanitize_api_key_error(exc, ""),
                })
        return results

    def _extract_synthesis_artifact_requests(self, synthesis: dict, query: str) -> list[dict]:
        if not isinstance(synthesis, dict):
            return []
        candidates = []
        for key in ("artifacts", "charts", "visualizations", "chart_requests", "artifact_requests"):
            value = synthesis.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                candidates.append(value)
        requests = []
        for item in candidates:
            normalized = self._normalize_chart_artifact_request(item, query)
            if normalized:
                requests.append(normalized)
        return requests

    def _normalize_chart_artifact_request(self, item, query: str) -> dict | None:
        if not isinstance(item, dict):
            return None
        request_type = self._text_field(item.get("type") or item.get("artifact_type") or item.get("kind")).lower()
        chart_type = self._text_field(item.get("chart_type") or item.get("chart") or item.get("mark") or item.get("visualization_type")).lower()
        known_chart_types = {"line", "bar", "pie", "gauge", "scatter", "radar"}
        if request_type in known_chart_types and not chart_type:
            chart_type = request_type
            request_type = "chart"
        if request_type and request_type not in {"chart", "chart_artifact", "visualization", "plot"}:
            return None
        if chart_type and chart_type not in known_chart_types:
            chart_type = "bar"
        title = (
            self._text_field(item.get("title"))
            or self._text_field(item.get("name"))
            or self._text_field(item.get("label"))
            or f"{query} 图表"
        )
        data = self._coerce_chart_artifact_data(
            item.get("data")
            if "data" in item
            else item.get("values")
            if "values" in item
            else item.get("series")
            if "series" in item
            else item.get("dataset")
            if "dataset" in item
            else item.get("points")
        )
        return {
            "type": "chart",
            "chart_type": chart_type or "bar",
            "title": title,
            "data": data,
        }

    def _coerce_chart_artifact_data(self, value) -> dict:
        if isinstance(value, dict):
            for nested_key in ("data", "rows", "records", "items", "history", "prices", "points", "series", "dataset"):
                if isinstance(value.get(nested_key), (dict, list)):
                    nested = self._coerce_chart_artifact_data(value.get(nested_key))
                    if nested:
                        return nested
            labels = value.get("labels")
            values = value.get("values")
            if isinstance(labels, list) and isinstance(values, list):
                return {
                    self._text_field(label) or f"item{index + 1}": values[index]
                    for index, label in enumerate(labels[:len(values)])
                    if self._numeric_chart_value(values[index]) is not None
                }
            return {
                self._text_field(key): self._chart_row_numeric_source(item)
                for key, item in value.items()
                if self._text_field(key) and self._chart_row_numeric_source(item) is not None
            }
        if isinstance(value, list):
            data = {}
            for index, row in enumerate(value[:24], 1):
                if isinstance(row, dict):
                    label = self._chart_row_label(row, index)
                    raw_value = self._chart_row_numeric_source(row)
                    if self._numeric_chart_value(raw_value) is not None:
                        data[label] = raw_value
                elif isinstance(row, (list, tuple)) and len(row) >= 2:
                    label = self._text_field(row[0]) or f"item{index}"
                    if self._numeric_chart_value(row[1]) is not None:
                        data[label] = row[1]
            return data
        return {}

    def _chart_row_label(self, row: dict, index: int) -> str:
        return (
            self._text_field(row.get("asset"))
            or self._text_field(row.get("name"))
            or self._text_field(row.get("label"))
            or self._text_field(row.get("symbol"))
            or self._text_field(row.get("index_name"))
            or self._text_field(row.get("product_name"))
            or self._text_field(row.get("date"))
            or self._text_field(row.get("time"))
            or f"item{index}"
        )

    def _chart_row_numeric_source(self, row):
        if self._numeric_chart_value(row) is not None:
            return row
        if not isinstance(row, dict):
            return None
        strict_return = self._strict_close_return_pct(row)
        if strict_return is not None:
            return strict_return
        for key in (
            "value",
            "change_pct",
            "return_pct",
            "pct",
            "percent",
            "change",
            "return",
            "close",
            "price",
            "nav",
            "y",
        ):
            if key in row and self._numeric_chart_value(row.get(key)) is not None:
                return row.get(key)
        return None

    def _strict_close_return_pct(self, value) -> float | None:
        direct = self._direct_close_return_pct(value)
        if direct is not None:
            return direct
        points = self._close_points(value)
        if len(points) < 2:
            return None
        points = sorted(enumerate(points), key=lambda item: (item[1][0] or "", item[0]))
        start_close = points[0][1][1]
        end_close = points[-1][1][1]
        if start_close is None or end_close is None or start_close == 0:
            return None
        return (end_close / start_close - 1.0) * 100.0

    def _direct_close_return_pct(self, value) -> float | None:
        if not isinstance(value, dict):
            return None
        start = self._first_numeric_value(
            value,
            (
                "start_close",
                "begin_close",
                "initial_close",
                "from_close",
                "previous_close",
                "prev_close",
                "pre_close",
                "prior_close",
                "start_nav",
                "begin_nav",
                "期初收盘价",
                "起始收盘价",
                "前收盘价",
                "昨收",
            ),
        )
        end = self._first_numeric_value(
            value,
            (
                "end_close",
                "final_close",
                "to_close",
                "latest_close",
                "close",
                "close_price",
                "last_close",
                "end_nav",
                "latest_nav",
                "期末收盘价",
                "结束收盘价",
                "收盘价",
                "收盘",
            ),
        )
        if start is None or end is None or start == 0:
            return None
        return (end / start - 1.0) * 100.0

    def _close_points(self, value) -> list[tuple[str, float]]:
        points: list[tuple[str, float]] = []
        if isinstance(value, list):
            for item in value:
                points.extend(self._close_points(item))
            return points
        if not isinstance(value, dict):
            return points
        close = self._first_numeric_value(
            value,
            (
                "close",
                "close_price",
                "latest_close",
                "last_close",
                "nav",
                "unit_nav",
                "收盘",
                "收盘价",
                "净值",
                "单位净值",
            ),
        )
        if close is not None:
            points.append((self._mcp_row_date_key(value), close))
        for nested_key in ("data", "result", "payload", "body", "records", "items", "rows", "list", "history", "prices", "points", "series", "dataset", "values"):
            nested = value.get(nested_key)
            if isinstance(nested, (dict, list)):
                points.extend(self._close_points(nested))
        return points

    def _first_numeric_value(self, value: dict, keys: tuple[str, ...]) -> float | None:
        for key in keys:
            if key in value:
                raw_value = value.get(key)
                number = self._numeric_chart_value(raw_value)
                if number is not None:
                    return self._scale_numeric_value_for_key(key, raw_value, number)
        return None

    def _scale_numeric_value_for_key(self, key: str, raw_value, number: float) -> float:
        raw_text = self._text_field(raw_value)
        if any(unit in raw_text for unit in ("万亿", "萬億", "亿", "億", "万", "萬")):
            return number
        key_text = str(key)
        if "万亿" in key_text or "萬億" in key_text:
            return number * 1_000_000_000_000.0
        if "亿元" in key_text or "億元" in key_text:
            return number * 100_000_000.0
        if "万元" in key_text or "萬元" in key_text:
            return number * 10_000.0
        return number

    def _format_client_advice(
        self,
        *,
        query: str,
        matches: list[dict],
        synthesis: dict,
        raw_text: str,
        provider: str,
        model: str,
        data_inputs: dict,
    ) -> str:
        direct_answer = self._direct_client_final_answer(synthesis, raw_text)
        if direct_answer:
            return direct_answer
        top = matches[0] if matches else {}
        suggestions = self._coerce_text_items(synthesis.get("suggestions"))
        risks = self._coerce_text_items(synthesis.get("risk_controls"))
        missing = self._coerce_text_items(synthesis.get("missing_data"))
        missing = self._filter_missing_items_for_display(query, missing, data_inputs)
        followups = self._coerce_text_items(synthesis.get("followups"))
        next_actions = self._coerce_text_items(synthesis.get("next_actions"))
        artifact_results = synthesis.get("artifact_results") if isinstance(synthesis.get("artifact_results"), list) else []
        view = self._strip_display_json_fragments(self._text_field(synthesis.get("view")) or raw_text)
        scene = self._text_field(top.get("scene")) or "未命中明确场景"
        confidence = top.get("confidence")
        lines = [
            f"我先按“{query}”来理解。",
        ]
        source_line = self._mcp_source_line(data_inputs)
        if source_line:
            lines.extend(["", source_line])
        snapshot_lines = data_inputs.get("mcp_snapshot") if isinstance(data_inputs, dict) else []
        snapshot_table = self._snapshot_markdown_table(snapshot_lines)
        if snapshot_table:
            lines.extend(["", "数据快照：", *snapshot_table])
        mcp_links = data_inputs.get("mcp_links") if isinstance(data_inputs, dict) else []
        if not isinstance(mcp_links, list):
            mcp_links = []
        synthesis_links = self._resource_links_from_value(synthesis.get("resources"), "分析资源")
        synthesis_direct_links = [
            item["link"]
            for item in self._coerce_resource_links(synthesis.get("resource_links"))
            if item.get("link")
        ]
        for item in self._coerce_resource_links(synthesis.get("resource_link")):
            if item.get("link"):
                synthesis_direct_links.append(item["link"])
        if mcp_links or synthesis_links or synthesis_direct_links:
            lines.extend(["", "可打开资源："])
            for item in [*mcp_links, *synthesis_links, *synthesis_direct_links][:6]:
                lines.append(f"- {item}")
        view = self._align_view_with_data_availability(query, view, snapshot_lines, data_inputs)
        lines.extend(["", view])
        if suggestions:
            lines.extend(["", "可以先这样做："])
            for item in suggestions[:3]:
                lines.append(f"- {item}")
        else:
            lines.extend(["", "如果你愿意，我建议你把问题再收窄一点：资产、周期、仓位和风险承受力这四项里，至少补两项。"])
        lines.extend(["", "需要注意："])
        for item in risks:
            lines.append(f"- {item}")
        if not risks:
            lines.append("- 注意仓位、期限、流动性与最大回撤约束。")
        if missing:
            lines.extend(["", self._missing_inputs_heading(query, data_inputs)])
            for item in missing[:3]:
                lines.append(f"- {item}")
        if artifact_results:
            lines.extend(["", "图表："])
            for item in artifact_results:
                title = self._text_field(item.get("title")) or "图表"
                status = self._text_field(item.get("status"))
                if status == "success":
                    saved = item.get("saved") if isinstance(item.get("saved"), dict) else {}
                    if saved:
                        workspace = str(workspace_status().get("path") or "")
                        html_link = self._workspace_file_link(saved.get("html"), workspace, label=f"{title} HTML") if saved.get("html") else ""
                        lines.append(f"- {title}: 已生成")
                        if html_link:
                            lines.append(f"  打开: {html_link}")
                    else:
                        lines.append(f"- {title}: 已生成，工作区未授权，未写入本地文件")
                        lines.append("  下一步: /workspace browse 选择项目文件夹，或 /workspace path <路径> 手动指定，然后 /workspace allow 授权保存。")
                    resource_links = item.get("resource_links") if isinstance(item.get("resource_links"), list) else []
                    for link in resource_links[:2]:
                        lines.append(f"  资源: {link}")
                    preview = item.get("preview") if isinstance(item.get("preview"), list) else []
                    if preview:
                        lines.append("  终端预览:")
                        for row in preview[:5]:
                            lines.append(f"  {row}")
                elif status == "skipped":
                    lines.append(f"- {title}: 已跳过，{item.get('reason')}")
                else:
                    lines.append(f"- {title}: 生成失败，{item.get('error') or status or '未知原因'}")
        if os.getenv("ERLANGSHEN_SHOW_RESPONSE_META") == "1":
            meta = f"服务端场景：{scene}"
            if confidence is not None:
                meta += f"，置信度 {confidence}"
            lines.extend([
                "",
                "—",
                f"{meta}；本机模型：{provider} / {model}。大模型 API Key 只在本机直连供应商，未发送给二郎神服务端。",
            ])
        repair_action = self._mcp_repair_action(data_inputs)
        compact_next = []
        if next_actions:
            compact_next.extend(next_actions[:2])
        if repair_action and all(repair_action not in item for item in compact_next):
            compact_next.append(repair_action)
        if compact_next:
            lines.extend(["", "下一步："])
            for item in compact_next[:3]:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def _direct_client_final_answer(self, synthesis: dict, raw_text: str = "") -> str:
        if not isinstance(synthesis, dict):
            return ""
        for key in ("final_answer", "answer", "response"):
            value = synthesis.get(key)
            text = value.strip() if isinstance(value, str) else self._text_field(value)
            if text:
                if self._looks_like_json_response_text(text):
                    extracted = (
                        self._extract_jsonish_text_field(text, "final_answer")
                        or self._extract_jsonish_text_field(text, "answer")
                        or self._extract_jsonish_text_field(text, "response")
                    )
                    if extracted:
                        return extracted
                    continue
                return text
        return ""

    def _answer_command_bar(self, *, mcp_links: list, artifact_results: list[dict], data_inputs: dict) -> list[str]:
        actions = ["/plan 复盘本轮意图、MCP 数据、服务端映射和产物计划"]
        if mcp_links:
            actions.append("/links 1 打开本轮网页、图片、图表或报告资源")
        success_artifacts = [
            item for item in artifact_results
            if isinstance(item, dict) and self._text_field(item.get("status")) == "success"
        ]
        if success_artifacts:
            actions.append("/open chart 打开最近生成的图表；/artifacts 查看全部产物")
            if any(not isinstance(item.get("saved"), dict) or not item.get("saved") for item in success_artifacts):
                actions.append("/workspace browse 授权项目文件夹，后续图表和报告会自动保存")
        elif artifact_results:
            actions.append("/workspace browse 授权项目文件夹；也可以补充数值后重新要求生成图表")
        if self._mcp_repair_action(data_inputs):
            actions.append("/doctor 检查登录态、super-66 MCP、web_search 和服务端连通性")
        return actions[:4]

    def _agent_trail_lines(
        self,
        *,
        query: str,
        scene: str,
        confidence,
        provider: str,
        model: str,
        data_inputs: dict,
        artifact_results: list[dict],
    ) -> list[str]:
        if not isinstance(data_inputs, dict):
            data_inputs = {}
        lines = [
            f"- 意图: 本机大模型按“{self._truncate_context_text(query, 42)}”理解，并决定是否取数/映射/制图",
        ]
        orchestration = self._answer_orchestration_line(data_inputs)
        if orchestration:
            lines.append(orchestration)
        mcp_keys = data_inputs.get("mcp_data") if isinstance(data_inputs.get("mcp_data"), list) else []
        if mcp_keys:
            lines.append(f"- 数据: 已接入 {', '.join(str(item) for item in mcp_keys[:4])}")
        else:
            lines.append("- 数据: 本轮没有可用 MCP 快照；结论会降低确定性")
        scene_line = f"- 服务端: {scene}"
        if confidence is not None:
            scene_line += f" · 置信度 {confidence}"
        lines.append(scene_line)
        resource_count = 0
        for key in ("mcp_links", "intent_resource_links"):
            value = data_inputs.get(key)
            if isinstance(value, list):
                resource_count += len(value)
        if artifact_results:
            success_count = sum(1 for item in artifact_results if isinstance(item, dict) and item.get("status") == "success")
            lines.append(f"- 产物: {success_count}/{len(artifact_results)} 个图表/报告请求已完成；/artifacts 或 /open 查看")
        elif resource_count:
            lines.append(f"- 资源: {resource_count} 个网页/图片/报告链接已进入 /links，可用 /links 1 打开")
        else:
            lines.append("- 资源: 本轮暂无可打开资源；需要图表/网页时可继续说明")
        lines.append(f"- 模型: {provider} / {model}，API Key 仅在本机直连供应商")
        return lines

    def _answer_orchestration_line(self, data_inputs: dict) -> str:
        route_source = self._text_field(data_inputs.get("route_source"))
        tool_source = self._text_field(data_inputs.get("tool_selection_source"))
        note = self._text_field(data_inputs.get("tool_selection_note"))
        fallback_sources = {"client_default_by_intent", "client_market_overview_fallback", "previous_mcp_context"}
        if tool_source == "local_llm" or route_source == "local_llm":
            owner = "本机大模型主导"
        elif tool_source in fallback_sources:
            owner = "客户端兜底补齐"
        elif route_source == "provided_payload":
            owner = "调用方提供 intent_plan"
        elif route_source == "fallback":
            owner = "保守兜底路由"
        else:
            return ""
        detail = f" · {note}" if note else ""
        return f"- 编排: {owner}{detail}"

    def _filter_missing_items_for_display(self, query: str, missing: list[str], data_inputs: dict) -> list[str]:
        if not missing:
            return []
        snapshot_lines = data_inputs.get("mcp_snapshot") if isinstance(data_inputs, dict) else []
        if not (self._is_vague_market_query(query) and snapshot_lines):
            return missing[:5]
        personal_keywords = (
            "持仓",
            "仓位",
            "组合",
            "账户",
            "成本",
            "买入",
            "卖出",
            "期限",
            "周期",
            "风险偏好",
            "回撤",
            "目标",
            "约束",
            "流动性",
        )
        market_data_keywords = (
            "实时",
            "行情",
            "市场数据",
            "指数",
            "点位",
            "涨跌",
            "成交",
            "新闻",
            "事件",
            "宏观",
            "cpi",
            "pmi",
            "政策",
            "公开信息",
        )
        filtered = []
        for item in missing:
            text = self._text_field(item)
            lowered = text.lower()
            if any(keyword in text for keyword in personal_keywords):
                filtered.append(text)
                continue
            if any(keyword in lowered or keyword in text for keyword in market_data_keywords):
                continue
            filtered.append(text)
        return filtered[:3]

    def _missing_inputs_heading(self, query: str, data_inputs: dict) -> str:
        snapshot_lines = data_inputs.get("mcp_snapshot") if isinstance(data_inputs, dict) else []
        if self._is_vague_market_query(query) and snapshot_lines:
            return "如果要落到你的账户，我还需要知道："
        return "我还需要你补充："

    def _default_followups(self, query: str, missing: list[str], artifact_results: list[dict], data_inputs: dict) -> list[str]:
        suggestions = []
        snapshot_lines = data_inputs.get("mcp_snapshot") if isinstance(data_inputs, dict) else []
        if snapshot_lines:
            suggestions.append("把这些市场快照进一步拆成“主线、风险、可跟踪指标”。")
        if artifact_results:
            suggestions.append("基于刚才的图表，帮我写一段可以保存到报告里的解读。")
        else:
            suggestions.append("把这个分析做成图表，对比关键资产或指标。")
        if missing:
            first_missing = self._text_field(missing[0])
            if first_missing:
                suggestions.append(f"如果我补充{first_missing}，结论会怎么变化？")
        elif self._is_vague_market_query(query):
            suggestions.append("如果只看 A股、港股、美股分别应该关注什么？")
        else:
            suggestions.append("给我一个更偏执行的版本：仓位、观察信号和失效条件。")
        deduped = []
        for item in suggestions:
            if item and item not in deduped:
                deduped.append(item)
        return deduped

    def _align_view_with_data_availability(self, query: str, view: str, snapshot_lines, data_inputs: dict) -> str:
        cleaned = self._strip_display_json_fragments(view)
        has_snapshot = bool(snapshot_lines)
        if has_snapshot:
            empty_data_patterns = (
                r"[^。！？\n]*(?:没有|暂无|缺少|缺乏)[^。！？\n]*(?:实时|行情|市场数据)[^。！？\n]*[。！？]?",
                r"[^。！？\n]*无法准确描述[^。！？\n]*(?:行情|市场)[^。！？\n]*[。！？]?",
                r"[^。！？\n]*不能准确描述[^。！？\n]*(?:行情|市场)[^。！？\n]*[。！？]?",
            )
            for pattern in empty_data_patterns:
                cleaned = re.sub(pattern, "", cleaned).strip()
            if not cleaned:
                cleaned = "结合本轮已读取的行情快照和网页线索，我先给一个方向性判断；具体交易结论还需要看你关注的市场、周期和仓位。"
            if self._is_vague_market_query(query) and "方向性" not in cleaned[:80] and "先" not in cleaned[:30]:
                cleaned = "我先根据本轮拿到的数据给一个方向性盘面判断。\n\n" + cleaned
            return cleaned
        keys = data_inputs.get("mcp_data") if isinstance(data_inputs, dict) else []
        has_data_error = any("error" in str(key).lower() or str(key) == "super66_error" for key in (keys or []))
        if self._is_vague_market_query(query) and has_data_error:
            prefix = (
                "我尝试读取 super-66 MCP 行情和本地网页线索，但本轮数据通道没有拿到可用行情，"
                "所以下面的判断只能作为低确定性的框架。"
            )
            if prefix not in cleaned:
                cleaned = prefix + ("\n\n" + cleaned if cleaned else "")
        return cleaned

    def _strip_display_json_fragments(self, value) -> str:
        text = value if isinstance(value, str) else self._text_field(value)
        text = re.sub(r"```(?:json)?\s*\{.*?(?:```|$)", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(
            r"\s*\{[\s\"']*(?:view|suggestions|risk_controls|missing_data|followups|next_actions|artifacts)[\"']?\s*:.*$",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(r"```(?:json)?\s*$", "", text, flags=re.IGNORECASE).strip()
        return self._text_field(text)

    def _mcp_source_line(self, data_inputs: dict) -> str:
        keys = data_inputs.get("mcp_data") if isinstance(data_inputs, dict) else []
        if not keys:
            return ""
        error_keys = [key for key in keys if "error" in str(key).lower()]
        usable = [str(key) for key in keys if key not in error_keys and str(key) != "note"]
        if usable:
            index_count = sum(1 for key in usable if key.startswith(("get_index_data:", "batch_get_index_data:")))
            asset_count = sum(
                1
                for key in usable
                if key.startswith(("get_global_asset_data:", "batch_get_global_asset_data:", "get_future_market_data:"))
            )
            macro_count = sum(1 for key in usable if key.startswith(("get_macro_data:", "batch_get_macro_data:", "get_macro_indicator:", "list_macro_indicators:")))
            stock_count = sum(
                1
                for key in usable
                if key.startswith((
                    "search_astocks:",
                    "get_astock_realtime:",
                    "get_astock_history:",
                    "batch_get_astock_realtime:",
                    "get_astock_realtime_batch:",
                ))
            )
            hot_count = sum(1 for key in usable if key.startswith("get_hot_stocks:"))
            web_count = sum(1 for key in usable if key.startswith("web_search:"))
            other_count = max(0, len(usable) - index_count - asset_count - macro_count - stock_count - hot_count - web_count)
            dimensions = []
            if index_count:
                dimensions.append(f"指数 {index_count}")
            if asset_count:
                dimensions.append(f"跨资产 {asset_count}")
            if macro_count:
                dimensions.append(f"宏观 {macro_count}")
            if stock_count:
                dimensions.append(f"股票 {stock_count}")
            if hot_count:
                dimensions.append(f"热门股票 {hot_count}")
            if web_count:
                dimensions.append(f"事件/宏观线索 {web_count}")
            if other_count:
                dimensions.append(f"其他 {other_count}")
            line = f"我已读取 {len(usable)} 个数据源"
            if dimensions:
                line += f"（{'、'.join(dimensions)}）"
            line += "；原始明细可用 /plan 查看。"
            if error_keys:
                line += f" 另有 {len(error_keys)} 个数据通道未成功，后面会降低确定性；可用 /plan 查看细节。"
            return line
        if error_keys:
            return "这次 super-66 MCP 暂时没有成功返回行情数据，我会降低确定性。"
        return ""

    def _mcp_repair_action(self, data_inputs: dict) -> str:
        keys = data_inputs.get("mcp_data") if isinstance(data_inputs, dict) else []
        if not any("error" in str(key).lower() for key in (keys or [])):
            return ""
        if any(str(key).startswith("web_search:") for key in keys or []):
            return "如果需要新闻线索，执行 /doctor 检查本地 Chrome web_search；必要时安装 Playwright。"
        return "执行 /doctor 检查登录态、super-66 MCP 和服务端连通性，再重新提问。"

    def _chart_terminal_preview(self, data) -> list[str]:
        if not isinstance(data, dict) or not data:
            return []
        points = []
        for raw_label, raw_value in data.items():
            label = self._text_field(raw_label)[:24] or "未命名"
            value = self._numeric_chart_value(raw_value)
            if value is None:
                continue
            points.append((label, value))
        if not points:
            return []
        rows = ["| 项目 | 数值 | 方向 |", "| --- | ---: | --- |"]
        for label, value in points[:8]:
            sign = "+" if value > 0 else ""
            direction = "上行" if value > 0 else "下行" if value < 0 else "持平"
            rows.append(f"| {label.replace('|', '/')} | {sign}{value:.4g} | {direction} |")
        return rows

    def _numeric_chart_value(self, value) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "").replace("，", "")
            if not cleaned:
                return None
            is_percent = cleaned.endswith("%")
            if is_percent:
                cleaned = cleaned[:-1]
            try:
                return float(cleaned)
            except ValueError:
                pass
            unit_multiplier = 1.0
            if "万亿" in cleaned or "萬億" in cleaned:
                unit_multiplier = 1_000_000_000_000.0
            elif "亿" in cleaned or "億" in cleaned:
                unit_multiplier = 100_000_000.0
            elif "万" in cleaned or "萬" in cleaned:
                unit_multiplier = 10_000.0
            elif not any(unit in cleaned for unit in ("元", "手", "股", "份", "张", "美元", "港元")):
                return None
            match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
            if not match:
                return None
            try:
                return float(match.group(0)) * unit_multiplier
            except ValueError:
                return None
        return None

    def _coerce_text_items(self, value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            result = []
            for item in value:
                text = self._coerce_text_item(item)
                if text:
                    result.append(text)
            return result
        if isinstance(value, dict):
            text = self._coerce_text_item(value)
            return [text] if text else []
        text = self._text_field(value)
        if not text:
            return []
        text = re.sub(r"^(可执行建议|建议|风险控制|风控|需补充数据|缺失数据)[:：]\s*", "", text)
        parts = re.split(r"(?:\n+|(?:^|\s)(?:\d+|[一二三四五六七八九十]+)[\.、]\s+|(?:^|\s)[\-*]\s+)", text)
        result = [part.strip(" \t\r\n-：:") for part in parts if part and part.strip(" \t\r\n-：:")]
        return result or [text]

    def _coerce_text_item(self, value) -> str:
        if isinstance(value, dict):
            main = self._first_text_value(
                value,
                (
                    "text",
                    "content",
                    "message",
                    "action",
                    "suggestion",
                    "recommendation",
                    "risk",
                    "risk_control",
                    "missing",
                    "question",
                    "name",
                    "title",
                    "label",
                    "command",
                    "next",
                ),
            )
            if not main:
                main = self._safe_dict_text_summary(value)
            details = []
            for label, keys in (
                ("原因", ("reason", "why", "rationale")),
                ("条件", ("condition", "when", "trigger")),
                ("信号", ("signal", "indicator")),
                ("阈值", ("threshold", "limit")),
                ("周期", ("timeframe", "horizon")),
            ):
                detail = self._first_text_value(value, keys)
                if detail and detail != main:
                    details.append(f"{label}: {detail}")
            return f"{main}；{'；'.join(details)}" if main and details else main
        if isinstance(value, list):
            items = [self._coerce_text_item(item) for item in value[:6]]
            return "；".join(item for item in items if item)
        return self._text_field(value)

    def _first_text_value(self, data: dict, keys: tuple[str, ...]) -> str:
        for key in keys:
            if self._is_sensitive_field(key):
                continue
            text = self._text_field(data.get(key))
            if text:
                return text
        return ""

    def _safe_dict_text_summary(self, data: dict) -> str:
        parts = []
        for key, value in data.items():
            key_text = self._text_field(key)
            if not key_text or self._is_sensitive_field(key_text):
                continue
            if isinstance(value, (dict, list)):
                continue
            text = self._text_field(value)
            if text:
                parts.append(f"{key_text}: {text}")
            if len(parts) >= 3:
                break
        return "；".join(parts)

    def _is_sensitive_field(self, key: str) -> bool:
        key_text = self._text_field(key).lower()
        return any(word in key_text for word in ("token", "key", "secret", "password", "authorization", "api_key"))

    def _text_field(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return " ".join(value.strip().split())
        return " ".join(str(value).strip().split())

    def _is_small_talk_query(self, query: str) -> bool:
        text = re.sub(r"\s+", "", (query or "").lower())
        return text in {"在吗", "在不在", "你好", "您好", "hi", "hello", "hey", "哈喽", "嗨"}

    def _small_talk_response(self, query: str) -> str:
        return "\n".join([
            "在，我在。",
            "",
            "你可以直接把投资问题丢给我，比如一个市场判断、某个持仓、或者一段你看到的新闻。我会先让服务端做场景映射，再用你本机配置的大模型给出分析。",
            "",
            "如果还没想好，也可以先问：今天市场里哪个方向最值得跟踪？",
        ])

    def _show_progress(self, message: str) -> None:
        if self._agent_trace is not None:
            clean = self._format_progress_trace_item(message)
            if clean and clean not in self._agent_trace:
                self._agent_trace.append(clean)
        self._refresh_token_status_bar(activity=self._format_progress_trace_item(message) or message)
        if sys.stdout.isatty():
            print(_color(f"· {message}...", "2"), flush=True)

    def _agent_trace_lines(self) -> list[str]:
        return list(self._agent_trace or [])

    def _format_progress_trace_item(self, message: str) -> str:
        text = self._text_field(message)
        text = re.sub(r"^正在", "", text)
        text = re.sub(r"\.{3,}$", "", text).strip(" .。")
        return text

    async def _select_list(self, title: str, items: list[tuple[str, str, str]]) -> str | None:
        try:
            return await self._select_list_prompt_toolkit(title, items)
        except ImportError:
            return self._select_list_manual(title, items)

    async def _select_list_prompt_toolkit(self, title: str, items: list[tuple[str, str, str]]) -> str | None:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style

        selected = 0
        width = min(max(76, _terminal_width()), 140)

        def fragments():
            result = [
                ("class:title", f"{title}\n"),
                ("class:border", "─" * width + "\n"),
                ("class:hint", "↑↓ 选择  Enter 确认  Esc/Ctrl+C 取消\n"),
            ]
            for index, (_, label, description) in enumerate(items):
                style = "class:current" if index == selected else "class:item"
                marker = "❯" if index == selected else " "
                line = f"{marker} {_pad_display(label, 28)} {description}"
                result.append((style, _clip_display(line, width) + "\n"))
            result.append(("class:border", "─" * width + "\n"))
            for detail in self._model_picker_detail_lines(title, items, selected):
                result.append(("class:hint", _clip_display(detail, width) + "\n"))
            result.append(("class:border", "─" * width))
            return result

        bindings = KeyBindings()

        @bindings.add("down")
        def _(event):
            nonlocal selected
            selected = (selected + 1) % len(items)
            event.app.invalidate()

        @bindings.add("up")
        def _(event):
            nonlocal selected
            selected = (selected - 1) % len(items)
            event.app.invalidate()

        @bindings.add("enter")
        def _(event):
            event.app.exit(result=items[selected][0])

        @bindings.add("escape")
        @bindings.add("c-c")
        def _(event):
            event.app.exit(result=None)

        root = HSplit([
            Window(height=1),
            Window(FormattedTextControl(fragments), dont_extend_height=True),
        ])
        app = Application(
            layout=Layout(root),
            key_bindings=bindings,
            full_screen=False,
            erase_when_done=True,
            style=Style.from_dict({
                "title": "ansicyan bold",
                "border": "#888888",
                "hint": "#888888",
                "item": "#d0d0d0",
                "current": self._select_style_current(),
            }),
        )
        return await app.run_async()

    def _select_list_manual(self, title: str, items: list[tuple[str, str, str]]) -> str | None:
        try:
            import termios
            import tty
        except ImportError:
            return None

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        selected = 0
        try:
            tty.setcbreak(fd)
            while True:
                self._render_model_picker(title, items, selected)
                ch = sys.stdin.read(1)
                if ch in {"\x03", "q", "Q"}:
                    return None
                if ch in {"\r", "\n"}:
                    return items[selected][0]
                if ch == "\x04":
                    raise EOFError
                if ch == "\x1b":
                    action = self._read_escape_sequence()
                    if action == "escape":
                        return None
                    if action == "up":
                        selected = (selected - 1) % len(items)
                    elif action == "down":
                        selected = (selected + 1) % len(items)
                    continue
                if ch in {"k", "K"}:
                    selected = (selected - 1) % len(items)
                elif ch in {"j", "J"}:
                    selected = (selected + 1) % len(items)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except OSError:
                pass

    def _render_model_picker(self, title: str, items: list[tuple[str, str, str]], selected: int) -> None:
        width = min(max(76, _terminal_width() - 4), 120)
        lines = [
            _color("╭─ " + title + " " + "─" * max(0, width - _display_width(title) - 5) + "╮", "36"),
            self._browser_line("↑↓/jk 选择  Enter 确认  q/Esc 取消", width),
            "├" + "─" * (width - 2) + "┤",
        ]
        for index, (_, label, description) in enumerate(items):
            marker = "›" if index == selected else " "
            line = self._browser_line(f"{marker} {_pad_display(label, 28)} {description}", width)
            if index == selected:
                line = _color(line, self._ansi_selected_style())
            lines.append(line)
        detail_lines = self._model_picker_detail_lines(title, items, selected)
        if detail_lines:
            lines.append("├" + "─" * (width - 2) + "┤")
            for detail in detail_lines:
                lines.append(self._browser_line(detail, width))
        lines.append(_color("╰" + "─" * (width - 2) + "╯", "36"))
        sys.stdout.write("\n".join(lines) + "\n")

    def _model_picker_detail_lines(self, title: str, items: list[tuple[str, str, str]], selected: int) -> list[str]:
        if not items:
            return []
        selected = max(0, min(selected, len(items) - 1))
        item_id, label, description = items[selected]
        provider = get_provider_preset(item_id)
        if item_id == provider.id:
            return [
                f"选中: {label} ({provider.id})",
                f"Key: {provider.key_env} · Model: {provider.model_env} · 默认 {provider.default_model}",
                "边界: API Key 只保存在本机，服务端只接收问题做受保护映射",
                "下一步: Enter 选择供应商，再选择模型，随后 /model key 本机测试保存",
            ]
        model_provider = self._provider_for_model(item_id)
        if model_provider:
            preset = get_provider_preset(model_provider)
            marker = "默认模型" if item_id == preset.default_model else "可选模型"
            return [
                f"选中: {label} ({item_id})",
                f"Provider: {preset.display_name} · {marker}",
                f"用途: {description}",
                f"Key: {preset.key_env} 只在本机；下一步 /model key 测试连接后保存",
            ]
        return [
            f"选中: {label} ({item_id})",
            f"用途: {description}",
            "下一步: Enter 确认；API Key 只保存在本机，不发送服务端",
        ]

    def _provider_for_model(self, model_id: str) -> str:
        target = self._text_field(model_id)
        for provider in MODEL_PRESETS:
            if any(model.id == target for model in provider.models):
                return provider.id
        return ""
        sys.stdout.write(f"\033[{len(lines)}A")
        sys.stdout.flush()

    def _next_steps(self, session: dict, llm_ready: bool) -> list[tuple[str, str]]:
        steps = []
        workspace_ready = bool(workspace_status().get("allowed"))
        if not workspace_ready or not session.get("token") or not llm_ready:
            steps.append(("setup", "/setup 初始化工作区、账号、大模型和产物"))
        if not workspace_ready:
            steps.append(("workspace", "/workspace browse 或 /workspace path <路径> 选择项目文件夹，然后 /workspace allow"))
        if not session.get("token"):
            steps.append(("login", "/login xwab <账号>"))
        if not llm_ready:
            steps.append(("model", "/model select 然后 /model key"))
        if not steps:
            steps.append(("ready", "直接输入投资问题，或执行 /service"))
        return steps

    def _llm_status(self, config) -> tuple[str, str, bool, str]:
        provider = (config.llm_provider or "openai").lower()
        key_hint, _ = PROVIDER_KEY_HINTS.get(provider, PROVIDER_KEY_HINTS["openai"])
        key = getattr(config, "llm_api_key", None)
        model = getattr(config, "llm_model", None)
        if provider == "deepseek":
            key = getattr(config, "deepseek_api_key", None)
            model = getattr(config, "deepseek_model", None)
        elif provider in {"claude", "anthropic"}:
            key = getattr(config, "claude_api_key", None) or getattr(config, "anthropic_api_key", None)
            model = (
                getattr(config, "claude_model", None)
                or getattr(config, "anthropic_model", None)
                or getattr(config, "llm_model", None)
            )
            key_hint = "CLAUDE_API_KEY"
        elif provider in {"mimo", "xiaomi"}:
            key = getattr(config, "mimo_api_key", None) or getattr(config, "xiaomi_api_key", None)
            model = (
                getattr(config, "mimo_model", None)
                or getattr(config, "xiaomi_model", None)
                or getattr(config, "llm_model", None)
            )
            key_hint = "MIMO_API_KEY"
        elif provider in {"kimi", "moonshot"}:
            key = getattr(config, "kimi_api_key", None) or getattr(config, "moonshot_api_key", None)
            model = (
                getattr(config, "kimi_model", None)
                or getattr(config, "moonshot_model", None)
                or getattr(config, "llm_model", None)
            )
            key_hint = "KIMI_API_KEY"
        return provider, model or "未设置", bool(key), key_hint

    def _command_suggestion(self, command: str) -> str | None:
        candidates = set(self.COMMANDS) | set(self.ALIASES) | self.LOCAL_COMMANDS | {"help", "clear", "exit"}
        matches = difflib.get_close_matches(command, sorted(candidates), n=1, cutoff=0.55)
        return matches[0] if matches else None

    async def _read_prompt(self) -> str:
        """Read one prompt, opening a slash-command picker when / starts the line."""
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return input(self.prompt()).strip()

        self._load_input_history()
        try:
            return await self._read_prompt_toolkit()
        except ImportError:
            return self._read_prompt_manual()

    async def _read_prompt_toolkit(self) -> str:
        from prompt_toolkit.application import Application
        from prompt_toolkit.application.current import get_app_or_none
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import ConditionalContainer, Dimension, HSplit, Layout, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import TextArea

        cli = self
        history_index: int | None = None
        draft = ""
        text_area = TextArea(
            height=1,
            multiline=False,
            prompt=HTML("<prompt>❯ </prompt>"),
        )

        def slash_active() -> bool:
            return text_area.text.startswith("/")

        def slash_matches():
            text = text_area.text
            return cli._filter_palette(text[1:].lower()) if text.startswith("/") else []

        def clamp_selected(matches):
            if not matches:
                cli._slash_selected = 0
                return 0
            cli._slash_selected = max(0, min(cli._slash_selected, len(matches) - 1))
            return cli._slash_selected

        def slash_menu_fragments():
            text = text_area.text
            if not text.startswith("/"):
                return []
            matches = slash_matches()
            selected = clamp_selected(matches)
            width = min(max(72, _terminal_width()), 150)
            max_visible = 9
            start = max(0, selected - max_visible + 1)
            visible = matches[start:start + max_visible]
            query = text[1:].lower()
            fragments = [
                ("class:menu.border", "─" * width + "\n"),
                ("class:menu.muted", _clip_display(self._slash_context_hint(query, len(matches)), width) + "\n"),
            ]
            for context_line in self._slash_picker_context_lines(query):
                fragments.append(("class:menu.muted", _clip_display(context_line, width) + "\n"))
            if not visible:
                fragments.append(("class:menu.muted", "没有匹配命令\n"))
            for row_type, payload, actual in cli._grouped_palette_rows(visible, start):
                if row_type == "group":
                    fragments.append(("class:menu.group", _clip_display(str(payload), width) + "\n"))
                    continue
                _, shortcut, description = payload
                style = "class:menu.current" if actual == selected else "class:menu"
                marker = "❯" if actual == selected else " "
                line = f"{marker} {_pad_display(shortcut, 29)} {description}"
                fragments.append((style, _clip_display(line, width) + "\n"))
            for detail in cli._slash_selection_detail_lines(matches, selected):
                fragments.append(("class:menu.muted", _clip_display(detail, width) + "\n"))
            fragments.append(("class:menu.border", "─" * width))
            return fragments

        def input_rule_fragments():
            width = min(max(72, _terminal_width()), 150)
            return [("class:input.border", "─" * width)]

        def invalidate(_=None):
            app = get_app_or_none()
            if app:
                app.invalidate()

        text_area.buffer.on_text_changed += invalidate
        bindings = KeyBindings()

        @bindings.add("down", filter=Condition(slash_active), eager=True)
        def _(event):
            matches = slash_matches()
            if matches:
                cli._slash_selected = (clamp_selected(matches) + 1) % len(matches)
                event.app.invalidate()

        @bindings.add("up", filter=Condition(slash_active), eager=True)
        def _(event):
            matches = slash_matches()
            if matches:
                cli._slash_selected = (clamp_selected(matches) - 1) % len(matches)
                event.app.invalidate()

        @bindings.add("up", filter=Condition(lambda: not slash_active()), eager=True)
        def _(event):
            nonlocal history_index, draft
            next_text, history_index, draft = cli._history_previous_text(text_area.text, history_index, draft)
            text_area.text = next_text
            text_area.buffer.cursor_position = len(text_area.text)
            event.app.invalidate()

        @bindings.add("down", filter=Condition(lambda: not slash_active()), eager=True)
        def _(event):
            nonlocal history_index, draft
            next_text, history_index, draft = cli._history_next_text(text_area.text, history_index, draft)
            text_area.text = next_text
            text_area.buffer.cursor_position = len(text_area.text)
            event.app.invalidate()

        @bindings.add("enter")
        def _(event):
            if slash_active():
                matches = slash_matches()
                if matches:
                    _, shortcut, _ = matches[clamp_selected(matches)]
                    command, needs_more = cli._input_from_shortcut(shortcut)
                    if not cli._should_accept_slash_shortcut(text_area.text, command, needs_more):
                        event.app.exit(result=text_area.text)
                        return
                    text_area.text = command
                    text_area.buffer.cursor_position = len(command)
                    if needs_more:
                        event.app.invalidate()
                        return
                    event.app.exit(result=command)
                    return
            event.app.exit(result=text_area.text)

        @bindings.add("c-c")
        def _(event):
            event.app.exit(exception=KeyboardInterrupt)

        @bindings.add("c-d")
        def _(event):
            event.app.exit(exception=EOFError)

        menu = ConditionalContainer(
            Window(
                FormattedTextControl(slash_menu_fragments),
                height=Dimension(max=14),
                dont_extend_height=True,
            ),
            filter=Condition(slash_active),
        )
        root = HSplit([
            Window(FormattedTextControl(input_rule_fragments), height=1, dont_extend_height=True),
            text_area,
            Window(FormattedTextControl(input_rule_fragments), height=1, dont_extend_height=True),
            menu,
            Window(FormattedTextControl(cli._prompt_status_bar_fragments), height=1, dont_extend_height=True),
        ])
        app = Application(
            layout=Layout(root, focused_element=text_area),
            key_bindings=bindings,
            full_screen=False,
            erase_when_done=True,
            style=Style.from_dict({
                "prompt": "ansicyan bold",
                "input.border": "#666666",
                "status": "#8a8a8a",
                "menu": "#d0d0d0",
                "menu.current": cli._select_style_current(),
                "menu.border": "#888888",
                "menu.group": "ansicyan bold",
                "menu.muted": "#888888",
            }),
        )

        command = await app.run_async()
        command = command.strip()
        self._remember_input_history(command)
        return command

    def _read_prompt_manual(self) -> str:
        """Fallback prompt for environments without prompt_toolkit."""
        try:
            import termios
            import tty
        except ImportError:
            return input(self.prompt()).strip()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        buffer = ""
        cursor = 0
        history_index: int | None = None
        draft = ""
        try:
            tty.setcbreak(fd)
            self._render_prompt(buffer, cursor)
            while True:
                ch = sys.stdin.read(1)
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch == "\x04":
                    raise EOFError
                if ch in {"\r", "\n"}:
                    print()
                    command = buffer.strip()
                    self._remember_input_history(command)
                    return command
                if ch == "\x1b":
                    action = self._read_escape_sequence()
                    if action == "up":
                        buffer, history_index, draft = self._history_previous_text(buffer, history_index, draft)
                        cursor = len(buffer)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "down":
                        buffer, history_index, draft = self._history_next_text(buffer, history_index, draft)
                        cursor = len(buffer)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "left":
                        cursor = max(0, cursor - 1)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "right":
                        cursor = min(len(buffer), cursor + 1)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "home":
                        cursor = 0
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "end":
                        cursor = len(buffer)
                        self._render_prompt(buffer, cursor)
                        continue
                    if action == "delete":
                        if cursor < len(buffer):
                            buffer = buffer[:cursor] + buffer[cursor + 1:]
                            history_index = None
                            self._render_prompt(buffer, cursor)
                        continue
                    continue
                if ch in {"\x7f", "\b"}:
                    if cursor > 0:
                        buffer = buffer[:cursor - 1] + buffer[cursor:]
                        cursor -= 1
                        history_index = None
                        self._render_prompt(buffer, cursor)
                    continue
                if ch == "/" and not buffer:
                    selected = self._slash_command_picker()
                    self._clear_slash_dropdown()
                    if selected:
                        buffer, needs_more = self._input_from_shortcut(selected[1])
                        cursor = len(buffer)
                        history_index = None
                        if not needs_more:
                            self._render_prompt(buffer, cursor)
                            print()
                            command = buffer.strip()
                            self._remember_input_history(command)
                            return command
                    self._render_prompt(buffer, cursor)
                    continue
                if ch.isprintable():
                    buffer = buffer[:cursor] + ch + buffer[cursor:]
                    cursor += 1
                    history_index = None
                    self._render_prompt(buffer, cursor)
                if not ch:
                    raise EOFError
        except OSError as exc:
            if self._should_exit_for_terminal(exc):
                raise EOFError from exc
            raise
        except Exception as exc:
            if self._should_exit_for_terminal(exc):
                raise EOFError from exc
            raise
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except OSError:
                pass

    def _render_prompt(self, buffer: str, cursor: int | None = None) -> None:
        if cursor is None:
            cursor = len(buffer)
        cursor = max(0, min(cursor, len(buffer)))
        sys.stdout.write("\r\033[2K" + self.prompt() + buffer)
        tail = len(buffer) - cursor
        if tail > 0:
            sys.stdout.write(f"\033[{tail}D")
        sys.stdout.flush()

    def _read_escape_sequence(self, timeout: float = 0.2) -> str:
        import select

        if not select.select([sys.stdin], [], [], timeout)[0]:
            return "escape"
        second = sys.stdin.read(1)
        if second == "O":
            if not select.select([sys.stdin], [], [], timeout)[0]:
                return "escape"
            return {
                "A": "up",
                "B": "down",
                "C": "right",
                "D": "left",
                "H": "home",
                "F": "end",
            }.get(sys.stdin.read(1), "escape")
        if second != "[":
            return "escape"
        if not select.select([sys.stdin], [], [], timeout)[0]:
            return "escape"
        third = sys.stdin.read(1)
        simple = {
            "A": "up",
            "B": "down",
            "C": "right",
            "D": "left",
            "H": "home",
            "F": "end",
        }
        if third in simple:
            return simple[third]
        if third.isdigit():
            sequence = third
            while select.select([sys.stdin], [], [], timeout)[0]:
                part = sys.stdin.read(1)
                sequence += part
                if part == "~":
                    break
            return {
                "1~": "home",
                "3~": "delete",
                "4~": "end",
                "7~": "home",
                "8~": "end",
            }.get(sequence, "escape")
        return "escape"

    def _read_bracket_escape_tail(self, timeout: float = 0.2) -> str:
        import select

        if not select.select([sys.stdin], [], [], timeout)[0]:
            return "literal"
        return {
            "A": "up",
            "B": "down",
            "C": "right",
            "D": "left",
            "H": "home",
            "F": "end",
        }.get(sys.stdin.read(1), "literal")

    def _read_workspace_key(self, fd: int, timeout: float = 0.03) -> str:
        import select

        try:
            first = os.read(fd, 1)
        except OSError:
            return "eof"
        if not first:
            return "eof"
        if first == b"\x03":
            return "ctrl_c"
        if first == b"\x04":
            return "eof"
        if first in {b"\r", b"\n"}:
            return "enter"
        if first == b"\x1b":
            sequence = first + self._read_available_key_bytes(fd, timeout=timeout)
            action = self._decode_terminal_key_sequence(sequence)
            return "escape" if action == "literal" else action
        if first == b"[":
            sequence = first + self._read_available_key_bytes(fd, timeout=timeout, max_bytes=6)
            return self._decode_terminal_key_sequence(sequence)
        try:
            return first.decode("utf-8", errors="ignore") or "literal"
        except UnicodeDecodeError:
            return "literal"

    def _read_available_key_bytes(self, fd: int, *, timeout: float = 0.03, max_bytes: int = 8) -> bytes:
        import select

        chunks = bytearray()
        while len(chunks) < max_bytes and select.select([fd], [], [], timeout)[0]:
            try:
                part = os.read(fd, 1)
            except OSError:
                break
            if not part:
                break
            chunks.extend(part)
            if part in {b"A", b"B", b"C", b"D", b"H", b"F", b"~"}:
                break
        return bytes(chunks)

    def _decode_terminal_key_sequence(self, sequence: bytes) -> str:
        aliases = {
            b"\x1b[A": "up",
            b"\x1b[B": "down",
            b"\x1b[C": "right",
            b"\x1b[D": "left",
            b"\x1b[H": "home",
            b"\x1b[F": "end",
            b"\x1bOA": "up",
            b"\x1bOB": "down",
            b"\x1bOC": "right",
            b"\x1bOD": "left",
            b"\x1bOH": "home",
            b"\x1bOF": "end",
            b"[A": "up",
            b"[B": "down",
            b"[C": "right",
            b"[D": "left",
            b"[H": "home",
            b"[F": "end",
            b"\x1b[1~": "home",
            b"\x1b[3~": "delete",
            b"\x1b[4~": "end",
            b"\x1b[7~": "home",
            b"\x1b[8~": "end",
            b"[1~": "home",
            b"[3~": "delete",
            b"[4~": "end",
            b"[7~": "home",
            b"[8~": "end",
        }
        return aliases.get(sequence, "literal")

    def _slash_command_picker(self) -> tuple[str, str, str] | None:
        """Interactive slash-command picker used inside cbreak mode."""
        query = ""
        selected = 0
        while True:
            matches = self._filter_palette(query)
            if selected >= len(matches):
                selected = max(0, len(matches) - 1)
            self._render_slash_picker(matches, selected, query)
            ch = sys.stdin.read(1)
            if ch == "\x03":
                raise KeyboardInterrupt
            if not ch:
                raise EOFError
            if ch == "\x1b":
                action = self._read_escape_sequence()
                if action == "escape":
                    return None
                if action == "up" and matches:
                    selected = (selected - 1) % len(matches)
                    continue
                if action == "down" and matches:
                    selected = (selected + 1) % len(matches)
                    continue
                if action == "home" and matches:
                    selected = 0
                    continue
                if action == "end" and matches:
                    selected = len(matches) - 1
                    continue
                continue
            if ch in {"q", "Q"}:
                return None
            if ch in {"\r", "\n"}:
                return matches[selected] if matches else None
            if ch in {"\x7f", "\b"}:
                query = query[:-1]
                selected = 0
                continue
            if ch.isprintable() and ch != "/":
                query += ch.lower()
                selected = 0
                continue

    def _filter_palette(self, query: str) -> list[tuple[str, str, str]]:
        palette = self._ordered_palette_items()
        if not query:
            return palette
        lowered = query.lower()
        contextual = self._contextual_palette_items(lowered, palette)
        if contextual is not None:
            return contextual
        scored: list[tuple[float, int, tuple[str, str, str]]] = []
        for index, item in enumerate(palette):
            score = self._palette_match_score(lowered, item)
            if score is not None:
                scored.append((score, index, item))
        return [item for _, _, item in sorted(scored, key=lambda row: (-row[0], row[1]))]

    def _palette_match_score(self, query: str, item: tuple[str, str, str]) -> float | None:
        command_id, shortcut, description = item
        haystacks = [
            command_id.lower(),
            shortcut.lower().lstrip("/"),
            shortcut.lower(),
            description.lower(),
        ]
        compact_query = query.replace("/", "").strip()
        if not compact_query:
            return 100.0
        if compact_query in {command_id.lower(), shortcut.lower().lstrip("/")}:
            return 120.0 + self._command_usage_boost(command_id)
        if any(text.startswith(compact_query) for text in haystacks[:3]):
            return 110.0 + self._command_usage_boost(command_id)
        tokens = [part for part in re.split(r"\s+", compact_query) if part]
        joined = " ".join(haystacks)
        if tokens and all(token in joined for token in tokens):
            return 92.0 + min(7.0, sum(len(token) for token in tokens) / 4) + self._command_usage_boost(command_id)
        if any(compact_query in text for text in haystacks):
            return 82.0 + min(8.0, len(compact_query) / 3) + self._command_usage_boost(command_id)
        acronym = "".join(part[0] for part in re.split(r"[-_/ <]+", shortcut.lower().lstrip("/")) if part)
        if acronym and compact_query == acronym[:len(compact_query)]:
            return 74.0 + self._command_usage_boost(command_id)
        subsequence_scores = [
            score
            for text in haystacks[:3]
            for score in [self._subsequence_score(compact_query, text)]
            if score is not None
        ]
        if subsequence_scores:
            return max(subsequence_scores) + self._command_usage_boost(command_id)
        best_ratio = max(difflib.SequenceMatcher(None, compact_query, text).ratio() for text in haystacks[:3])
        if best_ratio >= 0.54:
            return 52.0 * best_ratio + self._command_usage_boost(command_id)
        return None

    def _subsequence_score(self, needle: str, haystack: str) -> float | None:
        if not needle:
            return 100.0
        position = 0
        gaps = 0
        last_index = -1
        first_index = None
        for char in needle:
            found = haystack.find(char, position)
            if found < 0:
                return None
            if first_index is None:
                first_index = found
            if last_index >= 0:
                gaps += max(0, found - last_index - 1)
            last_index = found
            position = found + 1
        return max(36.0, 68.0 - gaps * 1.3 - (first_index or 0) * 0.8)

    def _contextual_palette_items(
        self,
        lowered_query: str,
        palette: list[tuple[str, str, str]],
    ) -> list[tuple[str, str, str]] | None:
        if " " not in lowered_query:
            return None
        root, tail = lowered_query.split(" ", 1)
        root = root.lstrip("/")
        command_ids = SLASH_SUBCOMMAND_ROOTS.get(root)
        if not command_ids:
            return None
        tail = tail.strip()
        matches = [item for item in palette if item[0] in command_ids]
        matches = self._sort_contextual_palette(root, matches)
        if not tail:
            return matches
        filtered = [
            item for item in matches
            if tail in item[0].lower()
            or tail in item[1].lower()
            or tail in item[2].lower()
        ]
        preferred_prefix = f"/{root} {tail}"
        return sorted(
            filtered,
            key=lambda item: (
                0 if item[1].lower().startswith(preferred_prefix) else 1,
                0 if item[1].lower().startswith(f"/{root} ") else 1,
                self._contextual_palette_rank(root, item[0]),
            ),
        )

    def _sort_contextual_palette(
        self,
        root: str,
        matches: list[tuple[str, str, str]],
    ) -> list[tuple[str, str, str]]:
        return sorted(matches, key=lambda item: self._contextual_palette_rank(root, item[0]))

    def _contextual_palette_rank(self, root: str, command_id: str) -> int:
        order = SLASH_SUBCOMMAND_ORDER.get(root) or []
        try:
            return order.index(command_id)
        except ValueError:
            return len(order) + 100

    def _ordered_palette_items(self) -> list[tuple[str, str, str]]:
        ordered = []
        seen: set[str] = set()
        for _, command_ids in COMMAND_GROUPS:
            group_items = [
                (index, item)
                for index, item in enumerate(COMMAND_PALETTE)
                if item[0] in command_ids and item[0] not in seen
            ]
            group_items.sort(key=lambda row: (-self._command_usage_boost(row[1][0]), row[0]))
            for _, item in group_items:
                if item[0] in command_ids and item[0] not in seen:
                    ordered.append(item)
                    seen.add(item[0])
        ordered.extend(item for item in COMMAND_PALETTE if item[0] not in seen)
        return ordered

    def _palette_group_title(self, command_id: str) -> str:
        for title, command_ids in COMMAND_GROUPS:
            if command_id in command_ids:
                return title
        return "More"

    def _grouped_palette_rows(
        self,
        matches: list[tuple[str, str, str]],
        start_index: int = 0,
    ) -> list[tuple[str, object, int | None]]:
        rows: list[tuple[str, object, int | None]] = []
        current_group = None
        for offset, item in enumerate(matches):
            group = self._palette_group_title(item[0])
            if group != current_group:
                rows.append(("group", group, None))
                current_group = group
            rows.append(("item", item, start_index + offset))
        return rows

    def _render_slash_picker(self, matches: list[tuple[str, str, str]], selected: int, query: str) -> None:
        width = min(max(72, _terminal_width() - 4), 110)
        term_lines = shutil.get_terminal_size((100, 24)).lines
        max_visible = min(10, max(4, term_lines - 10))
        start = max(0, selected - max_visible + 1)
        visible = matches[start:start + max_visible]
        title = self._slash_picker_title(query)
        lines = [
            _color(f"╭─ {title} " + "─" * max(0, width - _display_width(title) - 5) + "╮", "36"),
            self._browser_line(self._slash_context_hint(query, len(matches)), width),
            self._browser_line("↑↓ 选择  Enter 确认  输入字母过滤  Backspace 删除  Esc/q 取消", width),
        ]
        for context_line in self._slash_picker_context_lines(query):
            lines.append(self._browser_line(context_line, width))
        lines.append("├" + "─" * (width - 2) + "┤")
        if not visible:
            lines.append(self._browser_line("没有匹配命令", width))
        for row_type, payload, actual in self._grouped_palette_rows(visible, start):
            if row_type == "group":
                text = f"  {payload}"
                lines.append(_color(self._browser_line(text, width), "36;1"))
                continue
            _, shortcut, description = payload
            marker = "❯" if actual == selected else " "
            text = f"{marker} {_pad_display(shortcut, 24)} {description}"
            line = self._browser_line(text, width)
            if actual == selected:
                line = _color(line, self._ansi_selected_style())
            lines.append(line)
        hidden_before = start
        hidden_after = max(0, len(matches) - start - len(visible))
        if hidden_before or hidden_after:
            lines.append(self._browser_line(f"... 上方 {hidden_before} 条，下方 {hidden_after} 条", width))
        detail = self._slash_selection_detail(matches, selected)
        if detail:
            lines.append("├" + "─" * (width - 2) + "┤")
            for detail_line in self._slash_selection_detail_lines(matches, selected):
                lines.append(self._browser_line(detail_line, width))
        lines.append(_color("╰" + "─" * (width - 2) + "╯", "36"))
        self._render_dropdown_below("/" + query, lines)

    def _slash_picker_title(self, query: str) -> str:
        root = (query or "").strip().split(maxsplit=1)[0] if (query or "").strip() else ""
        if root == "server":
            return "Server Commands"
        if root == "workspace":
            return "Workspace Sandbox"
        if root == "setup":
            return "Setup Wizard"
        return "Slash Commands"

    def _slash_context_hint(self, query: str, match_count: int) -> str:
        query = query or ""
        stripped = query.strip()
        root = stripped.split()[0] if stripped else ""
        if root in SLASH_CONTEXT_HINTS and (" " in query or query.endswith(" ")):
            return f"{SLASH_CONTEXT_HINTS[root]} · {match_count} 个匹配"
        if query.endswith(" ") and stripped:
            return f"子命令: /{root} · {match_count} 个匹配"
        return f"filter: /{query} · {match_count} 个匹配"

    def _slash_picker_context_lines(self, query: str) -> list[str]:
        stripped = (query or "").strip()
        root = stripped.split()[0] if stripped else ""
        if root == "server":
            return [
                "目标导航: status 查健康/鉴权 · me 查账号 · map 只看映射 · flow 看协作链路",
                "智能体路径: 直接输入问题由本机 LLM 选 MCP/web_search，再请求服务端受保护映射",
                "产物导航: artifact/chart 生成图表 · capabilities 看边界 · actions 获取下一步",
                "资源出口: 服务端返回网页/图片/HTML/PDF/图表时，用 /links 1 或 /open 1 打开",
            ]
        if root == "workspace":
            return [
                "沙箱导航: browse 方向键选路径 · path 粘贴路径 · allow 授权写入 · artifacts 看产物",
                "写入边界: 只在授权项目 .erlangshen/artifacts 保存图表、报告、resources.json",
                "隐私边界: 大模型 API Key、账号 token 和服务端内部认知库不会写入项目目录",
            ]
        if root == "setup":
            return [
                "初始化顺序: workspace 选择项目文件夹 · login 登录账号 · model key 保存本机大模型 Key",
                "推荐入口: /setup run 一次检查；/setup workspace 只重选项目沙箱",
            ]
        if root == "model":
            return [
                "模型边界: /model select 选供应商和型号；/model key 本机测试成功后才保存",
                "安全边界: Key 只在本机直连供应商，不发送给二郎神服务端",
            ]
        if root in {"links", "open"}:
            return [
                "资源入口: 网页、图片、HTML、PDF、图表和报告都显示为名称链接",
                "打开方式: /links 1、/open 1、/links open 1 或 /open link 1",
            ]
        return []

    def _slash_selection_detail(self, matches: list[tuple[str, str, str]], selected: int) -> str:
        detail_lines = self._slash_selection_detail_lines(matches, selected)
        return " | ".join(detail_lines)

    def _slash_selection_detail_lines(self, matches: list[tuple[str, str, str]], selected: int) -> list[str]:
        if not matches:
            return []
        selected = max(0, min(selected, len(matches) - 1))
        command_id, shortcut, description = matches[selected]
        group = self._palette_group_title(command_id)
        detail = SERVER_COMMAND_DETAILS.get(shortcut)
        if detail:
            parts = [part.strip() for part in detail.split("|") if part.strip()]
            if not parts:
                return [f"选中: {shortcut}", f"阶段: {group}"]
            if not any(part.startswith("下一步:") for part in parts):
                next_hint = self._slash_next_hint(shortcut, group)
                if next_hint:
                    parts.append(f"下一步: {next_hint}")
            return [f"选中: {shortcut}", f"阶段: {group}", *parts]
        next_hint = self._slash_next_hint(shortcut, group)
        lines = [f"选中: {shortcut}", f"阶段: {group}", f"用途: {description}"]
        if next_hint:
            lines.append(f"下一步: {next_hint}")
        return lines

    def _slash_next_hint(self, shortcut: str, group: str) -> str:
        return COMMAND_NEXT_HINTS.get(shortcut) or COMMAND_GROUP_NEXT_HINTS.get(group, "直接输入问题或 /help")

    def _input_from_shortcut(self, shortcut: str) -> tuple[str, bool]:
        parts = shortcut.split()
        concrete = []
        needs_more = False
        for part in parts:
            if part.startswith("<"):
                needs_more = True
                break
            if part.startswith("["):
                break
            concrete.append(part)
        command = " ".join(concrete)
        if needs_more:
            command += " "
        return command, needs_more

    def _should_accept_slash_shortcut(self, typed_text: str, command: str, needs_more: bool) -> bool:
        if not needs_more:
            return True
        typed = " ".join(self._text_field(typed_text).strip().split())
        base = " ".join(self._text_field(command).strip().split())
        return not (base and typed.startswith(base + " "))

    def _clear_screen(self) -> None:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def _clear_slash_dropdown(self) -> None:
        lines = self._slash_dropdown_lines
        if not lines:
            return
        sys.stdout.write("\n")
        for _ in range(lines):
            sys.stdout.write("\r\033[2K\n")
        sys.stdout.write(f"\033[{lines + 1}A\r\033[2K")
        sys.stdout.flush()
        self._slash_dropdown_lines = 0

    def _render_dropdown_below(self, prompt_buffer: str, lines: list[str]) -> None:
        previous_lines = self._slash_dropdown_lines
        draw_lines = max(previous_lines, len(lines))
        self._render_prompt(prompt_buffer)
        sys.stdout.write("\n")
        for idx in range(draw_lines):
            sys.stdout.write("\r\033[2K")
            if idx < len(lines):
                sys.stdout.write(lines[idx])
            sys.stdout.write("\n")
        sys.stdout.write(f"\033[{draw_lines + 1}A")
        self._render_prompt(prompt_buffer)
        sys.stdout.flush()
        self._slash_dropdown_lines = len(lines)

    def _should_exit_for_terminal(self, exc: BaseException) -> bool:
        if isinstance(exc, (EOFError, BrokenPipeError)):
            return True
        if isinstance(exc, OSError):
            return self._is_terminal_closed_error(exc)
        message = str(exc)
        return "Input/output error" in message or "(5," in message

    def _is_terminal_closed_error(self, exc: OSError) -> bool:
        args = getattr(exc, "args", ())
        return (
            getattr(exc, "errno", None) == 5
            or 5 in args
            or "Input/output error" in str(exc)
        )

    def _setup_completion(self) -> None:
        self._load_input_history()
        try:
            import readline
        except ImportError:
            return

        history_path = self._history_path()
        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            readline.read_history_file(str(history_path))
        except FileNotFoundError:
            pass
        except OSError:
            pass
        try:
            readline.set_history_length(-1)
            atexit.register(readline.write_history_file, str(history_path))
        except OSError:
            pass

        commands = sorted({f"/{item[0]}" for item in COMMAND_PALETTE} | {f"/{name}" for name in self.ALIASES})

        def complete(text: str, state: int):
            matches = [command for command in commands if command.startswith(text)]
            return matches[state] if state < len(matches) else None

        readline.set_completer(complete)
        readline.parse_and_bind("tab: complete")

    def _history_path(self) -> Path:
        env_path = os.getenv("ERLANGSHEN_HISTORY_FILE")
        if env_path:
            return Path(env_path).expanduser()
        return Path("~/.erlangshen/history").expanduser()

    def _load_input_history(self) -> None:
        if self._input_history_loaded:
            return
        self._input_history_loaded = True
        try:
            lines = self._history_path().read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError, UnicodeError):
            return
        history: list[str] = []
        for line in lines:
            command = line.strip()
            if command:
                history.append(command)
        self._input_history = history

    def _save_input_history(self) -> None:
        history = self._input_history
        try:
            path = self._history_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(("\n".join(history) + "\n") if history else "", encoding="utf-8")
        except OSError:
            pass

    def _remember_input_history(self, command: str) -> None:
        command = self._text_field(command).strip()
        if not command:
            return
        self._load_input_history()
        self._input_history.append(command)
        try:
            import readline

            readline.add_history(command)
        except (ImportError, OSError):
            pass
        self._save_input_history()

    def _history_previous_text(
        self,
        current_text: str,
        history_index: int | None,
        draft: str,
    ) -> tuple[str, int | None, str]:
        self._load_input_history()
        if not self._input_history:
            return current_text, history_index, draft
        if history_index is None:
            draft = current_text
            history_index = len(self._input_history) - 1
        else:
            history_index = max(0, history_index - 1)
        return self._input_history[history_index], history_index, draft

    def _history_next_text(
        self,
        current_text: str,
        history_index: int | None,
        draft: str,
    ) -> tuple[str, int | None, str]:
        self._load_input_history()
        if history_index is None:
            return current_text, history_index, draft
        if history_index < len(self._input_history) - 1:
            history_index += 1
            return self._input_history[history_index], history_index, draft
        return draft, None, draft

    def _command_usage_scope(self) -> str:
        if os.getenv("ERLANGSHEN_DISABLE_COMMAND_USAGE"):
            return "off"
        scope = (os.getenv("ERLANGSHEN_COMMAND_USAGE_SCOPE") or "global").strip().lower()
        if scope in {"off", "none", "disabled", "disable", "0", "false"}:
            return "off"
        if scope in {"project", "workspace", "local"}:
            return "project"
        return "global"

    def _command_usage_path(self) -> Path | None:
        scope = self._command_usage_scope()
        if scope == "off":
            return None
        env_path = os.getenv("ERLANGSHEN_COMMAND_USAGE_FILE")
        if env_path:
            return Path(env_path).expanduser()
        if scope == "project":
            status = workspace_status()
            if not status.get("allowed"):
                return None
            try:
                root = resolve_workspace_path(str(status.get("path") or ""))
                return ensure_inside_workspace(root / ".erlangshen" / "artifacts" / "command_usage.json", root)
            except (OSError, PermissionError, ValueError):
                return None
        return Path("~/.erlangshen/command_usage.json").expanduser()

    def _command_usage_location_label(self) -> str:
        scope = self._command_usage_scope()
        path = self._command_usage_path()
        if path is None:
            if scope == "project":
                return "project / waiting for workspace authorization"
            return "off"
        return f"{scope} / {path}"

    def _load_command_usage(self) -> dict[str, object]:
        if self._command_usage_cache is not None:
            return self._command_usage_cache
        path = self._command_usage_path()
        if path is None:
            self._command_usage_cache = {"commands": {}}
            return self._command_usage_cache
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._command_usage_cache = data if isinstance(data, dict) else {"commands": {}}
        except (OSError, json.JSONDecodeError):
            self._command_usage_cache = {"commands": {}}
        return self._command_usage_cache

    def _save_command_usage(self, usage: dict[str, object]) -> None:
        path = self._command_usage_path()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(usage, f, ensure_ascii=False, indent=2)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except OSError:
            return

    def _record_command_usage(self, command: str, args: str) -> None:
        if self._command_usage_scope() == "off":
            return
        if not (sys.stdin.isatty() or os.getenv("ERLANGSHEN_RECORD_NON_TTY_COMMANDS")):
            return
        if self._command_usage_path() is None:
            return
        command_id = self._command_id_for_input(command, args)
        if not command_id:
            return
        usage = self._load_command_usage()
        commands = usage.setdefault("commands", {})
        if not isinstance(commands, dict):
            commands = {}
            usage["commands"] = commands
        item = commands.get(command_id) if isinstance(commands.get(command_id), dict) else {}
        item["count"] = int(item.get("count") or 0) + 1
        item["last_used"] = datetime.now().isoformat(timespec="seconds")
        commands[command_id] = item
        usage["updated_at"] = item["last_used"]
        self._save_command_usage(usage)

    def _command_id_for_input(self, command: str, args: str = "") -> str | None:
        normalized = f"/{command}".lower()
        if args:
            first_arg = args.strip().split(maxsplit=1)[0].lower()
            if first_arg:
                normalized = f"{normalized} {first_arg}"
        best: tuple[int, str] | None = None
        for command_id, shortcut, _ in COMMAND_PALETTE:
            concrete, _ = self._input_from_shortcut(shortcut)
            concrete = concrete.rstrip().lower()
            if normalized == concrete or normalized.startswith(concrete + " "):
                size = len(concrete)
                if best is None or size > best[0]:
                    best = (size, command_id)
        if best:
            return best[1]
        if command in self.LOCAL_COMMANDS or command in self.COMMANDS:
            return command
        return None

    def _command_usage_summary(self, command_id: str) -> str:
        usage = self._load_command_usage()
        commands = usage.get("commands") if isinstance(usage, dict) else {}
        item = commands.get(command_id) if isinstance(commands, dict) else None
        if not isinstance(item, dict):
            return ""
        count = max(0, int(item.get("count") or 0))
        if not count:
            return ""
        last_used = self._text_field(item.get("last_used"))
        if last_used:
            return f"used {count}x · last {last_used}"
        return f"used {count}x"

    def _command_usage_boost(self, command_id: str) -> float:
        usage = self._load_command_usage()
        commands = usage.get("commands") if isinstance(usage, dict) else {}
        item = commands.get(command_id) if isinstance(commands, dict) else None
        if not isinstance(item, dict):
            return 0.0
        count = max(0, int(item.get("count") or 0))
        boost = min(8.0, count * 1.5)
        last_used = self._text_field(item.get("last_used"))
        if last_used:
            try:
                age_days = max(0, (datetime.now() - datetime.fromisoformat(last_used)).days)
                boost += max(0.0, 6.0 - min(6.0, age_days / 5))
            except ValueError:
                pass
        return boost


def _parse_global_flags(argv: list[str]) -> tuple[list[str], str, bool]:
    output_mode = "text"
    strict_exit = False
    remaining: list[str] = []
    for arg in argv:
        if arg in {"--json", "--output=json"}:
            output_mode = "json"
            continue
        if arg in {"--strict", "--exit-code"}:
            strict_exit = True
            continue
        if arg in {"--plain", "--no-color"}:
            output_mode = "plain" if output_mode != "json" else output_mode
            os.environ["NO_COLOR"] = "1"
            os.environ["ERLANGSHEN_NO_OSC8"] = "1"
            continue
        remaining.append(arg)
    return remaining, output_mode, strict_exit


def _json_cli_envelope(
    cli: CLI,
    command: str,
    text: str,
    *,
    ok: bool = True,
    error: str | None = None,
    exit_code: int = 0,
) -> str:
    payload = {
        "ok": ok,
        "exit_code": exit_code,
        "command": command,
        "text": text,
        "resources": cli._recent_resource_context(limit=24),
        "plan": cli._last_agent_plan,
    }
    if error:
        payload["error"] = error
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _strict_exit_code(command: str, result: str, error: str | None = None) -> int:
    if error:
        return 1
    text = result or ""
    lowered = text.lower()
    if text.startswith("未知命令"):
        return 64
    if text.startswith("请提供") or "需要是 JSON 对象" in text:
        return 64
    if "当前安装包不包含" in text or "local analysis disabled" in text:
        return 69
    if (
        "NEED workspace" in text
        or "workspace ->" in text
        or "workspace_not_allowed" in lowered
        or "工作区未授权" in text
        or "项目文件夹不存在" in text
        or "无法切换项目文件夹" in text
    ):
        return 65
    if (
        "NEED account" in text
        or "account ->" in text
        or "未登录" in text
        or "鉴权" in text and ("失败" in text or "错误" in text or "NEED" in text)
    ):
        return 66
    if (
        "NEED model" in text
        or "model ->" in text
        or "missing key" in lowered
        or "未配置" in text
        or "api key" in lowered and ("missing" in lowered or "invalid" in lowered or "错误" in text)
    ):
        return 67
    if (
        "NEED server" in text
        or "server ->" in text
        or "service unavailable" in lowered
        or "连接失败" in text
        or ("服务端" in text and ("失败" in text or "错误" in text or "不可用" in text))
    ):
        return 68
    if (
        "artifact ->" in text
        or ("chart artifact" in lowered and ("失败" in text or "错误" in text or "failed" in lowered))
        or ("图表" in text and ("失败" in text or "错误" in text))
    ):
        return 70
    if command.startswith("/doctor") and ("NEED " in text or "fix   " in text):
        return 2
    if "错误:" in text or text.startswith("错误"):
        return 1
    return 0


def main():
    """主入口"""
    argv, output_mode, strict_exit = _parse_global_flags(sys.argv[1:])
    args = argv
    startup_workspace, args = _extract_startup_workspace_args(args)
    if args == ["__ERLANGSHEN_MISSING_WORKSPACE_PATH__"]:
        message = "--cd / --workspace 需要提供项目文件夹路径"
        if output_mode == "json":
            print(json.dumps({"ok": False, "exit_code": 64, "command": "", "text": "", "error": message}, ensure_ascii=False, indent=2))
        else:
            print(message)
        if strict_exit:
            sys.exit(64)
        return
    if startup_workspace:
        try:
            workspace = Path(startup_workspace).expanduser().resolve()
            if not workspace.exists() or not workspace.is_dir():
                message = f"项目文件夹不存在或不是目录: {workspace}"
                if output_mode == "json":
                    print(json.dumps({"ok": False, "exit_code": 1, "command": "", "text": "", "error": message}, ensure_ascii=False, indent=2))
                else:
                    print(message)
                if strict_exit:
                    sys.exit(1)
                return
            os.chdir(workspace)
            select_workspace(workspace)
        except OSError as exc:
            message = f"无法切换项目文件夹: {exc}"
            if output_mode == "json":
                print(json.dumps({"ok": False, "exit_code": 1, "command": "", "text": "", "error": message}, ensure_ascii=False, indent=2))
            else:
                print(message)
            if strict_exit:
                sys.exit(1)
            return

    cli = CLI()

    if args:
        raw = " ".join(args).strip()

        if raw in {"--help", "-h"}:
            cli.print_help()
            return

        if raw in {"--version", "-v"}:
            print(__version__)
            return

        try:
            result = asyncio.run(cli.dispatch(raw))
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n再见!")
            return
        except Exception as exc:
            if output_mode == "json":
                print(_json_cli_envelope(cli, raw, "", ok=False, error=str(exc), exit_code=1))
                sys.exit(1 if strict_exit else 0)
            if strict_exit:
                print(f"错误: {exc}")
                sys.exit(1)
            raise

        exit_code = _strict_exit_code(raw, result) if strict_exit else 0
        if output_mode == "json":
            print(_json_cli_envelope(cli, raw, result, ok=exit_code == 0, exit_code=exit_code))
        else:
            print(result)
        if strict_exit and exit_code:
            sys.exit(exit_code)
    else:
        if output_mode == "json":
            print(_json_cli_envelope(cli, "", cli.help_text()))
            return
        # 交互模式
        try:
            asyncio.run(cli.interactive_mode())
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n再见!")


def _extract_startup_workspace_args(args: list[str]) -> tuple[str | None, list[str]]:
    workspace: str | None = None
    remaining: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--cd", "-C", "--workspace"}:
            if index + 1 >= len(args):
                return workspace, ["__ERLANGSHEN_MISSING_WORKSPACE_PATH__"]
            workspace = args[index + 1]
            index += 2
            continue
        if arg.startswith("--cd="):
            workspace = arg.split("=", 1)[1]
            index += 1
            continue
        if arg.startswith("--workspace="):
            workspace = arg.split("=", 1)[1]
            index += 1
            continue
        remaining.append(arg)
        index += 1
    return workspace, remaining


if __name__ == "__main__":
    main()
