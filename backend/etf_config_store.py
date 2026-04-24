"""
ETF 配置 - JSON 文件存储
"""
import json
import os
from datetime import datetime
from typing import Optional

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "etf_config.json")


def load_configs() -> list:
    """加载所有 ETF 配置"""
    if not os.path.exists(CONFIG_FILE):
        # 默认配置
        default_configs = [
            {"id": 1, "code": "159915", "name": "创业板ETF", "market": "sz", "isActive": True},
            {"id": 2, "code": "518880", "name": "黄金ETF", "market": "sh", "isActive": True},
            {"id": 3, "code": "513100", "name": "纳指ETF", "market": "sh", "isActive": True},
            {"id": 4, "code": "511220", "name": "城投债ETF", "market": "sh", "isActive": True},
            {"id": 5, "code": "588000", "name": "科创50ETF", "market": "sh", "isActive": True},
            {"id": 6, "code": "159985", "name": "豆粕ETF", "market": "sz", "isActive": True},
            {"id": 7, "code": "513260", "name": "恒生科技ETF", "market": "sh", "isActive": True},
            {"id": 8, "code": "588220", "name": "科创100", "market": "sh", "isActive": True},
            {"id": 9, "code": "588230", "name": "科创200", "market": "sh", "isActive": True},
        ]
        save_configs(default_configs)
        return default_configs
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_configs(configs: list):
    """保存所有 ETF 配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


def get_config_by_id(config_id: int) -> Optional[dict]:
    """根据 ID 获取配置"""
    configs = load_configs()
    for config in configs:
        if config["id"] == config_id:
            return config
    return None


def update_config(config_id: int, updates: dict) -> Optional[dict]:
    """更新配置"""
    configs = load_configs()
    for i, config in enumerate(configs):
        if config["id"] == config_id:
            # 更新字段
            if "code" in updates and updates["code"] is not None:
                configs[i]["code"] = updates["code"]
            if "name" in updates and updates["name"] is not None:
                configs[i]["name"] = updates["name"]
            if "market" in updates and updates["market"] is not None:
                configs[i]["market"] = updates["market"]
            if "isActive" in updates and updates["isActive"] is not None:
                configs[i]["isActive"] = updates["isActive"]
            configs[i]["updatedAt"] = datetime.now().isoformat()
            save_configs(configs)
            return configs[i]
    return None


def create_config(config_data: dict) -> dict:
    """创建新配置"""
    configs = load_configs()
    new_id = max([c["id"] for c in configs], default=0) + 1
    new_config = {
        "id": new_id,
        "code": config_data["code"],
        "name": config_data["name"],
        "market": config_data["market"],
        "isActive": config_data.get("isActive", True),
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
    }
    configs.append(new_config)
    save_configs(configs)
    return new_config


def delete_config(config_id: int) -> bool:
    """删除配置"""
    configs = load_configs()
    new_configs = [c for c in configs if c["id"] != config_id]
    if len(new_configs) < len(configs):
        save_configs(new_configs)
        return True
    return False
