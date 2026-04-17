"""
知识库查询模块 - 从本地知识库查询公司数据
"""

import os
import re

KB_BASE = os.getenv('KB_BASE')


def resolve_company_dir(code_or_name):
    """根据股票代码或公司名找到知识库目录"""
    if '.' in code_or_name:
        pattern = f"*_{code_or_name}"
    else:
        pattern = f"{code_or_name}_*"

    stocks_dir = f"{KB_BASE}/stocks"
    if not os.path.exists(stocks_dir):
        return None

    for d in os.listdir(stocks_dir):
        if pattern.replace('*', '') in d:
            return f"{stocks_dir}/{d}"
    return None


def get_company_basic(code_or_name):
    """
    获取公司基础信息
    返回: {'ts_code', 'name', 'industry', 'list_date', 'market'}
    """
    company_dir = resolve_company_dir(code_or_name)
    if not company_dir:
        return None

    basic_file = f"{company_dir}/basic.md"
    if not os.path.exists(basic_file):
        return None

    content = open(basic_file, 'r', encoding='utf-8').read()
    result = {}
    patterns = {
        'ts_code': r'股票代码：([^\n]+)',
        'industry': r'所属行业：([^\n]+)',
        'list_date': r'上市日期：([^\n]+)',
        'market': r'市场类型：([^\n]+)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, content)
        if match:
            result[key] = match.group(1).strip()
    result['name'] = os.path.basename(company_dir).split('_')[0]
    return result


def get_company_profile(code_or_name):
    """
    获取公司档案
    返回: {'core_business', 'segments', 'chain_position', 'assumptions', 'risks'}
    """
    company_dir = resolve_company_dir(code_or_name)
    if not company_dir:
        return None

    profile_file = f"{company_dir}/company_profile.md"
    if not os.path.exists(profile_file):
        return None

    content = open(profile_file, 'r', encoding='utf-8').read()
    result = {}

    # 核心业务
    match = re.search(r'## 核心业务\n([^\n]+)', content)
    if match:
        result['core_business'] = match.group(1).strip()

    # 产业链定位
    match = re.search(r'## 产业链定位\n([^\n]+(?:\n(?!\#)[^\n]+)*)', content)
    if match:
        result['chain_position'] = match.group(1).strip()

    # 业务拆解
    result['segments'] = []
    table_match = re.search(r'## 业务拆解\n\|[^\n]+\n\|[^\n]+\n((?:\|[^\n]+\n)+)', content)
    if table_match:
        for line in table_match.group(1).strip().split('\n'):
            if line.startswith('|'):
                cols = [c.strip() for c in line.split('|')[1:-1]]
                if cols:
                    result['segments'].append({
                        'name': cols[0], 'ratio': cols[1], 'margin': cols[2],
                        'downstream': cols[3], 'upstream': cols[4],
                    })

    # 假设
    result['assumptions'] = []
    match = re.search(r'## 关键假设\n((?:- [^\n]+\n)+)', content)
    if match:
        for line in match.group(1).strip().split('\n'):
            if line.startswith('-'):
                result['assumptions'].append(line[2:].strip())

    # 风险
    result['risks'] = []
    match = re.search(r'## 风险信号\n((?:- [^\n]+\n)+)', content)
    if match:
        for line in match.group(1).strip().split('\n'):
            if line.startswith('-'):
                result['risks'].append(line[2:].strip())

    return result


def get_financial_data(code_or_name):
    """
    获取财务数据
    返回: {'revenue': [...], 'indicators': [...]}
    """
    company_dir = resolve_company_dir(code_or_name)
    if not company_dir:
        return None

    financial_file = f"{company_dir}/financial.md"
    if not os.path.exists(financial_file):
        return None

    content = open(financial_file, 'r', encoding='utf-8').read()
    result = {'revenue': [], 'indicators': []}

    # 营收利润表
    table_match = re.search(r'## 营收利润\n\|[^\n]+\n\|[^\n]+\n((?:\|[^\n]+\n)+)', content)
    if table_match:
        for line in table_match.group(1).strip().split('\n'):
            if line.startswith('|'):
                cols = [c.strip() for c in line.split('|')[1:-1]]
                if cols and cols[0]:
                    result['revenue'].append({
                        'year': cols[0], 'revenue': cols[1], 'revenue_yoy': cols[2],
                        'net_profit': cols[3], 'net_profit_yoy': cols[4],
                    })

    # 财务指标表
    table_match = re.search(r'## 财务指标\n\|[^\n]+\n\|[^\n]+\n((?:\|[^\n]+\n)+)', content)
    if table_match:
        for line in table_match.group(1).strip().split('\n'):
            if line.startswith('|'):
                cols = [c.strip() for c in line.split('|')[1:-1]]
                if cols and cols[0]:
                    result['indicators'].append({
                        'year': cols[0], 'gross_margin': cols[1],
                        'net_margin': cols[2], 'roe': cols[3],
                    })

    return result


def get_pricing_factors(code_or_name):
    """
    获取定价因子清单
    返回: [{'name', 'type', 'mechanism', 'priority'}, ...]
    """
    company_dir = resolve_company_dir(code_or_name)
    if not company_dir:
        return None

    factors_file = f"{company_dir}/pricing_factors.md"
    if not os.path.exists(factors_file):
        return None

    content = open(factors_file, 'r', encoding='utf-8').read()
    result = []

    table_match = re.search(r'\|[^\n]+\n\|[^\n]+\n((?:\|[^\n]+\n)+)', content)
    if table_match:
        for line in table_match.group(1).strip().split('\n'):
            if line.startswith('|'):
                cols = [c.strip() for c in line.split('|')[1:-1]]
                if cols and cols[0]:
                    result.append({
                        'name': cols[0], 'type': cols[1],
                        'mechanism': cols[2], 'priority': cols[3],
                    })

    return result


def get_external_monitor(code_or_name):
    """
    获取外部监控清单
    返回: {'upstream': [...], 'downstream': [...], 'competition': [...]}
    """
    company_dir = resolve_company_dir(code_or_name)
    if not company_dir:
        return None

    monitor_file = f"{company_dir}/external_monitor.md"
    if not os.path.exists(monitor_file):
        return None

    content = open(monitor_file, 'r', encoding='utf-8').read()
    result = {'upstream': [], 'downstream': [], 'competition': []}

    section_names = {'upstream': '上游材料价格', 'downstream': '下游需求指标', 'competition': '竞争格局'}
    for section in ['upstream', 'downstream', 'competition']:
        pattern = f'## {section_names[section]}\n((?:- [^\n]+\n(?:  - [^\n]+\n)*)+)'
        match = re.search(pattern, content)
        if match:
            items = match.group(1).strip().split('\n- ')
            for item in items:
                if not item.strip():
                    continue
                lines = item.strip().split('\n')
                main_line = lines[0]

                entry = {}
                name_match = re.search(r'\*\*([^*]+)\*\*', main_line)
                source_match = re.search(r'数据源：([^(]+)', main_line)
                freq_match = re.search(r'（([^)]+)）', main_line)

                if name_match:
                    entry['name'] = name_match.group(1).strip()
                if source_match:
                    entry['source'] = source_match.group(1).strip()
                if freq_match:
                    entry['frequency'] = freq_match.group(1).strip()

                for subline in lines[1:]:
                    if '预警' in subline:
                        thresh_match = re.search(r'预警：([^\n]+)', subline)
                        if thresh_match:
                            entry['threshold'] = thresh_match.group(1).strip()
                    elif '用途' in subline:
                        purpose_match = re.search(r'用途：([^\n]+)', subline)
                        if purpose_match:
                            entry['purpose'] = purpose_match.group(1).strip()

                if entry:
                    result[section].append(entry)

    return result


def get_company_info(code_or_name, sections=None):
    """
    综合获取公司信息
    sections: ['basic', 'profile', 'financial', 'pricing_factors', 'external_monitor']
    """
    if sections is None:
        sections = ['basic', 'profile', 'financial', 'pricing_factors', 'external_monitor']

    result = {}
    if 'basic' in sections:
        result['basic'] = get_company_basic(code_or_name)
    if 'profile' in sections:
        result['profile'] = get_company_profile(code_or_name)
    if 'financial' in sections:
        result['financial'] = get_financial_data(code_or_name)
    if 'pricing_factors' in sections:
        result['pricing_factors'] = get_pricing_factors(code_or_name)
    if 'external_monitor' in sections:
        result['external_monitor'] = get_external_monitor(code_or_name)

    return result