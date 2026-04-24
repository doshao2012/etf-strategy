#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从数据库读取ETF配置
"""
import sqlite3
import json
import sys

DB_PATH = '/app/server/database.sqlite'

def get_etf_configs():
    """从数据库读取所有启用的ETF配置"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT code, market, name
            FROM etf_config
            WHERE isActive = 1
            ORDER BY createdAt ASC
        ''')

        configs = []
        for row in cursor.fetchall():
            configs.append({
                'code': row[0],
                'market': '0' if row[1] == 'sz' else '1',
                'name': row[2],
            })

        conn.close()
        return configs
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []

if __name__ == '__main__':
    configs = get_etf_configs()
    print(json.dumps(configs, ensure_ascii=False))
