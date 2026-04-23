#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据和结果差异
"""
import numpy as np
import math
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
    print("创业板ETF (159915) 数据检查")
    print("=" * 80)

    print(f"\n数据总点数: {len(data)}")
    print(f"最后5个数据:")
    for i in range(-5, 0):
        print(f"  [{i+len(data)}] {data[i]['date']}: close={data[i]['close']}")

    # 按照聚宽代码的逻辑
    lookback_days = 25
    data_slice = data[-(lookback_days + 1):]  # 取最后26个
    prices = np.array([d['close'] for d in data_slice])  # 26个价格

    print(f"\n用于计算的26个数据:")
    for i in range(len(prices)):
        print(f"  [{i}] {prices[i]:.3f}")

    current_price = prices[-1]  # 最后一个价格
    last_close = data[-2]['close']  # data[-2]是倒数第二个数据
    today_pct = (current_price / last_close - 1) * 100

    print(f"\n涨跌幅计算:")
    print(f"  current_price: {current_price:.3f}")
    print(f"  last_close (data[-2]): {last_close:.3f}")
    print(f"  today_pct: {today_pct:.2f}%")

    print(f"\n聚宽的 today_pct: -0.03%")
    print(f"我的 today_pct: {today_pct:.2f}%")
    print(f"差异: {abs(today_pct - (-0.03)):.2f}%")

    # 动量计算
    y = np.log(prices)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, intercept = np.polyfit(x, y, 1, w=weights)

    ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot else 0

    ann_return = math.exp(slope * 250) - 1
    score = ann_return * r_squared

    print(f"\n动量计算结果:")
    print(f"  斜率: {slope:.6f}")
    print(f"  R²: {r_squared:.6f}")
    print(f"  年化收益率: {ann_return:.6f}")
    print(f"  动量得分: {score:.6f}")

    print(f"\n聚宽的结果:")
    print(f"  得分: 1.0589")
    print(f"  R²: 0.421")

    print(f"\n我的结果:")
    print(f"  得分: {score:.6f}")
    print(f"  R²: {r_squared:.6f}")

    print(f"\n差异:")
    print(f"  Δ得分: {abs(score - 1.0589):.6f}")
    print(f"  ΔR²: {abs(r_squared - 0.421):.6f}")

    # 检查是否需要使用不同的数据
    print(f"\n" + "=" * 80)
    print("检查数据顺序")
    print("=" * 80)

    # 检查数据是否是按时间倒序排列的
    dates = [d['date'] for d in data[-10:]]
    print(f"\n最后10个日期: {dates}")

    # 检查日期是否是递增的
    if len(dates) >= 2:
        if dates[0] < dates[-1]:
            print("数据是按时间正序排列（旧到新）")
        else:
            print("数据是按时间倒序排列（新到旧）")
