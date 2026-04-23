#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新ETF配置
"""
import sqlite3
import json
import sys

DB_PATH = '/workspace/projects/server/database.sqlite'

def update_etf_config(id, code=None, name=None, market=None, is_active=None):
    """更新ETF配置"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        updates = []
        values = []

        if code and code != 'null':
            updates.append('code = ?')
            values.append(code)
        if name and name != 'null':
            updates.append('name = ?')
            values.append(name)
        if market and market != 'null':
            updates.append('market = ?')
            values.append(market)
        if is_active is not None and is_active != 'null':
            updates.append('isActive = ?')
            values.append(int(is_active))

        if not updates:
            return None

        updates.append('updatedAt = datetime("now")')
        values.append(int(id))

        sql = f'UPDATE etf_config SET {", ".join(updates)} WHERE id = ?'
        cursor.execute(sql, values)

        conn.commit()
        conn.close()

        return {'message': '更新成功'}
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None

if __name__ == '__main__':
    id = sys.argv[1] if len(sys.argv) > 1 else ''
    code = sys.argv[2] if len(sys.argv) > 2 else None
    name = sys.argv[3] if len(sys.argv) > 3 else None
    market = sys.argv[4] if len(sys.argv) > 4 else None
    is_active = sys.argv[5] if len(sys.argv) > 5 else None

    result = update_etf_config(id, code, name, market, is_active)
    if result:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({'message': '更新失败'}, ensure_ascii=False))
