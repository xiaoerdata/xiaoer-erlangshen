"""
/report 命令 - 报告生成
"""

from typing import Optional
from datetime import datetime
from pathlib import Path
from src.brain import Brain
from src.mcp.registry import MCPRegistry


class ReportCommand:
    """
    报告生成命令处理器
    
    用法:
        /report 月度总结
        /report 季度策略
        /report 个股研究 贵州茅台
    """
    
    def __init__(self, brain: Brain, mcp: MCPRegistry):
        self.brain = brain
        self.mcp = mcp
        self.knowledge_dir = Path("~/.openclaw-agent-06/workspace/erlangshen/knowledge/reports").expanduser()
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute(self, args: str) -> str:
        """
        生成报告
        
        Args:
            args: 报告类型和主题
        
        Returns:
            报告内容
        """
        if not args:
            return self._help()
        
        # 解析报告类型
        report_type = self._parse_report_type(args)
        
        # 生成报告
        report_content = await self._generate_report(args, report_type)
        
        # 保存报告
        report_path = await self._save_report(args, report_content)
        
        return f"{report_content}\n\n📁 报告已保存至: {report_path}"
    
    def _parse_report_type(self, args: str) -> str:
        """解析报告类型"""
        args_lower = args.lower()
        
        if "月度" in args or "月报" in args:
            return "月度报告"
        elif "季度" in args or "季报" in args:
            return "季度报告"
        elif "年度" in args or "年报" in args:
            return "年度报告"
        elif "周" in args or "周报" in args:
            return "周报"
        elif "个股" in args or "研究" in args:
            return "个股研究报告"
        elif "策略" in args:
            return "策略报告"
        elif "宏观" in args:
            return "宏观报告"
        else:
            return "专题报告"
    
    async def _generate_report(self, args: str, report_type: str) -> str:
        """生成报告内容"""
        templates = {
            "月度报告": """# {title}

**生成时间**: {date}

## 本月回顾

### 宏观经济
(本月宏观经济运行情况)

### 市场表现
(本月市场走势回顾)

### 重要事件
(本月重要事件梳理)

## 下月展望

### 宏观预判
(对下月宏观经济的判断)

### 市场观点
(对下月市场的展望)

### 投资建议
(具体投资建议)
""",
            "季度报告": """# {title}

**生成时间**: {date}

## 本季度概述

### 宏观经济
(本季度宏观经济运行情况)

### 市场表现
(本季度市场走势回顾)

### 业绩归因
(组合业绩归因分析)

## 下季度展望

### 宏观预判
(对下季度宏观经济的判断)

### 市场观点
(对下季度市场的展望)

### 配置建议
(大类资产配置建议)
""",
            "个股研究报告": """# {title}

**生成时间**: {date}

## 投资摘要

### 核心观点
(1-2句话概括投资逻辑)

### 关键数据
| 指标 | 数值 |
|------|------|
| 当前价格 | - |
| 目标价格 | - |
| 评级 | - |

## 公司概况

### 主营业务
(公司主要业务介绍)

### 竞争优势
(公司的核心竞争优势)

## 财务分析

### 盈利能力
(营收、利润分析)

### 成长性
(同比、环比分析)

### 估值水平
(PE、PB分析)

## 风险提示

## 投资建议
""",
        }
        
        template = templates.get(report_type, templates["月度报告"])
        
        # 填充模板
        title = args.replace("月度", "").replace("季度", "").replace("报告", "").strip()
        if not title:
            title = report_type
        
        content = template.format(
            title=title,
            date=datetime.now().strftime("%Y年%m月%d日")
        )
        
        # 使用LLM增强报告内容
        enhanced = await self.brain.think(
            prompt=f"""请基于以下主题生成{report_type}内容：

主题：{args}

请生成完整、专业的报告内容，替换下方模板中的占位内容：

{content}
""",
            system="你是一位专业的投资研究报告撰写人，擅长生成结构清晰、数据翔实的投资报告。"
        )
        
        return enhanced if enhanced else content
    
    async def _save_report(self, args: str, content: str) -> Path:
        """保存报告"""
        # 生成文件名
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() else "_" for c in args[:20])
        filename = f"{date_str}_{safe_title}.md"
        
        filepath = self.knowledge_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath
    
    def _help(self) -> str:
        """帮助信息"""
        return """
/report - 报告生成命令

用法:
    /report <报告类型> [主题]

示例:
    /report 月度总结
    /report 季度策略
    /report 周报
    /report 个股研究 贵州茅台
    /report 宏观月报

支持的报告类型:
    月度报告, 季度报告, 年度报告, 周报,
    个股研究报告, 策略报告, 宏观报告
"""
