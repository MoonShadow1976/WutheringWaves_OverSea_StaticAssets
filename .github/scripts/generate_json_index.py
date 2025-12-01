#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any

def get_file_info(file_path: Path, base_path: Path) -> Dict[str, Any]:
    """获取单个文件的信息"""
    relative_path = file_path.relative_to(base_path)
    return {
        "name": file_path.name,
        "path": str(relative_path).replace("\\", "/"),
        "size": file_path.stat().st_size
    }

def generate_directory_json(directory_path: Path, resource_root: Path) -> None:
    """为单个目录生成JSON索引"""
    json_data = {
        "name": directory_path.name,
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    files = []
    subdirectories = []
    
    # 遍历目录内容（仅一级）
    for item in directory_path.iterdir():
        if item.is_file() and item.name != f"{directory_path.name}.json":
            files.append(get_file_info(item, resource_root.parent))
        elif item.is_dir():
            # 只记录二级目录的存在，不深入索引
            subdirectories.append({
                "name": item.name,
                "path": f"{directory_path.name}/{item.name}/"
            })
    
    json_data["files"] = files
    json_data["subdirectories"] = subdirectories
    
    # 写入JSON文件
    json_file = directory_path / f"{directory_path.name}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 已生成: {json_file}")

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
    
    print(f"开始为 {resource_root} 生成JSON索引...")
    
    # 为每个一级目录生成JSON
    for item in resource_root.iterdir():
        if item.is_dir():
            generate_directory_json(item, resource_root)
    
    # 生成顶层索引
    generate_resource_json(resource_root)
    
    print("✅ JSON索引生成完成！")

if __name__ == "__main__":
    main()