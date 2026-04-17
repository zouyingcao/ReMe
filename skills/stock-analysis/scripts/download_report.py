import re
import os
import sys
import argparse
import requests
from datetime import datetime
from get_report_list import get_financial_reports


KB_BASE = os.getenv('KB_BASE')


def detail_url_to_pdf_url(detail_url):
    """
    将巨潮详情页 URL 转换为 PDF 直链。

    anns_d 返回的 url 格式如:
      http://www.cninfo.com.cn/new/disclosure/detail?stockCode=000009&announcementId=1223101050&orgId=gssz0000009&announcementTime=2025-04-16

    对应的 PDF 直链为:
      https://static.cninfo.com.cn/finalpage/2025-04-16/1223101050.PDF

    规律: https://static.cninfo.com.cn/finalpage/{announcementTime}/{announcementId}.PDF
    """
    ann_id = re.search(r'announcementId=(\d+)', detail_url)
    ann_time = re.search(r'announcementTime=([\d-]+)', detail_url)

    if not ann_id or not ann_time:
        return None

    return f'https://static.cninfo.com.cn/finalpage/{ann_time.group(1)}/{ann_id.group(1)}.PDF'


def download_report_pdf(ts_code, company_name, report_title, url):
    """
    下载财报 PDF 到本地知识库

    Args:
        ts_code: 股票代码
        company_name: 公司名称
        report_title: 公告标题
        url: PDF 直接下载链接

    Returns:
        str: 下载后的文件路径，失败返回 None
    """
    company_dir = f"{KB_BASE}/stocks/{company_name}_{ts_code}/reports"
    os.makedirs(company_dir, exist_ok=True)

    filename = f"{company_name}_{report_title.replace('/', '_').replace(':', '')}.pdf"
    filepath = os.path.join(company_dir, filename)

    try:
        response = requests.get(url, timeout=120, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        if response.status_code == 200 and response.content[:5] == b'%PDF-':
            with open(filepath, 'wb') as f:
                f.write(response.content)
            size_mb = len(response.content) / 1024 / 1024
            print(f"✓ 下载成功: {filepath} ({size_mb:.2f} MB)")
            return filepath
        else:
            print(f"✗ 下载失败，状态码: {response.status_code}，内容非PDF格式")
    except Exception as e:
        print(f"✗ 下载出错: {e}")

    return None


def get_and_download_report(ts_code, name, report_type='annual', start_date=None, end_date=None):
    """
    获取并下载公司财报

    Args:
        ts_code: 股票代码，如 '300750.SZ'
        name: 公司名称，如 '宁德时代'
        report_type: 贡报类型 ('annual', 'semiannual', 'quarterly')
        start_date: 公告开始日期 (YYYYMMDD)
        end_date: 公告结束日期 (YYYYMMDD)

    Returns:
        dict: {'status': 'success/failed/not_found', 'title': ..., 'date': ..., 'filepath': ...}
    """
    df = get_financial_reports(ts_code, report_type=report_type, start_date=start_date, end_date=end_date)

    if df is None or len(df) == 0:
        return {'status': 'not_found', 'message': f'在公告时间{start_date}-{end_date}之内未找到{report_type}报告'}

    best = df.iloc[0]
    best_title = best['title']

    # 从详情页 URL 构建 PDF 直链
    pdf_url = detail_url_to_pdf_url(best['url'])

    if pdf_url is None:
        print(f"✗ 无法从URL提取PDF参数: {best['url']}")
        return {'status': 'failed', 'title': best_title, 'date': best['ann_date'],
                'url': best['url'], 'filepath': None, 'message': 'URL中缺少announcementId或announcementTime'}

    filepath = download_report_pdf(ts_code, name, best_title, pdf_url)

    return {
        'status': 'success' if filepath else 'failed',
        'title': best_title,
        'date': best['ann_date'],
        'url': pdf_url,
        'filepath': filepath
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("stock_code", help="stock code")
    parser.add_argument("company_name", help="company name")
    parser.add_argument("report_type", default=None, help="report type: annual, semiannual, quarterly", choices=["annual", "semiannual", "quarterly"])
    parser.add_argument("start_date", default=f"{datetime.now().year}0101", help="announcement start date")
    parser.add_argument("end_date", default=f"{datetime.now().year}1231", help="announcement end date")
    args = parser.parse_args()

    if not args.stock_code:
        print(f"Error: stock code not found: {args.stock_code}")
        sys.exit(1)
    elif not args.company_name:
        print(f"Error: company name not found: {args.company_name}")
        sys.exit(1)

    result = get_and_download_report(args.stock_code, args.company_name, args.report_type, args.start_date, args.end_date)
    print(f"状态: {result['status']}") # 'success' / 'failed' / 'not_found'
    if result['status'] == 'success':
        print(f"报告: {result['title']}")  # 报告标题
        print(f"日期: {result['date']}")  # 公告日期
        print(f"文件: {result['filepath']}")  # 本地文件路径