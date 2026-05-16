"""
报告模板 Skill
"""

from typing import Dict, Any
from datetime import datetime


class ReportTemplates:
    """
    报告模板库
    
    提供各种标准化的报告模板
    """
    
    TEMPLATES = {
        "daily": {
            "name": "日报模板",
            "description": "每日市场总结报告模板",
            "template": """# {title}

**日期**: {date}
**分析师**: 二郎神

---

## 今日市场回顾

### 宏观面
- 重要经济数据：
- 政策动向：

### 市场走势
| 指数 | 收盘价 | 涨跌幅 |
|------|--------|--------|
| 上证指数 | - | - |
| 深证成指 | - | - |
| 创业板指 | - | - |
| 沪深300 | - | - |

### 资金面
- 成交额：
- 北向资金：
- 融资融券：

## 热点聚焦

## 明日展望

## 风险提示

---
*本报告仅供参考，不构成投资建议*
"""
        },
        "weekly": {
            "name": "周报模板",
            "description": "每周市场总结报告模板",
            "template": """# {title}

**周期**: {date}
**分析师**: 二郎神

---

## 本周市场概述

### 宏观环境
- 国内经济数据：
- 政策动态：
- 海外市场：

### 市场表现
| 指数 | 本周涨跌幅 | 成交额变化 |
|------|-----------|-----------|
| 上证指数 | - | - |
| 深证成指 | - | - |
| 创业板指 | - | - |

### 行业表现
本周涨幅前五：
本周跌幅前五：

### 资金动向
- 北向资金：
- 融资余额：

## 下周展望

### 关注事件
1. 
2. 
3. 

### 投资建议

## 风险提示

---
*本报告仅供参考，不构成投资建议*
"""
        },
        "monthly": {
            "name": "月度报告模板",
            "description": "每月投资总结报告模板",
            "template": """# {title}

**期间**: {date}
**分析师**: 二郎神

---

## 本月宏观经济

### 经济数据
- GDP：
- CPI：
- PPI：
- PMI：
- 社融：

### 政策取向
- 货币政策：
- 财政政策：

## 本月市场表现

### 股票市场
| 指数 | 本月涨跌幅 | 成交额 |
|------|-----------|--------|
| 上证指数 | - | - |
| 深证成指 | - | - |
| 创业板指 | - | - |
| 沪深300 | - | - |

### 债券市场
### 商品市场
### 外汇市场

## 组合表现

### 收益表现
- 本月收益：
- YTD收益：
- 波动率：
- 最大回撤：

### 归因分析
- 资产配置贡献：
- 个券选择贡献：

## 下月展望

### 宏观判断
### 市场观点
### 配置建议

## 风险提示

---
*本报告仅供参考，不构成投资建议*
"""
        },
        "research": {
            "name": "个股研究报告模板",
            "description": "个股深度研究报告模板",
            "template": """# {title}

**股票代码**: 
**股票名称**: 
**报告日期**: {date}
**分析师**: 二郎神

---

## 投资摘要

### 核心观点
(1-2句话概括投资逻辑)

### 评级
- 评级：
- 目标价：
- 当前价：
- 上涨空间：

### 投资亮点

### 主要风险

---

## 公司概况

### 主营业务
### 发展历程
### 股权结构

## 行业分析

### 行业空间
### 竞争格局
### 发展趋势

## 业务分析

### 业务结构
### 核心竞争力
### 成长性分析

## 财务分析

### 盈利能力
| 指标 | 2021 | 2022 | 2023 | 2024E |
|------|------|------|------|--------|
| 营收(亿) | - | - | - | - |
| 净利润(亿) | - | - | - | - |
| 毛利率 | - | - | - | - |
| 净利率 | - | - | - | - |

### 成长性
### 现金流
### 资产负债

## 估值分析

### 相对估值
### 绝对估值
### 估值结论

## 风险提示

1. 
2. 
3. 

## 投资建议

---
*本报告仅供参考，不构成投资建议*
"""
        },
        "strategy": {
            "name": "策略报告模板",
            "description": "投资策略报告模板",
            "template": """# {title}

**类型**: {date}
**分析师**: 二郎神

---

## 核心观点

## 宏观背景

### 经济周期
### 政策环境
### 外部环境

## 市场判断

### 股票市场
### 债券市场
### 商品市场
### 外汇市场

## 资产配置建议

### 战略配置
| 资产类别 | 配置比例 | 变化 |
|----------|---------|------|
| 股票 | - | - |
| 债券 | - | - |
| 商品 | - | - |
| 现金 | - | - |

### 战术调整

## 行业配置

### 超配行业
### 低配行业
### 规避行业

## 风险提示

## 跟踪指标

---
*本报告仅供参考，不构成投资建议*
"""
        }
    }
    
    @classmethod
    def get_template(cls, template_name: str) -> Dict[str, Any]:
        """获取指定模板"""
        template = cls.TEMPLATES.get(template_name, {})
        
        if not template:
            return {}
        
        # 填充模板
        filled = template["template"].format(
            title="标题",
            date=datetime.now().strftime("%Y年%m月%d日")
        )
        
        return {
            "name": template["name"],
            "description": template["description"],
            "template": filled
        }
    
    @classmethod
    def list_templates(cls) -> list:
        """列出所有模板"""
        return [
            {
                "id": key,
                "name": value["name"],
                "description": value["description"]
            }
            for key, value in cls.TEMPLATES.items()
        ]
    
    @classmethod
    def render_template(cls, template_name: str, **kwargs) -> str:
        """渲染模板"""
        template = cls.TEMPLATES.get(template_name)
        
        if not template:
            return ""
        
        defaults = {
            "title": kwargs.get("title", "报告标题"),
            "date": kwargs.get("date", datetime.now().strftime("%Y年%m月%d日"))
        }
        defaults.update(kwargs)
        
        return template["template"].format(**defaults)
