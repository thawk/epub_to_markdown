import sys
import re
import os
import argparse

def sanitize_filename(name):
    """
    Sanitizes a string to be a valid filename.
    Removes invalid characters and replaces spaces with underscores.
    """
    name = name.strip()
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '_', name)
    return name

def process_chunk_headings(chunk, split_level, relevel, strip_top_heading):
    """
    Processes the headings in a chunk of markdown based on user options.
    """
    if not relevel and not strip_top_heading:
        return chunk.strip()

    lines = chunk.strip().split('\n')

    if strip_top_heading:
        content_to_process = '\n'.join(lines[1:])
        # When stripping the top heading, the next level becomes H1.
        # The shift required is the level of the heading we stripped.
        level_shift = split_level
    else: # just --relevel
        content_to_process = '\n'.join(lines)
        # When just re-leveling, the top heading becomes H1.
        # The shift is the original top level minus 1.
        level_shift = split_level - 1

    if level_shift <= 0:
        return content_to_process

    def heading_replacer(match):
        hashes = match.group(1)
        title = match.group(2)
        current_level = len(hashes)
        new_level = current_level - level_shift
        if new_level < 1:
            new_level = 1
        return '#' * new_level + ' ' + title

    # This regex finds any line that is a markdown heading
    processed_content = re.sub(
        r'^(#+)\s(.*)', heading_replacer, content_to_process, flags=re.MULTILINE
    )
    return processed_content

def split_markdown_file(file_path, level, relevel, strip_top_heading):
    """
    Splits a markdown file by its specified heading level, with options to process headings.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"错误：文件未找到 '{file_path}'")
        return

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = f"{base_name}_split_level_{level}"
    os.makedirs(output_dir, exist_ok=True)
    print(f"文件将保存在目录: '{output_dir}/'")

    heading_pattern = "#" * level
    split_regex = f'(?=^{heading_pattern} )'
    chunks = re.split(split_regex, content, flags=re.MULTILINE)

    file_counter = 0

    intro_content = chunks[0].strip()
    if intro_content:
        intro_filename = os.path.join(output_dir, f"{file_counter:02d}_introduction.md")
        with open(intro_filename, 'w', encoding='utf-8') as f:
            f.write(intro_content)
        print(f"  -> 已创建: {intro_filename}")
        file_counter += 1

    for chunk in chunks[1:]:
        first_line = chunk.split('\n', 1)[0]
        title = first_line.replace(f'{heading_pattern} ', '').strip()
        sanitized_title = sanitize_filename(title)
        if not sanitized_title:
            sanitized_title = "untitled"

        filename = os.path.join(output_dir, f"{file_counter:02d}_{sanitized_title}.md")

        # Process the chunk's headings before writing
        processed_chunk = process_chunk_headings(chunk, level, relevel, strip_top_heading)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(processed_chunk)
        print(f"  -> 已创建: {filename}")
        file_counter += 1

def main():
    """
    Main function to parse command-line arguments and run the splitter.
    """
    parser = argparse.ArgumentParser(
        description="Splits a markdown file into smaller files based on a specified heading level."
    )
    parser.add_argument(
        "file_path",
        metavar="MARKDOWN_FILE",
        help="The path to the markdown file to split."
    )
    parser.add_argument(
        "-l", "--level",
        type=int,
        default=2,
        help="The heading level to split on (e.g., 2 for '##'). Defaults to 2."
    )
    parser.add_argument(
        "--relevel",
        action="store_true",
        help="Re-level headings in output files to start from H1."
    )
    parser.add_argument(
        "--strip-top-heading",
        action="store_true",
        help="Remove the top-level heading from each split file and re-level subsequent headings."
    )

    args = parser.parse_args()

    split_markdown_file(args.file_path, args.level, args.relevel, args.strip_top_heading)

if __name__ == '__main__':
    main()