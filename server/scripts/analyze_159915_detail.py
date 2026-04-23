#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细分析创业板ETF数据
"""
import numpy as np
import json
import re

# 加载数据
with open('/workspace/projects/server/src/modules/strategy/etf-real-data.config.ts', 'r') as f:
    content = f.read()

# 提取创业板ETF的数据
match = re.search(r"'159915':\s*(\[[\s\S]*?\])\s*,\s*//", content)
if match:
    data_str = match.group(1)
    data = json.loads(data_str)

    print("=" * 80)
    print("创业板ETF (159915) 详细分析")
    print("=" * 80)

    print(f"\n数据总点数: {len(data)}")

    # 打印所有数据
    print(f"\n所有数据:")
    for i, d in enumerate(data):
        print(f"  [{i:2d}] {d['date']}: close={d['close']:.3f}")

    # 按照聚宽代码的逻辑
    lookback_days = 25
    data_slice = data[-(lookback_days + 1):]  # 取最后26个
    prices = np.array([d['close'] for d in data_slice])  # 26个价格

    print(f"\n" + "=" * 80)
    print("用于计算的26个数据（索引0-25）")
    print("=" * 80)

    for i, (d, price) in enumerate(zip(data_slice, prices)):
        print(f"  [{i:2d}] {d['date']}: {price:.3f}")

    current_price = prices[-1]  # 最后一个价格（索引25）
    last_close = data[-2]['close']  # data[-2]是倒数第二个数据（索引28）
    today_pct = (current_price / last_close - 1) * 100

    print(f"\n" + "=" * 80)
    print("涨跌幅计算")
    print("=" * 80)

    print(f"\ndata[-2] 的索引: {len(data) - 2}")
    print(f"data[-2] = {data[-2]}")
    print(f"\ncurrent_price (prices[-1], 即索引25): {current_price:.3f}")
    print(f"last_close (data[-2], 即索引{len(data)-2}): {last_close:.3f}")
    print(f"today_pct: {today_pct:.2f}%")

    print(f"\n聚宽的 today_pct: -0.03%")
    print(f"差异: {abs(today_pct - (-0.03)):.2f}%")

    print(f"\n" + "=" * 80)
    print("问题分析")
    print("=" * 80)

    print(f"\n如果聚宽的 today_pct = -0.03%，那么：")
    inferred_last_close = current_price / (1 - 0.03/100)
    print(f"  聚宽的 last_close 应该是: {inferred_last_close:.3f}")
    print(f"  我的 last_close: {last_close:.3f}")
    print(f"  差异: {abs(inferred_last_close - last_close):.3f}")

    # 检查 data[-1] 的 pre_close
    if 'pre_close' in data[-1]:
        print(f"\ndata[-1] 的 pre_close: {data[-1]['pre_close']}")
    else:
        print(f"\ndata[-1] 没有 pre_close 字段")

    # 检查 data[-2] 的 pre_close
    if 'pre_close' in data[-2]:
        print(f"data[-2] 的 pre_close: {data[-2]['pre_close']}")
    else:
        print(f"data[-2] 没有 pre_close 字段")

    # 计算 data[-1] 的 today_pct（如果存在 pre_close）
    if 'pre_close' in data[-1]:
        real_today_pct = (data[-1]['close'] / data[-1]['pre_close'] - 1) * 100
        print(f"\n使用 data[-1] 的 pre_close 计算的 today_pct: {real_today_pct:.2f}%")

    # 检查数据长度
    print(f"\n" + "=" * 80)
    print("数据长度检查")
    print("=" * 80)

    print(f"\n总数据点数: {len(data)}")
    print(f"需要的数据点数: {lookback_days + 1} = {lookback_days + 1}")
    print(f"是否足够: {'是' if len(data) >= lookback_days + 1 else '否'}")
