#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打印创业板ETF 159915 的完整历史数据
"""
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

    print("=" * 100)
    print("创业板ETF (159915) 历史数据")
    print("=" * 100)

    print(f"\n数据总点数: {len(data)}")

    print(f"\n{'索引':>6} | {'日期':<12} | {'开盘价':>8} | {'最高价':>8} | {'最低价':>8} | {'收盘价':>8} | {'成交量':>12}")
    print("-" * 100)

    for i, d in enumerate(data):
        print(f"{i:6d} | {d['date']:<12} | {d['open']:>8.3f} | {d['high']:>8.3f} | {d['low']:>8.3f} | {d['close']:>8.3f} | {d['volume']:>12.0f}")

    print("\n" + "=" * 100)
    print("最后10个数据（用于动量计算）")
    print("=" * 100)

    print(f"\n{'索引':>6} | {'日期':<12} | {'收盘价':>8} | {'涨跌幅计算'}")
    print("-" * 70)

    for i in range(-10, 0):
        idx = len(data) + i
        if i > -10:
            prev_close = data[idx - 1]['close'] if idx > 0 else data[idx]['close']
            change_pct = (data[idx]['close'] / prev_close - 1) * 100
            print(f"{idx:6d} | {data[idx]['date']:<12} | {data[idx]['close']:>8.3f} | {change_pct:>10.2f}%")
        else:
            print(f"{idx:6d} | {data[idx]['date']:<12} | {data[idx]['close']:>8.3f}")

    print("\n" + "=" * 100)
    print("聚宽代码需要的数据（最后26个）")
    print("=" * 100)

    lookback_days = 25
    prices = [d['close'] for d in data[-(lookback_days + 1):]]

    print(f"\n用于动量计算的26个收盘价:")
    for i, price in enumerate(prices):
        print(f"  [{i:2d}] {price:.3f}")

    print(f"\n\n聚宽计算时使用的参数:")
    print(f"  数据点数: {len(prices)}")
    print(f"  第一个价格: {prices[0]:.3f}")
    print(f"  最后一个价格: {prices[-1]:.3f}")
    print(f"  当前价格（显示用）: {prices[-1]:.3f}")

    # 检查 last_close
    last_close = data[-2]['close']
    today_pct = (prices[-1] / last_close - 1) * 100

    print(f"\n涨跌幅计算:")
    print(f"  data[-2]['close']: {last_close:.3f}")
    print(f"  prices[-1]: {prices[-1]:.3f}")
    print(f"  today_pct: {today_pct:.2f}%")

    print(f"\n聚宽显示的今日涨跌: -0.03%")
    print(f"差异: {abs(today_pct - (-0.03)):.2f}%")

else:
    print("未找到创业板ETF数据")
