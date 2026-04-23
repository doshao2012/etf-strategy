#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
找到问题的根源
"""
import numpy as np
import math

# 模拟数据（创业板ETF最近28天）
# 真实数据
prices_raw = [
    3.225, 3.201, 3.296, 3.335, 3.308, 3.3, 3.349, 3.273, 3.338, 3.303,
    3.341, 3.228, 3.237, 3.307, 3.263, 3.293, 3.264, 3.182, 3.141, 3.151,
    3.345, 3.32, 3.437, 3.468, 3.55, 3.511, 3.624, 3.669
]

# 截取最后25个数据
prices_25 = prices_raw[-25:]

print("=" * 80)
print("问题排查：np.polyfit 的使用方式")
print("=" * 80)

# ==================== 测试1：直接对原始价格做回归（错误的方式） ====================
print("\n【测试1】对原始价格做回归（错误的方式）")

x1 = np.arange(len(prices_25))
y1 = prices_25
weights1 = np.linspace(1, 2, len(prices_25))

slope1, intercept1 = np.polyfit(x1, y1, 1, w=weights1)
print(f"斜率: {slope1:.6f}")
print(f"截距: {intercept1:.6f}")

# ==================== 测试2：对log价格做回归（正确的方式） ====================
print("\n【测试2】对log价格做回归（正确的方式）")

x2 = np.arange(len(prices_25))
y2 = np.log(prices_25)
weights2 = np.linspace(1, 2, len(prices_25))

slope2, intercept2 = np.polyfit(x2, y2, 1, w=weights2)
print(f"斜率: {slope2:.6f}")
print(f"截距: {intercept2:.6f}")

# 计算R²
ss_res2 = np.sum(weights2 * (y2 - (slope2 * x2 + intercept2)) ** 2)
ss_tot2 = np.sum(weights2 * (y2 - np.mean(y2)) ** 2)
r_squared2 = 1 - ss_res2 / ss_tot2 if ss_tot2 else 0

# 计算得分
ann_return2 = math.exp(slope2 * 250) - 1
score2 = ann_return2 * r_squared2

print(f"R²: {r_squared2:.6f}")
print(f"年化收益率: {ann_return2:.6f}")
print(f"动量得分: {score2:.6f}")

# ==================== 测试3：手动实现加权最小二乘 ====================
print("\n【测试3】手动实现加权最小二乘（验证公式）")

y3 = np.log(prices_25)
x3 = np.arange(len(y3))
weights3 = np.linspace(1, 2, len(y3))

sumW = np.sum(weights3)
sumWX = np.sum(weights3 * x3)
sumWY = np.sum(weights3 * y3)

meanX = sumWX / sumW
meanY = sumWY / sumW

numerator = np.sum(weights3 * (x3 - meanX) * (y3 - meanY))
denominator = np.sum(weights3 * (x3 - meanX) ** 2)
slope3 = numerator / denominator if denominator != 0 else 0
intercept3 = meanY - slope3 * meanX

print(f"斜率: {slope3:.6f}")
print(f"截距: {intercept3:.6f}")

# 计算R²
ss_res3 = 0
ss_tot3 = 0
for i in range(len(y3)):
    w = weights3[i]
    yPred = slope3 * x3[i] + intercept3
    ss_res3 += w * (y3[i] - yPred) ** 2
    ss_tot3 += w * (y3[i] - meanY) ** 2

r_squared3 = 1 - ss_res3 / ss_tot3 if ss_tot3 != 0 else 0

# 计算得分
ann_return3 = math.exp(slope3 * 250) - 1
score3 = ann_return3 * r_squared3

print(f"R²: {r_squared3:.6f}")
print(f"年化收益率: {ann_return3:.6f}")
print(f"动量得分: {score3:.6f}")

# ==================== 对比 ====================
print("\n" + "=" * 80)
print("对比结果")
print("=" * 80)

print(f"\n测试2（np.polyfit）vs 测试3（手动）:")
print(f"  斜率差异: {abs(slope2 - slope3):.10f}")
print(f"  截距差异: {abs(intercept2 - intercept3):.10f}")
print(f"  R²差异: {abs(r_squared2 - r_squared3):.10f}")
print(f"  得分差异: {abs(score2 - score3):.10f}")

if abs(slope2 - slope3) < 1e-10:
    print("\n✅ np.polyfit 和手动计算完全一致！")
else:
    print(f"\n❌ np.polyfit 和手动计算有差异！")
    print(f"   这说明 np.polyfit 可能不是标准的加权最小二乘法！")

# ==================== 检查小程序代码 ====================
print("\n\n" + "=" * 80)
print("小程序后端代码问题分析")
print("=" * 80)

print("\n从之前的对比来看：")
print(f"  聚宽结果: slope=0.004299, score=0.659086")
print(f"  手动结果: slope=0.003556, score=0.503158")
print(f"  差异: Δslope=0.000743, Δscore=0.155928")

print("\n问题可能在于：")
print("  1. np.polyfit 的权重参数可能不是标准的加权最小二乘法")
print("  2. 聚宽可能修改了 numpy 的 polyfit 函数")
print("  3. 或者使用了其他回归算法")

print("\n建议解决方案：")
print("  1. 在小程序后端也使用 np.polyfit 的算法（如果可能）")
print("  2. 或者手动实现与 np.polyfit 完全一致的算法")
print("  3. 或者使用第三方的加权回归库")
