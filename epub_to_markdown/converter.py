# -*- coding: utf-8 -*-

import os
import re
import argparse
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup
import html2text

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

    safe_title = re.sub(r'[\\/*?:\":<>|]', "", title)
    book_output_dir = output_dir / safe_title
    images_dir = book_output_dir / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"开始转换书籍: {title}")

    # 2. 提取图片并建立路径映射
    image_map = {}
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        image_filename = Path(item.get_name()).name
        image_output_path = images_dir / image_filename
        
        # 保存图片文件
        with open(image_output_path, 'wb') as f:
            f.write(item.get_content())
            
        # 记录原始路径到新路径的映射
        image_map[item.get_name()] = Path('images') / image_filename

    # 3. 转换文档内容
    markdown_content = [f"# {title}\n"]
    h = html2text.HTML2Text()
    h.body_width = 0

    # 建立一个从 href 到 item 的映射，便于查找
    href_map = {item.get_name(): item for item in book.get_items()}

    # 4. 按目录顺序处理章节
    for item in book.toc:
        if isinstance(item, epub.Link):
            # item.href 可能包含片段标识符 (e.g., 'chap1.xhtml#section1')
            href_clean = item.href.split('#')[0]
            if href_clean in href_map:
                doc_item = href_map[href_clean]
                print(f"  - 正在处理章节: {item.title}")
                markdown_content.append(f"## {item.title}\n")
                
                # 读取 HTML 并用 BeautifulSoup 解析
                html_content = doc_item.get_content()
                soup = BeautifulSoup(html_content, 'html.parser')

                # 替换图片路径
                for img_tag in soup.find_all('img'):
                    original_src = img_tag.get('src')
                    if original_src:
                        # 尝试将相对路径转换为 EPUB 内的绝对路径
                        absolute_src = os.path.normpath(os.path.join(os.path.dirname(doc_item.get_name()), original_src))
                        if absolute_src in image_map:
                            img_tag['src'] = str(image_map[absolute_src])

                # 转换修改后的 HTML 为 Markdown
                md = h.handle(str(soup))
                markdown_content.append(md)
            else:
                print(f"    [警告] 在目录中找到但在 EPUB 中找不到链接: {item.href}")
        # 对于嵌套章节的元组 (epub.Section, [items...])，可以递归处理
        # 为简化起见，本示例只处理顶层章节

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