"""
分析框架 Skill
"""

from typing import Dict, Any


class AnalysisFramework:
    """
    分析框架库
    
    提供各种专业分析框架模板
    """
    
    FRAMEWORKS = {
        "macro": {
            "name": "宏观分析框架",
            "description": "用于宏观经济分析的标准框架",
            "structure": {
                "1. 经济周期": ["GDP增速", "产出缺口", "CPI/PPI"],
                "2. 货币金融": ["M2增速", "社融", "利率水平"],
                "3. 财政政策": ["赤字率", "专项债", "税收"],
                "4. 外部环境": ["出口", "汇率", "外资"],
                "5. 政策展望": ["逆周期调节", "改革举措"]
            }
        },
        "equity": {
            "name": "股票分析框架",
            "description": "用于个股和行业分析的标准框架",
            "structure": {
                "1. 行业分析": ["行业空间", "竞争格局", "景气度"],
                "2. 公司分析": ["商业模式", "核心竞争力", "管理层"],
                "3. 财务分析": ["盈利能力", "成长性", "现金流"],
                "4. 估值分析": ["PE/PB", "DCF", "相对估值"],
                "5. 风险因素": ["行业风险", "公司风险", "市场风险"]
            }
        },
        "multi_asset": {
            "name": "多资产配置框架",
            "description": "用于大类资产配置的分析框架",
            "structure": {
                "1. 宏观研判": ["经济周期", "政策取向", "风险偏好"],
                "2. 资产筛选": ["股票", "债券", "商品", "另类"],
                "3. 相关性分析": ["资产相关性", "动态相关性"],
                "4. 组合优化": ["风险预算", "收益预期", "约束条件"],
                "5. 动态调整": ["再平衡", "择时", "应急计划"]
            }
        },
        "risk": {
            "name": "风险管理框架",
            "description": "用于风险识别和评估的框架",
            "structure": {
                "1. 风险识别": ["市场风险", "信用风险", "流动性风险", "操作风险"],
                "2. 风险测量": ["VaR", "ES", "波动率", "最大回撤"],
                "3. 风险监控": ["预警指标", "限额管理", "压力测试"],
                "4. 风险缓释": ["对冲", "分散化", "保险"]
            }
        },
        "performance": {
            "name": "业绩归因框架",
            "description": "用于组合业绩归因的框架",
            "structure": {
                "1. 收益分解": ["资产配置", "个股选择", "交互效应"],
                "2. 因子暴露": ["市场因子", "风格因子", "行业因子"],
                "3. 风险归因": ["各类资产贡献", "各类因子贡献"],
                "4. 基准对比": ["相对收益", "信息比率", "跟踪误差"]
            }
        }
    }
    
    @classmethod
    def get_framework(cls, name: str) -> Dict[str, Any]:
        """获取指定框架"""
        return cls.FRAMEWORKS.get(name, {})
    
    @classmethod
    def list_frameworks(cls) -> list:
        """列出所有框架"""
        return [
            {
                "name": key,
                "name_cn": value["name"],
                "description": value["description"]
            }
            for key, value in cls.FRAMEWORKS.items()
        ]
    
    @classmethod
    def apply_framework(cls, framework_name: str, content: str) -> str:
        """应用框架格式化内容"""
        framework = cls.get_framework(framework_name)
        
        if not framework:
            return content
        
        output = f"# {framework['name']}\n\n"
        output += f"*{framework['description']}*\n\n"
        
        for section, items in framework["structure"].items():
            output += f"## {section}\n"
            for item in items:
                output += f"- {item}\n"
            output += "\n"
        
        return output
