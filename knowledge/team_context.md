# 团队上下文

## Agent 分工

| Agent | 角色 | 负责领域 |
|-------|------|---------|
| Agent-01 | 私募FOF总监 | 私募基金筛选、尽调、风控 |
| Agent-02 | 公募FOF总监 | 公募基金筛选、业绩归因 |
| Agent-03 | 交易总监 | 交易执行、下单风控 |
| Agent-04 | CTA量化总监 | CTA量化策略研发 |
| Agent-05 | 宏观策略总监 | 宏观研究、大类资产配置 |
| Agent-06 | IT总监 | 技术架构、基础设施 |
| Agent-07 | 数据总监 | 数据采集、数据治理 |
| Agent-08 | 市场营销总监 | 客户关系、市场推广 |
| Agent-09 | 主观股票总监 | 基本面研究、个股选择 |

## 模型配置

- 默认模型: openrouter/xiaomi/mimo-v2-pro
- Context: 1M tokens
- Max Output: 384K tokens
- 联网搜索: MiniMax MCP

## 技术架构

- 前端端口: 3002
- 后端端口: 8000
- 数据库: MySQL (macro_monitor + strategy_platform)

## 项目结构

```
~/.openclaw-agent-06/workspace/
├── erlangshen/           # 二郎神 (用户端)
├── investment-strategy/  # 投资策略管理系统
└── strategies-repo/     # 策略脚本仓库
```

## 访问规则

- `/SHARED/` → 共享知识库 (公司制度、团队规范)
- 各Agent独立目录 → 独立记忆和知识库
