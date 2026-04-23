#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从数据库读取ETF配置并获取市场数据，生成配置文件
"""
import sys
import sqlite3
import requests
import json
import re
from datetime import datetime, timedelta

DB_PATH = '/workspace/projects/server/database.sqlite'
CONFIG_OUTPUT_PATH = '/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts'

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
                'market': row[1],
                'name': row[2],
            })

        conn.close()
        return configs
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []

def get_realtime(market, code):
    """从腾讯财经获取实时价格"""
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text

        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None

        fields = match.group(1).split('~')
        # 转换日期格式：YYYYMMDDHHMMSS -> YYYY-MM-DD
        raw_date = fields[30] if len(fields) > 30 else datetime.now().strftime('%Y%m%d%H%M%S')
        if len(raw_date) >= 8:
            formatted_date = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        else:
            formatted_date = datetime.now().strftime('%Y-%m-%d')

        return {
            'current': float(fields[3]) if fields[3] else 0,
            'pre_close': float(fields[4]) if fields[4] else 0,
            'date': formatted_date,
        }
    except Exception as e:
        print(f"获取实时价格失败 {market}{code}: {e}", file=sys.stderr)
        return None

def get_historical_data(market, code, count=26):
    """从新浪财经获取历史K线数据"""
    try:
        # 多取几个数据点，以便删除今天的数据后还有足够的数量
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={count+10}"
        response = requests.get(url, timeout=10)
        data = json.loads(response.text)

        if not data or len(data) == 0:
            return []

        # 转换数据格式，并确保数值类型为float/int
        formatted_data = []
        for item in data:
            formatted_data.append({
                'date': item['day'],
                'open': float(item['open']),
                'high': float(item['high']),
                'low': float(item['low']),
                'close': float(item['close']),
                'volume': int(item['volume']),
            })

        return formatted_data
    except Exception as e:
        print(f"获取历史数据失败 {market}{code}: {e}", file=sys.stderr)
        return []

def generate_config_file():
    """生成配置文件"""
    print("开始从数据库读取ETF配置...")

    etfs = get_etf_configs()

    if not etfs:
        print("错误：未找到任何ETF配置", file=sys.stderr)
        return False

    print(f"找到 {len(etfs)} 个ETF配置")

    print("开始获取市场数据...")

    etf_data_dict = {}

    for etf in etfs:
        print(f"  正在处理 {etf['name']} ({etf['code']})...")

        # 获取历史数据（多取几个，以便删除重叠的数据）
        historical_data = get_historical_data(etf['market'], etf['code'], count=28)

        if len(historical_data) < 25:
            print(f"    警告：{etf['name']} 的历史数据不足25条，跳过", file=sys.stderr)
            continue

        # 获取实时价格
        realtime_data = get_realtime(etf['market'], etf['code'])

        if not realtime_data:
            print(f"    警告：{etf['name']} 无法获取实时价格，跳过", file=sys.stderr)
            continue

        print(f"    历史数据最后一条日期: {historical_data[-1]['date']}")
        print(f"    实时数据日期: {realtime_data['date']}")

        # 如果历史数据最后一条的日期和实时数据日期重叠，则删除历史数据最后一条
        if historical_data[-1]['date'] == realtime_data['date']:
            print(f"    检测到日期重叠，删除历史数据最后一条")
            historical_data = historical_data[:-1]

        # 取最后25个历史数据
        historical_data = historical_data[-25:]
        print(f"    历史数据数量: {len(historical_data)}")

        # 添加实时价格作为第26个数据
        today_data = {
            'date': realtime_data['date'],
            'open': realtime_data['current'],  # 简化处理，使用当前价格作为开盘价
            'high': realtime_data['current'],   # 简化处理，使用当前价格作为最高价
            'low': realtime_data['current'],    # 简化处理，使用当前价格作为最低价
            'close': realtime_data['current'],
            'volume': 0,
        }
        historical_data.append(today_data)

        etf_data_dict[etf['code']] = historical_data
        print(f"    成功获取 {len(historical_data)} 条数据（25条历史 + 1条实时）")

    # 生成配置文件
    config_content = f"""// ETF真实数据配置（自动生成，不要手动修改）
// 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// 数据来源: 腾讯财经（实时价格）+ 新浪财经（历史K线）

export const REAL_ETF_DATA = {{"""

    for code, data in etf_data_dict.items():
        config_content += f"\n    '{code}': {json.dumps(data, ensure_ascii=False)},"
    config_content += "\n};"

    # 写入文件
    with open(CONFIG_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print(f"配置文件已生成: {CONFIG_OUTPUT_PATH}")
    return True

if __name__ == '__main__':
    try:
        success = generate_config_file()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
