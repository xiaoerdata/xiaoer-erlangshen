# 二郎神 Erlangshen CLI

二郎神 CLI 是面向用户的命令行客户端，用来连接已经部署好的二郎神核心服务端。客户端负责登录、保存 token、查看服务状态、请求认知映射，并用本机大模型 API Key 直连模型供应商生成投资建议；核心认知库、策略框架、API 服务和生产域名都由服务端环境管理。

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
erlangshen /model select
erlangshen /model key
erlangshen /map 全球流动性转向时风险资产怎么看
erlangshen /advice 利率下行时A股红利资产怎么看
```

进入交互模式后，直接输入自然语言问题会先请求服务端做受保护场景映射，再由客户端使用本机 API Key 调用大模型生成建议：

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
| `/advice <问题>` | 服务端映射场景，本机大模型生成建议 |
| `/model select` | 选择大模型供应商和型号 |
| `/model key` | 在本机输入并保存当前供应商 API Key |
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

## 大模型 Key

大模型 API Key 不会发送给二郎神服务端。请在本机配置：

```bash
erlangshen /model select
erlangshen /model key
```

也可以使用环境变量，例如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`MIMO_API_KEY`、`KIMI_API_KEY`。`/advice` 只把问题发送给服务端做场景映射，最终文本分析由客户端直连模型供应商生成。

## 发布边界

npm 包是瘦客户端，只包含 CLI、登录会话、HTTP 客户端、配置和服务端调用命令。它不会发布服务端 API、核心认知库、内部测试、部署脚本或策略实现。

更多细节见 [README_CLI.md](./README_CLI.md)。

## License

MIT
