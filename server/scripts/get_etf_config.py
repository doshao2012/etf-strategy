#!/usr/bin/env python3
"""获取单个ETF配置"""
import sqlite3
import sys
import json

def get_etf_config(code):
    conn = sqlite3.connect('/workspace/projects/server/database.sqlite')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM etf_config WHERE code = ?', (code,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

if __name__ == '__main__':
    code = sys.argv[1].strip('"')
    config = get_etf_config(code)
    print(json.dumps(config) if config else 'null')
