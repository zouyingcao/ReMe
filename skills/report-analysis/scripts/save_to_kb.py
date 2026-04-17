"""
知识库存储模块 - 将分析结果存储到本地知识库
"""

import os
from datetime import datetime

KB_BASE = os.getenv('KB_BASE')


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def save_all_to_knowledge_base(result):
    """统一存储到知识库（5个文件）"""
    ts_code = result['ts_code']
    name = result['name']
    company_dir = f"{KB_BASE}/stocks/{name}_{ts_code}"
    ensure_dir(company_dir)

    save_basic(company_dir, result)
    save_company_profile(company_dir, result)
    save_financial(company_dir, result)
    save_pricing_factors(company_dir, result)
    save_external_monitor(company_dir, result)

    print(f"✓ 已保存到知识库: {company_dir}")


def save_basic(company_dir, data):
    """存储公司基础信息"""
    content = f"""# {data['name']} 基础信息

- 股票代码：{data['ts_code']}
- 所属行业：{data['basic']['industry']}
- 上市日期：{data['basic']['list_date']}
- 市场类型：{data['basic']['market']}
- 更新时间：{datetime.now().strftime('%Y-%m-%d')}
"""
    with open(f"{company_dir}/basic.md", 'w', encoding='utf-8') as f:
        f.write(content)


def save_company_profile(company_dir, data):
    """存储公司档案"""
    model = data['model']
    content = f"""# {data['name']} 公司档案

## 核心业务
{model['core_business']}

## 业务拆解
| 业务线 | 收入占比 | 毛利率 | 下游客户 | 上游原料 |
|-------|---------|--------|---------|---------|
"""
    for seg in model['segments']:
        content += f"| {seg['name']} | {seg['ratio']} | {seg['margin']} | {seg['downstream']} | {seg['upstream']} |\n"

    content += f"""

## 产业链定位
{model['chain_position']}

## 关键假设
"""
    for a in model.get('assumptions', []):
        content += f"- {a}\n"

    content += f"""
## 风险信号
"""
    for r in model.get('risks', []):
        content += f"- {r}\n"

    content += f"""
---
- 数据来源：{data.get('report_name', '年报分析')}
- 更新时间：{datetime.now().strftime('%Y-%m-%d')}
"""
    with open(f"{company_dir}/company_profile.md", 'w', encoding='utf-8') as f:
        f.write(content)


def save_financial(company_dir, data):
    """存储财务数据"""
    financial = data['financial']
    content = f"""# {data['name']} 财务数据

## 营收利润
| 年度 | 营收（亿） | 同比增长（YoY） | 净利润（亿） | 同比增长（YoY） |
|------|-----------|-----|-------------|-----|
"""
    for r in financial['revenue']:
        content += f"| {r['year']} | {r['revenue']} | {r['revenue_yoy']}% | {r['net_profit']} | {r['net_profit_yoy']}% |\n"

    content += f"""

## 财务指标
| 年度 | 毛利率 | 净利率 | ROE |
|------|--------|--------|-----|
"""
    for ind in financial['indicators']:
        content += f"| {ind['year']} | {ind['gross_margin']}% | {ind['net_margin']}% | {ind['roe']}% |\n"

    content += f"""
---
- 数据来源：Tushare（可实时更新）
"""
    with open(f"{company_dir}/financial.md", 'w', encoding='utf-8') as f:
        f.write(content)


def save_pricing_factors(company_dir, data):
    """存储定价因子"""
    factors = data['pricing_factors']
    content = f"""# {data['name']} 定价因子

| 因子 | 类型 | 影响机制 | 监控优先级 |
|------|------|---------|-----------|
"""
    for f in factors:
        content += f"| {f['name']} | {f['type']} | {f['mechanism']} | {f['priority']} |\n"

    content += f"""
---
- 更新时间：{datetime.now().strftime('%Y-%m-%d')}
"""
    with open(f"{company_dir}/pricing_factors.md", 'w', encoding='utf-8') as f:
        f.write(content)


def save_external_monitor(company_dir, data):
    """存储外部监控清单"""
    monitor = data['external_monitor']
    content = f"""# {data['name']} 外部监控清单

## 上游材料价格
"""
    for item in monitor['upstream']:
        content += f"- **{item['name']}** → 数据源：{item['source']}（{item['frequency']}）\n"
        if item.get('threshold'):
            content += f"  - 预警：{item['threshold']}\n"

    content += f"""
## 下游需求指标
"""
    for item in monitor['downstream']:
        content += f"- **{item['name']}** → 数据源：{item['source']}（{item['frequency']}）\n"
        content += f"  - 用途：{item['purpose']}\n"

    content += f"""
## 竞争格局
"""
    for item in monitor['competition']:
        content += f"- **{item['name']}** → 数据源：{item['source']}（{item['frequency']}）\n"

    content += f"""
---
- 更新时间：{datetime.now().strftime('%Y-%m-%d')}
"""
    with open(f"{company_dir}/external_monitor.md", 'w', encoding='utf-8') as f:
        f.write(content)