#!/usr/bin/env python3
"""更新ETF配置"""
import sqlite3
import sys
import json

def update_etf_config(code, new_code=None, name=None, market=None, is_active=None):
    conn = sqlite3.connect('/workspace/projects/server/database.sqlite')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    updates = []
    params = []
    if new_code:
        updates.append('code = ?')
        params.append(new_code)
    if name:
        updates.append('name = ?')
        params.append(name)
    if market:
        updates.append('market = ?')
        params.append(market)
    if is_active is not None:
        updates.append('isActive = ?')
        params.append(is_active)
    
    if updates:
        params.append(code)
        sql = f"UPDATE etf_config SET {', '.join(updates)} WHERE code = ?"
        cursor.execute(sql, params)
        conn.commit()
    
    cursor.execute('SELECT * FROM etf_config WHERE code = ?', (new_code if new_code else code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

if __name__ == '__main__':
    code = sys.argv[1].strip('"')
    new_code = sys.argv[2].strip('"') if sys.argv[2] != 'null' else None
    name = sys.argv[3].strip('"') if sys.argv[3] != 'null' else None
    market = sys.argv[4].strip('"') if sys.argv[4] != 'null' else None
    is_active = bool(int(sys.argv[5])) if sys.argv[5] != 'null' else None
    
    result = update_etf_config(code, new_code, name, market, is_active)
    print(json.dumps(result))
