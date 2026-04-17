---
name: report-analysis
description: "分析财报的核心是理解公司本身：识别业务模式、定价因子、外部依赖，并更新本地知识库。TRIGGER when: 用户请求分析某公司年报、理解公司业务模式、想知道公司利润受什么因素影响。DO NOT TRIGGER when: 只需查询具体财务数据、纯行情分析。"
license: MIT
---

# 财报分析 Skill

已知一家公司的财报，对财报的分析过程，重点不是产出财报摘要，而是构建更准确的公司模型，回答三个投资问题：

1. **这家公司在干什么？** → 业务模式抽象
2. **什么影响它的利润？** → 定价因子识别
3. **后续该跟踪什么？** → 外部监控体系

同时适时地更新本地知识库，让后续分析该公司时可快速复用。

---

## 适用场景

- 分析某公司年报，理解这家公司在干什么
- 识别影响公司利润的关键因子
- 建立外部数据监控体系，知道后续该跟踪什么
- 构建准确的公司模型，存入知识库供后续使用

## 不适用场景

- 只需要查单个财务指标（用 tushare-data skill）
- 纯行情/走势分析（用 tushare-data skill）
- 多标的横向对比（用 stock-analysis skill）
- 给出买卖建议

---

## Skill触发指南

即使用户完全不说"年报"、"公司模型"这些关键词，只要意图符合以下含义，也应该触发本 skill。

### 常见口语触发

- 帮我看看这家公司是干什么的
- 这家公司靠什么赚钱
- 影响利润的因素有哪些
- 后续应该跟踪什么
- 帮我理解一下这家公司
- 年报太长了帮我抓重点

### 理解优先原则

- "这家公司是干什么的" → 业务模式分析
- "利润受什么影响" → 定价因子识别
- "后续该看什么" → 外部监控清单
- "帮我分析年报" → 完整公司模型构建

---

## 意图分类

先识别任务类型，再决定分析深度。

| 意图类型 | 典型问题 | 分析维度 |
|---------|---------|---------|
| 业务模式理解 | 这家公司是干什么的 | 核心业务、业务拆解、产业链定位 |
| 定价因子识别 | 什么影响公司利润 | 成本端因子、收入端因子、竞争端因子 |
| 外部监控体系 | 后续该跟踪什么 | 上游数据源、下游数据源、竞争动态 |
| 完整公司模型构建 | 帮我分析年报 | 以上全部 + 假设风险 + 知识库存储 |

---

## 财报分析流程

### Step 1: 标的识别 + 数据获取
调用Tushare获取基础信息和财务数据
- **文件**: `scripts/fetch_data.py`
- **函数**:
  - `resolve_stock(code_or_name)` - 解析股票代码或公司名
  - `get_financial_data(ts_code)` - 获取营收利润
  - `get_financial_indicators(ts_code)` - 获取财务指标

### Step 2: 业务模式抽象
从年报提取业务描述、收入构成、成本构成

### Step 3: 定价因子识别
推导上游敏感度、下游敏感度、竞争格局

### Step 4: 外部监控体系
建立监控清单，指定数据源和频率

### Step 5: 存储到知识库
- **文件**: `scripts/save_to_kb.py`
- **函数**:
  - `save_all_to_knowledge_base(result)` - 统一存储入口

**知识库目录结构**
```
.reme/knowledge-base/
└── stocks/
    └── {公司名_股票代码}/
        ├── basic.md              # 公司基础信息
        ├── company_profile.md    # 公司档案（业务模式+产业链定位+假设风险）
        ├── financial.md          # 实时财务数据
        ├── pricing_factors.md    # 定价因子
        ├── external_monitor.md   # 外部监控清单
        └── reports/              # 年报原文及解析
```

**文件职责**：

| 文件 | 存什么 | 用途 |
|------|--------|------|
| `basic.md` | 股票代码、所属行业、上市日期 | 标的识别 |
| `company_profile.md` | 业务模式+产业链定位+假设风险 | 理解公司 |
| `financial.md` | 营收、利润、毛利率 | 实时数据 |
| `pricing_factors.md` | 定价因子清单 | 利润驱动 |
| `external_monitor.md` | 监控项+数据源+频率 | 后续跟踪 |

---

## 知识库查询
- **文件**: `scripts/query_kb.py`
- **函数**:
  - `get_company_profile(code_or_name)` - 获取公司档案
  - `get_pricing_factors(code_or_name)` - 获取定价因子
  - `get_external_monitor(code_or_name)` - 获取监控清单

---

## 接口使用示例

```python
from scripts.query_kb import get_company_profile, get_pricing_factors

# 查询公司档案
profile = get_company_profile('宁德时代')
# {'core_business': '动力电池+储能电池制造商', 'segments': [...], ...}

# 查询定价因子
factors = get_pricing_factors('宁德时代')
# [{'name': '碳酸锂价格', 'type': '成本端', ...}, ...]
```

---

## 数据结构示例

```python
result = {
    'ts_code': '300750.SZ',
    'name': '宁德时代',

    # 基础信息
    'basic': {
        'industry': '电气设备',
        'list_date': '2018-06-11',
        'market': '创业板',
    },

    # 公司档案
    'model': {
        'core_business': '动力电池+储能电池制造商',
        'segments': [
            {'name': '动力电池', 'ratio': '70%', 'margin': '17-18%', 'downstream': '新能源车企', 'upstream': '锂电材料'},
        ],
        'chain_position': '全球龙头，技术+规模双壁垒',
        'assumptions': ['电池技术路线不变', '新能源车渗透率持续提升'],
        'risks': ['碳酸锂价格剧烈波动', '车企自研电池加速'],
    },

    # 财务数据
    'financial': {
        'revenue': [{'year': '2023', 'revenue': 4009, ...}],
        'indicators': [{'year': '2023', 'gross_margin': 18.5, ...}],
    },

    # 定价因子
    'pricing_factors': [
        {'name': '碳酸锂价格', 'type': '成本端', 'mechanism': '成本占比高', 'priority': '高'},
    ],

    # 外部监控
    'external_monitor': {
        'upstream': [{'name': '碳酸锂现货价格', 'source': 'SMM', 'frequency': '周度'}],
        'downstream': [{'name': '新能源车销量', 'source': '乘联会', 'frequency': '月度'}],
        'competition': [{'name': '竞对毛利', 'source': '竞对公告', 'frequency': '季度'}],
    },
}
```

---

## 协作关系

| Skill | 关系 |
|-------|------|
| markdown-tree-builder | 前置依赖：生成年报树结构 |
| tushare-data | 数据依赖：基础信息、财务数据 |

---

## 分析原则

1. **模型优先**：产出是投资模型框架，不是财报摘要
2. **外部导向**：重点识别需要持续监控的外部变量
3. **数据分离**：历史数据只提取锚点，详细数据可实时拉取
4. **业务驱动**：从业务模式推导定价因子