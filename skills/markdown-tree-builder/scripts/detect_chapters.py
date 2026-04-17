#!/usr/bin/env python3
"""
Markdown Chapter Detection
解析 markdown 文件的章节结构，识别标题层级。

章节标题模式：
- Level 1: # 第X节 XXX （主章节）
- Level 2: # 一、XXX （二级标题）
- Level 3: # 1、XXX （三级标题）
- Special: # 致股东的信 等特殊章节
"""

import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# 标题匹配模式
CHAPTER_PATTERNS = {
    # 主章节：第一节、第二节...
    'level_1': re.compile(r'^# 第([一二三四五六七八九十]+)[节章]\s+(.+)$'),
    # 二级标题：一、二、三...
    'level_2': re.compile(r'^# [一二三四五六七八九十百]+、(.+)$'),
    # 三级标题：1、2、3...
    'level_3': re.compile(r'^# [0-9]+、(.+)$'),
}

# 特殊章节标题（需要单独处理）
SPECIAL_CHAPTERS = ['致股东的信']

# 需要忽略的标题（不是真正的章节）
IGNORE_PATTERNS = [
    re.compile(r'^# CATL$'),
    re.compile(r'^# 宁德时代'),
    re.compile(r'^# 202[0-9] 年年度报告'),
    re.compile(r'^# 目录$'),
    re.compile(r'^# 备查文件目录$'),
    re.compile(r'^# 释义$'),
]


def create_slug(title: str) -> str:
    """
    创建 URL 友好的 slug

    Args:
        title: 章节标题

    Returns:
        slug 字符串
    """
    # 移除章节序号前缀
    slug = re.sub(r'^第[一二三四五六七八九十]+[节章篇部]\s+', '', title)
    slug = re.sub(r'^[一二三四五六七八九十百]+[、]\s*', '', slug)
    slug = re.sub(r'^[0-9]+[、]\s*', '', slug)

    # 替换特殊字符
    slug = re.sub(r'[^\w\u4e00-\u9fff]+', '-', slug)
    slug = slug.strip('-').lower()

    # 限制长度
    return slug[:50] if len(slug) > 50 else slug


def count_tables(content: str) -> int:
    """
    计算内容中的表格数量

    Args:
        content: markdown 内容

    Returns:
        表格数量
    """
    return len(re.findall(r'<table>', content))


def count_images(content: str) -> int:
    """
    计算内容中的图片数量

    Args:
        content: markdown 内容

    Returns:
        图片数量
    """
    return len(re.findall(r'!\[.*?\]\(images/', content))


def parse_markdown_structure(content: str) -> List[Dict]:
    """
    解析 markdown 文件的章节结构

    Args:
        content: markdown 全文内容

    Returns:
        章节列表，每个章节包含：
        - title: 章节标题
        - line_start: 起始行号（0-indexed）
        - line_end: 结束行号（0-indexed）
        - line_count: 行数
        - level: 标题层级（1=主章节，2=二级，3=三级）
        - children: 子章节列表
        - split: 是否已拆分
        - table_count: 表格数量
        - image_count: 图片数量
    """
    lines = content.split('\n')
    sections = []

    # 找出所有主章节标题
    chapter_positions = []

    # 中文数字映射
    num_map = {'一': '一', '二': '二', '三': '三', '四': '四', '五': '五',
               '六': '六', '七': '七', '八': '八', '九': '九', '十': '十'}

    for i, line in enumerate(lines):
        line = line.strip()

        # 检查是否需要忽略
        should_ignore = False
        for pattern in IGNORE_PATTERNS:
            if pattern.match(line):
                should_ignore = True
                break
        if should_ignore:
            continue

        # 检查是否是主章节
        match = CHAPTER_PATTERNS['level_1'].match(line)
        if match:
            chapter_num = match.group(1)  # 中文数字：一、二、三...
            title_content = match.group(2).strip()
            chapter_positions.append({
                'line': i,
                'title': f"第{chapter_num}节 {title_content}",
                'raw_title': line
            })
            continue

        # 检查是否是特殊章节（如"致股东的信"）
        for special in SPECIAL_CHAPTERS:
            if line == f'# {special}':
                chapter_positions.append({
                    'line': i,
                    'title': special,
                    'raw_title': line,
                    'special': True
                })
                break

    if not chapter_positions:
        logger.warning("未检测到主章节标题")
        return []

    # 构建章节信息
    for idx, pos in enumerate(chapter_positions):
        line_start = pos['line']
        line_end = chapter_positions[idx + 1]['line'] - 1 if idx + 1 < len(chapter_positions) else len(lines) - 1

        # 提取章节内容
        section_content = '\n'.join(lines[line_start:line_end + 1])

        section = {
            'title': pos['title'],
            'line_start': line_start,
            'line_end': line_end,
            'line_count': line_end - line_start + 1,
            'level': 1,
            'children': [],
            'split': False,
            'table_count': count_tables(section_content),
            'image_count': count_images(section_content),
            'special': pos.get('special', False)
        }

        sections.append(section)

    logger.info(f"解析完成: {len(sections)} 个主章节")
    for s in sections[:5]:
        logger.info(f"  {s['title']}: {s['line_count']} 行 (p.{s['line_start']+1}-{s['line_end']+1})")

    return sections


def get_section_content(content: str, section: Dict) -> str:
    """
    获取指定章节的内容

    Args:
        content: markdown 全文
        section: 章节信息

    Returns:
        章节内容字符串
    """
    lines = content.split('\n')
    return '\n'.join(lines[section['line_start']:section['line_end'] + 1])


def find_all_titles(content: str, level: int = None) -> List[Dict]:
    """
    查找所有标题

    Args:
        content: markdown 内容
        level: 标题层级（None=全部，1/2/3=指定层级）

    Returns:
        标题列表
    """
    lines = content.split('\n')
    titles = []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line.startswith('#'):
            continue

        # 移除 # 符号
        clean_title = re.sub(r'^#+\s+', '', line)

        # 判断层级
        title_level = None
        if CHAPTER_PATTERNS['level_1'].match(line):
            title_level = 1
        elif CHAPTER_PATTERNS['level_2'].match(line):
            title_level = 2
        elif CHAPTER_PATTERNS['level_3'].match(line):
            title_level = 3
        elif line.strip() == '# 致股东的信':
            title_level = 0  # 特殊章节

        if title_level is not None:
            if level is None or title_level == level:
                titles.append({
                    'line': i,
                    'title': clean_title,
                    'level': title_level
                })

    return titles


def analyze_document(content: str) -> Dict:
    """
    分析文档结构，返回统计信息

    Args:
        content: markdown 内容

    Returns:
        统计信息字典
    """
    lines = content.split('\n')

    # 统计各层级标题数量
    level_1_count = sum(1 for line in lines if CHAPTER_PATTERNS['level_1'].match(line.strip()))
    level_2_count = sum(1 for line in lines if CHAPTER_PATTERNS['level_2'].match(line.strip()))
    level_3_count = sum(1 for line in lines if CHAPTER_PATTERNS['level_3'].match(line.strip()))

    # 统计表格和图片
    table_count = count_tables(content)
    image_count = count_images(content)

    return {
        'total_lines': len(lines),
        'level_1_count': level_1_count,
        'level_2_count': level_2_count,
        'level_3_count': level_3_count,
        'table_count': table_count,
        'image_count': image_count
    }