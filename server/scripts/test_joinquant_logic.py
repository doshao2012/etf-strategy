#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用配置文件中的数据重新测试聚宽算法
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
    print("创业板ETF (159915) - 使用配置文件数据")
    print("=" * 80)

    print(f"\n数据总点数: {len(all_prices)}")
    print(f"所有价格: {all_prices}")

    # 测试1：使用最后25个数据
    print("\n" + "=" * 80)
    print("测试1：使用最后25个数据（直接截取）")
    print("=" * 80)

    prices_1 = np.array(all_prices[-25:])

    y_1 = np.log(prices_1)
    x_1 = np.arange(len(y_1))
    weights_1 = np.linspace(1, 2, len(y_1))
    slope_1, intercept_1 = np.polyfit(x_1, y_1, 1, w=weights_1)

    ss_res_1 = np.sum(weights_1 * (y_1 - (slope_1 * x_1 + intercept_1)) ** 2)
    ss_tot_1 = np.sum(weights_1 * (y_1 - np.mean(y_1)) ** 2)
    r_squared_1 = 1 - ss_res_1 / ss_tot_1 if ss_tot_1 else 0

    ann_return_1 = math.exp(slope_1 * 250) - 1
    score_1 = ann_return_1 * r_squared_1

    print(f"数据点数: {len(prices_1)}")
    print(f"价格序列: {prices_1}")
    print(f"斜率: {slope_1:.6f}")
    print(f"R²: {r_squared_1:.6f}")
    print(f"年化收益率: {ann_return_1:.6f}")
    print(f"动量得分: {score_1:.6f}")

    # 测试2：使用最后26个数据中的前25个（按照聚宽代码的逻辑）
    print("\n" + "=" * 80)
    print("测试2：使用最后26个数据中的前25个（聚宽代码逻辑）")
    print("=" * 80)

    lookback_days = 25
    prices_2 = np.array(all_prices[-(lookback_days + 1):])  # 取最后26个
    prices_for_calc = prices_2[:-1]  # 前25个用于计算

    y_2 = np.log(prices_for_calc)
    x_2 = np.arange(len(y_2))
    weights_2 = np.linspace(1, 2, len(y_2))
    slope_2, intercept_2 = np.polyfit(x_2, y_2, 1, w=weights_2)

    ss_res_2 = np.sum(weights_2 * (y_2 - (slope_2 * x_2 + intercept_2)) ** 2)
    ss_tot_2 = np.sum(weights_2 * (y_2 - np.mean(y_2)) ** 2)
    r_squared_2 = 1 - ss_res_2 / ss_tot_2 if ss_tot_2 else 0

    ann_return_2 = math.exp(slope_2 * 250) - 1
    score_2 = ann_return_2 * r_squared_2

    print(f"数据点数: {len(prices_for_calc)}")
    print(f"价格序列: {prices_for_calc}")
    print(f"当前价格（最后一个）: {prices_2[-1]}")
    print(f"斜率: {slope_2:.6f}")
    print(f"R²: {r_squared_2:.6f}")
    print(f"年化收益率: {ann_return_2:.6f}")
    print(f"动量得分: {score_2:.6f}")

    # 对比
    print("\n" + "=" * 80)
    print("对比分析")
    print("=" * 80)

    print(f"\n测试1 vs 测试2:")
    print(f"  价格序列是否相同: {np.array_equal(prices_1, prices_for_calc)}")
    print(f"  Δslope: {abs(slope_1 - slope_2):.10f}")
    print(f"  Δscore: {abs(score_1 - score_2):.10f}")

    if np.array_equal(prices_1, prices_for_calc):
        print("\n✅ 两个测试使用的价格序列完全一致！")
        print(f"   结果：动量得分 = {score_1:.6f}")
    else:
        print(f"\n❌ 两个测试使用的价格序列不一致！")
        print(f"   差异：{abs(score_1 - score_2):.6f}")
