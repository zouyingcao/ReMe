#!/usr/bin/env python3
"""
Markdown to Tree Converter
将 markdown 文件转换为可导航的文件树，让 Agent 只读取需要的部分。

适用于 mineru-document-extractor 转换后的 markdown 文件。
"""

import re
import json
import argparse
import logging
import shutil

from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from detect_chapters import (
    parse_markdown_structure,
    get_section_content,
    count_tables,
    count_images,
    create_slug
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 拆分阈值
SUBSECTION_THRESHOLD = 300  # >300行拆出二级标题
SUBSUBSECTION_THRESHOLD = 1000  # >1000行拆出三级标题


def build_tree_structure(sections: List[Dict], content: str) -> List[Dict]:
    """
    构建文件树结构，对于大章节拆分子节点

    Args:
        sections: 解析出的章节列表
        content: markdown 全文内容

    Returns:
        带有子节点信息的章节树
    """
    tree = []
    lines = content.split('\n')

    for section in sections:
        line_count = section['line_end'] - section['line_start'] + 1

        # 判断是否需要拆分子节点
        if line_count > SUBSECTION_THRESHOLD:
            # 查找二级标题作为子节点
            subsections = find_subsections(
                lines,
                section['line_start'],
                section['line_end'],
                level=2
            )

            if subsections:
                # 更新章节信息
                section['children'] = subsections
                section['split'] = True

                # 对于超大章节，进一步拆分三级标题
                if line_count > SUBSUBSECTION_THRESHOLD:
                    for sub in subsections:
                        sub_line_count = sub['line_end'] - sub['line_start'] + 1
                        if sub_line_count > SUBSECTION_THRESHOLD:
                            subsubsections = find_subsections(
                                lines,
                                sub['line_start'],
                                sub['line_end'],
                                level=3
                            )
                            if subsubsections:
                                sub['children'] = subsubsections
                                sub['split'] = True

        tree.append(section)

    return tree


def find_subsections(lines: List[str], start: int, end: int, level: int = 2) -> List[Dict]:
    """
    在指定范围内查找子章节标题

    Args:
        lines: 文件所有行
        start: 起始行号（0-indexed）
        end: 结束行号（0-indexed）
        level: 标题层级（2=二级标题，3=三级标题）

    Returns:
        子章节列表
    """
    subsections = []

    # 标题匹配模式
    if level == 2:
        # 二级标题：# 一、# 二、# 三、
        pattern = re.compile(r'^# [一二三四五六七八九十百]+、')
    elif level == 3:
        # 三级标题：# 1、# 2、# 3、
        pattern = re.compile(r'^# [0-9]+、')
    else:
        return subsections

    # 查找所有匹配的标题行
    title_lines = []
    for i in range(start, end + 1):
        if i < len(lines) and pattern.match(lines[i]):
            title_lines.append(i)

    if not title_lines:
        return subsections

    # 构建子章节信息
    for idx, line_num in enumerate(title_lines):
        title = lines[line_num].strip()
        # 移除 # 符号
        title = re.sub(r'^#\s+', '', title)

        # 计算子章节范围
        sub_start = line_num
        if idx + 1 < len(title_lines):
            sub_end = title_lines[idx + 1] - 1
        else:
            sub_end = end

        # 提取子章节内容
        sub_content = '\n'.join(lines[sub_start:sub_end + 1])

        subsections.append({
            'title': title,
            'line_start': sub_start,
            'line_end': sub_end,
            'line_count': sub_end - sub_start + 1,
            'level': level,
            'children': [],
            'split': False,
            'table_count': count_tables(sub_content),
            'image_count': count_images(sub_content)
        })

    return subsections


def adjust_image_paths(content: str, depth: int = 1) -> str:
    """
    调整 markdown 内容中的图片相对路径

    Args:
        content: markdown 内容
        depth: 目录层级深度
              1 = sections/xx/ (需要 ../../images/, 向上2级)
              2 = sections/xx/subsections/xx/ (需要 ../../../../images/, 向上4级)
              3 = sections/xx/subsections/xx/subsubsections/xx/ (需要 ../../../../../../images/, 向上6级)

    Returns:
        调整后的内容
    """
    # 构建相对路径前缀：
    # depth=1 (section): 向上2级 = ../../images/
    # depth=2 (subsection): 向上4级 = ../../../../images/
    # depth=3 (subsubsection): 向上6级 = ../../../../../../images/
    # 公式：向上级数 = depth * 2
    prefix = "../" * (depth * 2)

    # 替换图片路径：![alt](images/xxx.png) → ![alt](../../images/xxx.png)
    # 匹配 ![...](images/...) 格式
    pattern = re.compile(r'!\[([^\]]*)\]\(images/([^)]+)\)')

    def replace_path(match):
        alt = match.group(1)
        filename = match.group(2)
        return f'![{alt}]({prefix}images/{filename})'

    return pattern.sub(replace_path, content)


def generate_section_files(
    output_dir: Path,
    section: Dict,
    lines: List[str],
    images_dir: Optional[Path] = None,
    section_idx: int = 0
):
    """
    生成单个章节的文件

    Args:
        output_dir: 输出目录
        section: 章节信息
        lines: 文件所有行
        images_dir: 图片目录路径
        section_idx: 章节序号
    """
    slug = create_slug(section['title'])
    section_dir = output_dir / f"{section_idx:02d}-{slug}"
    section_dir.mkdir(parents=True, exist_ok=True)

    # 获取章节内容
    content = '\n'.join(lines[section['line_start']:section['line_end'] + 1])

    # 调整图片路径（section 层级深度为 1）
    content = adjust_image_paths(content, depth=1)

    # 生成 content.md
    content_md = f"# {section['title']}\n\n"
    content_md += f"> 行数: {section['line_count']} · 表格: {section['table_count']} · 图片: {section['image_count']}\n\n"
    content_md += content

    with open(section_dir / "content.md", 'w', encoding='utf-8') as f:
        f.write(content_md)

    # 生成 index.md
    index_md = f"# {section['title']}\n\n"
    index_md += f"- 行数: {section['line_count']}\n"
    index_md += f"- 表格数: {section['table_count']}\n"
    index_md += f"- 图片数: {section['image_count']}\n\n"

    if section.get('children'):
        index_md += "## 子章节\n\n"
        for sub_idx, sub in enumerate(section['children']):
            sub_slug = create_slug(sub['title'])
            index_md += f"- [{sub['title']}](subsections/{sub_idx:02d}-{sub_slug}/index.md) — {sub['line_count']} 行\n"

    index_md += f"\n---\n\n[返回总目录](../../index.md)\n"

    with open(section_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write(index_md)

    # 生成 node.json
    node_json = {
        "id": f"section-{section_idx:02d}",
        "title": section['title'],
        "slug": slug,
        "level": section['level'],
        "line_start": section['line_start'] + 1,  # 1-indexed for user
        "line_end": section['line_end'] + 1,
        "line_count": section['line_count'],
        "table_count": section['table_count'],
        "image_count": section['image_count'],
        "children": [f"subsection-{section_idx:02d}-{i:02d}" for i in range(len(section.get('children', [])))]
    }

    with open(section_dir / "node.json", 'w', encoding='utf-8') as f:
        json.dump(node_json, f, ensure_ascii=False, indent=2)

    # 生成子章节文件
    if section.get('children'):
        subsections_dir = section_dir / "subsections"
        subsections_dir.mkdir(exist_ok=True)

        for sub_idx, sub in enumerate(section['children']):
            generate_subsection_files(
                subsections_dir,
                sub,
                lines,
                section_idx,
                sub_idx
            )


def generate_subsection_files(
    output_dir: Path,
    subsection: Dict,
    lines: List[str],
    parent_idx: int,
    sub_idx: int
):
    """
    生成子章节文件
    """
    slug = create_slug(subsection['title'])
    sub_dir = output_dir / f"{sub_idx:02d}-{slug}"
    sub_dir.mkdir(parents=True, exist_ok=True)

    # 获取内容
    content = '\n'.join(lines[subsection['line_start']:subsection['line_end'] + 1])

    # 调整图片路径（subsection 层级深度为 2）
    content = adjust_image_paths(content, depth=2)

    # 生成 content.md
    content_md = f"# {subsection['title']}\n\n"
    content_md += f"> 行数: {subsection['line_count']} · 表格: {subsection['table_count']} · 图片: {subsection['image_count']}\n\n"
    content_md += content

    with open(sub_dir / "content.md", 'w', encoding='utf-8') as f:
        f.write(content_md)

    # 生成 index.md
    index_md = f"# {subsection['title']}\n\n"
    index_md += f"- 行数: {subsection['line_count']}\n"
    index_md += f"- 表格数: {subsection['table_count']}\n"
    index_md += f"- 图片数: {subsection['image_count']}\n\n"

    if subsection.get('children'):
        index_md += "## 子章节\n\n"
        for ss_idx, ss in enumerate(subsection['children']):
            ss_slug = create_slug(ss['title'])
            index_md += f"- [{ss['title']}](subsubsections/{ss_idx:02d}-{ss_slug}/index.md) — {ss['line_count']} 行\n"

    index_md += f"\n---\n\n[返回上级](../../index.md)\n"

    with open(sub_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write(index_md)

    # 生成 node.json
    node_json = {
        "id": f"subsection-{parent_idx:02d}-{sub_idx:02d}",
        "title": subsection['title'],
        "slug": slug,
        "level": subsection['level'],
        "line_start": subsection['line_start'] + 1,
        "line_end": subsection['line_end'] + 1,
        "line_count": subsection['line_count'],
        "table_count": subsection['table_count'],
        "image_count": subsection['image_count'],
        "children": [f"subsubsection-{parent_idx:02d}-{sub_idx:02d}-{i:02d}" for i in range(len(subsection.get('children', [])))]
    }

    with open(sub_dir / "node.json", 'w', encoding='utf-8') as f:
        json.dump(node_json, f, ensure_ascii=False, indent=2)

    # 生成三级子章节
    if subsection.get('children'):
        subsubsections_dir = sub_dir / "subsubsections"
        subsubsections_dir.mkdir(exist_ok=True)

        for ss_idx, ss in enumerate(subsection['children']):
            generate_subsubsection_files(
                subsubsections_dir,
                ss,
                lines,
                parent_idx,
                sub_idx,
                ss_idx
            )


def generate_subsubsection_files(
    output_dir: Path,
    subsubsection: Dict,
    lines: List[str],
    parent_idx: int,
    sub_idx: int,
    ss_idx: int
):
    """
    生成三级子章节文件
    """
    slug = create_slug(subsubsection['title'])
    ss_dir = output_dir / f"{ss_idx:02d}-{slug}"
    ss_dir.mkdir(parents=True, exist_ok=True)

    content = '\n'.join(lines[subsubsection['line_start']:subsubsection['line_end'] + 1])

    # 调整图片路径（subsubsection 层级深度为 3）
    content = adjust_image_paths(content, depth=3)

    content_md = f"# {subsubsection['title']}\n\n"
    content_md += f"> 行数: {subsubsection['line_count']} · 表格: {subsubsection['table_count']} · 图片: {subsubsection['image_count']}\n\n"
    content_md += content

    with open(ss_dir / "content.md", 'w', encoding='utf-8') as f:
        f.write(content_md)

    index_md = f"# {subsubsection['title']}\n\n"
    index_md += f"- 行数: {subsubsection['line_count']}\n"
    index_md += f"- 表格数: {subsubsection['table_count']}\n"
    index_md += f"- 图片数: {subsubsection['image_count']}\n\n"
    index_md += f"\n---\n\n[返回上级](../../index.md)\n"

    with open(ss_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write(index_md)

    node_json = {
        "id": f"subsubsection-{parent_idx:02d}-{sub_idx:02d}-{ss_idx:02d}",
        "title": subsubsection['title'],
        "slug": slug,
        "level": subsubsection['level'],
        "line_start": subsubsection['line_start'] + 1,
        "line_end": subsubsection['line_end'] + 1,
        "line_count": subsubsection['line_count'],
        "table_count": subsubsection['table_count'],
        "image_count": subsubsection['image_count'],
        "children": []
    }

    with open(ss_dir / "node.json", 'w', encoding='utf-8') as f:
        json.dump(node_json, f, ensure_ascii=False, indent=2)


def generate_root_files(
    output_dir: Path,
    tree: List[Dict],
    lines: List[str],
    md_path: Path,
    images_dir: Optional[Path] = None
):
    """
    生成根目录文件（index.md, AGENTS.md, node.json）
    """
    total_lines = len(lines)

    # 1. index.md
    index_content = f"# {md_path.stem}\n\n"
    index_content += f"**总行数**: {total_lines}\n"
    index_content += f"**章节数**: {len(tree)}\n"
    index_content += f"**处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    index_content += "---\n\n"
    index_content += "## 章节列表\n\n"

    for idx, section in enumerate(tree):
        slug = create_slug(section['title'])
        table_mark = " · 含表格" if section['table_count'] > 0 else ""
        split_mark = " · 已拆分" if section.get('split') else ""

        index_content += f"- [{section['title']}](sections/{idx+1:02d}-{slug}/index.md) — {section['line_count']} 行{table_mark}{split_mark}\n"

        if section.get('children'):
            for sub_idx, sub in enumerate(section['children']):
                sub_slug = create_slug(sub['title'])
                index_content += f"  - [{sub['title']}](sections/{idx+1:02d}-{slug}/subsections/{sub_idx:02d}-{sub_slug}/index.md) — {sub['line_count']} 行\n"

    with open(output_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write(index_content)

    # 2. AGENTS.md
    agents_content = f"# {md_path.stem}\n\n"
    agents_content += "## 如何阅读此文档\n\n"
    agents_content += "这是一个可导航的 Markdown 文件树。\n\n"
    agents_content += "### 从这里开始\n\n"
    agents_content += "1. 阅读 `index.md` 了解文档结构\n"
    agents_content += "2. 根据章节摘要（行数、表格数、图片数）选择要阅读的章节\n"
    agents_content += "3. 进入 `sections/` 目录，读取对应章节的 `content.md`\n\n"
    agents_content += "### 章节导航\n\n"

    for idx, section in enumerate(tree):
        slug = create_slug(section['title'])
        agents_content += f"- [{section['title']}](sections/{idx+1:02d}-{slug}/index.md) — {section['line_count']} 行\n"

    agents_content += f"\n### 元数据\n\n"
    agents_content += f"- 总行数: {total_lines}\n"
    agents_content += f"- 章节数: {len(tree)}\n\n"

    agents_content += "### 选择章节的提示\n\n"
    agents_content += "- **需要详细分析**: 跳过行数较少的章节\n"
    agents_content += "- **需要财务数据**: 查找标题包含\"财务\"的章节\n"
    agents_content += "- **查看图片**: 检查 `image_count > 0` 的章节\n\n"

    agents_content += "### 文件结构\n\n"
    agents_content += "```\n"
    agents_content += f"{md_path.stem}/\n"
    agents_content += "├── index.md        # 章节索引\n"
    agents_content += "├── AGENTS.md       # 本文件\n"
    agents_content += "├── node.json       # 元数据\n"
    agents_content += "├── images/         # 图片目录\n"
    agents_content += "└── sections/       # 各章节\n"
    agents_content += "    ├── 01-章节/\n"
    agents_content += "    │   ├── index.md\n"
    agents_content += "    │   ├── content.md\n"
    agents_content += "    │   └── node.json\n"
    agents_content += "    └── ...\n"
    agents_content += "```\n"

    with open(output_dir / "AGENTS.md", 'w', encoding='utf-8') as f:
        f.write(agents_content)

    # 3. node.json
    root_node = {
        "id": "root",
        "title": md_path.stem,
        "slug": create_slug(md_path.stem),
        "level": 0,
        "line_count": total_lines,
        "children": [f"section-{idx+1:02d}" for idx in range(len(tree))]
    }

    with open(output_dir / "node.json", 'w', encoding='utf-8') as f:
        json.dump(root_node, f, ensure_ascii=False, indent=2)


def build_markdown_tree(md_path: str, output_dir: str):
    """
    将 markdown 文件转换为可导航的文件树

    Args:
        md_path: 输入 markdown 文件路径
        output_dir: 输出目录路径
    """
    md_path = Path(md_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"正在处理: {md_path}")
    logger.info(f"输出目录: {output_dir}")

    # 读取 markdown 文件
    content = md_path.read_text(encoding='utf-8')
    lines = content.split('\n')
    total_lines = len(lines)
    logger.info(f"总行数: {total_lines}")

    # 解析章节结构
    logger.info("正在解析章节结构...")
    sections = parse_markdown_structure(content)

    if not sections:
        logger.warning("未检测到章节标题，将整个文档作为单个节点")
        sections = [{
            'title': '全文',
            'line_start': 0,
            'line_end': total_lines - 1,
            'line_count': total_lines,
            'level': 1,
            'children': [],
            'split': False,
            'table_count': count_tables(content),
            'image_count': count_images(content)
        }]

    logger.info(f"检测到 {len(sections)} 个主章节")

    # 构建文件树（拆分大章节）
    logger.info("正在构建文件树...")
    tree = build_tree_structure(sections, content)

    # 检查图片目录
    images_dir = md_path.parent / "images"
    if images_dir.exists():
        logger.info(f"检测到图片目录: {images_dir}")
        # 复制图片目录到输出位置
        dest_images = output_dir / "images"
        if dest_images.exists():
            shutil.rmtree(dest_images)
        shutil.copytree(images_dir, dest_images)
        logger.info(f"已复制 {len(list(dest_images.iterdir()))} 个图片文件")

    # 生成章节文件
    logger.info("正在生成章节文件...")
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(exist_ok=True)

    for idx, section in enumerate(tree):
        generate_section_files(
            sections_dir,
            section,
            lines,
            images_dir,
            idx + 1
        )

    # 生成根目录文件
    generate_root_files(output_dir, tree, lines, md_path, images_dir)

    logger.info(f"\n✓ 转换完成！")
    logger.info(f"  输出目录: {output_dir}")
    logger.info(f"  章节数: {len(tree)}")

    # 统计拆分情况
    split_count = sum(1 for s in tree if s.get('split'))
    if split_count > 0:
        logger.info(f"  已拆分章节: {split_count}")

    logger.info(f"\n请从 {output_dir / 'index.md'} 或 {output_dir / 'AGENTS.md'} 开始阅读")


def main():
    parser = argparse.ArgumentParser(
        description="将 markdown 文件转换为可导航的文件树"
    )
    parser.add_argument("input", help="输入 markdown 文件路径")
    parser.add_argument("--out", "-o", required=True, help="输出目录")

    args = parser.parse_args()

    build_markdown_tree(args.input, args.out)


if __name__ == "__main__":
    main()