#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：详细对比聚宽算法和小程序算法
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
    print("创业板ETF (159915) 数据分析")
    print("=" * 80)

    print(f"\n数据总点数: {len(data)}")
    print(f"最近5个数据:")
    for i in range(-5, 0):
        print(f"  [{i+len(data)}] {data[i]['date']}: close={data[i]['close']}")

    # 测试1：使用前25个数据（不包括最后一个）
    print("\n" + "=" * 80)
    print("测试1：使用前25个数据（不包括最后一个）")
    print("=" * 80)

    data_slice_1 = data[-26:-1]  # 取最后26个，去掉最后一个
    prices_1 = np.array([d['close'] for d in data_slice_1])

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
    print(f"第一个数据: {prices_1[0]}")
    print(f"最后一个数据: {prices_1[-1]}")
    print(f"斜率: {slope_1:.6f}")
    print(f"R²: {r_squared_1:.6f}")
    print(f"年化收益率: {ann_return_1:.6f}")
    print(f"动量得分: {score_1:.6f}")

    # 测试2：使用最后26个数据中的前25个（包括倒数第二个，不包括最后一个）
    print("\n" + "=" * 80)
    print("测试2：使用最后26个数据中的前25个")
    print("=" * 80)

    data_slice_2 = data[-(25 + 1):]  # 取最后26个
    prices_2 = np.array([d['close'] for d in data_slice_2[:-1]])  # 前25个

    y_2 = np.log(prices_2)
    x_2 = np.arange(len(y_2))
    weights_2 = np.linspace(1, 2, len(y_2))
    slope_2, intercept_2 = np.polyfit(x_2, y_2, 1, w=weights_2)

    ss_res_2 = np.sum(weights_2 * (y_2 - (slope_2 * x_2 + intercept_2)) ** 2)
    ss_tot_2 = np.sum(weights_2 * (y_2 - np.mean(y_2)) ** 2)
    r_squared_2 = 1 - ss_res_2 / ss_tot_2 if ss_tot_2 else 0

    ann_return_2 = math.exp(slope_2 * 250) - 1
    score_2 = ann_return_2 * r_squared_2

    print(f"数据点数: {len(prices_2)}")
    print(f"第一个数据: {prices_2[0]}")
    print(f"最后一个数据: {prices_2[-1]}")
    print(f"斜率: {slope_2:.6f}")
    print(f"R²: {r_squared_2:.6f}")
    print(f"年化收益率: {ann_return_2:.6f}")
    print(f"动量得分: {score_2:.6f}")

    # 测试3：使用最后25个数据（不包括最后一个）
    print("\n" + "=" * 80)
    print("测试3：使用最后25个数据（不包括最后一个）")
    print("=" * 80)

    data_slice_3 = data[-26:-1]  # 取倒数第26到倒数第2个
    prices_3 = np.array([d['close'] for d in data_slice_3])

    y_3 = np.log(prices_3)
    x_3 = np.arange(len(y_3))
    weights_3 = np.linspace(1, 2, len(y_3))
    slope_3, intercept_3 = np.polyfit(x_3, y_3, 1, w=weights_3)

    ss_res_3 = np.sum(weights_3 * (y_3 - (slope_3 * x_3 + intercept_3)) ** 2)
    ss_tot_3 = np.sum(weights_3 * (y_3 - np.mean(y_3)) ** 2)
    r_squared_3 = 1 - ss_res_3 / ss_tot_3 if ss_tot_3 else 0

    ann_return_3 = math.exp(slope_3 * 250) - 1
    score_3 = ann_return_3 * r_squared_3

    print(f"数据点数: {len(prices_3)}")
    print(f"第一个数据: {prices_3[0]} ({data[-26]['date']})")
    print(f"最后一个数据: {prices_3[-1]} ({data[-2]['date']})")
    print(f"斜率: {slope_3:.6f}")
    print(f"R²: {r_squared_3:.6f}")
    print(f"年化收益率: {ann_return_3:.6f}")
    print(f"动量得分: {score_3:.6f}")

    # 对比
    print("\n" + "=" * 80)
    print("对比分析")
    print("=" * 80)

    print(f"\n测试1 vs 测试2:")
    print(f"  Δslope: {abs(slope_1 - slope_2):.10f}")
    print(f"  Δscore: {abs(score_1 - score_2):.10f}")

    print(f"\n测试2 vs 测试3:")
    print(f"  Δslope: {abs(slope_2 - slope_3):.10f}")
    print(f"  Δscore: {abs(score_2 - score_3):.10f}")

    if abs(slope_2 - slope_3) < 1e-10:
        print("\n✅ 测试2和测试3结果一致！")
    else:
        print(f"\n❌ 测试2和测试3结果不一致！")
