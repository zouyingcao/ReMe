import os
import sys
import argparse
import tushare as ts
from datetime import datetime

def get_financial_reports(stock_code, report_type=None, start_date=None, end_date=None):
    """
    获取公司财报公告列表

    Args:
        stock_code: 股票代码，如 '300750.SZ'
        report_type: 财报类型
            - 'annual': 年度报告
            - 'semiannual': 半年度报告
            - 'quarterly': 季度报告
            - None: 所有财报
        start_date: 公告开始日期
        end_date: 公告结束日期

    Returns:
        DataFrame: 符合条件的财报公告列表
    """
    pro = ts.pro_api(os.getenv('TUSHARE_TOKEN'))

    # 获取公告列表
    df = pro.anns_d(ts_code=stock_code, start_date=start_date, end_date=end_date)
    
    if df is None or len(df) == 0:
        return None

    # 财报关键词
    report_keywords = {
        'annual': ['年度报告', '年度审计报告'],
        'semiannual': ['半年度报告', '中期报告'],
        'quarterly': ['一季度报告', '三季度报告', '季度报告']
    }

    # 筛选财报
    if report_type and report_type in report_keywords:
        keywords = report_keywords[report_type]
        df = df[df['title'].str.contains('|'.join(keywords), na=False)]

    # 优先级排序：年报 > 季度报告 > 审计报告 > 摘要
    def get_priority(title):
        if '年度报告' in title and '摘要' not in title:
            return 1
        elif '半年度报告' in title and '摘要' not in title:
            return 2
        elif '一季度报告' in title or '三季度报告' in title:
            return 3
        elif '年度审计报告' in title:
            return 4
        elif '年度报告摘要' in title:
            return 5
        elif '半年度报告摘要' in title:
            return 6
        return 10

    df = df.copy()
    df['priority'] = df['title'].apply(get_priority)
    df = df.sort_values('priority').reset_index(drop=True)

    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stock_code", help="stock code")
    parser.add_argument("report_type", default=None, help="report type: annual, semiannual, quarterly", choices=["annual", "semiannual", "quarterly"])
    parser.add_argument("start_date", default=f"{datetime.now().year}0101", help="announcement start date")
    parser.add_argument("end_date", default=f"{datetime.now().year}1231", help="announcement end date")
    args = parser.parse_args()

    if not args.stock_code:
        print("Error: stock_code is required")
        sys.exit(1)

    df = get_financial_reports(args.stock_code, args.report_type, args.start_date, args.end_date)
    print(df[['ann_date', 'title', 'priority']])