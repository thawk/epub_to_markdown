# -*- coding: utf-8 -*- 

import os
import re
import argparse
import logging
from pathlib import Path
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
import html2text

def _process_chapter(chapter_link, soup, image_map):
    """
    辅助函数，处理单个章节的HTML内容，替换图片路径并进行去重。
    """
    # 替换图片路径
    for img_tag in soup.find_all('img'):
        original_src = img_tag.get('src')
        if original_src:
            # 路径规范化，处理 'Text/../Images/cover.jpg' 这样的情况
            absolute_src = os.path.normpath(os.path.join(os.path.dirname(chapter_link.href), original_src))
            if absolute_src in image_map:
                img_tag['src'] = str(image_map[absolute_src].as_posix())

    # 如果章节标题和正文中的第一个标题几乎一样，则删除正文中的标题
    first_heading = soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    if first_heading:
        chapter_title_norm = chapter_link.title.strip().lower()
        heading_text_norm = first_heading.get_text().strip().lower()
        if chapter_title_norm in heading_text_norm or heading_text_norm in chapter_title_norm:
            logging.debug(f"移除与章节标题 '{chapter_link.title}' 重复的 HTML 标题: '{first_heading.get_text().strip()}'")
            first_heading.decompose()
    
    return soup


def _recursive_add_toc(toc_items, level, markdown_content, href_map, image_map, book_title):
    """
    递归处理目录树，生成有层次的Markdown内容。
    """
    h = html2text.HTML2Text()
    h.body_width = 0

    for item in toc_items:
        if isinstance(item, epub.Link):
            # 这是叶子节点，一个实际的章节
            href_clean = item.href.split('#')[0]
            if href_clean in href_map:
                doc_item = href_map[href_clean]

                # 只有当章节标题不与书名相同时，才添加标题
                if item.title.strip().lower() != book_title.strip().lower():
                    heading = '#' * level
                    markdown_content.append(f"{heading} {item.title}\n")
                    logging.info(f"  - 正在处理 {level} 级章节: {item.title}")
                
                html_content = doc_item.get_content()
                soup = BeautifulSoup(html_content, 'html.parser')

                # 处理HTML内容（图片、去重）
                processed_soup = _process_chapter(item, soup, image_map)
                
                # 转换为Markdown并添加
                md = h.handle(str(processed_soup))
                markdown_content.append(md)
            else:
                logging.warning(f"在目录中找到但在 EPUB 中找不到链接: {item.href}")

        elif isinstance(item, (list, tuple)):
            # 这是父节点，一个包含子章节的 Section
            section, sub_items = item
            if isinstance(section, epub.Section):
                # 只有当Section标题不与书名相同时，才添加
                if section.title.strip().lower() != book_title.strip().lower():
                    heading = '#' * level
                    markdown_content.append(f"{heading} {section.title}\n")
                    logging.info(f"处理 {level} 级目录 Section: {section.title}")
            
            # 递归处理子项目，级别+1
            _recursive_add_toc(sub_items, level + 1, markdown_content, href_map, image_map, book_title)


def convert_epub_to_markdown(epub_path: Path, output_dir: Path):
    """
    将单个 EPUB 文件转换为一个包含图片和正确章节的 Markdown 文件。
    """
    if not epub_path.exists():
        logging.error(f"文件不存在: {epub_path}")
        return

    try:
        book = epub.read_epub(epub_path)
    except Exception as e:
        logging.error(f"无法读取 EPUB 文件 '{epub_path.name}': {e}", exc_info=True)
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
    
    logging.info(f"开始转换书籍: {title}")
    
    # 2. 提取图片并建立路径映射
    image_map = {}
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        image_filename = Path(item.get_name()).name
        image_output_path = images_dir / image_filename
        
        with open(image_output_path, 'wb') as f:
            f.write(item.get_content())
        image_map[item.get_name()] = Path('images') / image_filename

    # 3. 准备转换
    markdown_content = [f"# {title}\n"]
    href_map = {item.get_name(): item for item in book.get_items()}

    # 4. 递归处理整个目录树，从 level 2 (##) 开始
    _recursive_add_toc(book.toc, 2, markdown_content, href_map, image_map, title)

    # 5. 保存 Markdown 文件
    output_filename = book_output_dir / f"{safe_title}.md"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(markdown_content))
    
    logging.info(f"书籍 '{title}' 已成功转换为 Markdown: {output_filename}\n")


def main():
    """主函数，用于命令行执行"""
    parser = argparse.ArgumentParser(description="将一个或多个 EPUB 文件转换为结构良好、包含图片的 Markdown 文件。" )
    parser.add_argument("epub_files", type=str, nargs='+', help="一个或多个 EPUB 文件的路径。" )
    parser.add_argument("-o", "--output_dir", type=str, default="markdown_output", help="存放输出 Markdown 文件的根目录。" )
    parser.add_argument("-v", "--verbose", action="store_true", help="开启详细（DEBUG）日志输出。" )
    
    args = parser.parse_args()

    # 配置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s'
    )

    output_path = Path(args.output_dir)
    output_path.mkdir(exist_ok=True)
    logging.info(f"输出目录: {output_path.resolve()}")

    epub_paths = [Path(f) for f in args.epub_files]

    if not epub_paths:
        logging.warning("未提供任何 EPUB 文件。" )
    else:
        logging.info(f"找到 {len(epub_paths)} 个文件，准备开始转换...")
        for epub_file in epub_paths:
            convert_epub_to_markdown(epub_file, output_path)
        logging.info("所有书籍转换完成！")

if __name__ == '__main__':
    main()