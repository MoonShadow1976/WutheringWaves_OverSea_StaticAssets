#!/usr/bin/env python3
"""
为 WutheringWaves_OverSea_StaticAssets 仓库生成目录索引页。
此脚本会递归地为 data/resource 下的每个子目录创建 index.html 文件。
"""
import os
import time
from pathlib import Path
from urllib.parse import quote

def generate_index_for_directory(directory_path: Path, root_path: Path):
    """为指定目录生成 index.html"""
    # 获取目录下的所有条目，排除 index.html 本身和隐藏文件
    try:
        entries = sorted([e for e in directory_path.iterdir() 
                         if e.name != 'index.html' and not e.name.startswith('.')])
    except (PermissionError, OSError):
        return
    
    # 计算相对于根资源目录的路径，用于显示标题
    relative_path = directory_path.relative_to(root_path)
    
    html_content = []
    html_content.append('<!DOCTYPE html>')
    html_content.append('<html lang="zh-CN">')
    html_content.append('<head>')
    html_content.append('    <meta charset="UTF-8">')
    html_content.append(f'    <title>索引: /{relative_path}</title>')
    html_content.append('    <style>')
    html_content.append('        body { font-family: -apple-system, sans-serif; margin: 2em; }')
    html_content.append('        h1 { color: #333; border-bottom: 1px solid #eee; }')
    html_content.append('        ul { list-style: none; padding-left: 0; }')
    html_content.append('        li { margin: 0.5em 0; }')
    html_content.append('        a { text-decoration: none; color: #0366d6; }')
    html_content.append('        a:hover { text-decoration: underline; }')
    html_content.append('        .dir::before { content: "📁 "; }')
    html_content.append('        .file::before { content: "📄 "; }')
    html_content.append('        .size { color: #666; font-size: 0.9em; margin-left: 1em; }')
    html_content.append('        .footer { margin-top: 2em; color: #888; font-size: 0.9em; }')
    html_content.append('    </style>')
    html_content.append('</head>')
    html_content.append('<body>')
    html_content.append(f'    <h1>索引 /{relative_path}</h1>')
    html_content.append('    <ul>')
    
    # 如果不是根目录，添加上级目录链接
    if directory_path != root_path:
        html_content.append(f'        <li class="dir"><a href="../index.html">../ (上级目录)</a></li>')
    
    # 遍历目录条目
    for entry in entries:
        display_name = entry.name
        encoded_name = quote(entry.name)  # 对URL中的特殊字符进行编码
        is_dir = entry.is_dir()
        
        if is_dir:
            link_href = f'{encoded_name}/index.html'
            size_text = '[目录]'
            css_class = 'dir'
        else:
            link_href = encoded_name
            try:
                size_bytes = entry.stat().st_size
                if size_bytes < 1024:
                    size_text = f'{size_bytes} B'
                elif size_bytes < 1024 * 1024:
                    size_text = f'{size_bytes / 1024:.1f} KB'
                else:
                    size_text = f'{size_bytes / (1024 * 1024):.1f} MB'
            except OSError:
                size_text = '未知大小'
            css_class = 'file'
        
        html_content.append(f'        <li class="{css_class}">')
        html_content.append(f'            <a href="{link_href}">{display_name}</a>')
        html_content.append(f'            <span class="size">{size_text}</span>')
        html_content.append('        </li>')
    
    html_content.append('    </ul>')
    html_content.append(f'    <div class="footer">')
    html_content.append(f'        自动生成于 {time.strftime("%Y-%m-%d %H:%M:%S")}')
    html_content.append('    </div>')
    html_content.append('</body>')
    html_content.append('</html>')
    
    # 写入 index.html 文件
    index_file = directory_path / 'index.html'
    index_file.write_text('\n'.join(html_content), encoding='utf-8')
    print(f'已生成: {index_file}')

def main():
    """主函数：递归生成索引"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    resource_root = repo_root / 'data' / 'resource'
    
    if not resource_root.exists():
        print(f"错误：资源目录不存在 - {resource_root}")
        return
    
    print(f"开始为资源目录生成索引: {resource_root}")
    
    # 使用 os.walk 遍历所有子目录（包括根目录）
    for dirpath, dirnames, filenames in os.walk(resource_root):
        dir_path = Path(dirpath)
        generate_index_for_directory(dir_path, resource_root)
    
    print("索引生成完成！")

if __name__ == '__main__':
    main()