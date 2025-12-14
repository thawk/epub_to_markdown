# -*- coding: utf-8 -*-

import os
import re
import argparse
from pathlib import Path
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
import html2text

def _get_ordered_chapters(toc):
    """
    递归地展平目录结构，返回一个有序的章节链接列表。
    """
    chapters = []
    for item in toc:
        if isinstance(item, epub.Link):
            chapters.append(item)
        elif isinstance(item, (list, tuple)):
            # item 是一个元组，通常包含 (Section, [Sub-items])
            # 我们递归地处理子项目
            chapters.extend(_get_ordered_chapters(item))
    return chapters

def convert_epub_to_markdown(epub_path: Path, output_dir: Path):
    """
    将单个 EPUB 文件转换为一个包含图片和正确章节的 Markdown 文件。

    :param epub_path: EPUB 文件的路径。
    :param output_dir: 输出 Markdown 和相关资源的目录。
    """
    if not epub_path.exists():
        print(f"[错误] 文件不存在: {epub_path}")
        return

    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        print(f"[错误] 无法读取 EPUB 文件 '{epub_path.name}': {e}")
        return

    # 1. 获取书名并创建对应的输出文件夹
    try:
        title = book.get_metadata('DC', 'title')[0][0]
    except IndexError:
        title = epub_path.stem

    safe_title = re.sub(r'[\\/*?:":<>|]', "", title)
    book_output_dir = output_dir / safe_title
    images_dir = book_output_dir / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"开始转换书籍: {title}")

    # 2. 提取图片并建立路径映射
    image_map = {}
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        image_filename = Path(item.get_name()).name
        image_output_path = images_dir / image_filename
        
        with open(image_output_path, 'wb') as f:
            f.write(item.get_content())
            
        image_map[item.get_name()] = Path('images') / image_filename

    # 3. 转换文档内容
    markdown_content = [f"# {title}\n"]
    h = html2text.HTML2Text()
    h.body_width = 0

    href_map = {item.get_name(): item for item in book.get_items()}

    # 4. 按目录顺序处理所有章节（包括嵌套章节）
    ordered_chapters = _get_ordered_chapters(book.toc)
    
    for chapter_link in ordered_chapters:
        href_clean = chapter_link.href.split('#')[0]
        if href_clean in href_map:
            doc_item = href_map[href_clean]
            print(f"  - 正在处理章节: {chapter_link.title}")
            
            html_content = doc_item.get_content()
            soup = BeautifulSoup(html_content, 'html.parser')

            # --- 智能去重逻辑 ---
            # 如果章节标题和正文中的第一个标题几乎一样，则删除正文中的标题
            first_heading = soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if first_heading:
                # 使用简单的字符串包含检查，忽略大小写和空白
                chapter_title_norm = chapter_link.title.strip().lower()
                heading_text_norm = first_heading.get_text().strip().lower()
                if chapter_title_norm in heading_text_norm or heading_text_norm in chapter_title_norm:
                    print(f"    [信息] 移除与章节标题 '{chapter_link.title}' 重复的 HTML 标题: '{first_heading.get_text().strip()}'")
                    first_heading.decompose()
            # --- 结束去重逻辑 ---
            
            # 只有在标题不与书名重复时才添加
            if chapter_link.title.strip().lower() != title.strip().lower():
                markdown_content.append(f"## {chapter_link.title}\n")

            for img_tag in soup.find_all('img'):
                original_src = img_tag.get('src')
                if original_src:
                    absolute_src = os.path.normpath(os.path.join(os.path.dirname(doc_item.get_name()), original_src))
                    if absolute_src in image_map:
                        img_tag['src'] = str(image_map[absolute_src].as_posix())

            md = h.handle(str(soup))
            markdown_content.append(md)
        else:
            print(f"    [警告] 在目录中找到但在 EPUB 中找不到链接: {chapter_link.href}")

    # 5. 保存 Markdown 文件
    output_filename = book_output_dir / f"{safe_title}.md"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(markdown_content))
    
    print(f"书籍 '{title}' 已成功转换为 Markdown: {output_filename}\n")


def main():
    """主函数，用于命令行执行"""
    parser = argparse.ArgumentParser(description="将一个或多个 EPUB 文件转换为结构良好、包含图片的 Markdown 文件。")
    parser.add_argument("epub_files", type=str, nargs='+', help="一个或多个 EPUB 文件的路径。")
    parser.add_argument("-o", "--output_dir", type=str, default="markdown_output", help="存放输出 Markdown 文件的根目录。")
    
    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(exist_ok=True)
    print(f"输出目录: {output_path.resolve()}")

    epub_paths = [Path(f) for f in args.epub_files]

    if not epub_paths:
        print("未提供任何 EPUB 文件。" )
    else:
        print(f"找到 {len(epub_paths)} 个文件，准备开始转换...")
        for epub_file in epub_paths:
            convert_epub_to_markdown(epub_file, output_path)
        print("所有书籍转换完成！")

if __name__ == '__main__':
    main()