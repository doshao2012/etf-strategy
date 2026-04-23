#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取单个ETF配置
"""
import sqlite3
import json
import sys

DB_PATH = '/workspace/projects/server/database.sqlite'

def get_etf_config(id):
    """获取单个ETF配置"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, code, market, name, isActive
            FROM etf_config
            WHERE id = ?
        ''', (int(id),))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'code': row[1],
                'market': row[2],
                'name': row[3],
                'isActive': bool(row[4])
            }
        return None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    id = sys.argv[1] if len(sys.argv) > 1 else ''
    result = get_etf_config(id)
    if result:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({'message': '配置不存在'}, ensure_ascii=False))
