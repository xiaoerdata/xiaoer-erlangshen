# 二郎神 CLI 客户端说明

二郎神客户端是面向用户的瘦 CLI。它不内置核心认知库、服务端 API 或策略框架，而是通过登录和 HTTP API 对接已经部署好的二郎神核心服务端。

## 定位

- 客户端负责：登录、保存本地 token、调用服务端健康检查、状态查询、认知映射，并用本机大模型 API Key 直连模型供应商生成投资建议。
- 服务端负责：鉴权、权限层级、认知保护和受保护场景映射；不接收、不存储、不转发用户的大模型 API Key。
- npm 客户端默认连接 `https://xiaoerdata.site/api/erlangshen`；开发、灰度或私有部署可通过 `ERLANGSHEN_API_BASE_URL`、`ERLANGSHEN_SERVER_URL`、`~/.erlangshen/settings.json` 或 `/auth server <url>` 覆盖。

## 交互方式

CLI 采用服务端优先的交互方式，并借鉴 Claude Code 一类工具的优点：清晰的会话状态、slash commands、可脚本化的一次性命令、直接输入自然语言问题，以及登录/状态/退出这些高频命令的短路径。

进入交互模式：

```bash
erlangshen
```

启动后会显示当前服务端地址、登录状态和本机大模型配置。普通自然语言输入等同于 `/advice <问题>`：CLI 会先请求服务端做受保护场景映射，再用本机 API Key 直连大模型供应商生成建议。

```text
erlangshen:guest> 利率下行时A股红利资产怎么看
```

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `/login [xwab|xczt] [账号]` | 登录核心服务端 |
| `/logout` | 清除本地登录状态 |
| `/status` | 查看本地 token 和服务端校验状态 |
| `/service` | 查看服务端状态 |
| `/health` | 服务端健康检查 |
| `/map <问题>` | 请求服务端进行认知场景映射 |
| `/advice <问题>` | 服务端映射场景，本机大模型生成受保护投资建议 |
| `/model select` | 选择大模型供应商和型号 |
| `/model key` | 本机直连测试通过后保存当前供应商 API Key |
| `/auth server <url>` | 设置服务端地址 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

完整服务端命令仍保留在 `/auth <cmd>` 和 `/server <cmd>` 下，方便脚本和调试：

```bash
erlangshen /health
erlangshen /login xwab user@example.com
erlangshen /status
erlangshen /service
erlangshen /model select
erlangshen /model key
erlangshen /map 全球流动性转向时风险资产怎么看
erlangshen /advice 利率下行时A股红利资产怎么看
```

## CLI 交互优化与脚本模式

本轮 CLI 优化参考了 GitHub star 数量最高的一组开源 CLI/TUI 项目，数据固化在 `src/cli_benchmarks.json`：

```bash
erlangshen /benchmarks
erlangshen /benchmarks json
erlangshen /benchmarks checklist
python3 scripts/update_cli_benchmarks.py
```

已落地能力包括 `/commands <关键词>` 模糊命令搜索、`/commands usage` 命令热度面板、交互命令历史、命令使用频次排序、`/plan` 授权工作区持久化、`/plan diff` 失败恢复提示、`/links`/`/open` 统一资源出口，以及适合自动化的输出模式：

```bash
erlangshen --json /benchmarks
erlangshen --plain /help
erlangshen --strict /doctor
erlangshen --quiet /status
erlangshen /plan history
erlangshen /plan diff
erlangshen /plan history export
erlangshen /plan history prune 20
erlangshen /plan history prune 7d
erlangshen /commands usage
erlangshen /commands usage export
erlangshen /commands usage reset
python3 scripts/smoke_cli_strict.py
python3 scripts/smoke_cli_npm.py
python3 scripts/release_check.py
npm run release:check
npm run release:check:refresh
```

命令热度可通过 `ERLANGSHEN_COMMAND_USAGE_SCOPE=global|project|off` 控制：默认全局记录，`project` 写入授权工作区，`off` 完全关闭记录。

`/commands usage json` 可输出结构化热度数据，便于脚本读取当前 scope、文件和 top commands；`/commands usage export/reset` 可导出或清空当前热度快照。

`--strict` 退出码约定：`64` 未知命令/参数错误，`65` 工作区问题，`66` 账号或鉴权问题，`67` 本机模型/API Key 问题，`68` 服务端问题，`69` 本地分析模块缺失，`70` 图表或资源产物问题。

## 大模型 API Key 安全边界

用户的大模型 API Key 只在客户端使用：

1. `/model select` 选择供应商和模型。
2. `/model key` 在本机输入 API Key，默认保存到 `~/.erlangshen/settings.json`，或使用环境变量如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`MIMO_API_KEY`。
3. `/advice` 只把投资问题发送给二郎神服务端做场景映射；不会把大模型 API Key 发给服务端。
4. 最终建议由客户端直连 OpenAI、Claude、DeepSeek、小米 MiMo 或 Kimi 生成。

不要把 `~/.erlangshen/settings.json`、`~/.erlangshen/auth.json` 或任何 API Key 提交到仓库。

## 服务端地址配置

优先级从高到低：

1. `ERLANGSHEN_API_BASE_URL` 或 `ERLANGSHEN_SERVER_URL`
2. `/auth server <url>` 保存到 `~/.erlangshen/auth.json`
3. `~/.erlangshen/settings.json` 中的 `erlangshen_api_base_url`
4. 内置默认地址 `https://xiaoerdata.site/api/erlangshen`

生产 npm 包内置默认地址：

```text
https://xiaoerdata.site/api/erlangshen
```

开发、灰度或私有部署可以覆盖为其他地址：

```bash
export ERLANGSHEN_API_BASE_URL=http://127.0.0.1:8000
erlangshen /health

erlangshen /auth server https://xiaoerdata.site/api/erlangshen
```

客户端会自动兼容服务端当前的 `/health`、`/api/auth/*`、`/api/status` 和 `/api/cognition/map` 路径。`/server advice` 保留为调试入口；推荐用户直接使用 `/advice`，由客户端本机模型生成最终分析。

## 登录状态与安全

登录成功后 token 会保存到：

```bash
~/.erlangshen/auth.json
```

客户端会尽量将该文件权限设置为 `0600`。不要把该文件提交到仓库，也不要把生产 token 写入代码、README 或 npm 包默认配置。

退出登录：

```bash
erlangshen /logout
```

## 本地开发烟测

在客户端仓库中：

```bash
python3 -m src.cli --help
python3 -m src.cli /auth status
python3 -m src.cli /server health
node bin/cli.js --help
```

如果本机核心服务端运行在 `http://127.0.0.1:8000`，可先设置 `ERLANGSHEN_API_BASE_URL=http://127.0.0.1:8000` 再执行 `/server health`。

## 发布边界

npm 发布包只包含客户端必要文件：

- `bin/cli.js`
- `scripts/update_cli_benchmarks.py`
- `scripts/smoke_cli_strict.py`
- `scripts/smoke_cli_npm.py`
- `scripts/release_check.py`
- `src/cli.py`
- `src/cli_benchmarks.json`
- `src/auth/*`
- `src/client/*`
- `src/commands/auth.py`
- `src/commands/server.py`
- `src/config.py`
- `src/llm/*`
- `src/paths.py`
- `requirements-client.txt`

不会发布服务端 API、核心认知库、内部测试、部署脚本或策略实现。用户端不能枚举完整认知库，只能通过 `/map` 和 `/advice` 获取受保护结果；用户大模型 API Key 始终留在客户端。
