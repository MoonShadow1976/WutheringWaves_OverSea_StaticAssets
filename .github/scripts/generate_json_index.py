#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any

def get_file_info(file_path: Path, resource_root: Path) -> Dict[str, Any]:
    """获取单个文件的信息，计算相对于resource_root的路径"""
    # 计算相对于 data/resource 的路径
    relative_path = file_path.relative_to(resource_root)
    return {
        "name": file_path.name,
        "path": str(relative_path).replace("\\", "/"),
        "size": file_path.stat().st_size
    }

def find_all_files(directory_path: Path, resource_root: Path) -> List[Dict[str, Any]]:
    """递归查找目录下的所有文件"""
    all_files = []
    # 使用 rglob 递归遍历，但排除JSON文件本身
    for item in directory_path.rglob("*"):
        if item.is_file() and not item.name.endswith('.json'):  # 排除所有JSON文件
            all_files.append(get_file_info(item, resource_root))
    return all_files

def generate_directory_json(directory_path: Path, resource_root: Path) -> None:
    """为单个目录生成JSON索引，并将JSON文件输出到resource_root下"""
    json_data = {
        "name": directory_path.name,
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    # 递归查找该目录下的所有文件
    all_files = find_all_files(directory_path, resource_root)
    
    # 提取该目录下的直接子目录（仅名称）
    subdirectories = []
    for item in directory_path.iterdir():
        if item.is_dir():
            rel_path = item.relative_to(resource_root)
            subdirectories.append({
                "name": item.name,
                "path": str(rel_path).replace("\\", "/") + "/"
            })
    
    json_data["files"] = all_files
    json_data["subdirectories"] = sorted(subdirectories, key=lambda x: x["name"])
    
    # 关键修改：将JSON文件生成到 resource_root (data/resource/) 下，而不是各自的目录里
    json_file = resource_root / f"{directory_path.name}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 已生成: {json_file} (包含 {len(all_files)} 个文件)")

def generate_resource_json(resource_root: Path) -> None:
    """生成顶层资源总索引，放到 data/ 目录下"""
    directories = []
    
    # 获取所有一级目录（排除文件）
    for item in resource_root.iterdir():
        if item.is_dir():
            directories.append(item.name)
    
    resource_data = {
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "directories": sorted(directories),
        "total_index_files": len(directories)  # 索引文件数量
    }
    
    # 关键修改：将resource.json生成到 data/ 目录下（resource_root的父目录）
    resource_json = resource_root.parent / "resource.json"
    with open(resource_json, 'w', encoding='utf-8') as f:
        json.dump(resource_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 已生成顶层索引: {resource_json}")

def main():
    repo_root = Path(__file__).parent.parent.parent
    resource_root = repo_root / "data" / "resource"
    
    if not resource_root.exists():
        print("❌ 资源目录不存在")
        return
    
    print(f"开始为 {resource_root} 生成扁平化JSON索引...")
    print("索引文件将直接放置在 data/resource/ 目录下")
    
    # 为每个一级目录生成JSON（文件会输出到resource_root下）
    for item in resource_root.iterdir():
        if item.is_dir():
            generate_directory_json(item, resource_root)
    
    # 生成顶层索引（文件会输出到data/目录下）
    generate_resource_json(resource_root)
    
    # 统计总文件数
    total_files = 0
    index_files = []
    for json_file in resource_root.glob("*.json"):
        if json_file.name != "resource.json":  # 排除顶层索引（它不在这个目录）
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                file_count = len(data.get("files", []))
                total_files += file_count
                index_files.append(f"{json_file.name}: {file_count} 个文件")
    
    print("\n📊 索引生成统计:")
    for info in sorted(index_files):
        print(f"  {info}")
    print(f"✅ 总计索引 {len(index_files)} 个目录, {total_files} 个文件")
    print(f"📁 索引文件位置: {resource_root}/")
    print(f"📁 顶层索引位置: {resource_root.parent}/resource.json")

if __name__ == "__main__":
    main()