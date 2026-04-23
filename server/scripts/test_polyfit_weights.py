#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深入测试 np.polyfit 的权重处理
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

raw_weights = np.linspace(1, 2, n)

print("=" * 80)
print("深入测试 np.polyfit 的权重处理")
print("=" * 80)

# 聚宽方法
slope_jq, intercept_jq = np.polyfit(x, y, 1, w=raw_weights)

# 使用不同权重计算R²
print(f"\n【聚宽方法的R²计算】")
print(f"  斜率: {slope_jq:.6f}")
print(f"  截距: {intercept_jq:.6f}")

# 测试1：使用原始权重计算R²
ss_res1 = np.sum(raw_weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot1 = np.sum(raw_weights * (y - np.mean(y)) ** 2)
r_squared1 = 1 - ss_res1 / ss_tot1 if ss_tot1 else 0

print(f"\n  测试1：使用原始权重计算R²")
print(f"    R² = {r_squared1:.6f}")

# 测试2：使用归一化权重计算R²
norm_weights = raw_weights / np.sum(raw_weights)
ss_res2 = np.sum(norm_weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot2 = np.sum(norm_weights * (y - np.mean(y)) ** 2)
r_squared2 = 1 - ss_res2 / ss_tot2 if ss_tot2 else 0

print(f"  测试2：使用归一化权重计算R²")
print(f"    R² = {r_squared2:.6f}")

# 测试3：使用加权均值计算R²
mean_y_weighted = np.sum(norm_weights * y)
ss_res3 = np.sum(norm_weights * (y - (slope_jq * x + intercept_jq)) ** 2)
ss_tot3 = np.sum(norm_weights * (y - mean_y_weighted) ** 2)
r_squared3 = 1 - ss_res3 / ss_tot3 if ss_tot3 else 0

print(f"  测试3：使用加权均值计算R²")
print(f"    R² = {r_squared3:.6f}")

# 对比聚宽的R²计算
# 我需要看看聚宽的R²是怎么计算的
# 从聚宽代码来看：
# ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
# ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
# r_squared = 1 - ss_res / ss_tot if ss_tot else 0

# 这说明聚宽使用的是原始权重！
# 但是 slope 是使用归一化权重计算的

# 让我验证这个假设
print("\n" + "=" * 80)
print("验证假设：slope使用归一化权重，R²使用原始权重")
print("=" * 80)

# 使用归一化权重计算slope
norm_weights_slope = raw_weights / np.sum(raw_weights)
sumW = np.sum(norm_weights_slope)
sumWX = np.sum(norm_weights_slope * x)
sumWY = np.sum(norm_weights_slope * y)

meanX = sumWX / sumW
meanY = sumWY / sumW

numerator = np.sum(norm_weights_slope * (x - meanX) * (y - meanY))
denominator = np.sum(norm_weights_slope * (x - meanX) ** 2)
slope_hypothesis = numerator / denominator if denominator != 0 else 0
intercept_hypothesis = meanY - slope_hypothesis * meanX

# 使用原始权重计算R²
ss_res_hypo = np.sum(raw_weights * (y - (slope_hypothesis * x + intercept_hypothesis)) ** 2)
ss_tot_hypo = np.sum(raw_weights * (y - np.mean(y)) ** 2)
r_squared_hypo = 1 - ss_res_hypo / ss_tot_hypo if ss_tot_hypo else 0

print(f"\n假设方法：")
print(f"  斜率: {slope_hypothesis:.6f}")
print(f"  截距: {intercept_hypothesis:.6f}")
print(f"  R²: {r_squared_hypo:.6f}")

print(f"\n与聚宽方法对比：")
print(f"  Δslope: {abs(slope_jq - slope_hypothesis):.10f}")
print(f"  Δintercept: {abs(intercept_jq - intercept_hypothesis):.10f}")
print(f"  ΔR²: {abs(r_squared1 - r_squared_hypo):.10f}")

if abs(slope_jq - slope_hypothesis) < 1e-10 and abs(r_squared1 - r_squared_hypo) < 1e-10:
    print("\n✅ 假设成立！slope使用归一化权重，R²使用原始权重！")
else:
    print(f"\n❌ 假设不成立！")
