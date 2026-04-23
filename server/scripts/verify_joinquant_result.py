#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证聚宽算法结果
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

    # 提取所有收盘价
    all_prices = [d['close'] for d in data]

    print("=" * 80)
    print("验证聚宽算法结果")
    print("=" * 80)

    # 按照用户要求的逻辑：取最后26个数据
    prices_all = np.array(all_prices[-(25 + 1):])  # 取最后26个
    prices = prices_all[:-1]  # 前25个用于动量计算
    current_price = prices_all[-1]  # 第26个数据

    print(f"\n数据点数: {len(prices_all)}")
    print(f"动量计算用数据（前25个）: {prices}")
    print(f"当前价格（第26个）: {current_price}")

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
    print(f"  截距: {intercept:.6f}")
    print(f"  R²: {r_squared:.6f}")
    print(f"  年化收益率: {ann_return:.6f}")
    print(f"  动量得分: {score:.6f}")

    # 对比直接使用最后25个数据
    print("\n" + "=" * 80)
    print("对比：直接使用最后25个数据")
    print("=" * 80)

    prices_direct = np.array(all_prices[-25:])

    y_direct = np.log(prices_direct)
    x_direct = np.arange(len(y_direct))
    weights_direct = np.linspace(1, 2, len(y_direct))
    slope_direct, intercept_direct = np.polyfit(x_direct, y_direct, 1, w=weights_direct)

    ss_res_direct = np.sum(weights_direct * (y_direct - (slope_direct * x_direct + intercept_direct)) ** 2)
    ss_tot_direct = np.sum(weights_direct * (y_direct - np.mean(y_direct)) ** 2)
    r_squared_direct = 1 - ss_res_direct / ss_tot_direct if ss_tot_direct else 0

    ann_return_direct = math.exp(slope_direct * 250) - 1
    score_direct = ann_return_direct * r_squared_direct

    print(f"\n数据点数: {len(prices_direct)}")
    print(f"价格序列: {prices_direct}")
    print(f"\n动量计算结果:")
    print(f"  斜率: {slope_direct:.6f}")
    print(f"  R²: {r_squared_direct:.6f}")
    print(f"  年化收益率: {ann_return_direct:.6f}")
    print(f"  动量得分: {score_direct:.6f}")

    # 对比
    print("\n" + "=" * 80)
    print("对比分析")
    print("=" * 80)

    print(f"\n价格序列是否相同: {np.array_equal(prices, prices_direct)}")
    print(f"Δslope: {abs(slope - slope_direct):.10f}")
    print(f"Δscore: {abs(score - score_direct):.10f}")

    # 打印两个价格序列的差异
    if not np.array_equal(prices, prices_direct):
        print(f"\n价格序列差异:")
        for i in range(len(prices_direct)):
            if i < len(prices):
                if abs(prices[i] - prices_direct[i]) > 1e-10:
                    print(f"  位置 {i}: {prices[i]:.4f} vs {prices_direct[i]:.4f}")
            else:
                print(f"  位置 {i}: N/A vs {prices_direct[i]:.4f}")

    print(f"\n建议:")
    print(f"  如果您希望动量得分与聚宽代码一致，应该使用最后25个数据直接计算")
    print(f"  动量得分: {score_direct:.6f}")
    print(f"  或者使用您要求的逻辑（前25个+第26个），动量得分: {score:.6f}")
