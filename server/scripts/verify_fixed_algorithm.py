#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证修复后的算法
"""
import numpy as np
import math

# 模拟数据
prices = np.array([3.225, 3.201, 3.296, 3.335, 3.308, 3.3, 3.349, 3.273, 3.338, 3.303,
                   3.341, 3.228, 3.237, 3.307, 3.263, 3.293, 3.264, 3.182, 3.141, 3.151,
                   3.345, 3.32, 3.437, 3.468, 3.55, 3.511, 3.624, 3.669])

prices = prices[-25:]
y = np.log(prices)
x = np.arange(len(y))
n = len(y)

print("=" * 80)
print("验证修复后的算法")
print("=" * 80)

# 聚宽方法（np.polyfit）
raw_weights = np.linspace(1, 2, n)
slope_jq, intercept_jq = np.polyfit(x, y, 1, w=raw_weights)

# 计算R²
ss_res = np.sum(raw_weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot = np.sum(raw_weights * (y - np.mean(y)) ** 2)
r_squared_jq = 1 - ss_res / ss_tot if ss_tot else 0

# 计算得分
ann_return_jq = math.exp(slope_jq * 250) - 1
score_jq = ann_return_jq * r_squared_jq

print(f"\n【聚宽方法（np.polyfit）】")
print(f"  斜率: {slope_jq:.6f}")
print(f"  截距: {intercept_jq:.6f}")
print(f"  R²: {r_squared_jq:.6f}")
print(f"  年化收益率: {ann_return_jq:.6f}")
print(f"  动量得分: {score_jq:.6f}")

# 修复后的方法（带权重归一化）
raw_weights_nestjs = np.linspace(1, 2, n)
sum_raw_weights = np.sum(raw_weights_nestjs)
weights_nestjs = raw_weights_nestjs / sum_raw_weights

sumW = np.sum(weights_nestjs)
sumWX = np.sum(weights_nestjs * x)
sumWY = np.sum(weights_nestjs * y)

meanX = sumWX / sumW
meanY = sumWY / sumW

numerator = np.sum(weights_nestjs * (x - meanX) * (y - meanY))
denominator = np.sum(weights_nestjs * (x - meanX) ** 2)
slope_nestjs = numerator / denominator if denominator != 0 else 0
intercept_nestjs = meanY - slope_nestjs * meanX

# 计算R²
ss_res_nestjs = 0
ss_tot_nestjs = 0
for i in range(len(y)):
    w = weights_nestjs[i]
    yPred = slope_nestjs * x[i] + intercept_nestjs
    ss_res_nestjs += w * (y[i] - yPred) ** 2
    ss_tot_nestjs += w * (y[i] - meanY) ** 2

r_squared_nestjs = 1 - ss_res_nestjs / ss_tot_nestjs if ss_tot_nestjs != 0 else 0

# 计算得分
ann_return_nestjs = math.exp(slope_nestjs * 250) - 1
score_nestjs = ann_return_nestjs * r_squared_nestjs

print(f"\n【修复后的小程序方法（带权重归一化）】")
print(f"  斜率: {slope_nestjs:.6f}")
print(f"  截距: {intercept_nestjs:.6f}")
print(f"  R²: {r_squared_nestjs:.6f}")
print(f"  年化收益率: {ann_return_nestjs:.6f}")
print(f"  动量得分: {score_nestjs:.6f}")

# 对比
print("\n" + "=" * 80)
print("对比结果")
print("=" * 80)

print(f"\n斜率差异: {abs(slope_jq - slope_nestjs):.15f}")
print(f"截距差异: {abs(intercept_jq - intercept_nestjs):.15f}")
print(f"R²差异: {abs(r_squared_jq - r_squared_nestjs):.15f}")
print(f"得分差异: {abs(score_jq - score_nestjs):.15f}")

if abs(slope_jq - slope_nestjs) < 1e-10:
    print("\n✅ 斜率计算完全一致！")
else:
    print(f"\n❌ 斜率计算有差异！")

if abs(r_squared_jq - r_squared_nestjs) < 1e-10:
    print("✅ R²计算完全一致！")
else:
    print(f"❌ R²计算有差异！")

if abs(score_jq - score_nestjs) < 1e-10:
    print("✅ 得分计算完全一致！")
else:
    print(f"❌ 得分计算有差异！")
