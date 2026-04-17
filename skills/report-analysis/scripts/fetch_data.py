"""
数据获取模块 - 从Tushare获取股票基础信息和财务数据
"""

import tushare as ts
import os


def resolve_stock(code_or_name):
    """
    解析股票代码或公司名
    返回: ts_code, name, basic_info
    """
    pro = ts.pro_api(os.getenv('TUSHARE_TOKEN'))

    if '.' in code_or_name:
        df = pro.stock_basic(ts_code=code_or_name)
        if len(df) > 0:
            row = df.iloc[0]
            return row['ts_code'], row['name'], {
                'industry': row['industry'],
                'list_date': row['list_date'],
                'market': row['market'],
            }

    df = pro.stock_basic(name=code_or_name)
    if len(df) == 0:
        df = pro.stock_basic()
        matches = df[df['name'].str.contains(code_or_name, na=False)]
        if len(matches) > 0:
            row = matches.iloc[0]
            return row['ts_code'], row['name'], {
                'industry': row['industry'],
                'list_date': row['list_date'],
                'market': row['market'],
            }
    elif len(df) >= 1:
        row = df.iloc[0]
        return row['ts_code'], row['name'], {
            'industry': row['industry'],
            'list_date': row['list_date'],
            'market': row['market'],
        }

    raise ValueError(f"无法识别股票: {code_or_name}")


def get_financial_data(ts_code, years=3):
    """获取营收利润数据"""
    pro = ts.pro_api(os.getenv('TUSHARE_TOKEN'))
    income_df = pro.income(ts_code=ts_code, report_type='1', limit=years)
    results = []
    for _, row in income_df.iterrows():
        results.append({
            'year': row['end_date'][:4],
            'revenue': round(row['total_revenue'] / 1e8, 2),  # 营业总收入
            'revenue_yoy': row['revenue_yoy'],
            'net_profit': round(row['n_income'] / 1e8, 2),  # 净利润
            'net_profit_yoy': row['net_profit_yoy'],  # 净利润同比
        })
    return sorted(results, key=lambda x: x['year'])


def get_financial_indicators(ts_code):
    """获取财务指标"""
    pro = ts.pro_api(os.getenv('TUSHARE_TOKEN'))
    fina_df = pro.fina_indicator(ts_code=ts_code, limit=4)
    results = []
    for _, row in fina_df.iterrows():
        results.append({
            'year': row['end_date'][:4],
            'gross_margin': row['grossprofit_margin'],
            'net_margin': row['netprofit_margin'],
            'roe': row['roe'],
        })
    return results