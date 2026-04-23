#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比聚宽算法和小程序算法
"""
import numpy as np
import math
from typing import List, Tuple

# 模拟数据（创业板ETF最近25天）
# 真实数据从配置文件中读取
prices = [
    3.225, 3.201, 3.296, 3.335, 3.308, 3.3, 3.349, 3.273, 3.338, 3.303,
    3.341, 3.228, 3.237, 3.307, 3.263, 3.293, 3.264, 3.182, 3.141, 3.151,
    3.345, 3.32, 3.437, 3.468, 3.55, 3.511, 3.624, 3.669
]

# 截取最后25个数据
prices_25 = prices[-25:]

print("=" * 80)
print("算法对比分析")
print("=" * 80)

# ==================== 聚宽算法 ====================
print("\n【聚宽算法】")

# 数据准备
y_joinquant = np.log(prices_25)
x_joinquant = np.arange(len(y_joinquant))
weights_joinquant = np.linspace(1, 2, len(y_joinquant))

# 计算回归参数
slope_joinquant, intercept_joinquant = np.polyfit(x_joinquant, y_joinquant, 1, w=weights_joinquant)

# 计算 R²
ss_res = np.sum(weights_joinquant * (y_joinquant - (slope_joinquant * x_joinquant + intercept_joinquant)) ** 2)
ss_tot = np.sum(weights_joinquant * (y_joinquant - np.mean(y_joinquant)) ** 2)
r_squared_joinquant = 1 - ss_res / ss_tot if ss_tot else 0

# 计算得分
ann_return_joinquant = math.exp(slope_joinquant * 250) - 1
score_joinquant = ann_return_joinquant * r_squared_joinquant

print(f"数据点数: {len(prices_25)}")
print(f"斜率: {slope_joinquant:.6f}")
print(f"截距: {intercept_joinquant:.6f}")
print(f"R²: {r_squared_joinquant:.6f}")
print(f"年化收益率: {ann_return_joinquant:.6f}")
print(f"动量得分: {score_joinquant:.6f}")

# ==================== 小程序算法 ====================
print("\n【小程序算法】")

# 数据准备
y_nestjs = [math.log(p) for p in prices_25]
x_nestjs = list(range(len(y_nestjs)))
weights_nestjs = [1 + (i / (len(y_nestjs) - 1)) for i in range(len(y_nestjs))]

# 计算加权和
sumW = sum(weights_nestjs)
sumWX = sum(w * x_nestjs[i] for i, w in enumerate(weights_nestjs))
sumWY = sum(w * y_nestjs[i] for i, w in enumerate(weights_nestjs))

# 计算加权均值
meanX = sumWX / sumW
meanY = sumWY / sumW

# 计算斜率
numerator = 0
denominator = 0
for i in range(len(y_nestjs)):
    w = weights_nestjs[i]
    dx = x_nestjs[i] - meanX
    dy = y_nestjs[i] - meanY
    numerator += w * dx * dy
    denominator += w * dx * dx

slope_nestjs = numerator / denominator if denominator != 0 else 0

# 计算截距
intercept_nestjs = meanY - slope_nestjs * meanX

# 计算 R²
ss_res_nestjs = 0
ss_tot_nestjs = 0
for i in range(len(y_nestjs)):
    w = weights_nestjs[i]
    yPred = slope_nestjs * x_nestjs[i] + intercept_nestjs
    ss_res_nestjs += w * (y_nestjs[i] - yPred) ** 2
    ss_tot_nestjs += w * (y_nestjs[i] - meanY) ** 2

r_squared_nestjs = 1 - ss_res_nestjs / ss_tot_nestjs if ss_tot_nestjs != 0 else 0

# 计算得分
ann_return_nestjs = math.exp(slope_nestjs * 250) - 1
score_nestjs = ann_return_nestjs * r_squared_nestjs

print(f"数据点数: {len(prices_25)}")
print(f"斜率: {slope_nestjs:.6f}")
print(f"截距: {intercept_nestjs:.6f}")
print(f"R²: {r_squared_nestjs:.6f}")
print(f"年化收益率: {ann_return_nestjs:.6f}")
print(f"动量得分: {score_nestjs:.6f}")

# ==================== 对比 ====================
print("\n" + "=" * 80)
print("算法对比结果")
print("=" * 80)

print(f"\n斜率差异: {abs(slope_joinquant - slope_nestjs):.10f}")
print(f"截距差异: {abs(intercept_joinquant - intercept_nestjs):.10f}")
print(f"R²差异: {abs(r_squared_joinquant - r_squared_nestjs):.10f}")
print(f"得分差异: {abs(score_joinquant - score_nestjs):.10f}")

if abs(slope_joinquant - slope_nestjs) < 1e-10:
    print("\n✅ 斜率计算完全一致！")
else:
    print(f"\n❌ 斜率计算有差异！")

if abs(r_squared_joinquant - r_squared_nestjs) < 1e-10:
    print("✅ R²计算完全一致！")
else:
    print(f"❌ R²计算有差异！")

if abs(score_joinquant - score_nestjs) < 1e-10:
    print("✅ 得分计算完全一致！")
else:
    print(f"❌ 得分计算有差异！")
