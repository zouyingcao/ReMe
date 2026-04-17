---
name: markdown-tree-builder
description: 将 markdown 文件转换为可导航的文件树，让 Agent 只读取需要的部分。适用于 mineru-document-extractor 转换后的长文档（如年报、财报、说明书）。
author: custom
version: 1.0.0
requirements:
  python: ">=3.10"
  packages: []
  system_deps: []
notes: |
  - 输入为已转换的 markdown 文件（由 mineru-document-extractor 生成）
  - 自动识别章节结构，大章节（>300行）拆出子节点
  - 图片目录自动复制到输出位置
---

# Build Markdown Tree

将 markdown 文件（由 mineru-document-extractor 转换）组织为可导航的文件树，让 Agent 只读取需要的部分。

## 触发条件

当用户表达以下意图时，使用本 skill：

- "解析这份年报"
- "把 markdown 转换成可读的结构"
- "读取某公司 2024 年年报的财务数据部分"
- "这份财报的主要内容是什么"
- "帮我分析一下这个文档的章节结构"

## 快速开始

### 1. 转换 Markdown

```bash
# 基本用法
cd skills/build-markdown-tree/scripts
python build_markdown_tree.py /path/to/report.md --out /path/to/output_dir

# 示例：解析宁德时代年报
python build_markdown_tree.py \
  "/path/to/宁德时代_2025_年度报告.md" \
  --out "/path/to/宁德时代_2025_年度报告_tree"
```

### 2. 阅读结构

```
output/
├── AGENTS.md          ← 导航入口
├── index.md           ← 章节索引
├── node.json          ← 元数据
├── images/            ← 图片目录
└── sections/          ← 章节目录
    ├── 01-致股东的信/
    │   ├── index.md
    │   ├── content.md
    │   └── node.json
    ├── 02-重要提示目录和释义/
    ├── 03-管理层讨论与分析/      ← 大章节，已拆分
    │   ├── subsections/
    │       ├── 01-报告期内公司从事的主要业务/
    │       ├── 02-报告期内公司所处行业情况/
    │       └── ...
    ├── 08-财务报告/              ← 超大章节，已拆分
    │   ├── subsections/
    │       ├── 01-审计报告/
    │       ├── 02-合并财务报表/
    │       └── ...
    └── ...
```

### 3. Agent 使用流程

1. 读取 `index.md` 查看章节摘要（行数、表格数、图片数）
2. 根据任务需求选择章节
3. 读取目标章节的 `content.md`
4. 大章节可进入 `subsections/` 读取子节点

## 脚本功能

### 核心特性

- **自动章节检测**：识别 `# 第X节`、`# 一、`、`# 1、` 等标题模式
- **智能拆分**：大章节（>300行）自动拆出二级标题作为子节点；超大章节（>1000行）拆出三级标题
- **元数据生成**：每个章节包含行数、表格数、图片数等信息
- **图片复制**：自动复制 `images/` 目录到输出位置

### 章节识别模式

| 模式 | 示例 | 层级 |
|------|------|------|
| `# 第X节 XXX` | `# 第三节 管理层讨论与分析` | Level 1（主章节） |
| `# 一、XXX` | `# 一、报告期内公司从事的主要业务` | Level 2（二级标题） |
| `# 1、XXX` | `# 1、主要业务` | Level 3（三级标题） |
| `# 致股东的信` | 特殊章节 | Level 0 |

### 拆分策略

| 条件 | 操作 |
|------|------|
| 章节 < 300行 | 保持单个节点 |
| 章节 > 300行 | 拆出二级标题作为子节点 |
| 章节 > 1000行 | 二级标题也拆出三级标题 |

### 命令行参数

| 参数 | 说明 |
|------|------|
| `input` | 输入 markdown 文件（mineru 转换后） |
| `--out, -o` | 输出目录（必填） |

## 使用示例

### 查看章节结构

```python
import json
from pathlib import Path

output_dir = Path("宁德时代_2025_年度报告_tree")

# 1. 查看章节索引
with open(output_dir / "index.md") as f:
    print(f.read())

# 2. 查看章节元数据
with open(output_dir / "sections/08-财务报告/node.json") as f:
    node = json.load(f)
    print(f"章节：{node['title']}")
    print(f"行数：{node['line_count']}")
    print(f"表格数：{node['table_count']}")
    print(f"子节点：{len(node['children'])}")
```

