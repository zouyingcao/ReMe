# 获取公司财报公告

使用 Tushare [anns_d](https://tushare.pro/wctapi/documents/176.md) 接口获取上市公司公告，并下载财报 PDF 到本地知识库。

## Step 1: 查看可用财报列表

使用 [scripts/get_report_list.py](../scripts/get_report_list.py) 中的 `get_financial_reports`（基于 Tushare `anns_d` 拉取公告后按标题关键词筛选财报，并计算 `priority` 排序）。

**环境**

- 设置环境变量 `TUSHARE_TOKEN`（Tushare Pro token）。
- 需已安装 `tushare`。

**`get_financial_reports(stock_code, report_type=None, start_date=None, end_date=None)`**

| 参数 | 说明 |
|------|------|
| `stock_code` | 股票代码，如 `300750.SZ`。 |
| `report_type` | `annual`（年度）、`semiannual`（半年度）、`quarterly`（季度）；不传则不过滤类型，仍按标题关键词保留财报相关公告。 |
| `start_date` / `end_date` | 公告日期区间，格式 `YYYYMMDD`；对应传给 `anns_d` 的 `start_date` / `end_date`。 |

返回 `pandas.DataFrame`，常用列包括 `ann_date`、`title`、`priority`（数值越小表示脚本认为越「主报告」优先）；无数据时返回 `None`。

**使用示例**：获取宁德时代 2025 年公告区间内的年报类公告
四个位置参数依次为 `股票代码` `report_type` `start_date` `end_date`（日期为 `YYYYMMDD`）：

```bash
python scripts/get_report_list.py 300750.SZ annual 20250101 20251231
```

## Step 2: 下载相关年度报告到本地

使用 [scripts/download_report.py](../scripts/download_report.py) 下载财报PDF到本地知识库。

**使用示例**：想要下载宁德时代2025年年报，注意日期参数是**公告日期**而非报告年度。年报通常在次年3月左右发布，所以2025年年报的公告日期在2026年：

```bash
python scripts/download_report.py 300750.SZ 宁德时代 annual 20260101 20261231
```

**参数说明**：

| 顺序 | 参数 | 说明 | 示例 |
|------|------|------|------|
|1| `stock_code` | 股票代码 | `300750.SZ` |
|2| `company_name` | 公司名称 | `宁德时代` |
|3| `report_type` | 报告类型：`annual`/`semiannual`/`quarterly` | `annual` |
|4| `start_date` | 公告开始日期 | `20250101` |
|5| `end_date` | 公告结束日期 | `20251231` |

**返回值说明**：

| 字段 | 说明 |
|------|------|
| `status` | 状态：`success`(成功)、`failed`(下载失败)、`not_found`(未找到) |
| `title` | 报告标题 |
| `date` | 公告日期 |
| `url` | 公告URL |
| `filepath` | 本地PDF文件路径 |

### 知识库存储路径示例

```
.reme/knowledge-base/stocks/
└── 宁德时代_300750.SZ/
    └── reports/
        └── 宁德时代_宁德时代2024年年度报告.pdf
```
