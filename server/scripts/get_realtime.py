#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取当前实时价格并更新
"""
import requests
import re
from datetime import datetime

ETF_LIST = [
    {'code': '159915', 'market': 'sz', 'name': '创业板ETF'},
    {'code': '518880', 'market': 'sh', 'name': '黄金ETF'},
    {'code': '513100', 'market': 'sh', 'name': '纳指ETF'},
    {'code': '511220', 'market': 'sh', 'name': '城投债ETF'},
    {'code': '588000', 'market': 'sh', 'name': '科创50ETF'},
    {'code': '159985', 'market': 'sz', 'name': '豆粕ETF'},
    {'code': '513260', 'market': 'sh', 'name': '恒生科技ETF'},
]

def get_realtime(market, code):
    try:
        url = f"https://qt.gtimg.cn/q={market}{code}"
        response = requests.get(url, timeout=5)
        content = response.text

        # 解析数据
        match = re.search(f'v_{market}{code}="([^"]+)"', content)
        if not match:
            return None

        fields = match.group(1).split('~')

        return {
            'code': code,
            'name': fields[1],
            'current': float(fields[3]) if fields[3] else 0,
            'pre_close': float(fields[4]) if fields[4] else 0,
            'open': float(fields[5]) if fields[5] else 0,
            'volume': int(fields[6]) if fields[6] else 0,
            'high': float(fields[41]) if len(fields) > 41 and fields[41] else 0,
            'low': float(fields[42]) if len(fields) > 42 and fields[42] else 0,
            'change': float(fields[11]) if len(fields) > 11 and fields[11] else 0,
            'time': fields[30] if len(fields) > 30 else '',
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

print(f"{'代码':<10} {'名称':<12} {'当前价':>8} {'昨收':>8} {'涨跌幅':>8} {'时间':<16}")
print('-' * 70)

for etf in ETF_LIST:
    data = get_realtime(etf['market'], etf['code'])
    if data:
        # 计算涨跌幅
        change_pct = ((data['current'] - data['pre_close']) / data['pre_close'] * 100) if data['pre_close'] > 0 else 0
        print(f"{data['code']:<10} {data['name']:<12} {data['current']:>8.4f} {data['pre_close']:>8.4f} {change_pct:>8.2f}% {data['time']}")
