#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any

def get_file_info(file_path: Path, resource_root: Path) -> Dict[str, Any]:
    """获取单个文件的信息，计算相对于resource_root的路径"""
    # 关键修改：计算相对于 data/resource 的路径
    relative_path = file_path.relative_to(resource_root)
    return {
        "name": file_path.name,
        "path": str(relative_path).replace("\\", "/"),
        "size": file_path.stat().st_size
    }

def find_all_files(directory_path: Path, resource_root: Path) -> List[Dict[str, Any]]:
    """递归查找目录下的所有文件"""
    all_files = []
    
    for item in directory_path.rglob("*"):  # 使用 rglob 进行递归遍历
        if item.is_file() and item.suffix not in ['.json', '.md']:  # 排除索引文件和说明文件
            all_files.append(get_file_info(item, resource_root))
    
    return all_files

def generate_directory_json(directory_path: Path, resource_root: Path) -> None:
    """为单个目录生成JSON索引（包含所有子目录文件）"""
    json_data = {
        "name": directory_path.name,
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    # 递归查找该目录下的所有文件
    all_files = find_all_files(directory_path, resource_root)
    
    # 提取该目录下的直接子目录（仅名称，用于展示结构）
    subdirectories = []
    for item in directory_path.iterdir():
        if item.is_dir():
            # 获取相对于resource_root的子目录路径
            rel_path = item.relative_to(resource_root)
            subdirectories.append({
                "name": item.name,
                "path": str(rel_path).replace("\\", "/") + "/"  # 如: "avatar/special/"
            })
    
    json_data["files"] = all_files
    json_data["subdirectories"] = subdirectories
    
    # 写入JSON文件
    json_file = directory_path / f"{directory_path.name}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 已生成 {json_file}，包含 {len(all_files)} 个文件")

def generate_resource_json(resource_root: Path) -> None:
    """生成顶层resource.json"""
    directories = []
    
    for item in resource_root.iterdir():
        if item.is_dir():
            directories.append(item.name)
    
    resource_data = {
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "directories": sorted(directories)
    }
    
    resource_json = resource_root / "resource.json"
    with open(resource_json, 'w', encoding='utf-8') as f:
        json.dump(resource_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 已生成: {resource_json}")

def main():
    repo_root = Path(__file__).parent.parent.parent
    resource_root = repo_root / "data" / "resource"
    
    if not resource_root.exists():
        print("❌ 资源目录不存在")
        return
    
    print(f"开始为 {resource_root} 生成完整的JSON索引...")
    
    # 为每个一级目录生成JSON（会递归包含子目录文件）
    for item in resource_root.iterdir():
        if item.is_dir():
            generate_directory_json(item, resource_root)
    
    # 生成顶层索引
    generate_resource_json(resource_root)
    
    # 统计总文件数
    total_files = 0
    for item in resource_root.iterdir():
        if item.is_dir():
            json_file = item / f"{item.name}.json"
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total_files += len(data.get("files", []))
    
    print(f"✅ JSON索引生成完成！总计索引 {total_files} 个文件")

if __name__ == "__main__":
    main()