# 二郎神 CLI 客户端说明

二郎神客户端是面向用户的瘦 CLI。它不内置核心认知库、服务端 API、策略框架或生产域名，而是通过登录和 HTTP API 对接已经部署好的二郎神核心服务端。

## 定位

- 客户端负责：登录、保存本地 token、调用服务端健康检查、状态查询、认知映射和投资建议。
- 服务端负责：鉴权、权限层级、认知保护、策略框架、数据融合和建议生成。
- 生产域名不需要写进代码仓库；部署后通过 `ERLANGSHEN_API_BASE_URL`、`ERLANGSHEN_SERVER_URL`、`~/.erlangshen/settings.json` 或 `/auth server <url>` 配置。

## 交互方式

CLI 采用服务端优先的交互方式，并借鉴 Claude Code 一类工具的优点：清晰的会话状态、slash commands、可脚本化的一次性命令、直接输入自然语言问题，以及登录/状态/退出这些高频命令的短路径。

进入交互模式：

```bash
erlangshen
```

启动后会显示当前服务端地址和登录状态。普通自然语言输入会默认走服务端建议接口，等同于 `/advice <问题>`。

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
| `/advice <问题>` | 请求服务端生成受保护投资建议 |
| `/auth server <url>` | 设置服务端地址 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

完整服务端命令仍保留在 `/auth <cmd>` 和 `/server <cmd>` 下，方便脚本和调试：

```bash
erlangshen /auth server https://erlangshen.example.com
erlangshen /login xwab user@example.com
erlangshen /status
erlangshen /service
erlangshen /map 全球流动性转向时风险资产怎么看
erlangshen /advice 利率下行时A股红利资产怎么看
```

## 服务端地址配置

优先级从高到低：

1. `ERLANGSHEN_API_BASE_URL` 或 `ERLANGSHEN_SERVER_URL`
2. `/auth server <url>` 保存到 `~/.erlangshen/auth.json`
3. `~/.erlangshen/settings.json` 中的 `erlangshen_api_base_url`
4. 默认开发地址 `http://127.0.0.1:8000`

生产环境建议由部署脚本或运维配置注入域名，例如：

```bash
export ERLANGSHEN_API_BASE_URL=https://erlangshen.example.com
erlangshen /health
```

如果反向代理挂在 `/api/erlangshen` 路径下，也可以直接配置完整 base URL：

```bash
erlangshen /auth server https://example.com/api/erlangshen
```

客户端会自动兼容服务端当前的 `/health`、`/api/auth/*`、`/api/status`、`/api/cognition/map` 和 `/api/advice` 路径。

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

如果本机核心服务端运行在 `http://127.0.0.1:8000`，`/server health` 应返回健康状态。生产部署时把服务端地址替换为生产域名即可。

## 发布边界

npm 发布包只包含客户端必要文件：

- `bin/cli.js`
- `src/cli.py`
- `src/auth/*`
- `src/client/*`
- `src/commands/auth.py`
- `src/commands/server.py`
- `src/config.py`
- `src/paths.py`
- `requirements-client.txt`

不会发布服务端 API、核心认知库、内部测试、部署脚本或策略实现。用户端不能枚举完整认知库，只能通过 `/map` 和 `/advice` 获取受保护结果。
