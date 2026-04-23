#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除ETF配置
"""
import sqlite3
import json
import sys

DB_PATH = '/workspace/projects/server/database.sqlite'

def delete_etf_config(id):
    """删除ETF配置"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM etf_config WHERE id = ?', (int(id),))

        conn.commit()
        conn.close()

        return {'message': '删除成功'}
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    id = sys.argv[1] if len(sys.argv) > 1 else ''
    result = delete_etf_config(id)
    if result:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({'message': '删除失败'}, ensure_ascii=False))
