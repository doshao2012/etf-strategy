#!/usr/bin/env python3
"""删除ETF配置"""
import sqlite3
import sys
import json

def delete_etf_config(code):
    conn = sqlite3.connect('/workspace/projects/server/database.sqlite')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM etf_config WHERE code = ?', (code,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

if __name__ == '__main__':
    code = sys.argv[1].strip('"')
    success = delete_etf_config(code)
    print(json.dumps({'success': success}))
