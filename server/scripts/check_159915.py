#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查创业板ETF的最新数据
"""
import json

with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取创业板ETF的数据
import re
match = re.search(r"'159915':\s*(\[[\s\S]*?\])\s*,\s*// 处理后的数据", content)

if match:
    data_str = match.group(1)
    data = json.loads(data_str)

    print(f"创业板ETF (159915) 数据概况:")
    print(f"数据点数: {len(data)}")
    print(f"起始日期: {data[0]['date']}")
    print(f"结束日期: {data[-1]['date']}")
    print(f"最新收盘价: {data[-1]['close']}")
    print(f"昨日收盘价: {data[-2]['close']}")
    print(f"涨跌幅: {((data[-1]['close'] - data[-2]['close']) / data[-2]['close'] * 100):.2f}%")
else:
    print("未找到创业板ETF数据")
