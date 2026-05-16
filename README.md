# 小二嘎 (小二嘎) CLI

基于 Claude Code 架构的投资分析智能体 CLI 工具。

## 功能特性

- 🤖 **多Agent协作**: 宏观分析师、股票分析师、多资产分析师
- 📊 **MCP工具**: 行情数据、宏观数据、飞书文档
- ⚡ **斜杠命令**: `/analyze`, `/macro`, `/stock`, `/report` 等
- 🧠 **LLM大脑**: 支持 DeepSeek、OpenAI 等多种模型
- 📝 **知识沉淀**: 纪要、报告自动保存

## 目录结构

```
erlangshen/
├── bin/
│   └── erlangshen          # CLI 入口脚本
├── src/
│   ├── cli.py               # CLI 主入口
│   ├── config.py            # 配置管理
│   ├── brain.py             # LLM 大脑
│   ├── mcp/                 # MCP 工具
│   │   ├── market.py        # 行情数据
│   │   ├── macro.py         # 宏观数据
│   │   ├── feishu.py        # 飞书文档
│   │   └── registry.py      # MCP 注册表
│   ├── agents/              # 专业智能体
│   │   ├── base.py          # 基础Agent
│   │   ├── macro.py         # 宏观Agent
│   │   ├── equity.py        # 股票Agent
│   │   └── multi_asset.py   # 多资产Agent
│   ├── commands/             # 斜杠命令
│   │   ├── analyze.py
│   │   ├── macro.py
│   │   ├── stock.py
│   │   ├── report.py
│   │   ├── search.py
│   │   ├── portfolio.py
│   │   ├── risk.py
│   │   └── memo.py
│   ├── skills/              # 技能
│   │   ├── framework.py
│   │   └── templates.py
│   └── hooks/               # 事件钩子
│       ├── session_start.py
│       └── session_end.py
├── .claude/
│   └── settings.json        # 配置文件
├── knowledge/               # 知识库
│   ├── memos/               # 纪要
│   ├── reports/             # 报告
│   ├── insights/            # 洞察
│   └── facts/               # 事实库
└── requirements.txt
```

## 安装

```bash
# 克隆或下载项目
cd ~/.openclaw-agent-06/workspace/erlangshen

# 安装依赖
pip install -r requirements.txt

# 添加执行权限
chmod +x bin/erlangshen

# 链接到 PATH (可选)
ln -s ~/.openclaw-agent-06/workspace/erlangshen/bin/erlangshen /usr/local/bin/erlangshen
```

## 配置

编辑 `~/.openclaw-agent-06/workspace/erlangshen/.claude/settings.json`:

```json
{
  "llm_provider": "deepseek",
  "deepseek_api_key": "your-api-key",
  "deepseek_model": "deepseek-chat",
  "db_host": "localhost",
  "db_port": 5432,
  "db_name": "market",
  "feishu_app_id": "your-feishu-app-id",
  "feishu_app_secret": "your-feishu-app-secret"
}
```

## 使用方式

### 交互模式

```bash
erlangshen
```

### 命令模式

```bash
erlangshen /analyze A股当前走势
erlangshen /macro CPI走势
erlangshen /stock 贵州茅台
erlangshen /report 月度总结
```

### 斜杠命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/analyze` | 综合分析 | `/analyze A股走势` |
| `/macro` | 宏观分析 | `/macro LPR利率` |
| `/stock` | 股票分析 | `/stock 茅台` |
| `/report` | 报告生成 | `/report 月度报告` |
| `/search` | 搜索 | `/search 量化策略` |
| `/portfolio` | 组合分析 | `/portfolio 风险` |
| `/risk` | 风险分析 | `/risk 市场风险` |
| `/memo` | 纪要管理 | `/memo 记录会议` |

## MCP 工具

### Market MCP (行情)
- `get_stock_price`: 实时股价
- `get_stock_history`: 历史行情
- `get_index_quote`: 指数行情
- `get_futures_price`: 期货价格

### Macro MCP (宏观)
- `get_macro_indicator`: 宏观指标
- `get_interest_rates`: 利率数据
- `get_currency_rates`: 汇率数据
- `get_economic_calendar`: 经济日历

### Feishu MCP (飞书)
- `create_doc`: 创建文档
- `append_doc`: 追加内容
- `search_docs`: 搜索文档
- `send_message`: 发送消息

## Agents

### MacroAgent (宏观分析师)
专注宏观经济、政策解读、大类资产配置

### EquityAgent (股票分析师)
专注A股、港股、美股基本面和技术面分析

### MultiAssetAgent (多资产分析师)
专注跨资产配置、组合优化、风险预算

## 开发

```bash
# 直接运行
python -m src.cli

# 或使用入口脚本
./bin/erlangshen
```

## 依赖

- Python 3.10+
- openai >= 1.0.0
- pydantic >= 2.0.0
- psycopg2-binary >= 2.9.0 (可选，用于数据库)
- lark-oapi >= 1.0.0 (可选，用于飞书)

## License

MIT
