#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从数据库读取ETF配置并生成配置文件
"""
import sqlite3
import json
import sys
from datetime import datetime

DB_PATH = '/workspace/projects/database.sqlite'
OUTPUT_PATH = '/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts'

def fetch_etf_configs():
    """从数据库读取所有ETF配置"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT code, market, name, status, created_at
        FROM etf_config
        WHERE status = 'active'
        ORDER BY created_at ASC
    ''')

    configs = []
    for row in cursor.fetchall():
        configs.append({
            'code': row[0],
            'market': row[1],
            'name': row[2],
            'status': row[3],
        })

    conn.close()
    return configs

def generate_config_file(etf_configs):
    """生成TypeScript配置文件"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    header = f"""// ETF真实数据配置文件
// 自动生成时间: {timestamp}
// 来源: 数据库

export const REAL_ETF_DATA = {{
"""

    # 生成每个ETF的配置
    etf_configs_str = ""
    for etf in etf_configs:
        etf_configs_str += f"""  '{etf['code']}': {{
    market: '{etf['market']}',
    name: '{etf['name']}',
    status: '{etf['status']}',
    data: []
  }},
"""

    footer = """};

// ETF代码映射
export const ETF_CODES = {
"""

    # 生成ETF代码映射
    mapping_str = ""
    for etf in etf_configs:
        mapping_str += f"  '{etf['code']}': '{etf['name']}',\n"

    footer += mapping_str + "};"

    return header + etf_configs_str + "\n" + footer

def main():
    """主函数"""
    print("开始生成配置文件...")

    try:
        # 从数据库读取配置
        configs = fetch_etf_configs()

        if not configs:
            print("❌ 数据库中没有ETF配置，使用默认配置")
            sys.exit(1)

        print(f"✅ 从数据库读取到 {len(configs)} 个ETF配置")
        for config in configs:
            print(f"  - {config['code']}: {config['name']} ({config['market']})")

        # 生成配置文件
        content = generate_config_file(configs)

        # 写入文件
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ 配置文件已生成: {OUTPUT_PATH}")

    except Exception as e:
        print(f"❌ 生成配置文件失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
