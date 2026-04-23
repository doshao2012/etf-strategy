#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加ETF配置
"""
import sqlite3
import json
import sys

DB_PATH = '/workspace/projects/server/database.sqlite'

def add_etf_config(code, name, market, is_active=1):
    """添加ETF配置"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO etf_config (code, market, name, isActive, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        ''', (code, market, name, is_active))

        conn.commit()
        config_id = cursor.lastrowid
        conn.close()

        return {
            'id': config_id,
            'code': code,
            'market': market,
            'name': name,
            'isActive': bool(is_active)
        }
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    code = sys.argv[1] if len(sys.argv) > 1 else ''
    name = sys.argv[2] if len(sys.argv) > 2 else ''
    market = sys.argv[3] if len(sys.argv) > 3 else 'sz'
    is_active = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    result = add_etf_config(code, name, market, is_active)
    if result:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({'message': '添加失败'}, ensure_ascii=False))