### 查找特定章节

```python
import json
from pathlib import Path

def find_section(output_dir, keyword):
    """根据关键词查找章节"""
    sections_dir = Path(output_dir) / "sections"
    for section_dir in sorted(sections_dir.iterdir()):
        node_file = section_dir / "node.json"
        if node_file.exists():
            with open(node_file) as f:
                node = json.load(f)
                if keyword in node.get("title", ""):
                    content_file = section_dir / "content.md"
                    if content_file.exists():
                        return content_file.read_text()
    return None

# 查找"财务报告"章节
content = find_section("宁德时代_2025_年度报告_tree", "财务报告")
```

### 读取子章节

```python
# 读取财务报告的审计报告子章节
content = Path("output/sections/08-财务报告/subsections/01-审计报告/content.md").read_text()
```

## 输出格式

### index.md 示例

```markdown
# 宁德时代_2025_年度报告

**总行数**: 4509
**章节数**: 8
**处理时间**: 2026-04-01 19:00:00

---

## 章节列表

- [致股东的信](sections/01-致股东的信/index.md) — 68 行
- [第一节 重要提示、目录和释义](sections/02-重要提示目录和释义/index.md) — 73 行
- [第二节 公司简介和主要财务指标](sections/03-公司简介和主要财务指标/index.md) — 96 行
- [第三节 管理层讨论与分析](sections/04-管理层讨论与分析/index.md) — 568 行 · 已拆分
  - [一、报告期内公司从事的主要业务](sections/04-.../subsections/01-...) — 100 行
  - [二、报告期内公司所处行业情况](sections/04-.../subsections/02-...) — 50 行
- [第八节 财务报告](sections/08-财务报告/index.md) — 2685 行 · 已拆分
  - [一、审计报告](...) — 80 行
  - [二、合并财务报表](...) — 200 行
```

### node.json 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 节点唯一标识符 |
| `title` | string | 章节标题 |
| `slug` | string | URL 友好的标题 |
| `level` | int | 标题层级（1=主章节，2=二级，3=三级） |
| `line_start` | int | 在源文件中的起始行号（1-indexed） |
| `line_end` | int | 在源文件中的结束行号（1-indexed） |
| `line_count` | int | 行数 |
| `table_count` | int | 表格数量 |
| `image_count` | int | 图片数量 |
| `children` | string[] | 子节点 ID 列表 |

## 故障排查

### 问题 1：未检测到章节标题

**现象：** 输出只有一个"全文"节点

**原因：** markdown 文件中的标题格式不符合识别模式

**解决方案：** 检查标题格式是否为：
- `# 第X节 XXX`（主章节）
- `# 一、XXX`（二级标题）

### 问题 2：图片链接失效

**现象：** content.md 中图片无法显示

**原因：** 图片目录未正确复制

**解决方案：** 确保 markdown 文件同目录下有 `images/` 目录

## 最佳实践

1. **从 index.md 开始**：先了解文档结构，不要直接读取整个文件
2. **利用元数据决策**：根据 `line_count`、`table_count`、`image_count` 选择章节
3. **按需读取**：只读取与任务相关的章节，避免 token 浪费
4. **大章节进子节点**：拆分的章节进入 `subsections/` 目录读取更细粒度内容
5. **财务数据在第八节**：A股年报的财务报告通常在最后一节

## 工作流示例

### A 股年报分析

1. **快速概览**：读取 `index.md` 查看章节列表
2. **股东信**：读取 `01-致股东的信/content.md` 了解公司战略
3. **财务数据**：进入 `08-财务报告/subsections/` 查找具体报表
4. **管理层讨论**：进入 `03-管理层讨论与分析/subsections/` 了解业务分析

### 关键数据定位

```python
# 快速定位财务报告中的资产负债表
for subsection in Path("output/sections/08-财务报告/subsections").iterdir():
    content = subsection / "content.md"
    if "资产负债表" in content.read_text():
        print(f"找到: {subsection.name}")
```