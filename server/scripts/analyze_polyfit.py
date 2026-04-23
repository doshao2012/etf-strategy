#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深入分析 np.polyfit 的算法
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
weights = np.linspace(1, 2, len(y))

print("=" * 80)
print("深入分析 np.polyfit 的加权算法")
print("=" * 80)

# 方法1：使用 np.polyfit
slope1, intercept1 = np.polyfit(x, y, 1, w=weights)
print(f"\n【方法1】np.polyfit:")
print(f"  斜率: {slope1:.10f}")
print(f"  截距: {intercept1:.10f}")

# 方法2：手动实现标准加权最小二乘
sumW = np.sum(weights)
sumWX = np.sum(weights * x)
sumWY = np.sum(weights * y)
meanX = sumWX / sumW
meanY = sumWY / sumW

numerator = np.sum(weights * (x - meanX) * (y - meanY))
denominator = np.sum(weights * (x - meanX) ** 2)
slope2 = numerator / denominator if denominator != 0 else 0
intercept2 = meanY - slope2 * meanX

print(f"\n【方法2】手动实现标准加权最小二乘:")
print(f"  斜率: {slope2:.10f}")
print(f"  截距: {intercept2:.10f}")

# 方法3：使用 sqrt(weights)
weights_sqrt = np.sqrt(weights)

sumW3 = np.sum(weights_sqrt)
sumWX3 = np.sum(weights_sqrt * x)
sumWY3 = np.sum(weights_sqrt * y)
meanX3 = sumWX3 / sumW3
meanY3 = sumWY3 / sumW3

numerator3 = np.sum(weights_sqrt * (x - meanX3) * (y - meanY3))
denominator3 = np.sum(weights_sqrt * (x - meanX3) ** 2)
slope3 = numerator3 / denominator3 if denominator3 != 0 else 0
intercept3 = meanY3 - slope3 * meanX3

print(f"\n【方法3】使用 sqrt(weights):")
print(f"  斜率: {slope3:.10f}")
print(f"  截距: {intercept3:.10f}")

# 方法4：使用范德蒙德矩阵 + 最小二乘
# 构造范德蒙德矩阵
V = np.vstack([x, np.ones(len(x))]).T

# 使用权重矩阵
W = np.diag(weights)
W_sqrt = np.sqrt(W)

# 最小化 (W_sqrt * (V*p - y))^2
# => (V^T * W * V) * p = V^T * W * y
A = V.T @ W @ V
b = V.T @ W @ y
p4 = np.linalg.solve(A, b)
slope4, intercept4 = p4[0], p4[1]

print(f"\n【方法4】使用范德蒙德矩阵 + 最小二乘:")
print(f"  斜率: {slope4:.10f}")
print(f"  截距: {intercept4:.10f}")

# 方法5：使用 scipy (如果可用)
try:
    from scipy import stats
    slope5, intercept5, r_value, p_value, std_err = stats.linregress(x, y)
    print(f"\n【方法5】scipy.stats.linregress (无权重):")
    print(f"  斜率: {slope5:.10f}")
    print(f"  截距: {intercept5:.10f}")
except ImportError:
    print(f"\n【方法5】scipy 不可用")

# 对比
print("\n" + "=" * 80)
print("对比结果")
print("=" * 80)
print(f"\npolyfit vs 方法2: Δslope={abs(slope1 - slope2):.10f}")
print(f"polyfit vs 方法3: Δslope={abs(slope1 - slope3):.10f}")
print(f"polyfit vs 方法4: Δslope={abs(slope1 - slope4):.10f}")

# 找到最接近的方法
differences = [
    ("方法2（标准加权最小二乘）", abs(slope1 - slope2)),
    ("方法3（sqrt权重）", abs(slope1 - slope3)),
    ("方法4（范德蒙德矩阵）", abs(slope1 - slope4)),
]

differences.sort(key=lambda x: x[1])
print(f"\n最接近 polyfit 的方法是: {differences[0][0]}")
print(f"差异: {differences[0][1]:.10f}")

# 检查方法4的细节
print("\n" + "=" * 80)
print("方法4的详细检查")
print("=" * 80)
print(f"\n范德蒙德矩阵 V:\n{V}")
print(f"\n权重矩阵 W (对角):\n{np.diag(weights)[:5]} ...")
print(f"\nV.T @ W @ V:\n{A}")
print(f"\nV.T @ W @ y:\n{b}")
print(f"\n解 p = (V.T @ W @ V)^-1 @ (V.T @ W @ y):\n{p4}")
