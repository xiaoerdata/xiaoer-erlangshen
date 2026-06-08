# 二郎神 Erlangshen CLI

二郎神 CLI 是面向用户的命令行客户端，用来连接已经部署好的二郎神核心服务端。客户端负责登录、保存 token、查看服务状态、请求认知映射和生成投资建议；核心认知库、策略框架、API 服务和生产域名都由服务端环境管理。

## 安装

```bash
npm install -g erlangshen
```

安装脚本会检查 Python 3.9+，并安装客户端所需的轻量 Python 依赖。

## 快速开始

```bash
erlangshen
erlangshen /health
erlangshen /login xwab user@example.com
erlangshen /status
erlangshen /map 全球流动性转向时风险资产怎么看
erlangshen /advice 利率下行时A股红利资产怎么看
```

进入交互模式后，直接输入自然语言问题会默认请求服务端 `/advice` 能力：

```text
erlangshen:guest> 利率下行时A股红利资产怎么看
```

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `/login [xwab|xczt] [账号]` | 登录核心服务端 |
| `/logout` | 清除本地登录状态 |
| `/status` | 查看登录状态 |
| `/service` | 查看服务端状态 |
| `/health` | 服务端健康检查 |
| `/map <问题>` | 认知场景映射 |
| `/advice <问题>` | 生成受保护投资建议 |
| `/auth server <url>` | 设置服务端地址 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

## 服务端地址

npm 客户端默认连接：

```text
https://xiaoerdata.site/api/erlangshen
```

按优先级可通过以下方式覆盖：

1. `ERLANGSHEN_API_BASE_URL` 或 `ERLANGSHEN_SERVER_URL`
2. `/auth server <url>`
3. `~/.erlangshen/settings.json` 中的 `erlangshen_api_base_url`
4. 内置默认地址 `https://xiaoerdata.site/api/erlangshen`

反向代理如果挂在 `/api/erlangshen`，也可以直接配置完整 base URL：

```bash
erlangshen /auth server https://xiaoerdata.site/api/erlangshen
```

## 发布边界

npm 包是瘦客户端，只包含 CLI、登录会话、HTTP 客户端、配置和服务端调用命令。它不会发布服务端 API、核心认知库、内部测试、部署脚本或策略实现。

更多细节见 [README_CLI.md](./README_CLI.md)。

## License

MIT
